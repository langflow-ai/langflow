"""Tests for masking of MCP auth_settings ciphertext in folder response schemas.

`FolderRead` / `FolderReadWithFlows` are returned by `/api/v1/projects/`
and `/api/v1/projects/{id}`. They must not leak the encrypted
`oauth_client_secret` / `api_key` blobs to clients — even as ciphertext —
because the listing endpoint returns globally-shared folders to every
authenticated user, and shipping secret material off the server is a
defense-in-depth failure on its own.
"""

from __future__ import annotations

from uuid import UUID

from langflow.services.database.models.folder.model import (
    Folder,
    FolderRead,
    FolderReadWithFlows,
    _mask_auth_settings,
)

_FOLDER_ID = UUID("00000000-0000-0000-0000-000000000001")
_CIPHER_OAUTH = "gAAAAABoauth-ciphertext-blob-XXXX"  # pragma: allowlist secret
_CIPHER_APIKEY = "gAAAAABapikey-ciphertext-blob-XXXX"  # pragma: allowlist secret
_MASK = "*******"


class TestMaskAuthSettingsHelper:
    def test_none_passthrough(self):
        assert _mask_auth_settings(None) is None

    def test_empty_dict_passthrough(self):
        assert _mask_auth_settings({}) == {}

    def test_masks_oauth_client_secret(self):
        result = _mask_auth_settings({"auth_type": "oauth", "oauth_client_secret": _CIPHER_OAUTH})
        assert result == {"auth_type": "oauth", "oauth_client_secret": _MASK}

    def test_masks_api_key(self):
        result = _mask_auth_settings({"auth_type": "apikey", "api_key": _CIPHER_APIKEY})
        assert result == {"auth_type": "apikey", "api_key": _MASK}

    def test_preserves_non_secret_fields(self):
        result = _mask_auth_settings(
            {
                "auth_type": "oauth",
                "oauth_client_id": "public-client-id",
                "oauth_client_secret": _CIPHER_OAUTH,
                "oauth_server_url": "https://oauth.example.com",
            }
        )
        assert result["oauth_client_id"] == "public-client-id"
        assert result["oauth_server_url"] == "https://oauth.example.com"
        assert result["oauth_client_secret"] == _MASK

    def test_does_not_mutate_input(self):
        original = {"auth_type": "apikey", "api_key": _CIPHER_APIKEY}
        _mask_auth_settings(original)
        assert original == {"auth_type": "apikey", "api_key": _CIPHER_APIKEY}

    def test_empty_secret_value_is_left_alone(self):
        # Empty string is falsy, so we don't replace it with a mask.
        result = _mask_auth_settings({"auth_type": "apikey", "api_key": ""})
        assert result == {"auth_type": "apikey", "api_key": ""}


class TestFolderReadSerializer:
    def _make(self, **overrides):
        kwargs = {
            "id": _FOLDER_ID,
            "parent_id": None,
            "name": "Project",
            "description": "desc",
        }
        kwargs.update(overrides)
        return FolderRead(**kwargs)

    def test_masks_both_secret_fields_when_present(self):
        folder = self._make(
            auth_settings={
                "auth_type": "oauth",
                "oauth_client_id": "id-public",
                "oauth_client_secret": _CIPHER_OAUTH,
                "api_key": _CIPHER_APIKEY,
            }
        )
        dumped = folder.model_dump()
        assert dumped["auth_settings"]["oauth_client_secret"] == _MASK
        assert dumped["auth_settings"]["api_key"] == _MASK
        assert dumped["auth_settings"]["oauth_client_id"] == "id-public"

    def test_none_auth_settings_serializes_as_none(self):
        folder = self._make(auth_settings=None)
        assert folder.model_dump()["auth_settings"] is None

    def test_secrets_masked_in_json_output(self):
        folder = self._make(
            auth_settings={
                "auth_type": "apikey",
                "api_key": _CIPHER_APIKEY,
            }
        )
        # `model_dump_json` is the path FastAPI takes for response bodies.
        payload = folder.model_dump_json()
        assert _CIPHER_APIKEY not in payload
        assert _MASK in payload


class TestFolderReadWithFlowsSerializer:
    def test_masks_secrets(self):
        folder = FolderReadWithFlows(
            id=_FOLDER_ID,
            parent_id=None,
            name="Project",
            description="desc",
            auth_settings={
                "auth_type": "oauth",
                "oauth_client_secret": _CIPHER_OAUTH,
            },
            flows=[],
        )
        dumped = folder.model_dump()
        assert dumped["auth_settings"]["oauth_client_secret"] == _MASK
        assert dumped["flows"] == []


class TestFolderOrmModelUnaffected:
    """ORM model must keep raw ciphertext, only response schemas mask.

    The encrypt/decrypt code paths read `Folder.auth_settings` as a dict via
    attribute access. We must not mask values when the table model is dumped,
    or those code paths break. Only the response schemas should mask.
    """

    def test_orm_folder_dump_keeps_ciphertext(self):
        folder = Folder(
            name="Project",
            description="desc",
            auth_settings={
                "auth_type": "oauth",
                "oauth_client_secret": _CIPHER_OAUTH,
                "api_key": _CIPHER_APIKEY,
            },
        )
        dumped = folder.model_dump()
        assert dumped["auth_settings"]["oauth_client_secret"] == _CIPHER_OAUTH
        assert dumped["auth_settings"]["api_key"] == _CIPHER_APIKEY

    def test_attribute_access_returns_real_dict(self):
        folder = Folder(
            name="Project",
            description="desc",
            auth_settings={
                "auth_type": "apikey",
                "api_key": _CIPHER_APIKEY,
            },
        )
        # `auth_helpers.handle_auth_settings_update` and friends rely on this:
        # `existing_project.auth_settings.get("auth_type")`,
        # `existing_project.auth_settings.copy()`, etc.
        assert folder.auth_settings is not None
        assert folder.auth_settings["api_key"] == _CIPHER_APIKEY
        assert folder.auth_settings.get("auth_type") == "apikey"
