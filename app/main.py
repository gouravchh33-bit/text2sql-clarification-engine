import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv

from app.schemas import QueryRequest, QueryResponse
from app.engine import process_query
from app.database import setup_dummy_data

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("text2sql")

# Modern FastAPI lifespan manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs exactly once when the server starts
    setup_dummy_data()
    logger.info("Startup complete — sample database is ready")
    yield
    # Anything after 'yield' would run when the server shuts down (not needed here)

app = FastAPI(
    title="Text-to-SQL Clarification Engine",
    description="Intent-aware text-to-SQL engine powered by Groq and DuckDB.",
    version="1.0.0",
    lifespan=lifespan  # Connect the lifespan manager here
)

@app.post("/api/v1/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    request_id = uuid.uuid4().hex[:12]
    try:
        return process_query(request.prompt)
    except Exception:
        # Full traceback goes to the server log; the client only gets a reference ID.
        logger.exception("Unhandled error processing prompt [request_id=%s]", request_id)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error. Reference: {request_id}",
        ) from None
