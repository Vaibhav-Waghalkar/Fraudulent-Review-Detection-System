"""
Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Review schemas
# ---------------------------------------------------------------------------

class ReviewSubmit(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, example="Great product, highly recommend!")
    user_id: str = Field(..., min_length=1, max_length=64, example="user-abc123")
    rating: int = Field(..., ge=1, le=5, example=5)


class ReviewSubmitResponse(BaseModel):
    id: str
    status: str
    message: str


class BatchDetectItem(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    user_id: str
    rating: int = Field(..., ge=1, le=5)


class BatchDetectResponse(BaseModel):
    id: str
    score: float
    status: str
    explanation: dict[str, Any]
    fallback: bool = False


class ReviewDetail(BaseModel):
    id: str
    text: str
    user_id: str
    rating: int
    score: Optional[float] = None
    status: str
    reasons: list[str] = []
    explanation: Optional[dict] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    fallback: bool = False


class ReviewListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ReviewDetail]


class OverrideRequest(BaseModel):
    moderator_id: str = Field(..., example="mod-001")
    action: str = Field(..., pattern="^(approve|reject)$", example="approve")
    note: Optional[str] = Field(None, max_length=500)


class OverrideResponse(BaseModel):
    review_id: str
    moderator_id: str
    action: str
    note: Optional[str]
    timestamp: datetime


# ---------------------------------------------------------------------------
# Drift schemas
# ---------------------------------------------------------------------------

class DriftStatus(BaseModel):
    checked_at: Optional[datetime]
    p_value: Optional[float]
    alert: bool
    message: str
    recent_events: list[dict]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    mongo_connected: bool
    redis_connected: bool
    version: str = "1.0.0"
