"""Unit tests for the detect_env_vars endpoint (POST /variables/detections)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langflow.api.v1.schemas.deployments import DetectVarsRequest
from langflow.api.v1.variable import _derive_env_var_name, detect_env_vars
from langflow.services.database.models.flow_version.exceptions import FlowVersionNotFoundError

MODULE = "langflow.api.v1.variable"


def _flow_version_with_data(data: dict) -> SimpleNamespace:
    return SimpleNamespace(data=data)


def _node(template: dict) -> dict:
    return {"data": {"node": {"template": template}}}


# ---------------------------------------------------------------------------
# _derive_env_var_name
# ---------------------------------------------------------------------------


class TestDeriveEnvVarName:
    def test_falls_back_to_uppercased_field_key(self):
        assert _derive_env_var_name("api_key", {}) == "API_KEY"

    def test_uses_category_from_model_field_when_value_is_list(self):
        template = {"model": {"value": [{"category": "OpenAI"}]}}
        assert _derive_env_var_name("api_key", template) == "OPENAI_API_KEY"

    def test_uses_category_from_json_encoded_model_value(self):
        template = {"model": {"value": json.dumps([{"category": "Anthropic"}])}}
        assert _derive_env_var_name("api_key", template) == "ANTHROPIC_API_KEY"

    def test_normalizes_spaces_and_hyphens_in_category(self):
        template = {"model": {"value": [{"category": "My-Custom Provider"}]}}
        assert _derive_env_var_name("secret", template) == "MY_CUSTOM_PROVIDER_SECRET"

    def test_ignores_empty_category(self):
        template = {"model": {"value": [{"category": ""}]}}
        assert _derive_env_var_name("token", template) == "TOKEN"

    def test_ignores_non_dict_model_field(self):
        assert _derive_env_var_name("key", {"model": "not-a-dict"}) == "KEY"

    def test_ignores_malformed_json_in_model_value(self):
        template = {"model": {"value": "{not valid json"}}
        assert _derive_env_var_name("key", template) == "KEY"


# ---------------------------------------------------------------------------
# detect_env_vars endpoint
# ---------------------------------------------------------------------------


class TestDetectEnvVars:
    @pytest.mark.asyncio
    async def test_returns_global_variable_refs(self):
        fv_id = uuid4()
        version = _flow_version_with_data(
            {
                "nodes": [
                    _node(
                        {
                            "api_key": {
                                "load_from_db": True,
                                "value": "MY_OPENAI_KEY",
                            }
                        }
                    )
                ]
            }
        )
        with patch(f"{MODULE}.get_flow_version_entry_or_raise", new_callable=AsyncMock, return_value=version):
            result = await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv_id]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )
        assert len(result.variables) == 1
        assert result.variables[0].key == "MY_OPENAI_KEY"
        assert result.variables[0].global_variable_name == "MY_OPENAI_KEY"

    @pytest.mark.asyncio
    async def test_returns_password_field_suggestions(self):
        fv_id = uuid4()
        version = _flow_version_with_data({"nodes": [_node({"api_key": {"password": True}})]})
        with patch(f"{MODULE}.get_flow_version_entry_or_raise", new_callable=AsyncMock, return_value=version):
            result = await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv_id]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )
        assert len(result.variables) == 1
        assert result.variables[0].key == "API_KEY"
        assert result.variables[0].global_variable_name is None

    @pytest.mark.asyncio
    async def test_global_var_takes_precedence_over_password(self):
        """Global var takes precedence over password suggestion.

        When the same key appears as both a global var ref and a password
        suggestion, only the global var entry is returned.
        """
        fv_id = uuid4()
        version = _flow_version_with_data(
            {
                "nodes": [
                    _node(
                        {
                            "api_key": {"load_from_db": True, "value": "API_KEY"},
                            "other_key": {"password": True},
                        }
                    ),
                    _node({"api_key": {"password": True}}),
                ]
            }
        )
        with patch(f"{MODULE}.get_flow_version_entry_or_raise", new_callable=AsyncMock, return_value=version):
            result = await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv_id]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )
        keys = {v.key for v in result.variables}
        assert "API_KEY" in keys
        api_key_var = next(v for v in result.variables if v.key == "API_KEY")
        assert api_key_var.global_variable_name == "API_KEY"

    @pytest.mark.asyncio
    async def test_deduplicates_across_versions(self):
        fv1, fv2 = uuid4(), uuid4()
        version1 = _flow_version_with_data({"nodes": [_node({"api_key": {"load_from_db": True, "value": "MY_KEY"}})]})
        version2 = _flow_version_with_data({"nodes": [_node({"api_key": {"load_from_db": True, "value": "MY_KEY"}})]})

        async def mock_get(session, *, version_id, user_id):  # noqa: ARG001
            return version1 if version_id == fv1 else version2

        with patch(f"{MODULE}.get_flow_version_entry_or_raise", side_effect=mock_get):
            result = await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv1, fv2]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )
        assert len(result.variables) == 1

    @pytest.mark.asyncio
    async def test_skips_missing_flow_versions(self):
        fv_id = uuid4()

        async def mock_get(session, *, version_id, user_id):  # noqa: ARG001
            raise FlowVersionNotFoundError(version_id)

        with patch(f"{MODULE}.get_flow_version_entry_or_raise", side_effect=mock_get):
            result = await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv_id]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )
        assert result.variables == []

    @pytest.mark.asyncio
    async def test_handles_non_dict_data(self):
        fv_id = uuid4()
        version = _flow_version_with_data(None)
        with patch(f"{MODULE}.get_flow_version_entry_or_raise", new_callable=AsyncMock, return_value=version):
            result = await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv_id]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )
        assert result.variables == []

    @pytest.mark.asyncio
    async def test_empty_flow_version_ids(self):
        result = await detect_env_vars(
            payload=DetectVarsRequest(flow_version_ids=[]),
            session=AsyncMock(),
            current_user=SimpleNamespace(id=uuid4()),
        )
        assert result.variables == []

    @pytest.mark.asyncio
    async def test_password_with_model_category(self):
        fv_id = uuid4()
        version = _flow_version_with_data(
            {
                "nodes": [
                    _node(
                        {
                            "api_key": {"password": True},
                            "model": {"value": [{"category": "OpenAI"}]},
                        }
                    )
                ]
            }
        )
        with patch(f"{MODULE}.get_flow_version_entry_or_raise", new_callable=AsyncMock, return_value=version):
            result = await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv_id]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )
        assert len(result.variables) == 1
        assert result.variables[0].key == "OPENAI_API_KEY"
        assert result.variables[0].global_variable_name is None
