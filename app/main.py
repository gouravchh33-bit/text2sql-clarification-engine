from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from app.schemas import QueryRequest, QueryResponse
from app.engine import process_query
from app.database import setup_dummy_data
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Modern FastAPI lifespan manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs exactly once when the server starts
    setup_dummy_data()
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
    try:
        result = process_query(request.prompt)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))