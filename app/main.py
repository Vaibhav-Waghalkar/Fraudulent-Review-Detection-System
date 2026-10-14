"""
ReviewGuard - FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.core.config import settings
from app.db import connect_db, close_db
from app.services import inference as inference_svc
from app.services.drift import load_reference_scores
from app.api.reviews import router as reviews_router
from app.api.system import router as system_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting ReviewGuard API...")
    await connect_db()
    inference_svc.load_model()
    load_reference_scores()
    logger.info("Startup complete.")
    yield
    logger.info("Shutting down ReviewGuard API...")
    await close_db()


app = FastAPI(
    title="ReviewGuard",
    description=(
        "Fraud review detection service. "
        "Combines NLP (DistilBERT ONNX) with rule-based heuristics and velocity tracking."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(reviews_router)
app.include_router(system_router)


@app.get("/", tags=["root"])
async def root():
    return {
        "service": "ReviewGuard",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
