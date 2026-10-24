import os
from openai import OpenAI
import instructor
from app.schemas import QueryResponse, IntentStatus
from app.database import execute_safe_query
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Groq client with Instructor
client = instructor.from_openai(
    OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ.get("GROQ_API_KEY"),
    ),
    mode=instructor.Mode.JSON,
)

# Load the model name, defaulting to qwen if not found in .env
MODEL_NAME = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")

SCHEMA_CONTEXT = """
Table: products
Columns:
- category (VARCHAR) PRIMARY KEY
- total_revenue (DOUBLE)
- quantity_sold (INT)
- unit_price (DOUBLE)
"""

def process_query(prompt: str) -> dict:
    """Processes the user prompt, determines intent, and executes safe SQL."""
    system_prompt = f"""
    You are an intent-aware Text-to-SQL engine.
    Analyze the user prompt based on this schema:
    {SCHEMA_CONTEXT}

    If the prompt is subjective, ambiguous, or lacks enough detail to write an exact SQL query, set status to AMBIGUOUS and provide clarification_options.
    If the prompt is clear, set status to CLEAR and provide the exact DuckDB SQL query.
    """

    try:
        # 1. Call the LLM with structured output via Instructor
        response = client.chat.completions.create(
            model=MODEL_NAME,
            response_model=QueryResponse,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_retries=2
        )

        # 2. If the LLM marks it as ambiguous, return early without touching the database
        if response.status == IntentStatus.AMBIGUOUS:
            return response.model_dump()

        # 3. If CLEAR, execute the query securely against DuckDB
        if response.status == IntentStatus.CLEAR and response.sql_query:
            try:
                data = execute_safe_query(response.sql_query)
                response.data = data
            except Exception as db_err:
                response.error = "Database execution failed."
                response.final_error = str(db_err)

        return response.model_dump()

    except Exception as e:
        # Fallback error handling if the LLM completely fails validation
        return {
            "status": "CLEAR",
            "sql_query": None,
            "data": None,
            "reasoning": None,
            "clarification_options": None,
            "attempts_used": 2,
            "error": "Failed to generate valid SQL after 2 attempts.",
            "final_error": str(e)
        }