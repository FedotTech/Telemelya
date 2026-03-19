"""Tests for edge cases and boundary conditions."""

import uuid

import pytest


class TestMalformedRequests:
    """Edge cases with malformed or unexpected request data."""

    def test_bot_api_empty_json(self, http, bot_token, headers):
        """sendMessage with empty JSON body — should handle gracefully."""
        resp = http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={},
        )
        # Should return 200 with empty/null fields, not crash
        assert resp.status_code == 200

    def test_bot_api_no_content_type(self, http, bot_token, headers):
        """sendMessage with no body at all."""
        resp = http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
        )
        assert resp.status_code == 200

    def test_send_update_extra_fields_ignored(self, http, headers):
        """Extra fields in send_update body should be ignored by Pydantic."""
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "no-hook"},
            json={"chat_id": 1, "text": "test", "unknown_field": "extra"},
        )
        # Should not crash — 424 because no webhook, but not 422
        assert resp.status_code == 424

    def test_send_update_negative_chat_id(self, http, headers):
        """Negative chat_id (group chats use negative IDs in Telegram)."""
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "no-hook"},
            json={"chat_id": -1001234567890, "text": "group message"},
        )
        assert resp.status_code == 424  # no webhook, but chat_id accepted

    def test_send_update_zero_chat_id(self, http, headers):
        """chat_id = 0 is technically invalid for Telegram but should not crash."""
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "no-hook"},
            json={"chat_id": 0, "text": "zero id"},
        )
        assert resp.status_code == 424

    def test_send_message_very_long_text(self, http, bot_token, headers, session_id):
        """Very long text message — should be accepted without truncation."""
        long_text = "A" * 10_000
        resp = http.post(
            f"/bot{bot_token}/sendMessage",
            headers=headers,
            json={"chat_id": 12345, "text": long_text},
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["text"] == long_text


class TestMultipleResponsesOrder:
    """Ensure response ordering is preserved (FIFO)."""

    def test_fifo_order(self, http, bot_token, headers, session_id):
        messages = [f"msg_{i}" for i in range(5)]
        for msg in messages:
            http.post(
                f"/bot{bot_token}/sendMessage",
                headers=headers,
                json={"chat_id": 1, "text": msg},
            )

        resp = http.get(
            "/api/v1/test/responses",
            headers=headers,
            params={"session_id": session_id},
        )
        texts = [r["text"] for r in resp.json()["responses"]]
        assert texts == messages


class TestWebhookLifecycle:
    """Full webhook set → verify → delete → verify lifecycle."""

    def test_full_lifecycle(self, http):
        token = f"lifecycle-{uuid.uuid4()}"
        url = "http://bot.example.com/webhook"

        # Initially no webhook
        info = http.post(f"/bot{token}/getWebhookInfo").json()
        assert info["result"]["url"] == ""

        # Set webhook
        http.post(f"/bot{token}/setWebhook", json={"url": url})
        info = http.post(f"/bot{token}/getWebhookInfo").json()
        assert info["result"]["url"] == url

        # Delete webhook
        http.post(f"/bot{token}/deleteWebhook")
        info = http.post(f"/bot{token}/getWebhookInfo").json()
        assert info["result"]["url"] == ""


class TestMultipleTokens:
    """Different bot tokens should have independent webhook registries."""

    def test_webhook_isolation_by_token(self, http):
        token_a = f"bot-a-{uuid.uuid4()}"
        token_b = f"bot-b-{uuid.uuid4()}"

        http.post(f"/bot{token_a}/setWebhook", json={"url": "http://bot-a.local/hook"})
        http.post(f"/bot{token_b}/setWebhook", json={"url": "http://bot-b.local/hook"})

        info_a = http.post(f"/bot{token_a}/getWebhookInfo").json()
        info_b = http.post(f"/bot{token_b}/getWebhookInfo").json()

        assert info_a["result"]["url"] == "http://bot-a.local/hook"
        assert info_b["result"]["url"] == "http://bot-b.local/hook"

        # Cleanup
        http.post(f"/bot{token_a}/deleteWebhook")
        http.post(f"/bot{token_b}/deleteWebhook")


class TestConcurrentSessions:
    """Multiple sessions interacting simultaneously."""

    def test_parallel_sessions_dont_interfere(self, http, base_headers, bot_token):
        sessions = [str(uuid.uuid4()) for _ in range(3)]

        # Each session sends a unique message
        for i, sid in enumerate(sessions):
            h = {**base_headers, "X-Test-Session": sid}
            http.post(
                f"/bot{bot_token}/sendMessage",
                headers=h,
                json={"chat_id": i + 1, "text": f"session-{i}"},
            )

        # Verify isolation
        for i, sid in enumerate(sessions):
            h = {**base_headers, "X-Test-Session": sid}
            resp = http.get(
                "/api/v1/test/responses",
                headers=h,
                params={"session_id": sid},
            )
            responses = resp.json()["responses"]
            assert len(responses) == 1
            assert responses[0]["text"] == f"session-{i}"

        # Cleanup
        for sid in sessions:
            h = {**base_headers, "X-Test-Session": sid}
            http.post("/api/v1/test/reset", headers=h, params={"session_id": sid})
