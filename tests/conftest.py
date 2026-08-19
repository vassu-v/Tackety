"""
Shared pytest fixtures for the Tackety test suite.

These tests run entirely in-process against a fresh, isolated SQLite data
directory - no live server, no real AI provider key, no network access.
call_ai() is monkeypatched per-test to return a scripted response, since
it's imported directly (`from engine.ai import call_ai`) into chatbot.py
and normalizer.py - patching engine.ai.call_ai itself would not affect
those already-bound references, so we patch each module's own name.
"""
import os
import sys
import shutil
import tempfile
import json as jsonlib

import pytest

# Make `engine` importable regardless of where pytest is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_API_KEY = "test_suite_api_key_do_not_use_in_prod"


@pytest.fixture(scope="session")
def data_dir():
    """A temp directory for all SQLite files this test session creates."""
    d = tempfile.mkdtemp(prefix="tackety_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="session")
def app(data_dir):
    """
    Imports engine.api exactly once per test session. Import triggers
    heavy one-time setup (loading the sentence-transformer model), so we
    do this once and reuse the app across all tests rather than reimport
    per test - individual tests isolate themselves with fresh session/
    cluster ids instead of a fresh database.
    """
    os.environ["TACKETY_DATA_DIR"] = data_dir
    os.environ["TACKETY_API_KEY"] = TEST_API_KEY
    # Never let a real call_ai() call escape into a test by accident -
    # if a test forgets to patch it, this makes the failure obvious
    # instead of silently hitting a real (or missing) AI provider.
    os.environ.setdefault("AI_API", "unused-in-tests")

    from engine import api as api_module
    return api_module


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """
    engine.rate_limit keeps its hit-tracking in a process-global dict so
    it survives across requests within a real server process - which
    means it also persists across tests sharing this session-scoped app,
    and every TestClient request looks like it comes from the same
    client. Without this, tests would silently depend on how many
    /session/* calls happened to run before them - reset it before every
    test so each test's rate-limit behavior only depends on what that
    test itself does.
    """
    import engine.rate_limit as rl
    rl._hits.clear()
    yield
    rl._hits.clear()


@pytest.fixture()
def client(app):
    from fastapi.testclient import TestClient
    with TestClient(app.app) as c:
        yield c


@pytest.fixture()
def auth_headers():
    return {"X-API-Key": TEST_API_KEY}


@pytest.fixture()
def mock_ai_response(app, monkeypatch):
    """
    Returns a function you call with the JSON dict you want the "AI" to
    produce; the chatbot's structured-output parser reads it back out of
    a code fence exactly like a real model response.

        mock_ai_response({"state": "RAISE_TICKET", "collected": {...}})
    """
    def _set(payload: dict, response_text: str = "Sorry about that, I've raised a ticket."):
        full = f"{response_text}\n```json\n{jsonlib.dumps(payload)}\n```"

        def fake_call_ai(prompt="", system_prompt="", config=None):
            return full

        monkeypatch.setattr("engine.chatbot.call_ai", fake_call_ai)
        monkeypatch.setattr("engine.normalizer.call_ai", fake_call_ai)

    return _set
