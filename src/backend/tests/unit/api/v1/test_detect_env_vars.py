"""Unit tests for the detect_env_vars endpoint (POST /variables/detections)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1.schemas.deployments import DetectVarsRequest
from langflow.api.v1.variable import detect_env_vars
from pydantic import ValidationError

MODULE = "langflow.api.v1.variable"


def _flow_version_with_data(data: object) -> SimpleNamespace:
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
            patch(
                f"{MODULE}.get_flow_version_entries_by_ids",
                new_callable=AsyncMock,
                return_value={fv_id: version},
            ),
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
            patch(
                f"{MODULE}.get_flow_version_entries_by_ids",
                new_callable=AsyncMock,
                return_value={fv_id: version},
            ),
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
            patch(
                f"{MODULE}.get_flow_version_entries_by_ids",
                new_callable=AsyncMock,
                return_value={fv_id: version},
            ),
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

        with (
            patch(
                f"{MODULE}.get_flow_version_entries_by_ids",
                new_callable=AsyncMock,
                return_value={fv1: version1, fv2: version2},
            ),
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

        with (
            patch(
                f"{MODULE}.get_flow_version_entries_by_ids",
                new_callable=AsyncMock,
                return_value={},
            ),
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
            patch(
                f"{MODULE}.get_flow_version_entries_by_ids",
                new_callable=AsyncMock,
                return_value={fv_id: version},
            ),
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
    async def test_fails_fast_for_missing_nodes_list(self):
        fv_id = uuid4()
        version = _flow_version_with_data({})
        with (
            patch(
                f"{MODULE}.get_flow_version_entries_by_ids",
                new_callable=AsyncMock,
                return_value={fv_id: version},
            ),
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
    async def test_fails_fast_for_non_list_nodes(self):
        fv_id = uuid4()
        version = _flow_version_with_data({"nodes": {"template": {}}})
        with (
            patch(
                f"{MODULE}.get_flow_version_entries_by_ids",
                new_callable=AsyncMock,
                return_value={fv_id: version},
            ),
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
    async def test_deduplicates_flow_version_ids_in_request(self):
        flow_version_id = uuid4()
        request = DetectVarsRequest(flow_version_ids=[flow_version_id, flow_version_id])
        assert request.flow_version_ids == [flow_version_id]

    @pytest.mark.asyncio
    async def test_rejects_more_than_50_flow_version_ids(self):
        with pytest.raises(ValidationError):
            DetectVarsRequest(flow_version_ids=[uuid4() for _ in range(51)])

    @pytest.mark.asyncio
    async def test_strips_whitespace_from_detected_variable_name(self):
        fv_id = uuid4()
        version = _flow_version_with_data(
            {
                "nodes": [
                    _node(
                        {
                            "api_key": {
                                "load_from_db": True,
                                "value": "  MY_OPENAI_KEY  ",
                            }
                        }
                    )
                ]
            }
        )
        with (
            patch(
                f"{MODULE}.get_flow_version_entries_by_ids",
                new_callable=AsyncMock,
                return_value={fv_id: version},
            ),
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
    async def test_ignores_non_string_and_blank_variable_values(self):
        fv_id = uuid4()
        version = _flow_version_with_data(
            {
                "nodes": [
                    _node(
                        {
                            "null_value": {"load_from_db": True, "value": None},
                            "int_value": {"load_from_db": True, "value": 123},
                            "blank_value": {"load_from_db": True, "value": "   "},
                            "valid_value": {"load_from_db": True, "value": "VALID_KEY"},
                        }
                    )
                ]
            }
        )
        with (
            patch(
                f"{MODULE}.get_flow_version_entries_by_ids",
                new_callable=AsyncMock,
                return_value={fv_id: version},
            ),
            patch(
                f"{MODULE}.get_variable_service",
                return_value=_variable_service_with_names(["VALID_KEY"]),
            ),
        ):
            result = await detect_env_vars(
                payload=DetectVarsRequest(flow_version_ids=[fv_id]),
                session=AsyncMock(),
                current_user=SimpleNamespace(id=uuid4()),
            )
        assert result.variables == ["VALID_KEY"]

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
            patch(
                f"{MODULE}.get_flow_version_entries_by_ids",
                new_callable=AsyncMock,
                return_value={fv_id: version},
            ),
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
