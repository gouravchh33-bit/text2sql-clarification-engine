import os
from dotenv import load_dotenv
from groq import Groq
import instructor
from app.schemas import IntentAnalysis

# Load environment variables from .env file
load_dotenv()

# Initialize Groq client wrapped with Instructor for structured JSON outputs
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
client = instructor.from_groq(groq_client, mode=instructor.Mode.JSON)


def analyze_user_intent(prompt: str) -> IntentAnalysis:
    """
    Sends the user's natural language prompt to Llama 3.3 via Groq.
    Forces structured output conforming to the IntentAnalysis schema.
    """
    system_prompt = """
You are a Text-to-SQL intent classifier for a database with the following table:

Table: products
Columns: 
- product_name (VARCHAR)
- category (VARCHAR)
- unit_price (DECIMAL)
- quantity_sold (INTEGER)
- total_revenue (DECIMAL)

RULES:
1. If the user query is clear and maps to a direct SQL metric (e.g., "highest price", "most quantity sold", "highest revenue"), set status to 'CLEAR' and generate the SQL.
2. Subjective terms like "best product", "top product", or "performing well" are AMBIGUOUS because "best" can mean highest total revenue OR highest quantity sold.
3. If the query is AMBIGUOUS, set status to 'AMBIGUOUS' and provide clarification options asking whether they mean volume (quantity_sold) or revenue (total_revenue).
"""

    response = client.chat.completions.create(
        model="qwen/qwen3.8-27b",
        response_model=IntentAnalysis,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0
    )

    return response