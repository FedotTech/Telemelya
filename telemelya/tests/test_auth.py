"""Tests for authentication: API key validation, missing/invalid tokens."""

import pytest


class TestAuthRequired:
    """Control API endpoints require Bearer token."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/api/v1/test/health"),
        ("GET", "/api/v1/test/responses"),
        ("GET", "/api/v1/test/responses/wait"),
        ("POST", "/api/v1/test/reset"),
        ("POST", "/api/v1/test/send_update"),
    ]

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_no_auth_header_rejected(self, http, method, path):
        resp = http.request(method, path)
        assert resp.status_code in (401, 403)


class TestAuthNotRequired:
    """Bot API endpoints should NOT require auth."""

    BOT_API_ENDPOINTS = [
        "/bot123:token/getMe",
        "/bot123:token/setWebhook",
        "/bot123:token/deleteWebhook",
        "/bot123:token/getWebhookInfo",
        "/bot123:token/sendMessage",
        "/bot123:token/sendPhoto",
        "/bot123:token/editMessageText",
        "/bot123:token/answerCallbackQuery",
    ]

    @pytest.mark.parametrize("path", BOT_API_ENDPOINTS)
    def test_bot_api_no_auth(self, http, path):
        """Bot API endpoints must accept requests without Authorization header."""
        resp = http.post(path, json={})
        # Should not be 403 — may be 200 or other depends on payload
        assert resp.status_code != 403
