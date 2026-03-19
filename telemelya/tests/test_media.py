"""Tests for media handling: sendPhoto with file, getFile, file download."""

import uuid

import pytest


class TestGetFile:
    """POST /bot{token}/getFile — lookup file metadata."""

    def test_file_not_found(self, http, bot_token, headers, session_id):
        resp = http.post(
            f"/bot{bot_token}/getFile",
            headers=headers,
            json={"file_id": "nonexistent-file-id"},
        )
        data = resp.json()
        assert data["ok"] is False
        assert data["error_code"] == 400
        assert "not found" in data["description"].lower()

    def test_file_found_after_send_photo(self, http, bot_token, headers, session_id):
        """After sendPhoto with a real file, getFile should find the metadata."""
        # Upload a small test image via sendPhoto
        photo_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # Minimal fake PNG
        resp = http.post(
            f"/bot{bot_token}/sendPhoto",
            headers=headers,
            files={"photo": ("test.png", photo_data, "image/png")},
            data={"chat_id": "12345"},
        )
        assert resp.status_code == 200
        file_id = resp.json()["result"]["photo"][0]["file_id"]

        # Now getFile should find it
        resp = http.post(
            f"/bot{bot_token}/getFile",
            headers=headers,
            json={"file_id": file_id},
        )
        data = resp.json()
        assert data["ok"] is True
        assert data["result"]["file_id"] == file_id
        assert "file_path" in data["result"]

    def test_empty_file_id(self, http, bot_token, headers, session_id):
        resp = http.post(
            f"/bot{bot_token}/getFile",
            headers=headers,
            json={"file_id": ""},
        )
        data = resp.json()
        assert data["ok"] is False


class TestFileDownload:
    """GET /bot{token}/file/{file_path} — download file from MinIO."""

    def test_download_nonexistent_file(self, http, bot_token):
        resp = http.get(f"/bot{bot_token}/file/nonexistent/path/file.jpg")
        data = resp.json()
        assert data["ok"] is False
        assert data["error_code"] == 404

    def test_upload_and_download(self, http, bot_token, headers, session_id):
        """Full flow: sendPhoto → getFile → download."""
        photo_content = b"fake-image-data-for-test-" + uuid.uuid4().bytes
        resp = http.post(
            f"/bot{bot_token}/sendPhoto",
            headers=headers,
            files={"photo": ("photo.jpg", photo_content, "image/jpeg")},
            data={"chat_id": "12345"},
        )
        assert resp.status_code == 200
        file_id = resp.json()["result"]["photo"][0]["file_id"]

        # Get file path
        resp = http.post(
            f"/bot{bot_token}/getFile",
            headers=headers,
            json={"file_id": file_id},
        )
        file_path = resp.json()["result"]["file_path"]

        # Download
        resp = http.get(f"/bot{bot_token}/file/{file_path}")
        assert resp.status_code == 200
        assert resp.content == photo_content


class TestMediaInSession:
    """GET /api/v1/test/media/{file_id} — control API media download."""

    def test_media_not_found(self, http, headers, session_id):
        resp = http.get(
            "/api/v1/test/media/nonexistent-file-id",
            headers=headers,
            params={"session_id": session_id},
        )
        assert resp.status_code == 200  # Returns JSON error, not HTTP 404
        data = resp.json()
        assert data["ok"] is False

    def test_media_requires_auth(self, http):
        resp = http.get("/api/v1/test/media/some-file-id")
        assert resp.status_code in (401, 403)
