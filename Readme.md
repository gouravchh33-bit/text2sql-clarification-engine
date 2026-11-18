# Text-to-SQL Clarification Engine

An intent-aware Text-to-SQL API built with FastAPI, DuckDB and the Groq API. It classifies a question *before* touching the database: clear questions become validated DuckDB SQL, ambiguous ones come back as clarification options, and failing SQL is corrected and retried automatically.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-28%20passing-brightgreen.svg)](#testing)
[![CI / Deploy](https://github.com/gouravchh33-bit/text2sql-clarification-engine/actions/workflows/deploy.yml/badge.svg)](https://github.com/gouravchh33-bit/text2sql-clarification-engine/actions/workflows/deploy.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

> **Deployed on AWS EC2.** Interactive docs: `http://<ec2-public-dns>:8000/docs` (replace the placeholder with your instance's public DNS or IP).

---

## Features

- **Intent routing** — prompts are classified as `CLEAR` or `AMBIGUOUS` before any SQL runs.
- **Clarification instead of guessing** — subjective prompts return 3 concrete alternative questions.
- **Real self-correction** — on a DuckDB error, the error is fed back to the LLM and corrected SQL is retried; `attempts_used` reports the true count.
- **Schema-aware prompting** — the prompt context is introspected from the live database, so it can never drift from the schema.
- **Structured LLM output** — Instructor + Pydantic enforce a typed JSON contract; no regex or markdown parsing.
- **Layered SQL safety** — keyword filter, read-only connection, and a forced `LIMIT 100`.
- **API protection** — opt-in `X-API-Key` auth, per-client sliding-window rate limiting, and bounded prompt length.
- **Observable** — per-request latency, attempt count and token usage in the response; structured logs server-side.
- **Tested and typed** — 28 pytest tests, Ruff linting, pinned runtime dependencies.
- **Safe deploys** — GitHub Actions lints, tests and builds before SSHing to EC2; post-deploy health check with automatic rollback.

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
                         │  auth · rate limit · validation   │
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
      │  guarded DuckDB + retry   │                 │ Return clarification       │
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
| Database | DuckDB (embedded analytics), introspected schema |
| LLM | Groq API (`qwen/qwen3.8-27b`) |
| Structured output | Instructor |
| Tests / lint | pytest, httpx, Ruff |
| Containers | Docker, Docker Compose (non-root, healthcheck) |
| CI/CD | GitHub Actions → EC2 over SSH, with test gate and rollback |

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

Docs at <http://127.0.0.1:8000/docs>, health at <http://127.0.0.1:8000/health>.

### Option 2 — local Python

Requires Python 3.11+.

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env            # then add GROQ_API_KEY
export GROQ_API_KEY=...         # PowerShell: $env:GROQ_API_KEY="..."
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
  "sql_query": "SELECT p.category, SUM(s.total_revenue) AS revenue FROM sales s JOIN products p ON s.product_id = p.product_id GROUP BY p.category ORDER BY revenue DESC",
  "data": [
    { "category": "Electronics", "revenue": 53550.0 },
    { "category": "Furniture", "revenue": 15020.0 },
    { "category": "Accessories", "revenue": 13275.0 }
  ],
  "attempts_used": 1,
  "execution_time_ms": 412.7,
  "tokens_used": 183
}
```

### Ambiguous intent — clarification instead of a guess

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
  ],
  "attempts_used": 0
}
```

### With authentication enabled

Set `API_KEY` in the environment and send it as a header:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/query \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your_key_here' \
  -d '{"prompt": "How many sales were in Europe?"}'
```

Unhandled failures return `500` with a reference ID; the underlying exception is logged server-side and never exposed to the client.

---

## Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `GROQ_API_KEY` | Yes | — | Groq API credential |
| `LLM_MODEL` | No | `qwen/qwen3.8-27b` | Groq-hosted model ID |
| `DB_PATH` | No | `text2sql.db` | DuckDB file (set via the container environment) |
| `MAX_SQL_RETRIES` | No | `2` | SQL execute → fix → retry attempts |
| `API_KEY` | No | unset | If set, requests must send `X-API-Key` |
| `RATE_LIMIT_PER_MINUTE` | No | `30` | Sliding-window limit per client |
| `LOG_LEVEL` | No | `INFO` | Server log verbosity |

See `.env.example` for the template. `.env` is gitignored and excluded from Docker builds via `.dockerignore`.

---

## Testing

```bash
pip install -r requirements-dev.txt
ruff check app tests
pytest
```

The suite covers guardrails, schema introspection, row limiting, Pydantic validation, self-correction, authentication, rate limiting and error disclosure. The LLM client is replaced with a fake, so **no API key is needed** to run the tests.

---

## Project structure

```
text2sql-clarification-engine/
├── app/
│   ├── __init__.py
│   ├── config.py         # central env loading and settings
│   ├── main.py           # routes, auth, rate limit, logging, lifespan
│   ├── engine.py         # classification + self-correcting SQL loop
│   ├── database.py       # DuckDB seed, introspection, guarded execution
│   └── schemas.py        # Pydantic contracts
├── tests/                # 28 tests, LLM mocked
├── .github/workflows/deploy.yml  # test gate + SSH deploy + rollback
├── .dockerignore         # keeps secrets and caches out of image layers
├── .gitattributes        # LF normalization across OSes
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── LICENSE
├── pyproject.toml        # pytest + Ruff configuration
├── Readme.md
├── requirements.txt      # pinned runtime dependencies
└── requirements-dev.txt  # test and lint dependencies
```

---

## Deployment / CI-CD

Pushing to `main` runs a two-job workflow:

```
push to main
      ▼
Job 1: checkout → setup Python 3.11 → pip install
       → ruff check → pytest → docker build
      ▼ (only if all pass)
Job 2: SSH to EC2
       → git pull --ff-only origin main
       → docker compose up -d --build --remove-orphans
       → poll /health (up to 60s)
       → on failure: checkout previous commit, rebuild, exit 1
```

Required repository secrets: `EC2_HOST`, `EC2_USERNAME`, `EC2_SSH_KEY`.

To enable auth in production, SSH to EC2 and add `API_KEY=<long random string>` to the `.env` file there, then redeploy. The `X-API-Key` header becomes required immediately.

---

## Security design

1. **Input bounds** — prompts limited to 1–1000 characters; optional shared-key auth; 30 requests/minute per client by default.
2. **Application filter** — destructive keywords are rejected (string literals are stripped first to avoid false positives).
3. **Read-only connection** — DuckDB opens the database with `read_only=True`; this is the actual enforcement boundary.
4. **Row cap** — every query is wrapped as `SELECT * FROM (<query>) LIMIT 100`.
5. **No error disclosure** — exceptions are logged with a request reference ID; clients receive a generic message.
6. **Non-root container** — the API process runs as `appuser`, not root.

---

## Limitations / next steps

- Single EC2 instance: the in-memory rate limiter resets on restart and is not shared across instances (use Redis if you scale out).
- The demo database has no persistent volume, so seeding happens fresh on each deploy.
- No HTTPS or custom domain in front of the EC2 instance yet.
- The keyword filter is a heuristic first pass; the read-only connection is the real guarantee.
- Auth is opt-in; set `API_KEY` on the EC2 host to enable it.
