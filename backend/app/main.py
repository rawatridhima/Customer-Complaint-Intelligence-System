import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.database import Base, get_engine
from app.core.exceptions import AppError
from app.core.logging import configure_logging, correlation_id
from app.models import Complaint, Prediction, User  # noqa: F401  (registers tables)

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Customer Complaint Intelligence System",
    version="0.1.0",
    description="Skeleton build. ML and LLM stages are stubbed.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    cid = f"req_{uuid.uuid4().hex[:8]}"
    correlation_id.set(cid)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "correlation_id": correlation_id.get(),
            }
        },
    )


@app.on_event("startup")
def on_startup() -> None:
    """Skeleton uses create_all. Replace with Alembic before week 6."""
    Base.metadata.create_all(bind=get_engine())
    logger.info("schema ready")


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "version": app.version}


app.include_router(api_router)
