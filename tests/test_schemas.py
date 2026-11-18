import pytest
from pydantic import ValidationError

from app.schemas import QueryRequest, QueryResponse


def test_prompt_is_required():
    with pytest.raises(ValidationError):
        QueryRequest()


def test_prompt_rejects_empty_string():
    with pytest.raises(ValidationError):
        QueryRequest(prompt="")


def test_prompt_rejects_overlong_input():
    with pytest.raises(ValidationError):
        QueryRequest(prompt="x" * 1001)


def test_prompt_accepts_valid_input():
    assert QueryRequest(prompt="Show revenue by region").prompt == "Show revenue by region"


def test_request_has_swagger_example():
    example = QueryRequest.model_config["json_schema_extra"]["examples"][0]
    assert "prompt" in example


def test_response_contains_observability_fields():
    response = QueryResponse(status="CLEAR", attempts_used=1)
    dumped = response.model_dump()
    assert dumped["execution_time_ms"] is None
    assert dumped["tokens_used"] is None
    assert dumped["attempts_used"] == 1
