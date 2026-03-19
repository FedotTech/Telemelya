"""Tests for Bot API endpoints: setWebhook, deleteWebhook, getWebhookInfo, getMe."""

import pytest


class TestGetMe:
    """POST /bot{token}/getMe."""

    def test_returns_bot_info(self, http, bot_token):
        resp = http.post(f"/bot{bot_token}/getMe")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["result"]["is_bot"] is True
        assert data["result"]["username"] == "telemelya_bot"

    def test_any_token_accepted(self, http):
        resp = http.post("/botfake-token-xxx/getMe")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_no_auth_required(self, http, bot_token):
        # Bot API endpoints should not require auth (bots don't send Bearer)
        resp = http.post(f"/bot{bot_token}/getMe")
        assert resp.status_code == 200


class TestSetWebhook:
    """POST /bot{token}/setWebhook."""

    def test_set_webhook_success(self, http, bot_token):
        resp = http.post(
            f"/bot{bot_token}/setWebhook",
            json={"url": "http://example.com/webhook"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["description"] == "Webhook was set"

    def test_set_webhook_without_url(self, http, bot_token):
        resp = http.post(f"/bot{bot_token}/setWebhook", json={})
        data = resp.json()
        assert data["ok"] is False
        assert data["error_code"] == 400

    def test_set_webhook_empty_url(self, http, bot_token):
        resp = http.post(f"/bot{bot_token}/setWebhook", json={"url": ""})
        data = resp.json()
        assert data["ok"] is False
        assert data["error_code"] == 400

    def test_set_webhook_form_data(self, http, bot_token):
        resp = http.post(
            f"/bot{bot_token}/setWebhook",
            data={"url": "http://example.com/webhook"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_set_webhook_overwrites_previous(self, http, bot_token):
        http.post(
            f"/bot{bot_token}/setWebhook",
            json={"url": "http://first.com/hook"},
        )
        http.post(
            f"/bot{bot_token}/setWebhook",
            json={"url": "http://second.com/hook"},
        )
        resp = http.post(f"/bot{bot_token}/getWebhookInfo")
        assert resp.json()["result"]["url"] == "http://second.com/hook"


class TestDeleteWebhook:
    """POST /bot{token}/deleteWebhook."""

    def test_delete_existing_webhook(self, http, bot_token):
        http.post(
            f"/bot{bot_token}/setWebhook",
            json={"url": "http://example.com/webhook"},
        )
        resp = http.post(f"/bot{bot_token}/deleteWebhook")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify webhook is gone
        info = http.post(f"/bot{bot_token}/getWebhookInfo").json()
        assert info["result"]["url"] == ""

    def test_delete_nonexistent_webhook(self, http, bot_token):
        # deleteWebhook on token with no webhook should succeed
        resp = http.post("/botnonexistent-token/deleteWebhook")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestGetWebhookInfo:
    """POST /bot{token}/getWebhookInfo."""

    def test_no_webhook_set(self, http):
        resp = http.post("/botunused-token-123/getWebhookInfo")
        data = resp.json()
        assert data["ok"] is True
        assert data["result"]["url"] == ""

    def test_with_webhook_set(self, http, bot_token):
        http.post(
            f"/bot{bot_token}/setWebhook",
            json={"url": "http://my-bot.local/hook"},
        )
        resp = http.post(f"/bot{bot_token}/getWebhookInfo")
        data = resp.json()
        assert data["ok"] is True
        assert data["result"]["url"] == "http://my-bot.local/hook"
        assert data["result"]["has_custom_certificate"] is False
