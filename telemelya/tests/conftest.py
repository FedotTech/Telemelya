"""Pytest fixtures for Telemelya server integration tests.

Requires a running Telemelya stack (docker-compose.local.yml).
"""

import uuid

import httpx
import pytest

SERVER_URL = "http://127.0.0.1:8080"
API_KEY = "test-api-key-12345"
BOT_TOKEN = "123456789:ABCDefGhIjKlMnOpQrStUvWxYz"


@pytest.fixture(scope="session")
def server_url():
    return SERVER_URL


@pytest.fixture(scope="session")
def api_key():
    return API_KEY


@pytest.fixture(scope="session")
def bot_token():
    return BOT_TOKEN


@pytest.fixture(scope="session")
def base_headers():
    return {"Authorization": f"Bearer {API_KEY}"}


@pytest.fixture()
def session_id():
    return str(uuid.uuid4())


@pytest.fixture()
def headers(base_headers, session_id):
    return {**base_headers, "X-Test-Session": session_id}


@pytest.fixture(scope="session")
def http():
    """Shared httpx client for direct HTTP calls."""
    with httpx.Client(base_url=SERVER_URL, timeout=30.0) as client:
        yield client


@pytest.fixture(autouse=True)
def _reset_session(http, headers, session_id):
    """Reset session state after each test."""
    yield
    http.post(
        "/api/v1/test/reset",
        headers=headers,
        params={"session_id": session_id},
    )
