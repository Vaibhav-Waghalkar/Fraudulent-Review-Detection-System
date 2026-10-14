"""
Drift and health API routers.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.schemas import DriftStatus, HealthResponse
from app.services import inference as inference_svc
from app.services.cache import ping as redis_ping

router = APIRouter(tags=["system"])
logger = logging.getLogger(__name__)


@router.get("/api/drift/status", response_model=DriftStatus, summary="Current drift detection status")
async def drift_status(db: AsyncIOMotorDatabase = Depends(get_db)):
    drift_events = db["drift_events"]

    # Get latest event
    latest = await drift_events.find_one(
        {}, sort=[("checked_at", -1)]
    )

    # Get recent events (last 24)
    cursor = drift_events.find({}).sort("checked_at", -1).limit(24)
    recent = await cursor.to_list(length=24)
    for r in recent:
        r.pop("_id", None)
        if isinstance(r.get("checked_at"), datetime):
            r["checked_at"] = r["checked_at"].isoformat()

    if not latest:
        return DriftStatus(
            checked_at=None,
            p_value=None,
            alert=False,
            message="No drift checks have run yet. Start the Celery beat scheduler.",
            recent_events=[],
        )

    p = latest.get("p_value")
    alert = latest.get("alert", False)
    message = (
        f"Drift detected (p={p:.4f} < 0.05). Check model performance."
        if alert
        else f"No drift detected (p={p:.4f} >= 0.05)."
    ) if p is not None else latest.get("error", "Unknown")

    checked_at = latest.get("checked_at")
    if isinstance(checked_at, str):
        checked_at = datetime.fromisoformat(checked_at)

    return DriftStatus(
        checked_at=checked_at,
        p_value=p,
        alert=alert,
        message=message,
        recent_events=recent,
    )


@router.get("/health", response_model=HealthResponse, summary="Service health check")
async def health_check(db: AsyncIOMotorDatabase = Depends(get_db)):
    # MongoDB check
    mongo_ok = False
    try:
        await db.command("ping")
        mongo_ok = True
    except Exception:
        pass

    # Redis check
    redis_ok = redis_ping()

    return HealthResponse(
        status="ok" if (mongo_ok and redis_ok) else "degraded",
        model_loaded=inference_svc.is_model_loaded(),
        mongo_connected=mongo_ok,
        redis_connected=redis_ok,
    )
