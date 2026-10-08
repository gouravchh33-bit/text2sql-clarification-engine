from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.schemas import IntentAnalysis
from app.engine import analyze_user_intent
from app.database import execute_query

app = FastAPI(
    title="Text-to-SQL Clarification Engine",
    description="A FastAPI backend that classifies query intent, resolves ambiguity, and executes SQL queries using DuckDB and Groq.",
    version="1.0.0"
)

# Request schema for receiving JSON body in POST requests
class QueryRequest(BaseModel):
    prompt: str


@app.get("/")
def root():
    """Health check endpoint to verify that the server is up and running."""
    return {
        "status": "online",
        "message": "Text-to-SQL Clarification Engine API is running."
    }


@app.post("/api/v1/query")
def process_query(request: QueryRequest):
    """
    Processes a natural language query:
    1. Sends prompt to LLM (via engine.py) for intent analysis.
    2. If AMBIGUOUS: Returns reasoning and clarification options.
    3. If CLEAR: Executes generated SQL in DuckDB (via database.py) and returns results.
    """
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    # Step 1: Send user prompt to LLM for intent analysis
    try:
        analysis: IntentAnalysis = analyze_user_intent(request.prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Engine Error: {str(e)}")

    # Step 2: Handle Ambiguous Queries
    if analysis.status == "AMBIGUOUS":
        return {
            "status": "AMBIGUOUS",
            "reasoning": analysis.reasoning,
            "clarification_options": analysis.clarification_options
        }

    # Step 3: Execute SQL in DuckDB if query is CLEAR
    try:
        query_results = execute_query(analysis.sql_query)
        return {
            "status": "CLEAR",
            "sql_query": analysis.sql_query,
            "data": query_results
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SQL Execution Error: {str(e)}")