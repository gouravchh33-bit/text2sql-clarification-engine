from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class IntentAnalysis(BaseModel):
    status: Literal["CLEAR", "AMBIGUOUS"] = Field(
        description="Whether the query is clear enough to run SQL or ambiguous."
    )
    sql_query: Optional[str] = Field(
        default=None,
        description="The generated SQL query if status is CLEAR."
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Explanation of why the prompt is vague if status is AMBIGUOUS."
    )
    clarification_options: Optional[List[str]] = Field(
        default=None,
        description="List of clarification options to present to the user."
    )