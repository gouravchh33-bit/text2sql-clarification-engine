"""FastAPI application: auth, rate limiting, routing and error mapping."""

import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app import config
from app.database import check_database_health, setup_dummy_data
from app.engine import process_query
from app.schemas import HealthResponse, QueryRequest, QueryResponse

logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("text2sql")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_dummy_data()
    logger.info("Startup complete — demo database ready at %s", config.DB_PATH)
    yield


app = FastAPI(
    title="Text-to-SQL Clarification Engine",
    description="Intent-aware text-to-SQL engine powered by Groq and DuckDB.",
    version=config.APP_VERSION,
    lifespan=lifespan,
)

# --- Lightweight in-memory sliding-window rate limiter -------------------
_window_hits: dict[str, deque] = defaultdict(deque)
_window_lock = Lock()


def _allow_request(client_id: str) -> bool:
    now = time.monotonic()
    with _window_lock:
        hits = _window_hits[client_id]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= config.RATE_LIMIT_PER_MINUTE:
            return False
        hits.append(now)
        return True


def verify_request(request: Request) -> None:
    """Opt-in API key check plus per-client rate limiting."""
    client_id = request.client.host if request.client else "unknown"

    if config.API_KEY:
        supplied = request.headers.get("X-API-Key")
        if supplied != config.API_KEY:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        # Do not log or store the full secret.
        client_id = f"key:{supplied[:8]}"

    if not _allow_request(client_id):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({config.RATE_LIMIT_PER_MINUTE}/minute)",
        )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    if not check_database_health():
        raise HTTPException(status_code=503, detail="Database unavailable")
    return HealthResponse(
        status="ok", database="connected", version=config.APP_VERSION
    )


@app.post(
    "/api/v1/query",
    response_model=QueryResponse,
    dependencies=[Depends(verify_request)],
)
async def handle_query(request: QueryRequest) -> QueryResponse:
    request_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    try:
        # The Groq/Instructor client is synchronous; keep the event loop free.
        return await run_in_threadpool(process_query, request.prompt)
    except Exception:
        logger.exception("Unhandled error processing prompt [request_id=%s]", request_id)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error. Reference: {request_id}",
        ) from None
    finally:
        logger.info(
            "request_id=%s total_latency_ms=%.1f completed",
            request_id,
            (time.perf_counter() - started) * 1000,
        )
