import duckdb
import os

DB_PATH = os.getenv("DB_PATH", "text2sql.db")

def setup_dummy_data():
    """Initializes the database with sample data if it doesn't exist."""
    conn = duckdb.connect(DB_PATH)
    # Fix 1: Added PRIMARY KEY to the category column
    conn.execute("CREATE TABLE IF NOT EXISTS products (category VARCHAR PRIMARY KEY, total_revenue DOUBLE, quantity_sold INT, unit_price DOUBLE)")
    
    # Fix 2: Added (category) to the ON CONFLICT clause
    conn.execute("INSERT INTO products VALUES ('Electronics', 25000.0, 100, 250.0), ('Accessories', 22000.0, 500, 44.0) ON CONFLICT (category) DO NOTHING")
    conn.close()

def execute_safe_query(query: str) -> list:
    """Executes a query with strict read-only constraints and limits."""
    # 1. Block destructive keywords at the application level
    forbidden_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE"]
    if any(keyword in query.upper() for keyword in forbidden_keywords):
        raise ValueError("Security Guardrail: Destructive SQL commands are blocked.")

    # 2. Connect in read-only mode to physically prevent database modification
    conn = duckdb.connect(database=DB_PATH, read_only=True)
    try:
        # Remove any trailing spaces or semicolons from the LLM's output
        clean_query = query.strip().rstrip(";")
        
        # Force a row limit to prevent memory overflow from bad JOINs
        safe_query = f"SELECT * FROM ({clean_query}) LIMIT 100"
        
        # Execute and return as a list of dictionaries
        df = conn.execute(safe_query).df()
        return df.to_dict(orient="records")
    finally:
        conn.close()