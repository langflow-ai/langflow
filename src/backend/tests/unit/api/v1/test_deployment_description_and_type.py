"""Tests for deployment description column and deployment_type enum.

Covers:
- Model: Deployment and DeploymentRead require DeploymentType enum and accept description
- API responses: shape_deployment_create_result surfaces persisted description
- Mapper: shape_deployment_update_result reads description from the DB row
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.api.v1.mappers.deployments.base import BaseDeploymentMapper
from langflow.services.database.models.deployment.model import Deployment, DeploymentRead
from lfx.services.adapters.deployment.schema import (
    DEPLOYMENT_DESCRIPTION_MAX_LENGTH,
    BaseDeploymentData,
    BaseDeploymentDataUpdate,
    DeploymentCreateResult,
    DeploymentType,
    DeploymentUpdateResult,
)
from pydantic import ValidationError

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
        now = datetime.now(timezone.utc)
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
        now = datetime.now(timezone.utc)
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


class TestAdapterDescriptionValidation:
    def test_create_payload_rejects_description_over_max_length(self):
        with pytest.raises(ValidationError, match="at most"):
            BaseDeploymentData(
                name="test",
                description="x" * (DEPLOYMENT_DESCRIPTION_MAX_LENGTH + 1),
                type=DeploymentType.AGENT,
            )

    def test_update_payload_rejects_description_over_max_length(self):
        with pytest.raises(ValidationError, match="at most"):
            BaseDeploymentDataUpdate(description="x" * (DEPLOYMENT_DESCRIPTION_MAX_LENGTH + 1))


# ---------------------------------------------------------------------------
# shape_deployment_create_result tests
# ---------------------------------------------------------------------------


class TestCreateResponse:
    def test_surfaces_description_from_db_row(self):
        mapper = BaseDeploymentMapper()
        now = datetime.now(timezone.utc)
        provider_account_id = uuid4()
        row = SimpleNamespace(
            id=uuid4(),
            resource_key="rk-1",
            deployment_provider_account_id=provider_account_id,
            name="deploy",
            description="my description",
            deployment_type=DeploymentType.AGENT,
            created_at=now,
            updated_at=now,
        )
        result = DeploymentCreateResult(id="prov-1")
        response = mapper.shape_deployment_create_result(result, row, provider_key="test-provider")
        assert response.description == "my description"
        assert response.provider_id == provider_account_id
        assert response.provider_key == "test-provider"

    def test_description_none_when_not_set(self):
        mapper = BaseDeploymentMapper()
        now = datetime.now(timezone.utc)
        provider_account_id = uuid4()
        row = SimpleNamespace(
            id=uuid4(),
            resource_key="rk-1",
            deployment_provider_account_id=provider_account_id,
            name="deploy",
            description=None,
            deployment_type=DeploymentType.AGENT,
            created_at=now,
            updated_at=now,
        )
        result = DeploymentCreateResult(id="prov-1")
        response = mapper.shape_deployment_create_result(result, row, provider_key="test-provider")
        assert response.description is None
        assert response.provider_id == provider_account_id
        assert response.provider_key == "test-provider"

    def test_uses_enum_type_from_row(self):
        mapper = BaseDeploymentMapper()
        now = datetime.now(timezone.utc)
        provider_account_id = uuid4()
        row = SimpleNamespace(
            id=uuid4(),
            resource_key="rk-1",
            deployment_provider_account_id=provider_account_id,
            name="deploy",
            description=None,
            deployment_type=DeploymentType.AGENT,
            created_at=now,
            updated_at=now,
        )
        result = DeploymentCreateResult(id="prov-1")
        response = mapper.shape_deployment_create_result(result, row, provider_key="test-provider")
        assert response.type == DeploymentType.AGENT
        assert response.provider_id == provider_account_id
        assert response.provider_key == "test-provider"


# ---------------------------------------------------------------------------
# Mapper: shape_deployment_update_result tests
# ---------------------------------------------------------------------------


class TestMapperUpdateResult:
    def test_reads_description_from_row(self):
        mapper = BaseDeploymentMapper()
        now = datetime.now(timezone.utc)
        provider_account_id = uuid4()
        row = SimpleNamespace(
            id=uuid4(),
            resource_key="rk-1",
            deployment_provider_account_id=provider_account_id,
            name="deploy",
            description="persisted desc",
            deployment_type=DeploymentType.AGENT,
            created_at=now,
            updated_at=now,
        )
        result = DeploymentUpdateResult(id="prov-1", provider_result={"ok": True})
        shaped = mapper.shape_deployment_update_result(result, row, provider_key="test-provider")
        assert shaped.description == "persisted desc"
        assert shaped.type == DeploymentType.AGENT
        assert shaped.provider_id == provider_account_id
        assert shaped.provider_key == "test-provider"

    def test_description_none_from_row(self):
        mapper = BaseDeploymentMapper()
        now = datetime.now(timezone.utc)
        provider_account_id = uuid4()
        row = SimpleNamespace(
            id=uuid4(),
            resource_key="rk-1",
            deployment_provider_account_id=provider_account_id,
            name="deploy",
            description=None,
            deployment_type=DeploymentType.AGENT,
            created_at=now,
            updated_at=now,
        )
        result = DeploymentUpdateResult(id="prov-1")
        shaped = mapper.shape_deployment_update_result(result, row, provider_key="test-provider")
        assert shaped.description is None
        assert shaped.provider_id == provider_account_id
        assert shaped.provider_key == "test-provider"

    def test_no_description_kwarg_needed(self):
        """Signature no longer accepts a description keyword argument."""
        mapper = BaseDeploymentMapper()
        import inspect

        sig = inspect.signature(mapper.shape_deployment_update_result)
        param_names = list(sig.parameters.keys())
        assert "description" not in param_names
