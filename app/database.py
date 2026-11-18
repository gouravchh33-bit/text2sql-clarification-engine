"""DuckDB setup, schema introspection and guarded query execution."""

import re
from datetime import date, datetime
from decimal import Decimal

import duckdb

from app.config import DB_PATH

# Word-boundary matching avoids false positives such as "created_at".
# String literals are stripped first so SELECT 'UPDATE' is not blocked.
_DESTRUCTIVE = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE|REPLACE|"
    r"ATTACH|DETACH|COPY|EXPORT|IMPORT|GRANT|REVOKE)\b",
    re.IGNORECASE,
)
_STRING_LITERAL = re.compile(r"'(?:''|[^'])*'")


def _strip_literals(query: str) -> str:
    return _STRING_LITERAL.sub("''", query)


def _json_safe(value):
    """Convert DuckDB types into JSON-serialisable Python values."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def setup_dummy_data():
    """Create and seed the demo schema. Safe to call on every startup."""
    conn = duckdb.connect(DB_PATH)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS regions ("
            "region_id INTEGER PRIMARY KEY, region_name VARCHAR UNIQUE NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS products ("
            "product_id INTEGER PRIMARY KEY, product_name VARCHAR NOT NULL, "
            "category VARCHAR NOT NULL, unit_price DOUBLE NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS sales ("
            "sale_id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL "
            "REFERENCES products(product_id), region_id INTEGER NOT NULL "
            "REFERENCES regions(region_id), quantity_sold INTEGER NOT NULL, "
            "total_revenue DOUBLE NOT NULL, sale_date DATE NOT NULL)"
        )

        conn.executemany(
            "INSERT INTO regions VALUES (?, ?) ON CONFLICT (region_id) DO NOTHING",
            [
                (1, "North America"),
                (2, "Europe"),
                (3, "Asia Pacific"),
                (4, "Latin America"),
            ],
        )

        products = [
            (1, "Laptop Pro", "Electronics", 1200.0),
            (2, "Wireless Mouse", "Accessories", 25.0),
            (3, "USB-C Hub", "Accessories", 45.0),
            (4, "Standing Desk", "Furniture", 350.0),
            (5, "Mechanical Keyboard", "Electronics", 110.0),
            (6, "Desk Lamp", "Furniture", 60.0),
        ]
        conn.executemany(
            "INSERT INTO products VALUES (?, ?, ?, ?) "
            "ON CONFLICT (product_id) DO NOTHING",
            products,
        )

        # Deterministic seed: one sale per product/region (24 rows).
        quantities = {
            1: [10, 8, 12, 5],
            2: [80, 60, 90, 40],
            3: [40, 35, 50, 20],
            4: [8, 6, 10, 4],
            5: [30, 25, 35, 15],
            6: [25, 20, 30, 12],
        }
        prices = {product_id: price for product_id, _, _, price in products}
        dates = ["2026-01-05", "2026-02-10", "2026-03-15", "2026-04-20"]
        sales_rows = []
        sale_id = 1
        for product_id, per_region in quantities.items():
            for region_id, quantity in enumerate(per_region, start=1):
                sales_rows.append(
                    (
                        sale_id,
                        product_id,
                        region_id,
                        quantity,
                        round(prices[product_id] * quantity, 2),
                        dates[region_id - 1],
                    )
                )
                sale_id += 1

        conn.executemany(
            "INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (sale_id) DO NOTHING",
            sales_rows,
        )
    finally:
        conn.close()


def get_schema_context() -> str:
    """Build the LLM schema prompt from the live database, not a hardcoded string."""
    conn = duckdb.connect(database=DB_PATH, read_only=True)
    try:
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        blocks = []
        for (table_name,) in tables:
            columns = conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'main' AND table_name = ? "
                "ORDER BY ordinal_position",
                [table_name],
            ).fetchall()
            column_list = ", ".join(f"{name} ({dtype})" for name, dtype in columns)
            blocks.append(f"Table: {table_name}\nColumns: {column_list}")
        return "\n".join(blocks)
    finally:
        conn.close()


def check_database_health() -> bool:
    try:
        conn = duckdb.connect(database=DB_PATH, read_only=True)
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
        return True
    except Exception:
        return False


def execute_safe_query(query: str) -> list:
    """Execute LLM-generated SQL with layered guardrails."""
    if not query or not query.strip():
        raise ValueError("Empty SQL query.")

    # 1. Application-level keyword filter (a first pass, not the real boundary).
    if _DESTRUCTIVE.search(_strip_literals(query)):
        raise ValueError("Security Guardrail: Destructive SQL commands are blocked.")

    # 2. Read-only connection physically prevents modification.
    conn = duckdb.connect(database=DB_PATH, read_only=True)
    try:
        clean_query = query.strip().rstrip(";")

        # 3. Force a row cap to avoid runaway results.
        safe_query = f"SELECT * FROM ({clean_query}) LIMIT 100"
        cursor = conn.execute(safe_query)
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        return [
            {column: _json_safe(value) for column, value in zip(columns, row, strict=True)}
            for row in rows
        ]
    finally:
        conn.close()
