"""
Reviews API router.
"""
import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.db import get_db
from app.schemas import (
    BatchDetectItem,
    BatchDetectResponse,
    OverrideRequest,
    OverrideResponse,
    ReviewDetail,
    ReviewListResponse,
    ReviewSubmit,
    ReviewSubmitResponse,
)
from app.services import inference as inference_svc
from app.services.cache import get_user_velocity, increment_user_velocity
from app.services.rules import score_rules

router = APIRouter(prefix="/api/reviews", tags=["reviews"])
logger = logging.getLogger(__name__)


def _oid_to_str(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


# ---------------------------------------------------------------------------
# POST /api/reviews/submit
# ---------------------------------------------------------------------------
@router.post(
    "/submit",
    response_model=ReviewSubmitResponse,
    summary="Submit a review for fraud analysis",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "id": "664f2e3a1b2c3d4e5f6a7b8c",
                        "status": "pending",
                        "message": "Review queued for scoring.",
                    }
                }
            }
        }
    },
)
async def submit_review(
    payload: ReviewSubmit,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    velocity = increment_user_velocity(payload.user_id)

    doc = {
        "text": payload.text,
        "user_id": payload.user_id,
        "rating": payload.rating,
        "velocity": velocity,
        "status": "pending",
        "score": None,
        "reasons": [],
        "explanation": {},
        "fallback": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }

    result = await db["reviews"].insert_one(doc)
    review_id = str(result.inserted_id)

    # Enqueue Celery scoring task
    from app.workers.tasks import score_review
    score_review.delay(review_id)

    return ReviewSubmitResponse(
        id=review_id,
        status="pending",
        message="Review queued for scoring.",
    )


# ---------------------------------------------------------------------------
# POST /api/reviews/detect/batch
# ---------------------------------------------------------------------------
@router.post(
    "/detect/batch",
    response_model=list[BatchDetectResponse],
    summary="Synchronously score a batch of reviews",
)
async def detect_batch(
    items: list[BatchDetectItem] = Body(...),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if not items:
        return []

    velocities = [float(get_user_velocity(item.user_id)) for item in items]
    texts = [item.text for item in items]

    # Optimized batch inference
    nlp_results = inference_svc.infer_batch(texts, velocities)

    now = datetime.now(timezone.utc)
    docs = []
    metadata = []

    for item, velocity, (nlp_score, fallback) in zip(items, velocities, nlp_results):
        rule_score, triggered_rules = score_rules(item.text, item.rating, int(velocity))
        vel_norm = min(velocity / 10.0, 1.0)
        final_score = float(min(
            settings.nlp_weight * nlp_score + settings.velocity_weight * vel_norm,
            1.0,
        ))
        has_lang_bias = any(r.get("rule") == "low_confidence_language" for r in triggered_rules)
        if has_lang_bias:
            status = "needs_review"
        else:
            status = "quarantined" if final_score > settings.quarantine_threshold else "reviewed"

        doc = {
            "text": item.text,
            "user_id": item.user_id,
            "rating": item.rating,
            "velocity": int(velocity),
            "score": final_score,
            "nlp_score": nlp_score,
            "rule_score": rule_score,
            "status": status,
            "reasons": [r["rule"] for r in triggered_rules],
            "explanation": {"rules": triggered_rules},
            "fallback": fallback,
            "created_at": now,
            "updated_at": now,
        }
        docs.append(doc)
        metadata.append((final_score, status, triggered_rules, fallback))

    res = await db["reviews"].insert_many(docs)

    results = [
        BatchDetectResponse(
            id=str(ins_id),
            score=f_score,
            status=st,
            explanation={"rules": tr_rules},
            fallback=fb,
        )
        for ins_id, (f_score, st, tr_rules, fb) in zip(res.inserted_ids, metadata)
    ]
    return results


# ---------------------------------------------------------------------------
# GET /api/reviews/{id}
# ---------------------------------------------------------------------------
@router.get(
    "/{review_id}",
    response_model=ReviewDetail,
    summary="Get a review by ID",
)
async def get_review(
    review_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    try:
        oid = ObjectId(review_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID format.")

    doc = await db["reviews"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Review not found.")

    return ReviewDetail(
        id=str(doc["_id"]),
        text=doc["text"],
        user_id=doc["user_id"],
        rating=doc["rating"],
        score=doc.get("score"),
        status=doc.get("status", "pending"),
        reasons=doc.get("reasons", []),
        explanation=doc.get("explanation"),
        created_at=doc["created_at"],
        updated_at=doc.get("updated_at"),
        fallback=doc.get("fallback", False),
    )


# ---------------------------------------------------------------------------
# GET /api/reviews
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=ReviewListResponse,
    summary="List reviews with filtering and pagination",
)
async def list_reviews(
    score_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    score_max: Optional[float] = Query(None, ge=0.0, le=1.0),
    user_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    query: dict = {}
    if score_min is not None or score_max is not None:
        query["score"] = {}
        if score_min is not None:
            query["score"]["$gte"] = score_min
        if score_max is not None:
            query["score"]["$lte"] = score_max
    if user_id:
        query["user_id"] = user_id
    if status:
        query["status"] = status

    total = await db["reviews"].count_documents(query)
    skip = (page - 1) * page_size

    cursor = db["reviews"].find(query).sort("created_at", -1).skip(skip).limit(page_size)
    docs = await cursor.to_list(length=page_size)

    items = [
        ReviewDetail(
            id=str(d["_id"]),
            text=d["text"],
            user_id=d["user_id"],
            rating=d["rating"],
            score=d.get("score"),
            status=d.get("status", "pending"),
            reasons=d.get("reasons", []),
            explanation=d.get("explanation"),
            created_at=d["created_at"],
            updated_at=d.get("updated_at"),
            fallback=d.get("fallback", False),
        )
        for d in docs
    ]

    return ReviewListResponse(total=total, page=page, page_size=page_size, items=items)


# ---------------------------------------------------------------------------
# GET /api/reviews/{id}/explain
# ---------------------------------------------------------------------------
@router.get(
    "/{review_id}/explain",
    summary="Get LIME explanation for a review (on demand)",
)
async def explain_review(
    review_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    try:
        oid = ObjectId(review_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID format.")

    doc = await db["reviews"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Review not found.")

    from app.services.explain import explain_review as _explain
    result = _explain(
        text=doc["text"],
        velocity=float(doc.get("velocity", 0)),
    )
    return {"review_id": review_id, "lime_explanation": result}


# ---------------------------------------------------------------------------
# POST /api/reviews/{id}/override
# ---------------------------------------------------------------------------
@router.post(
    "/{review_id}/override",
    response_model=OverrideResponse,
    summary="Moderator override for a review (stored in audit log)",
)
async def override_review(
    review_id: str,
    payload: OverrideRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    try:
        oid = ObjectId(review_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid review ID format.")

    doc = await db["reviews"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Review not found.")

    now = datetime.now(timezone.utc)
    new_status = "approved" if payload.action == "approve" else "rejected"

    await db["reviews"].update_one(
        {"_id": oid},
        {"$set": {"status": new_status, "updated_at": now}},
    )

    audit_entry = {
        "review_id": review_id,
        "moderator_id": payload.moderator_id,
        "action": payload.action,
        "previous_status": doc.get("status"),
        "new_status": new_status,
        "note": payload.note,
        "timestamp": now,
    }
    await db["audit_log"].insert_one(audit_entry)

    return OverrideResponse(
        review_id=review_id,
        moderator_id=payload.moderator_id,
        action=payload.action,
        note=payload.note,
        timestamp=now,
    )


# ---------------------------------------------------------------------------
# GET /api/reviews/export/labels (Moderator overrides CSV)
# ---------------------------------------------------------------------------
@router.get(
    "/export/labels",
    summary="Export moderator overrides as CSV labels dataset for retraining",
)
async def export_labels(db: AsyncIOMotorDatabase = Depends(get_db)):
    import csv
    import io
    from fastapi.responses import Response

    cursor = db["audit_log"].find().sort("timestamp", -1)
    audit_docs = await cursor.to_list(length=5000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["review_id", "moderator_id", "action", "previous_status", "new_status", "note", "timestamp"])

    for a in audit_docs:
        writer.writerow([
            str(a.get("review_id", "")),
            str(a.get("moderator_id", "")),
            str(a.get("action", "")),
            str(a.get("previous_status", "")),
            str(a.get("new_status", "")),
            str(a.get("note", "")),
            a.get("timestamp").isoformat() if hasattr(a.get("timestamp"), "isoformat") else str(a.get("timestamp", "")),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=moderator_labels.csv"},
    )


# ---------------------------------------------------------------------------
# GET /api/reviews/audit/logs (Global audit log list)
# ---------------------------------------------------------------------------
@router.get(
    "/audit/logs",
    summary="Get recent moderator audit actions",
)
async def get_audit_logs(
    limit: int = 100,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cursor = db["audit_log"].find().sort("timestamp", -1).limit(min(limit, 200))
    docs = await cursor.to_list(length=limit)
    for d in docs:
        d["id"] = str(d.pop("_id"))
        if hasattr(d.get("timestamp"), "isoformat"):
            d["timestamp"] = d["timestamp"].isoformat()
    return docs


# ---------------------------------------------------------------------------
# POST /api/reviews/webhook (HMAC-verified)
# ---------------------------------------------------------------------------
@router.post(
    "/webhook",
    summary="Webhook endpoint for review submission with HMAC signature check",
)
async def webhook_submit(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    body = await request.body()

    # Verify HMAC
    if not x_signature:
        raise HTTPException(status_code=401, detail="Missing X-Signature header.")

    expected = hmac.new(
        settings.webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(f"sha256={expected}", x_signature):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature.")

    import json
    try:
        data = json.loads(body)
        payload = ReviewSubmit(**data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    velocity = increment_user_velocity(payload.user_id)
    doc = {
        "text": payload.text,
        "user_id": payload.user_id,
        "rating": payload.rating,
        "velocity": velocity,
        "status": "pending",
        "score": None,
        "reasons": [],
        "explanation": {},
        "fallback": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
        "source": "webhook",
    }
    result = await db["reviews"].insert_one(doc)
    review_id = str(result.inserted_id)

    from app.workers.tasks import score_review
    score_review.delay(review_id)

    return {"id": review_id, "status": "pending", "message": "Webhook review queued."}
