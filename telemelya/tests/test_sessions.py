"""Tests for session management: responses, wait, reset, isolation."""

import time
import uuid

import httpx
import pytest


class TestGetResponses:
    """GET /api/v1/test/responses."""

    def test_empty_session(self, http, headers, session_id):
        resp = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["responses"] == []
        assert data["session_id"] == session_id

    def test_returns_recorded_responses(self, http, headers, session_id, bot_token):
        # Generate some responses
        http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={"chat_id": 1, "text": "msg1"},
        )
        http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={"chat_id": 1, "text": "msg2"},
        )
        resp = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        )
        responses = resp.json()["responses"]
        assert len(responses) == 2
        assert responses[0]["text"] == "msg1"
        assert responses[1]["text"] == "msg2"

    def test_requires_auth(self, http):
        resp = http.get("/api/v1/test/responses")
        assert resp.status_code in (401, 403)

    def test_default_session(self, http, base_headers):
        """Without session header or param, uses 'default'."""
        resp = http.get("/api/v1/test/responses", headers=base_headers)
        assert resp.json()["session_id"] == "default"


class TestWaitForResponse:
    """GET /api/v1/test/responses/wait."""

    def test_timeout_returns_null(self, http, headers, session_id):
        resp = http.get(
            "/api/v1/test/responses/wait",
            headers=headers,
            params={"session_id": session_id, "timeout": 1},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] is None
        assert data.get("timeout") is True

    def test_returns_existing_response(self, http, headers, session_id, bot_token):
        """If a response is already in the queue, wait returns it immediately."""
        http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={"chat_id": 1, "text": "preloaded"},
        )
        resp = http.get(
            "/api/v1/test/responses/wait",
            headers=headers,
            params={"session_id": session_id, "timeout": 3},
            timeout=10,
        )
        data = resp.json()
        assert data["response"] is not None
        assert data["response"]["text"] == "preloaded"

    def test_wait_consumes_response(self, http, headers, session_id, bot_token):
        """wait_for_response should BLPOP (consume), so the response is gone after."""
        http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={"chat_id": 1, "text": "consumed"},
        )
        # First wait — gets it
        resp1 = http.get(
            "/api/v1/test/responses/wait",
            headers=headers,
            params={"session_id": session_id, "timeout": 3},
            timeout=10,
        )
        assert resp1.json()["response"] is not None

        # Second wait — nothing left
        resp2 = http.get(
            "/api/v1/test/responses/wait",
            headers=headers,
            params={"session_id": session_id, "timeout": 1},
            timeout=10,
        )
        assert resp2.json()["response"] is None

    def test_requires_auth(self, http):
        resp = http.get("/api/v1/test/responses/wait")
        assert resp.status_code in (401, 403)


class TestResetSession:
    """POST /api/v1/test/reset."""

    def test_reset_clears_responses(self, http, headers, session_id, bot_token):
        http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={"chat_id": 1, "text": "to be cleared"},
        )
        # Reset
        resp = http.post(
            "/api/v1/test/reset",
            headers=headers,
            params={"session_id": session_id},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify empty
        resp = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        )
        assert resp.json()["responses"] == []

    def test_reset_nonexistent_session(self, http, headers):
        """Resetting a session that doesn't exist is a no-op, not an error."""
        resp = http.post(
            "/api/v1/test/reset",
            headers=headers,
            params={"session_id": "never-existed"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_requires_auth(self, http):
        resp = http.post("/api/v1/test/reset")
        assert resp.status_code in (401, 403)


class TestSessionIsolation:
    """Verify that sessions don't leak data between each other."""

    def test_responses_isolated(self, http, base_headers, bot_token):
        sid_a = str(uuid.uuid4())
        sid_b = str(uuid.uuid4())
        headers_a = {**base_headers, "X-Test-Session": sid_a}
        headers_b = {**base_headers, "X-Test-Session": sid_b}

        # Bot sends message in session A
        http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers_a,
            json={"chat_id": 1, "text": "session A only"},
        )
        # Bot sends message in session B
        http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers_b,
            json={"chat_id": 2, "text": "session B only"},
        )

        resp_a = http.get(
            "/api/v1/test/responses",
            headers=headers_a,
            params={"session_id": sid_a},
        )
        resp_b = http.get(
            "/api/v1/test/responses",
            headers=headers_b,
            params={"session_id": sid_b},
        )

        assert len(resp_a.json()["responses"]) == 1
        assert resp_a.json()["responses"][0]["text"] == "session A only"

        assert len(resp_b.json()["responses"]) == 1
        assert resp_b.json()["responses"][0]["text"] == "session B only"

        # Cleanup
        http.post("/api/v1/test/reset", headers=headers_a, params={"session_id": sid_a})
        http.post("/api/v1/test/reset", headers=headers_b, params={"session_id": sid_b})

    def test_reset_does_not_affect_other_sessions(self, http, base_headers, bot_token):
        sid_a = str(uuid.uuid4())
        sid_b = str(uuid.uuid4())
        headers_a = {**base_headers, "X-Test-Session": sid_a}
        headers_b = {**base_headers, "X-Test-Session": sid_b}

        http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers_a,
            json={"chat_id": 1, "text": "keep me"},
        )
        http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers_b,
            json={"chat_id": 2, "text": "delete me"},
        )

        # Reset only session B
        http.post("/api/v1/test/reset", headers=headers_b, params={"session_id": sid_b})

        # Session A should still have its response
        resp_a = http.get(
            "/api/v1/test/responses",
            headers=headers_a,
            params={"session_id": sid_a},
        )
        assert len(resp_a.json()["responses"]) == 1

        # Session B should be empty
        resp_b = http.get(
            "/api/v1/test/responses",
            headers=headers_b,
            params={"session_id": sid_b},
        )
        assert resp_b.json()["responses"] == []

        # Cleanup
        http.post("/api/v1/test/reset", headers=headers_a, params={"session_id": sid_a})
