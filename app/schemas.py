from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from enum import Enum

class IntentStatus(str, Enum):
    CLEAR = "CLEAR"
    AMBIGUOUS = "AMBIGUOUS"

# Instructor Model for LLM Output
class LLMQueryClassification(BaseModel):
    status: IntentStatus = Field(description="CLEAR if the query is specific and measurable. AMBIGUOUS if subjective or unclear.")
    sql_query: Optional[str] = Field(None, description="The DuckDB SQL query if status is CLEAR. Must not contain destructive commands.")
    reasoning: Optional[str] = Field(None, description="Explanation of why the query is ambiguous.")
    clarification_options: Optional[List[str]] = Field(None, description="3 alternative specific questions the user could ask.")

# API Request Model (with Swagger UI example)
class QueryRequest(BaseModel):
    prompt: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "prompt": "Which product category is performing the best right now?"
                }
            ]
        }
    }

# API Response Model
class QueryResponse(BaseModel):
    status: IntentStatus
    sql_query: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    reasoning: Optional[str] = None
    clarification_options: Optional[List[str]] = None
    attempts_used: Optional[int] = None
    error: Optional[str] = None
    final_error: Optional[str] = None