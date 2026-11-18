from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class IntentStatus(StrEnum):
    CLEAR = "CLEAR"
    AMBIGUOUS = "AMBIGUOUS"


# Structured output contract for the LLM
class LLMQueryClassification(BaseModel):
    status: IntentStatus = Field(
        description="CLEAR if the query is specific and measurable. "
        "AMBIGUOUS if subjective or unclear."
    )
    sql_query: str | None = Field(
        None,
        description="DuckDB SQL for CLEAR prompts. Use only SELECT statements.",
    )
    reasoning: str | None = Field(
        None, description="Why the prompt is ambiguous, when applicable."
    )
    clarification_options: list[str] | None = Field(
        None, description="3 specific alternative questions the user could ask."
    )


# API request model
class QueryRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1000)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"prompt": "Which product category earned the most revenue?"}
            ]
        }
    }


# API response model
class QueryResponse(BaseModel):
    status: IntentStatus
    sql_query: str | None = None
    data: list[dict[str, Any]] | None = None
    reasoning: str | None = None
    clarification_options: list[str] | None = None
    attempts_used: int | None = None
    execution_time_ms: float | None = None
    tokens_used: int | None = None
    error: str | None = None
    final_error: str | None = None


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
