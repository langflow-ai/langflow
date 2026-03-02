"""Tests for deployment exception hierarchy, metadata, and service instantiation."""

import pytest
from lfx.services.deployment import DeploymentService
from lfx.services.deployment.exceptions import (
    AuthenticationError,
    AuthSchemeError,
    CredentialResolutionError,
    DeploymentConflictError,
    DeploymentError,
    DeploymentNotFoundError,
    DeploymentSupportError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
)


def test_exception_hierarchy_is_preserved() -> None:
    assert issubclass(AuthenticationError, DeploymentError)
    assert issubclass(CredentialResolutionError, AuthenticationError)
    assert issubclass(AuthSchemeError, AuthenticationError)
    assert issubclass(DeploymentConflictError, DeploymentError)
    assert issubclass(InvalidContentError, DeploymentError)
    assert issubclass(InvalidDeploymentOperationError, DeploymentError)


def test_exception_error_codes_are_set() -> None:
    assert CredentialResolutionError().error_code == "credentials_resolution_error"
    assert DeploymentConflictError().error_code == "deployment_conflict"
    assert DeploymentSupportError().error_code == "unsupported_deployment_type"
    assert InvalidDeploymentTypeError().error_code == "invalid_deployment_type"
    assert InvalidContentError().error_code == "unprocessable_content_error"
    assert InvalidDeploymentOperationError().error_code == "invalid_deployment_operation"
    assert AuthSchemeError().error_code == "unsupported_auth_type"


def test_deployment_type_exceptions_have_distinct_default_messages() -> None:
    assert str(DeploymentSupportError()) == "Deployment type is unsupported by this adapter"
    assert str(InvalidDeploymentTypeError()) == "Deployment type is malformed or unknown"


def test_deployment_not_found_includes_context_when_id_is_provided() -> None:
    err = DeploymentNotFoundError(deployment_id="dep_1")
    assert str(err) == "Deployment not found: dep_1"
    assert err.error_code == "deployment_not_found"


def test_base_error_supports_cause_chaining() -> None:
    root = ValueError("boom")
    err = DeploymentError("failed", error_code="deployment_error", cause=root)
    assert err.cause is root
    assert err.__cause__ is root


def test_deployment_service_is_instantiable_and_ready() -> None:
    svc = DeploymentService()
    assert svc.ready is True
    assert svc.name == "deployment_service"


async def test_deployment_service_stub_methods_raise() -> None:
    svc = DeploymentService()
    with pytest.raises(NotImplementedError):
        await svc.create(user_id="u1", payload=None, db=None)


async def test_deployment_service_teardown_is_noop() -> None:
    svc = DeploymentService()
    await svc.teardown()
