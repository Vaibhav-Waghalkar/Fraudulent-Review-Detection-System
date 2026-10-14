"""
Application configuration using pydantic-settings.
All values can be overridden via environment variables.
"""
import os
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017/?replicaSet=rs0",
        env="MONGODB_URI",
    )
    mongodb_db: str = Field(default="reviewguard", env="MONGODB_DB")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # Celery
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1", env="CELERY_BROKER_URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2", env="CELERY_RESULT_BACKEND"
    )

    # Model paths
    model_path: str = Field(
        default="models/fusion_model.onnx", env="MODEL_PATH"
    )
    quantized_model_path: str = Field(
        default="models/fusion_model_quantized.onnx", env="QUANTIZED_MODEL_PATH"
    )
    reference_scores_path: str = Field(
        default="models/reference_scores.npy", env="REFERENCE_SCORES_PATH"
    )
    scaler_path: str = Field(
        default="models/scaler.pkl", env="SCALER_PATH"
    )

    # Scoring weights
    nlp_weight: float = Field(default=0.8, env="NLP_WEIGHT")
    velocity_weight: float = Field(default=0.2, env="VELOCITY_WEIGHT")
    quarantine_threshold: float = Field(default=0.7, env="QUARANTINE_THRESHOLD")

    # Drift
    ks_p_value_threshold: float = Field(default=0.05, env="KS_P_VALUE_THRESHOLD")

    # Webhook
    webhook_secret: str = Field(default="changeme-webhook-secret", env="WEBHOOK_SECRET")

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        env="CORS_ORIGINS",
    )

    # Velocity cache TTL (seconds)
    velocity_ttl: int = Field(default=86400, env="VELOCITY_TTL")  # 1 day

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
