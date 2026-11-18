"""Shared test setup. Must configure the environment before app modules load."""

import os
import tempfile

os.environ["DB_PATH"] = os.path.join(tempfile.gettempdir(), "text2sql_pytest.db")
os.environ["LLM_MODEL"] = "test-model"
os.environ.pop("API_KEY", None)

import pytest  # noqa: E402

from app import config  # noqa: E402
from app.database import setup_dummy_data  # noqa: E402
from app.main import _window_hits  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database():
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
    setup_dummy_data()
    _window_hits.clear()
    yield
    _window_hits.clear()
