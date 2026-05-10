"""Tests for masking of MCP auth_settings ciphertext in folder response schemas.

`FolderRead` / `FolderReadWithFlows` are returned by `/api/v1/projects/`
and `/api/v1/projects/{id}`. They must not leak the encrypted
`oauth_client_secret` / `api_key` blobs to clients — even as ciphertext —
because the listing endpoint returns globally-shared folders to every
authenticated user, and shipping secret material off the server is a
defense-in-depth failure on its own.

Helper-level coverage of `mask_auth_settings` lives in
`tests/unit/services/auth/test_mcp_encryption_mask.py`.
"""

from __future__ import annotations

from uuid import UUID

from langflow.services.auth.mcp_encryption import SENSITIVE_FIELD_MASK
from langflow.services.database.models.folder.model import (
    Folder,
    FolderRead,
    FolderReadWithFlows,
)

_FOLDER_ID = UUID("00000000-0000-0000-0000-000000000001")
_CIPHER_OAUTH = "gAAAAABoauth-ciphertext-blob-XXXX"  # pragma: allowlist secret
_CIPHER_APIKEY = "gAAAAABapikey-ciphertext-blob-XXXX"  # pragma: allowlist secret


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
        assert dumped["auth_settings"]["oauth_client_secret"] == SENSITIVE_FIELD_MASK
        assert dumped["auth_settings"]["api_key"] == SENSITIVE_FIELD_MASK
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
        assert SENSITIVE_FIELD_MASK in payload


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
        assert dumped["auth_settings"]["oauth_client_secret"] == SENSITIVE_FIELD_MASK
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
