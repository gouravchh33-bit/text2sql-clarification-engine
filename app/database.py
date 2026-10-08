import duckdb

# Initialize in-memory DuckDB database
conn = duckdb.connect(database=":memory:")

def init_db():
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER,
            product_name VARCHAR,
            category VARCHAR,
            unit_price DECIMAL(10,2),
            quantity_sold INTEGER,
            total_revenue DECIMAL(10,2)
        );
    """)

    # Clear table if re-initializing
    conn.execute("DELETE FROM products;")

    # Seed data: 
    # - 'Enterprise Laptop' has highest unit price & revenue ($15,000) but low units (10)
    # - 'USB-C Cable' has lowest price ($10) but highest units sold (1,200) generating $12,000 revenue
    conn.execute("""
        INSERT INTO products VALUES
        (101, 'Enterprise Laptop', 'Electronics', 1500.00, 10, 15000.00),
        (102, 'USB-C Cable', 'Accessories', 10.00, 1200, 12000.00),
        (103, 'Wireless Mouse', 'Accessories', 25.00, 400, 10000.00),
        (104, '4K Monitor', 'Electronics', 400.00, 25, 10000.00);
    """)

def execute_query(sql_query: str):
    """Executes SQL against DuckDB and returns rows as dictionaries."""
    result = conn.execute(sql_query).fetchall()
    columns = [desc[0] for desc in conn.description]
    return [dict(zip(columns, row)) for row in result]

# Run initialization
init_db()