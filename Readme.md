# Intent-Aware Text-to-SQL Clarification Engine

A production-ready FastAPI backend that transforms natural language queries into executable SQL over DuckDB. Unlike traditional "naive" AI wrappers that blindly execute LLM-generated code, this engine evaluates prompt ambiguity first, enforcing schema constraints and returning structured clarification options before touching the database.

---
## 🏗️ Architecture Overview

```
                        ┌───────────────────────────────────┐
                        │        Client / Web App           │
                        └─────────────────┬─────────────────┘
                                          │
                                   HTTP POST /api/v1/query
                                          │
                                          ▼
                        ┌───────────────────────────────────┐
                        │      FastAPI Router (main.py)     │
                        └─────────────────┬─────────────────┘
                                          │
                                          ▼
                        ┌───────────────────────────────────┐
                        │     LLM Engine (engine.py)        │
                        │    Instructor + Groq API          │
                        └─────────────────┬─────────────────┘
                                          │
                             [Classify Query Intent]
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   │                                             │
                   ▼                                             ▼
            Status: CLEAR                                Status: AMBIGUOUS
                   │                                             │
                   ▼                                             ▼
     ┌───────────────────────────┐                 ┌───────────────────────────┐
     │  Execution Layer          │                 │ Bypass Database           │
     │  (database.py - DuckDB)   │                 │ Return Options to Client  │
     └─────────────┬─────────────┘                 └─────────────┬─────────────┘
                   │                                             │
                   └──────────────────────┬──────────────────────┘
                                          │
                                          ▼
                        ┌───────────────────────────────────┐
                        │      Structured JSON Response     │
                        └───────────────────────────────────┘
```
---

## ✨ Key Engineering Features

* **Two-Path Intent Disambiguation:** Differentiates between clear metric queries and subjective prompts (e.g., *"Which is the best product?"*). Ambiguous prompts bypass execution and return user options.
* **Schema Enforcement via Instructor & Pydantic:** Guarantees strict JSON output structures from the LLM, eliminating regex parsing errors or invalid markdown wrapping.
* **In-Memory Analytical Engine:** Powered by DuckDB for sub-millisecond analytical query execution.
* **Production-Ready Architecture:** Clean separation of concerns across modules (`schemas`, `engine`, `database`, `main`).
* **Containerized Deployment:** Fully dockerized with `Dockerfile` and `docker-compose.yml` for single-command orchestration.

---

## 🛠️ Tech Stack

* **Framework:** FastAPI (Python 3.11)
* **Database:** DuckDB
* **LLM Orchestration:** Instructor, Groq Cloud API (`qwen/qwen3.8-27b`)
* **Validation:** Pydantic v2
* **Containerization:** Docker & Docker Compose

---

## 🚀 Quickstart Guide

### Prerequisites
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed **OR** Python 3.11+
* A free [Groq API Key](https://console.groq.com)

---

### Option 1: Run with Docker Compose (Recommended)

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/gouravchh33-bit/text2sql-clarification-engine.git](https://github.com/gouravchh33-git/text2sql-clarification-engine.git)
   cd text2sql-clarification-engine
Configure environment variables:

Bash
cp .env.example .env
Open .env and add your Groq API key:

Code snippet
GROQ_API_KEY=gsk_your_actual_api_key_here
Start the application:

Bash
docker compose up --build
The API will be live at http://127.0.0.1:8000/docs.

Option 2: Run Locally with Python
Create and activate a virtual environment:

Bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
Install dependencies:

Bash
pip install -r requirements.txt
Set up .env:

Bash
cp .env.example .env
Add your GROQ_API_KEY to .env.

Launch the server:

Bash
uvicorn app.main:app --reload
🧪 API Usage Examples
1. Clear Intent Query
Endpoint: POST /api/v1/query

Payload:

JSON
{
  "prompt": "Show me total revenue by category"
}
Response (200 OK):

JSON
{
  "status": "CLEAR",
  "sql_query": "SELECT category, SUM(total_revenue) AS total_revenue FROM products GROUP BY category",
  "data": [
    {
      "category": "Electronics",
      "total_revenue": 25000.0
    },
    {
      "category": "Accessories",
      "total_revenue": 22000.0
    }
  ]
}
2. Ambiguous Intent Query (Guardrail Triggered)
Endpoint: POST /api/v1/query

Payload:

JSON
{
  "prompt": "Which is the best product?"
}
Response (200 OK):

JSON
{
  "status": "AMBIGUOUS",
  "reasoning": "The term 'best' is ambiguous because it can refer to highest total revenue or highest sales volume (quantity sold).",
  "clarification_options": [
    "Product with the highest total revenue",
    "Product with the highest quantity sold",
    "Product with the highest unit price"
  ]
}

📂 Project Structure

text2sql-clarification-engine/
├── app/
│   ├── __init__.py
│   ├── database.py       # DuckDB connection & schema execution
│   ├── engine.py         # Instructor/Groq LLM intent classification
│   ├── main.py           # FastAPI routes & HTTP middleware
│   └── schemas.py        # Pydantic data contracts
├── .dockerignore
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── README.md
└── requirements.txt