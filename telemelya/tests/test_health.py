"""Tests for root and health endpoints."""

import pytest


class TestRootEndpoint:
    """GET / — service info."""

    def test_returns_service_info(self, http):
        resp = http.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "Telemelya"
        assert "version" in data

    def test_no_auth_required(self, http):
        resp = http.get("/")
        assert resp.status_code == 200


class TestHealthEndpoint:
    """GET /api/v1/test/health."""

    def test_health_ok(self, http, base_headers):
        resp = http.get("/api/v1/test/health", headers=base_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["redis"] == "ok"
        assert data["minio"] == "ok"

    def test_health_requires_auth(self, http):
        resp = http.get("/api/v1/test/health")
        assert resp.status_code in (401, 403)
