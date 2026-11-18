# Text-to-SQL Clarification Engine

An intent-aware Text-to-SQL API built with FastAPI, DuckDB and the Groq API. It classifies a question *before* touching the database: clear questions are turned into validated DuckDB SQL, while ambiguous questions come back as clarification options instead of a guessed answer.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![CI / Deploy](https://github.com/gouravchh33-bit/text2sql-clarification-engine/actions/workflows/deploy.yml/badge.svg)](https://github.com/gouravchh33-bit/text2sql-clarification-engine/actions/workflows/deploy.yml)

> **Deployed on AWS EC2.** Interactive docs: `http://<ec2-public-dns>:8000/docs` (replace the placeholder with your instance's public DNS or IP).

---

## Features

- **Intent routing** — prompts are classified as `CLEAR` or `AMBIGUOUS` before any SQL runs.
- **Clarification instead of guessing** — subjective prompts ("Which product is best?") return 3 concrete alternative questions.
- **Structured LLM output** — Instructor + Pydantic enforce a typed JSON contract, so no regex/markdown parsing.
- **Layered SQL safety** — keyword blocklist, read-only DuckDB connection, and a forced `LIMIT 100`.
- **Validated-output retries** — Instructor retries malformed LLM responses up to 2 times.
- **Clean architecture** — separate `schemas`, `engine`, `database` and `main` modules with a FastAPI `lifespan` for startup.
- **One-command deployment** — Docker Compose locally, GitHub Actions → SSH → EC2 in production.

---

## Architecture

```
                         ┌───────────────────────────────────┐
                         │        Client / Web App           │
                         └─────────────────┬─────────────────┘
                                           │ POST /api/v1/query
                                           ▼
                         ┌───────────────────────────────────┐
                         │      FastAPI router (main.py)     │
                         │   validation, logging, errors     │
                         └─────────────────┬─────────────────┘
                                           ▼
                         ┌───────────────────────────────────┐
                         │     LLM engine (engine.py)        │
                         │    Instructor + Groq API          │
                         └─────────────────┬─────────────────┘
                                           │ classify intent
                    ┌──────────────────────┴──────────────────────┐
                    ▼                                             ▼
             Status: CLEAR                                Status: AMBIGUOUS
                    │                                             │
                    ▼                                             ▼
      ┌───────────────────────────┐                 ┌───────────────────────────┐
      │  Execution layer          │                 │ Bypass database           │
      │  (database.py - DuckDB)   │                 │ Return clarification       │
      │  guardrails + LIMIT 100   │                 │ options to client          │
      └─────────────┬─────────────┘                 └─────────────┬─────────────┘
                    └──────────────────────┬──────────────────────┘
                                           ▼
                         ┌───────────────────────────────────┐
                         │      Structured JSON response     │
                         └───────────────────────────────────┘
```

---

## Tech stack

| Layer | Choice |
| --- | --- |
| Framework | FastAPI, Pydantic v2 |
| Database | DuckDB (embedded, in-process analytics) |
| LLM | Groq API (`qwen/qwen3.8-27b`) |
| Structured output | Instructor |
| Containers | Docker, Docker Compose |
| CI/CD | GitHub Actions → EC2 over SSH |

---

## Quickstart

### Option 1 — Docker Compose (recommended)

```bash
git clone https://github.com/gouravchh33-bit/text2sql-clarification-engine.git
cd text2sql-clarification-engine
cp .env.example .env
# edit .env and add your Groq API key
docker compose up --build
```

API docs are then at <http://127.0.0.1:8000/docs>.

### Option 2 — local Python

Requires Python 3.11+.

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then add GROQ_API_KEY
export GROQ_API_KEY=...         # Windows PowerShell: $env:GROQ_API_KEY="..."
uvicorn app.main:app --reload
```

---

## API usage

### Clear intent

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Show me total revenue by category"}'
```

```json
{
  "status": "CLEAR",
  "sql_query": "SELECT category, SUM(total_revenue) AS total_revenue FROM products GROUP BY category",
  "data": [
    { "category": "Electronics", "total_revenue": 25000.0 },
    { "category": "Accessories", "total_revenue": 22000.0 }
  ]
}
```

### Ambiguous intent — guardrail triggers a clarification

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "Which is the best product?"}'
```

```json
{
  "status": "AMBIGUOUS",
  "reasoning": "'Best' could mean highest revenue, highest quantity sold, or highest unit price.",
  "clarification_options": [
    "Product with the highest total revenue",
    "Product with the highest quantity sold",
    "Product with the highest unit price"
  ]
}
```

Unhandled failures return `500` with a reference ID; the underlying exception is logged server-side, never exposed to the client.

---

## Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `GROQ_API_KEY` | Yes | — | Groq API credential |
| `LLM_MODEL` | No | `qwen/qwen3.8-27b` | Groq-hosted model ID |
| `DB_PATH` | No | `text2sql.db` | DuckDB file (set via the container environment / Compose `env_file`) |

See `.env.example` for the template. `.env` is gitignored and excluded from Docker builds via `.dockerignore`.

---

## Project structure

```
text2sql-clarification-engine/
├── app/
│   ├── __init__.py
│   ├── main.py           # routes, logging, error mapping, lifespan
│   ├── engine.py         # intent classification via Instructor + Groq
│   ├── database.py       # DuckDB seed data + guarded execution
│   └── schemas.py        # Pydantic request/response contracts
├── .github/workflows/deploy.yml  # GitHub Actions → EC2
├── .dockerignore         # keeps secrets and caches out of image layers
├── .gitattributes        # LF normalization across OSes
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── Readme.md
└── requirements.txt
```

---

## Deployment / CI-CD

Pushing to `main` triggers `.github/workflows/deploy.yml`, which SSHes into the EC2 instance, pulls the latest commit and rebuilds the containers:

```
git push origin main
      ▼
GitHub Actions (ubuntu-latest)
      ▼
appleboy/ssh-action → EC2
      ▼
git pull origin main && docker compose up -d --build
```

Required repository secrets: `EC2_HOST`, `EC2_USERNAME`, `EC2_SSH_KEY`.

---

## Security design

1. **Application filter** — destructive keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`) are rejected before execution.
2. **Read-only connection** — DuckDB opens the database with `read_only=True`; this is the actual enforcement boundary.
3. **Row cap** — every query is wrapped as `SELECT * FROM (<query>) LIMIT 100`.
4. **No error disclosure** — exceptions are logged with a request reference ID; clients receive a generic message.

---

## Limitations / next steps

- The demo schema is a single 2-row `products` table and `SCHEMA_CONTEXT` is hardcoded in `engine.py`; a richer multi-table schema with introspected metadata would show real joins.
- Instructor retries validate the *shape* of the LLM response, not SQL semantics — a true execute → error → regenerate loop is not implemented yet.
- The public endpoint has no authentication or rate limiting; add both before relying on it outside a demo.
- The keyword filter is a heuristic first pass; the read-only connection is the real guarantee.
