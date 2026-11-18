"""Intent classification and self-correcting SQL execution."""

import logging
import time

import instructor
from openai import OpenAI

from app import config
from app.database import execute_safe_query, get_schema_context
from app.schemas import (
    IntentStatus,
    LLMQueryClassification,
    QueryResponse,
)

logger = logging.getLogger("text2sql.engine")

_client = None


def get_client():
    """Lazily create the Instructor client so imports never need a live API key."""
    global _client
    if _client is None:
        _client = instructor.from_openai(
            OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=config.GROQ_API_KEY,
            ),
            mode=instructor.Mode.JSON,
        )
    return _client


def build_system_prompt() -> str:
    return f"""You are an intent-aware Text-to-SQL engine.

Database schema (read from the live database):
{get_schema_context()}

Rules:
- If the prompt is subjective, ambiguous or lacks enough detail for an exact
  SQL query, set status to AMBIGUOUS and provide 3 clarification_options.
- Otherwise set status to CLEAR and return one DuckDB SELECT statement in
  sql_query. Never generate destructive commands.
- Prefer joins across the tables when the question needs data from more than one.
"""


def _extract_tokens(response) -> int:
    raw = getattr(response, "_raw_response", None)
    usage = getattr(raw, "usage", None)
    return getattr(usage, "total_tokens", None) or 0


def _finalize(result: QueryResponse, started: float, tokens: int) -> dict:
    result.execution_time_ms = round((time.perf_counter() - started) * 1000, 2)
    result.tokens_used = tokens or None
    logger.info(
        "query completed status=%s attempts=%s latency_ms=%.1f tokens=%s",
        result.status.value,
        result.attempts_used,
        result.execution_time_ms,
        tokens,
    )
    return result.model_dump()


def process_query(prompt: str) -> dict:
    """Classify intent, then execute SQL with an execute -> error -> fix loop."""
    started = time.perf_counter()
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": prompt},
    ]

    try:
        response = get_client().chat.completions.create(
            model=config.LLM_MODEL,
            response_model=LLMQueryClassification,
            messages=messages,
            max_retries=2,  # Instructor retries malformed *structured output*
        )
        tokens = _extract_tokens(response)

        if response.status == IntentStatus.AMBIGUOUS:
            return _finalize(
                QueryResponse(
                    status=IntentStatus.AMBIGUOUS,
                    reasoning=response.reasoning,
                    clarification_options=response.clarification_options,
                    attempts_used=0,
                ),
                started,
                tokens,
            )

        attempts = 0
        last_sql = ""
        last_error = ""
        conversation = list(messages)

        while attempts < config.MAX_SQL_RETRIES:
            attempts += 1

            if attempts > 1:
                correction = (
                    f"The previous SQL failed with: {last_error}\n"
                    f"Previous SQL:\n{last_sql}\n"
                    "Return a corrected DuckDB SELECT query for the original question."
                )
                conversation = messages + [
                    {"role": "assistant", "content": f"SQL:\n{last_sql}"},
                    {"role": "user", "content": correction},
                ]
                response = get_client().chat.completions.create(
                    model=config.LLM_MODEL,
                    response_model=LLMQueryClassification,
                    messages=conversation,
                    max_retries=2,
                )
                tokens += _extract_tokens(response)

                if response.status == IntentStatus.AMBIGUOUS:
                    return _finalize(
                        QueryResponse(
                            status=IntentStatus.AMBIGUOUS,
                            reasoning=response.reasoning,
                            clarification_options=response.clarification_options,
                            attempts_used=attempts,
                        ),
                        started,
                        tokens,
                    )

            if not response.sql_query:
                last_error = "The model returned no SQL query."
                last_sql = ""
                continue

            try:
                data = execute_safe_query(response.sql_query)
                return _finalize(
                    QueryResponse(
                        status=IntentStatus.CLEAR,
                        sql_query=response.sql_query,
                        data=data,
                        reasoning=response.reasoning,
                        attempts_used=attempts,
                    ),
                    started,
                    tokens,
                )
            except Exception as exc:
                last_sql = response.sql_query
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "SQL attempt %s/%s failed: %s",
                    attempts,
                    config.MAX_SQL_RETRIES,
                    last_error,
                )

        return _finalize(
            QueryResponse(
                status=IntentStatus.CLEAR,
                sql_query=last_sql,
                attempts_used=attempts,
                error=f"SQL execution failed after {attempts} attempts.",
                final_error="See server logs for details.",
            ),
            started,
            tokens,
        )

    except Exception:
        logger.exception("LLM request failed or returned an invalid structure")
        return QueryResponse(
            status=IntentStatus.CLEAR,
            attempts_used=0,
            error="Failed to generate a valid SQL response. Please try again.",
            final_error="See server logs for details.",
            execution_time_ms=round((time.perf_counter() - started) * 1000, 2),
        ).model_dump()
