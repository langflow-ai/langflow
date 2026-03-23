"""Tests for deployment description column and deployment_type enum.

Covers:
- Model: Deployment and DeploymentRead require DeploymentType enum and accept description
- TypeDecorator: validates on write, coerces on read
- API responses: to_deployment_create_response surfaces persisted description
- Mapper: shape_deployment_update_result reads description from the DB row
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper
from langflow.api.v1.mappers.deployments.helpers import to_deployment_create_response
from langflow.services.database.models.deployment.model import Deployment, DeploymentRead, _DeploymentTypeColumn
from lfx.services.adapters.deployment.schema import DeploymentCreateResult, DeploymentType, DeploymentUpdateResult

# ---------------------------------------------------------------------------
# Model-level tests
# ---------------------------------------------------------------------------


class TestDeploymentModel:
    def test_deployment_accepts_deployment_type_enum(self):
        row = Deployment(
            resource_key="rk-1",
            user_id=uuid4(),
            project_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            name="test",
            deployment_type=DeploymentType.AGENT,
        )
        assert row.deployment_type == DeploymentType.AGENT
        assert row.deployment_type == "agent"

    def test_deployment_accepts_description(self):
        row = Deployment(
            resource_key="rk-1",
            user_id=uuid4(),
            project_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            name="test",
            deployment_type=DeploymentType.AGENT,
            description="A test deployment",
        )
        assert row.description == "A test deployment"

    def test_deployment_description_defaults_to_none(self):
        row = Deployment(
            resource_key="rk-1",
            user_id=uuid4(),
            project_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            name="test",
            deployment_type=DeploymentType.AGENT,
        )
        assert row.description is None

    def test_deployment_read_has_description_and_enum_type(self):
        now = datetime.now(UTC)
        read = DeploymentRead(
            id=uuid4(),
            resource_key="rk-1",
            user_id=uuid4(),
            project_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            name="test",
            description="read description",
            deployment_type=DeploymentType.AGENT,
            created_at=now,
            updated_at=now,
        )
        assert read.description == "read description"
        assert read.deployment_type == DeploymentType.AGENT

    def test_deployment_read_description_defaults_to_none(self):
        now = datetime.now(UTC)
        read = DeploymentRead(
            id=uuid4(),
            resource_key="rk-1",
            user_id=uuid4(),
            project_id=uuid4(),
            deployment_provider_account_id=uuid4(),
            name="test",
            deployment_type=DeploymentType.AGENT,
            created_at=now,
            updated_at=now,
        )
        assert read.description is None
        assert read.deployment_type == DeploymentType.AGENT


# ---------------------------------------------------------------------------
# TypeDecorator tests
# ---------------------------------------------------------------------------


class TestDeploymentTypeColumn:
    def test_rejects_none_on_bind(self):
        col = _DeploymentTypeColumn()
        with pytest.raises(ValueError, match="must not be None"):
            col.process_bind_param(None, None)

    def test_coerces_enum_to_string_on_bind(self):
        col = _DeploymentTypeColumn()
        assert col.process_bind_param(DeploymentType.AGENT, None) == "agent"

    def test_coerces_valid_string_on_bind(self):
        col = _DeploymentTypeColumn()
        assert col.process_bind_param("agent", None) == "agent"

    def test_rejects_invalid_string_on_bind(self):
        col = _DeploymentTypeColumn()
        with pytest.raises(ValueError, match="is not a valid"):
            col.process_bind_param("garbage", None)

    def test_returns_enum_on_result(self):
        col = _DeploymentTypeColumn()
        result = col.process_result_value("agent", None)
        assert result is DeploymentType.AGENT
        assert isinstance(result, DeploymentType)


# ---------------------------------------------------------------------------
# to_deployment_create_response tests
# ---------------------------------------------------------------------------


class TestCreateResponse:
    def test_surfaces_description_from_db_row(self):
        now = datetime.now(UTC)
        row = SimpleNamespace(
            id=uuid4(),
            name="deploy",
            description="my description",
            deployment_type=DeploymentType.AGENT,
            created_at=now,
            updated_at=now,
        )
        result = DeploymentCreateResult(id="prov-1")
        response = to_deployment_create_response(result, row)
        assert response.description == "my description"

    def test_description_none_when_not_set(self):
        now = datetime.now(UTC)
        row = SimpleNamespace(
            id=uuid4(),
            name="deploy",
            description=None,
            deployment_type=DeploymentType.AGENT,
            created_at=now,
            updated_at=now,
        )
        result = DeploymentCreateResult(id="prov-1")
        response = to_deployment_create_response(result, row)
        assert response.description is None

    def test_uses_enum_type_from_row(self):
        now = datetime.now(UTC)
        row = SimpleNamespace(
            id=uuid4(),
            name="deploy",
            description=None,
            deployment_type=DeploymentType.AGENT,
            created_at=now,
            updated_at=now,
        )
        result = DeploymentCreateResult(id="prov-1")
        response = to_deployment_create_response(result, row)
        assert response.type == DeploymentType.AGENT


# ---------------------------------------------------------------------------
# Mapper: shape_deployment_update_result tests
# ---------------------------------------------------------------------------


class TestMapperUpdateResult:
    def test_reads_description_from_row(self):
        mapper = BaseDeploymentMapper()
        now = datetime.now(UTC)
        row = SimpleNamespace(
            id=uuid4(),
            name="deploy",
            description="persisted desc",
            deployment_type=DeploymentType.AGENT,
            created_at=now,
            updated_at=now,
        )
        result = DeploymentUpdateResult(id="prov-1", provider_result={"ok": True})
        shaped = mapper.shape_deployment_update_result(result, row)
        assert shaped.description == "persisted desc"
        assert shaped.type == DeploymentType.AGENT

    def test_description_none_from_row(self):
        mapper = BaseDeploymentMapper()
        now = datetime.now(UTC)
        row = SimpleNamespace(
            id=uuid4(),
            name="deploy",
            description=None,
            deployment_type=DeploymentType.AGENT,
            created_at=now,
            updated_at=now,
        )
        result = DeploymentUpdateResult(id="prov-1")
        shaped = mapper.shape_deployment_update_result(result, row)
        assert shaped.description is None

    def test_no_description_kwarg_needed(self):
        """Signature no longer accepts a description keyword argument."""
        mapper = BaseDeploymentMapper()
        import inspect

        sig = inspect.signature(mapper.shape_deployment_update_result)
        param_names = list(sig.parameters.keys())
        assert "description" not in param_names
