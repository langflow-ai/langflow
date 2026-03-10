"""Tests for deployment exception hierarchy, metadata, and service instantiation."""

import pytest
from lfx.services.adapters.deployment import (
    BaseDeploymentService,
    DeploymentError,
    DeploymentNotConfiguredError,
    DeploymentService,
    DeploymentServiceError,
)
from lfx.services.adapters.deployment.exceptions import (
    AuthenticationError,
    AuthSchemeError,
    CredentialResolutionError,
    DeploymentConflictError,
    DeploymentNotFoundError,
    DeploymentSupportError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
)
from lfx.services.interfaces import DeploymentServiceProtocol


def test_exception_hierarchy_is_preserved() -> None:
    # DeploymentServiceError is the common root
    assert issubclass(DeploymentError, DeploymentServiceError)
    assert issubclass(AuthenticationError, DeploymentServiceError)

    # AuthenticationError is a sibling of DeploymentError, NOT a child
    assert not issubclass(AuthenticationError, DeploymentError)
    assert not issubclass(DeploymentError, AuthenticationError)

    # Auth subtypes
    assert issubclass(CredentialResolutionError, AuthenticationError)
    assert issubclass(AuthSchemeError, AuthenticationError)

    # Deployment operation subtypes
    assert issubclass(DeploymentConflictError, DeploymentError)
    assert issubclass(InvalidContentError, DeploymentError)
    assert issubclass(InvalidDeploymentOperationError, DeploymentError)
    assert issubclass(DeploymentNotConfiguredError, DeploymentError)


def test_exception_error_codes_are_set() -> None:
    assert CredentialResolutionError().error_code == "credentials_resolution_error"
    assert DeploymentConflictError().error_code == "deployment_conflict"
    assert DeploymentSupportError().error_code == "unsupported_deployment_type"
    assert InvalidDeploymentTypeError().error_code == "invalid_deployment_type"
    assert InvalidContentError().error_code == "unprocessable_content_error"
    assert InvalidDeploymentOperationError().error_code == "invalid_deployment_operation"
    assert AuthSchemeError().error_code == "unsupported_auth_type"
    assert DeploymentNotConfiguredError().error_code == "deployment_not_configured"


def test_deployment_type_exceptions_have_distinct_default_messages() -> None:
    assert str(DeploymentSupportError()) == "Deployment type is unsupported by this adapter"
    assert str(InvalidDeploymentTypeError()) == "Deployment type is malformed or unknown"


def test_deployment_not_found_includes_context_when_id_is_provided() -> None:
    err = DeploymentNotFoundError(deployment_id="dep_1")
    assert str(err) == "Deployment not found: dep_1"
    assert err.error_code == "deployment_not_found"
    assert err.deployment_id == "dep_1"


def test_deployment_not_found_default_message() -> None:
    err = DeploymentNotFoundError()
    assert str(err) == "Deployment not found"
    assert err.deployment_id is None


def test_deployment_not_found_preserves_deployment_id_with_custom_message() -> None:
    err = DeploymentNotFoundError(message="Custom error", deployment_id="dep_1")
    assert str(err) == "Custom error"
    assert err.deployment_id == "dep_1"


def test_base_error_supports_cause_chaining() -> None:
    root = ValueError("boom")
    err = DeploymentError("failed", error_code="deployment_error", cause=root)
    assert err.cause is root
    assert err.__cause__ is root


def test_base_error_requires_error_code() -> None:
    err = DeploymentError("failed", error_code="test_code")
    assert err.error_code == "test_code"


def test_deployment_service_is_instantiable() -> None:
    svc = DeploymentService()
    assert svc.name == "deployment_service"


def test_deployment_service_satisfies_protocol() -> None:
    svc = DeploymentService()
    assert isinstance(svc, DeploymentServiceProtocol)


def test_deployment_service_is_base_deployment_service() -> None:
    assert issubclass(DeploymentService, BaseDeploymentService)


@pytest.mark.parametrize(
    ("method_name", "kwargs"),
    [
        ("create", {"user_id": "u1", "payload": None, "db": None}),
        ("list_types", {"user_id": "u1", "db": None}),
        ("list", {"user_id": "u1", "db": None}),
        ("get", {"user_id": "u1", "deployment_id": "d1", "db": None}),
        ("update", {"user_id": "u1", "deployment_id": "d1", "payload": None, "db": None}),
        ("redeploy", {"user_id": "u1", "deployment_id": "d1", "db": None}),
        ("duplicate", {"user_id": "u1", "deployment_id": "d1", "db": None}),
        ("delete", {"user_id": "u1", "deployment_id": "d1", "db": None}),
        ("get_status", {"user_id": "u1", "deployment_id": "d1", "db": None}),
        ("create_execution", {"user_id": "u1", "payload": None, "db": None}),
        ("get_execution", {"user_id": "u1", "execution_id": "e1", "db": None}),
    ],
)
async def test_deployment_service_stub_methods_raise(method_name: str, kwargs: dict) -> None:
    svc = DeploymentService()
    with pytest.raises(DeploymentNotConfiguredError, match="requires a concrete deployment adapter"):
        await getattr(svc, method_name)(**kwargs)


async def test_deployment_service_teardown_is_noop() -> None:
    svc = DeploymentService()
    await svc.teardown()


def test_deployment_not_configured_includes_method_name() -> None:
    err = DeploymentNotConfiguredError(method="create")
    assert "DeploymentService.create()" in str(err)
    assert err.error_code == "deployment_not_configured"


def test_deployment_not_configured_default_message() -> None:
    err = DeploymentNotConfiguredError()
    assert "No deployment adapter is registered" in str(err)


def test_auth_errors_not_caught_by_deployment_error() -> None:
    """Ensure except DeploymentError does NOT catch auth failures."""

    def raise_auth_error() -> None:
        try:
            raise CredentialResolutionError
        except DeploymentError:
            pytest.fail("DeploymentError should not catch AuthenticationError")

    with pytest.raises(AuthenticationError):
        raise_auth_error()


def test_deployment_service_error_catches_both_hierarchies() -> None:
    """DeploymentServiceError catches both deployment and auth errors."""
    with pytest.raises(DeploymentServiceError):
        raise CredentialResolutionError
    with pytest.raises(DeploymentServiceError):
        raise DeploymentNotFoundError


def test_package_exports_base_and_error() -> None:
    from lfx.services.adapters.deployment import BaseDeploymentService, DeploymentError, DeploymentService

    assert BaseDeploymentService is not None
    assert DeploymentError is not None
    assert DeploymentService is not None
