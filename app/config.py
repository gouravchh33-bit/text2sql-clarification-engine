"""Central, import-safe configuration.

Loading .env here (once) means every module reads the same values, and
importing the app never requires a Groq API key to be present.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


APP_VERSION = "1.1.0"

# LLM
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")
MAX_SQL_RETRIES = _int_env("MAX_SQL_RETRIES", 2)

# Storage
DB_PATH = os.getenv("DB_PATH", "text2sql.db")

# API protection (auth is opt-in so deployments cannot lock themselves out)
API_KEY = os.getenv("API_KEY")
RATE_LIMIT_PER_MINUTE = _int_env("RATE_LIMIT_PER_MINUTE", 30)

# Observability
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
