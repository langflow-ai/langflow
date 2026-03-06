from unittest.mock import MagicMock

import pytest
from langflow.services.database.models.deployment.model import Deployment, DeploymentCreate, DeploymentRead


class TestDeploymentValidation:
    """Tests for Deployment model field validators."""

    def _make_info(self, field_name: str) -> MagicMock:
        info = MagicMock()
        info.field_name = field_name
        return info

    def test_rejects_empty_name(self):
        with pytest.raises(ValueError, match="name must not be empty"):
            Deployment.validate_non_empty("", self._make_info("name"))

    def test_rejects_whitespace_name(self):
        with pytest.raises(ValueError, match="name must not be empty"):
            Deployment.validate_non_empty("   ", self._make_info("name"))

    def test_rejects_empty_resource_key(self):
        with pytest.raises(ValueError, match="resource_key must not be empty"):
            Deployment.validate_non_empty("", self._make_info("resource_key"))

    def test_rejects_whitespace_resource_key(self):
        with pytest.raises(ValueError, match="resource_key must not be empty"):
            Deployment.validate_non_empty("   ", self._make_info("resource_key"))

    def test_strips_whitespace_from_name(self):
        result = Deployment.validate_non_empty("  hello  ", self._make_info("name"))
        assert result == "hello"

    def test_strips_whitespace_from_resource_key(self):
        result = Deployment.validate_non_empty("  rk-1  ", self._make_info("resource_key"))
        assert result == "rk-1"


class TestDeploymentRead:
    """Tests for DeploymentRead schema."""

    def test_has_expected_fields(self):
        expected = {
            "id",
            "resource_key",
            "user_id",
            "project_id",
            "deployment_provider_account_id",
            "name",
            "created_at",
            "updated_at",
        }
        assert set(DeploymentRead.model_fields.keys()) == expected


class TestDeploymentCreate:
    """Tests for DeploymentCreate schema."""

    def test_rejects_empty_name(self):
        from uuid import uuid4

        with pytest.raises(ValueError, match="name must not be empty"):
            DeploymentCreate(
                resource_key="rk-1",
                deployment_provider_account_id=uuid4(),
                project_id=uuid4(),
                name="",
            )

    def test_rejects_empty_resource_key(self):
        from uuid import uuid4

        with pytest.raises(ValueError, match="resource_key must not be empty"):
            DeploymentCreate(
                resource_key="   ",
                deployment_provider_account_id=uuid4(),
                project_id=uuid4(),
                name="my-deploy",
            )

    def test_valid_create(self):
        from uuid import uuid4

        obj = DeploymentCreate(
            resource_key="rk-1",
            deployment_provider_account_id=uuid4(),
            project_id=uuid4(),
            name="my-deploy",
        )
        assert obj.name == "my-deploy"
        assert obj.resource_key == "rk-1"

    def test_has_expected_fields(self):
        expected = {
            "resource_key",
            "deployment_provider_account_id",
            "project_id",
            "name",
        }
        assert set(DeploymentCreate.model_fields.keys()) == expected
