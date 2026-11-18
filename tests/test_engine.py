from types import SimpleNamespace

from app import config
from app.engine import process_query
from app.schemas import IntentStatus


def classification(status="CLEAR", sql=None, reasoning=None, options=None):
    return SimpleNamespace(
        status=IntentStatus(status),
        sql_query=sql,
        reasoning=reasoning,
        clarification_options=options,
    )


def fake_client(monkeypatch, responses):
    """Replace the LLM client; responses may be values or exceptions."""
    calls = []

    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setattr("app.engine.get_client", lambda: client)
    return calls


def test_clear_query_executes_in_one_attempt(monkeypatch):
    sql = (
        "SELECT p.category, SUM(s.total_revenue) AS revenue "
        "FROM sales s JOIN products p ON s.product_id = p.product_id "
        "GROUP BY p.category"
    )
    fake_client(monkeypatch, [classification(sql=sql)])

    result = process_query("revenue by category")

    assert result["status"] == "CLEAR"
    assert result["attempts_used"] == 1
    assert len(result["data"]) == 3
    assert result["execution_time_ms"] >= 0


def test_ambiguous_query_never_touches_database(monkeypatch):
    fake_client(
        monkeypatch,
        [
            classification(
                status="AMBIGUOUS",
                reasoning="Best is subjective",
                options=["Most revenue", "Most units", "Highest price"],
            )
        ],
    )

    result = process_query("Which product is best?")

    assert result["status"] == "AMBIGUOUS"
    assert result["data"] is None
    assert len(result["clarification_options"]) == 3
    assert result["attempts_used"] == 0


def test_bad_sql_is_corrected_on_retry(monkeypatch):
    calls = fake_client(
        monkeypatch,
        [
            classification(sql="SELECT missing_column FROM sales"),
            classification(sql="SELECT COUNT(*) AS total FROM sales"),
        ],
    )

    result = process_query("How many sales were there?")

    assert result["attempts_used"] == 2
    assert result["data"] == [{"total": 24}]
    assert len(calls) == 2
    assert "failed with" in calls[1]["messages"][-1]["content"]


def test_guardrail_failure_also_triggers_correction(monkeypatch):
    calls = fake_client(
        monkeypatch,
        [
            classification(sql="DELETE FROM sales"),
            classification(sql="SELECT COUNT(*) AS total FROM sales"),
        ],
    )

    result = process_query("Count sales")

    assert result["attempts_used"] == 2
    assert result["data"] == [{"total": 24}]
    assert len(calls) == 2


def test_exhausted_retries_return_honest_attempt_count(monkeypatch):
    fake_client(
        monkeypatch,
        [
            classification(sql="SELECT * FROM missing_table"),
            classification(sql="SELECT * FROM another_missing_table"),
        ],
    )

    result = process_query("show me things")

    assert result["attempts_used"] == config.MAX_SQL_RETRIES
    assert "failed after" in result["error"]
    assert result["final_error"] == "See server logs for details."


def test_llm_failure_does_not_leak_exception(monkeypatch):
    fake_client(monkeypatch, [RuntimeError("secret provider credential")])

    result = process_query("anything")

    assert "Please try again" in result["error"]
    assert "secret provider credential" not in str(result)
