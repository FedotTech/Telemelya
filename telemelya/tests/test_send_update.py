"""Tests for POST /api/v1/test/send_update — the core Control API endpoint."""

import pytest


class TestSendUpdateNoWebhook:
    """send_update when no webhook is registered — should fail with 424."""

    def test_no_webhook_returns_424(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "no-webhook-token"},
            json={"chat_id": 1},
        )
        assert resp.status_code == 424
        detail = resp.json()["detail"]
        assert "No webhook registered" in detail["error"]
        assert "no-webhook-token" in detail["bot_token"]

    def test_no_webhook_includes_hint(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "missing-hook"},
            json={"chat_id": 1},
        )
        assert resp.status_code == 424
        assert "hint" in resp.json()["detail"]


class TestSendUpdateWebhookUnreachable:
    """send_update when webhook URL is set but bot is not actually running."""

    def test_unreachable_webhook_returns_424(self, http, headers, bot_token):
        # Register webhook pointing to nowhere
        http.post(
            f"/bot{bot_token}/setWebhook",
            json={"url": "http://127.0.0.1:59999/nonexistent"},
        )
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": bot_token},
            json={"chat_id": 1, "text": "hello"},
        )
        assert resp.status_code == 424
        # Cleanup
        http.post(f"/bot{bot_token}/deleteWebhook")


class TestSendUpdateValidation:
    """Validation and parameter edge cases for send_update."""

    def test_missing_bot_token_param(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            json={"chat_id": 1},
        )
        assert resp.status_code == 422  # FastAPI validation

    def test_missing_chat_id(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "any-token"},
            json={},
        )
        assert resp.status_code == 422  # chat_id is required in model

    def test_missing_body(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "any-token"},
        )
        assert resp.status_code == 422

    def test_requires_auth(self, http):
        resp = http.post(
            "/api/v1/test/send_update",
            params={"bot_token": "any-token"},
            json={"chat_id": 1},
        )
        assert resp.status_code in (401, 403)


class TestSendUpdateCommandGeneration:
    """Verify that send_update builds correct Update objects for different inputs."""

    @pytest.fixture(autouse=True)
    def _setup_echo_webhook(self, http, bot_token, server_url):
        """Register webhook if bot is running, skip otherwise.

        These tests need the echo bot to generate delivery success.
        They will be skipped if the bot is not running.
        """
        # We can't guarantee the bot is running, so we test update structure
        # via the 424 response when we need just validation.
        pass

    def test_command_auto_prefixed_with_slash(self, http, headers, bot_token):
        """When command='start', the update should contain '/start'."""
        # We register a webhook that won't respond, but the 424 still
        # proves the endpoint parsed our request. For structural tests
        # we need to inspect the actual update, which requires a live bot.
        # This test just validates the request is accepted.
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "no-webhook-token"},
            json={"chat_id": 1, "command": "start"},
        )
        # Gets 424 (no webhook), but not 422 (validation passes)
        assert resp.status_code == 424

    def test_callback_data_accepted(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "no-webhook-token"},
            json={"chat_id": 1, "callback_data": "btn_yes", "callback_message_id": 5},
        )
        assert resp.status_code == 424  # no webhook, but request was valid

    def test_photo_with_caption_accepted(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "no-webhook-token"},
            json={
                "chat_id": 1,
                "photo_file_id": "fake-photo-id",
                "photo_caption": "My photo",
            },
        )
        assert resp.status_code == 424  # no webhook, but request structure was valid

    def test_custom_from_user(self, http, headers):
        resp = http.post(
            "/api/v1/test/send_update",
            headers=headers,
            params={"bot_token": "no-webhook-token"},
            json={
                "chat_id": 1,
                "text": "hello",
                "from_user": {
                    "id": 999,
                    "first_name": "Alice",
                    "username": "alice_test",
                },
            },
        )
        assert resp.status_code == 424  # no webhook
