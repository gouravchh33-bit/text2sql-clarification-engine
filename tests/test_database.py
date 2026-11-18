import duckdb
import pytest

from app import config
from app.database import (
    check_database_health,
    execute_safe_query,
    get_schema_context,
)


def test_seed_creates_all_tables():
    conn = duckdb.connect(config.DB_PATH, read_only=True)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main'"
        ).fetchall()
    }
    conn.close()
    assert {"products", "regions", "sales"} <= tables


def test_seed_row_counts():
    assert len(execute_safe_query("SELECT * FROM products")) == 6
    assert len(execute_safe_query("SELECT * FROM regions")) == 4
    assert len(execute_safe_query("SELECT * FROM sales")) == 24


def test_schema_context_comes_from_live_database():
    context = get_schema_context()
    assert "Table: sales" in context
    assert "sale_date (DATE)" in context
    assert "Table: products" in context


def test_rows_are_dicts_and_dates_are_serialised():
    rows = execute_safe_query(
        "SELECT sale_date, total_revenue FROM sales ORDER BY sale_id LIMIT 2"
    )
    assert isinstance(rows[0], dict)
    assert isinstance(rows[0]["sale_date"], str)


def test_row_limit_is_enforced():
    assert len(execute_safe_query("SELECT * FROM range(1000)")) == 100


def test_join_query_works():
    rows = execute_safe_query(
        "SELECT p.category, SUM(s.total_revenue) AS revenue "
        "FROM sales s JOIN products p ON s.product_id = p.product_id "
        "GROUP BY p.category ORDER BY revenue DESC"
    )
    assert len(rows) == 3
    assert rows[0]["revenue"] >= rows[1]["revenue"]


def test_destructive_keywords_are_blocked():
    with pytest.raises(ValueError, match="Security Guardrail"):
        execute_safe_query("DROP TABLE products")


def test_keyword_inside_string_literal_is_not_false_positive():
    assert execute_safe_query("SELECT 'UPDATE' AS literal") == [
        {"literal": "UPDATE"}
    ]


def test_read_only_connection_rejects_writes():
    conn = duckdb.connect(config.DB_PATH, read_only=True)
    try:
        with pytest.raises(duckdb.Error):
            conn.execute("CREATE TABLE hacked (id INTEGER)")
    finally:
        conn.close()


def test_health_check():
    assert check_database_health() is True
