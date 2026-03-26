"""Tests for gp_client.py — HMAC auth and API operations."""

import base64
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _expected_signature(password: str, message: str) -> str:
    sig = hmac.new(
        bytes(password, "ISO-8859-1"),
        msg=bytes(message, "ISO-8859-1"),
        digestmod=hashlib.sha1,
    ).digest()
    return base64.b64encode(sig).decode()


# ---------------------------------------------------------------------------
# get_headers
# ---------------------------------------------------------------------------

class TestGetHeaders:
    def test_get_request_authorization_format(self):
        with patch.dict(
            "os.environ",
            {"GP_ADMIN_USER_ID": "user123", "GP_ADMIN_PASSWORD": "secret"},
        ):
            import importlib
            import scripts.gp.gp_client as gp_client  # noqa: PLC0415
            importlib.reload(gp_client)

            headers = gp_client.get_headers("https://example.com/api", "GET")

        assert headers["Authorization"].startswith("GP-HMAC user123:")
        assert "GP-Date" in headers
        assert headers["accept"] == "application/json"
        assert "Content-Type" not in headers

    def test_put_request_includes_content_type(self):
        with patch.dict(
            "os.environ",
            {"GP_ADMIN_USER_ID": "user123", "GP_ADMIN_PASSWORD": "secret"},
        ):
            import importlib
            import scripts.gp.gp_client as gp_client  # noqa: PLC0415
            importlib.reload(gp_client)

            headers = gp_client.get_headers("https://example.com/api", "PUT", {"key": "val"})

        assert headers["Content-Type"] == "application/json"

    def test_patch_request_uses_merge_patch_content_type(self):
        with patch.dict(
            "os.environ",
            {"GP_ADMIN_USER_ID": "user123", "GP_ADMIN_PASSWORD": "secret"},
        ):
            import importlib
            import scripts.gp.gp_client as gp_client  # noqa: PLC0415
            importlib.reload(gp_client)

            headers = gp_client.get_headers("https://example.com/api", "PATCH", {})

        assert headers["Content-Type"] == "application/merge-patch+json"

    def test_hmac_signature_is_deterministic_for_same_inputs(self):
        with patch.dict(
            "os.environ",
            {"GP_ADMIN_USER_ID": "user123", "GP_ADMIN_PASSWORD": "secret"},
        ):
            import importlib
            import scripts.gp.gp_client as gp_client  # noqa: PLC0415
            importlib.reload(gp_client)

            with patch("scripts.gp.gp_client.datetime") as mock_dt:
                mock_dt.now.return_value.strftime.return_value = "Thu, 26 Mar 2026 12:00:00 UTC"

                h1 = gp_client.get_headers("https://example.com", "GET")
                h2 = gp_client.get_headers("https://example.com", "GET")

        assert h1["Authorization"] == h2["Authorization"]


# ---------------------------------------------------------------------------
# list_bundles
# ---------------------------------------------------------------------------

class TestListBundles:
    def test_returns_parsed_json_on_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"bundleIds": ["langflow-ui"]}

        with patch.dict(
            "os.environ",
            {"GP_ADMIN_USER_ID": "u", "GP_ADMIN_PASSWORD": "p"},
        ), patch("scripts.gp.gp_client.requests.get", return_value=mock_response) as mock_get:
            import importlib
            import scripts.gp.gp_client as gp_client  # noqa: PLC0415
            importlib.reload(gp_client)

            result = gp_client.list_bundles()

        mock_get.assert_called_once()
        mock_response.raise_for_status.assert_called_once()
        assert result == {"bundleIds": ["langflow-ui"]}

    def test_raises_on_http_error(self):
        import requests as req

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError("401 Unauthorized")

        with patch.dict(
            "os.environ",
            {"GP_ADMIN_USER_ID": "u", "GP_ADMIN_PASSWORD": "p"},
        ), patch("scripts.gp.gp_client.requests.get", return_value=mock_response):
            import importlib
            import scripts.gp.gp_client as gp_client  # noqa: PLC0415
            importlib.reload(gp_client)

            with pytest.raises(req.exceptions.HTTPError):
                gp_client.list_bundles()

    def test_raises_on_timeout(self):
        import requests as req

        with patch.dict(
            "os.environ",
            {"GP_ADMIN_USER_ID": "u", "GP_ADMIN_PASSWORD": "p"},
        ), patch(
            "scripts.gp.gp_client.requests.get",
            side_effect=req.exceptions.Timeout,
        ):
            import importlib
            import scripts.gp.gp_client as gp_client  # noqa: PLC0415
            importlib.reload(gp_client)

            with pytest.raises(req.exceptions.Timeout):
                gp_client.list_bundles()


# ---------------------------------------------------------------------------
# upload_strings
# ---------------------------------------------------------------------------

class TestUploadStrings:
    def test_successful_upload(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}

        with patch.dict(
            "os.environ",
            {"GP_ADMIN_USER_ID": "u", "GP_ADMIN_PASSWORD": "p"},
        ), patch("scripts.gp.gp_client.requests.put", return_value=mock_response) as mock_put:
            import importlib
            import scripts.gp.gp_client as gp_client  # noqa: PLC0415
            importlib.reload(gp_client)

            result = gp_client.upload_strings({"hello": "Hello"})

        mock_put.assert_called_once()
        assert result == {"status": "ok"}

    def test_raises_on_server_error(self):
        import requests as req

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError("500")

        with patch.dict(
            "os.environ",
            {"GP_ADMIN_USER_ID": "u", "GP_ADMIN_PASSWORD": "p"},
        ), patch("scripts.gp.gp_client.requests.put", return_value=mock_response):
            import importlib
            import scripts.gp.gp_client as gp_client  # noqa: PLC0415
            importlib.reload(gp_client)

            with pytest.raises(req.exceptions.HTTPError):
                gp_client.upload_strings({"hello": "Hello"})


# ---------------------------------------------------------------------------
# get_strings
# ---------------------------------------------------------------------------

class TestGetStrings:
    def test_returns_parsed_json(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "resourceStrings": {"hello": {"value": "Bonjour"}}
        }

        with patch.dict(
            "os.environ",
            {"GP_ADMIN_USER_ID": "u", "GP_ADMIN_PASSWORD": "p"},
        ), patch("scripts.gp.gp_client.requests.get", return_value=mock_response):
            import importlib
            import scripts.gp.gp_client as gp_client  # noqa: PLC0415
            importlib.reload(gp_client)

            result = gp_client.get_strings("fr")

        assert result["resourceStrings"]["hello"]["value"] == "Bonjour"

    def test_raises_on_403(self):
        import requests as req

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError("403 Forbidden")

        with patch.dict(
            "os.environ",
            {"GP_ADMIN_USER_ID": "u", "GP_ADMIN_PASSWORD": "p"},
        ), patch("scripts.gp.gp_client.requests.get", return_value=mock_response):
            import importlib
            import scripts.gp.gp_client as gp_client  # noqa: PLC0415
            importlib.reload(gp_client)

            with pytest.raises(req.exceptions.HTTPError):
                gp_client.get_strings("fr")
