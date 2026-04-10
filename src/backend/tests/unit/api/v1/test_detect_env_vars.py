"""Unit tests for the detect_env_vars endpoint (POST /variables/detections)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1.schemas.deployments import DetectVarsRequest
from langflow.api.v1.variable import detect_env_vars
from langflow.services.database.models.flow_version.exceptions import FlowVersionNotFoundError
from pydantic import ValidationError

MODULE = "langflow.api.v1.variable"


def _flow_version_with_data(data: dict) -> SimpleNamespace:
    return SimpleNamespace(data=data)


def _node(template: dict) -> dict:
    return {"data": {"node": {"template": template}}}


def _variable_service_with_names(names: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(list_variables=AsyncMock(return_value=names or []))


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
        with (
            patch(f"{MODULE}.get_flow_version_entry_or_raise", new_callable=AsyncMock, return_value=version),
            patch(
                f"{MODULE}.get_variable_service",
                return_value=_variable_service_with_names(["MY_OPENAI_KEY"]),
            ),
        ):
            result = await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv_id]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )
        assert result.variables == ["MY_OPENAI_KEY"]

    @pytest.mark.asyncio
    async def test_ignores_password_only_fields(self):
        fv_id = uuid4()
        version = _flow_version_with_data({"nodes": [_node({"api_key": {"password": True}})]})
        with (
            patch(f"{MODULE}.get_flow_version_entry_or_raise", new_callable=AsyncMock, return_value=version),
            patch(
                f"{MODULE}.get_variable_service",
                return_value=_variable_service_with_names(["API_KEY"]),
            ),
        ):
            result = await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv_id]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )
        assert result.variables == []

    @pytest.mark.asyncio
    async def test_load_from_db_is_used_even_when_password_fields_exist(self):
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
        with (
            patch(f"{MODULE}.get_flow_version_entry_or_raise", new_callable=AsyncMock, return_value=version),
            patch(
                f"{MODULE}.get_variable_service",
                return_value=_variable_service_with_names(["API_KEY"]),
            ),
        ):
            result = await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv_id]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )
        assert result.variables == ["API_KEY"]

    @pytest.mark.asyncio
    async def test_deduplicates_across_versions(self):
        fv1, fv2 = uuid4(), uuid4()
        version1 = _flow_version_with_data({"nodes": [_node({"api_key": {"load_from_db": True, "value": "MY_KEY"}})]})
        version2 = _flow_version_with_data({"nodes": [_node({"api_key": {"load_from_db": True, "value": "MY_KEY"}})]})

        async def mock_get(session, *, version_id, user_id):  # noqa: ARG001
            return version1 if version_id == fv1 else version2

        with (
            patch(f"{MODULE}.get_flow_version_entry_or_raise", side_effect=mock_get),
            patch(
                f"{MODULE}.get_variable_service",
                return_value=_variable_service_with_names(["MY_KEY"]),
            ),
        ):
            result = await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv1, fv2]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )
        assert result.variables == ["MY_KEY"]

    @pytest.mark.asyncio
    async def test_fails_fast_for_missing_flow_versions(self):
        fv_id = uuid4()

        async def mock_get(session, *, version_id, user_id):  # noqa: ARG001
            raise FlowVersionNotFoundError(version_id)

        with (
            patch(f"{MODULE}.get_flow_version_entry_or_raise", side_effect=mock_get),
            patch(
                f"{MODULE}.get_variable_service",
                return_value=_variable_service_with_names(["ANY_KEY"]),
            ),
            pytest.raises(HTTPException, match=f"Flow version {fv_id} not found"),
        ):
            await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv_id]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )

    @pytest.mark.asyncio
    async def test_fails_fast_for_non_dict_data(self):
        fv_id = uuid4()
        version = _flow_version_with_data(None)
        with (
            patch(f"{MODULE}.get_flow_version_entry_or_raise", new_callable=AsyncMock, return_value=version),
            patch(
                f"{MODULE}.get_variable_service",
                return_value=_variable_service_with_names(["ANY_KEY"]),
            ),
            pytest.raises(
                HTTPException,
                match=(
                    f"Flow version {fv_id} data must be a JSON object with a 'nodes' list containing node templates."
                ),
            ),
        ):
            await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv_id]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )

    @pytest.mark.asyncio
    async def test_rejects_empty_flow_version_ids(self):
        with pytest.raises(ValidationError):
            DetectVarsRequest(flow_version_ids=[])

    @pytest.mark.asyncio
    async def test_filters_out_non_existing_variable_names(self):
        fv_id = uuid4()
        version = _flow_version_with_data(
            {
                "nodes": [
                    _node(
                        {
                            "api_key": {"load_from_db": True, "value": "sk-live-secret"},
                            "other_key": {"password": True},
                        }
                    )
                ]
            }
        )
        with (
            patch(f"{MODULE}.get_flow_version_entry_or_raise", new_callable=AsyncMock, return_value=version),
            patch(
                f"{MODULE}.get_variable_service",
                return_value=_variable_service_with_names([]),
            ),
        ):
            result = await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv_id]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )

        assert result.variables == []
