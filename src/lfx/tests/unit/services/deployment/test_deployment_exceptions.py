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
    AuthorizationError,
    AuthSchemeError,
    CredentialResolutionError,
    DeploymentConflictError,
    DeploymentNotFoundError,
    DeploymentSupportError,
    DeploymentTimeoutError,
    InvalidContentError,
    InvalidDeploymentOperationError,
    InvalidDeploymentTypeError,
    OperationNotSupportedError,
    RateLimitError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    raise_for_status_and_detail,
)
from lfx.services.interfaces import DeploymentServiceProtocol


def test_exception_hierarchy_is_preserved() -> None:
    # DeploymentServiceError is the common root
    assert issubclass(DeploymentError, DeploymentServiceError)
    assert issubclass(AuthenticationError, DeploymentServiceError)
    assert issubclass(AuthorizationError, DeploymentServiceError)

    # AuthenticationError is a sibling of DeploymentError, NOT a child
    assert not issubclass(AuthenticationError, DeploymentError)
    assert not issubclass(AuthorizationError, DeploymentError)
    assert not issubclass(DeploymentError, AuthenticationError)
    assert not issubclass(DeploymentError, AuthorizationError)

    # Auth subtypes
    assert issubclass(CredentialResolutionError, AuthenticationError)
    assert issubclass(AuthSchemeError, AuthenticationError)

    # Deployment operation subtypes
    assert issubclass(DeploymentConflictError, DeploymentError)
    assert issubclass(InvalidContentError, DeploymentError)
    assert issubclass(InvalidDeploymentOperationError, DeploymentError)
    assert issubclass(ResourceNotFoundError, DeploymentError)
    assert issubclass(DeploymentNotFoundError, ResourceNotFoundError)
    assert issubclass(DeploymentNotConfiguredError, DeploymentError)
    assert issubclass(OperationNotSupportedError, DeploymentError)


def test_exception_error_codes_are_set() -> None:
    assert AuthorizationError("forbidden", error_code="authorization_error").error_code == "authorization_error"
    assert CredentialResolutionError().error_code == "credentials_resolution_error"
    assert DeploymentConflictError().error_code == "deployment_conflict"
    assert RateLimitError().error_code == "deployment_rate_limited"
    assert DeploymentTimeoutError().error_code == "deployment_timeout"
    assert ServiceUnavailableError().error_code == "deployment_provider_unavailable"
    assert DeploymentSupportError().error_code == "unsupported_deployment_type"
    assert ResourceNotFoundError().error_code == "resource_not_found"
    assert InvalidDeploymentTypeError().error_code == "invalid_deployment_type"
    assert InvalidContentError().error_code == "unprocessable_content_error"
    assert InvalidDeploymentOperationError().error_code == "invalid_deployment_operation"
    assert AuthSchemeError().error_code == "unsupported_auth_type"
    assert DeploymentNotConfiguredError().error_code == "deployment_not_configured"
    assert OperationNotSupportedError().error_code == "operation_not_supported"


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


def test_resource_not_found_defaults() -> None:
    err = ResourceNotFoundError(resource_id="r1")
    assert str(err) == "Resource not found: r1"
    assert err.resource_id == "r1"
    assert err.error_code == "resource_not_found"


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
        ("list_configs", {"user_id": "u1", "db": None}),
        ("list_snapshots", {"user_id": "u1", "db": None}),
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


def test_authorization_errors_not_caught_by_deployment_error() -> None:
    """Ensure except DeploymentError does NOT catch authorization failures."""

    def raise_authorization_error() -> None:
        error_message = "forbidden"
        try:
            raise AuthorizationError(error_message, error_code="authorization_error")
        except DeploymentError:
            pytest.fail("DeploymentError should not catch AuthorizationError")

    with pytest.raises(AuthorizationError):
        raise_authorization_error()


def test_deployment_service_error_catches_both_hierarchies() -> None:
    """DeploymentServiceError catches both deployment and auth errors."""
    with pytest.raises(DeploymentServiceError):
        raise CredentialResolutionError
    with pytest.raises(DeploymentServiceError):
        raise DeploymentNotFoundError


def test_raise_for_status_and_detail_maps_known_http_statuses() -> None:
    with pytest.raises(AuthenticationError):
        raise_for_status_and_detail(status_code=401, detail="unauthorized", message_prefix="x")
    with pytest.raises(AuthorizationError):
        raise_for_status_and_detail(status_code=403, detail="forbidden", message_prefix="x")
    with pytest.raises(DeploymentNotFoundError):
        raise_for_status_and_detail(status_code=404, detail="missing", message_prefix="x")
    with pytest.raises(DeploymentConflictError):
        raise_for_status_and_detail(status_code=409, detail="conflict", message_prefix="x")
    with pytest.raises(InvalidContentError):
        raise_for_status_and_detail(status_code=422, detail="unprocessable", message_prefix="x")
    with pytest.raises(InvalidDeploymentOperationError):
        raise_for_status_and_detail(status_code=400, detail="bad request", message_prefix="x")
    with pytest.raises(InvalidDeploymentOperationError):
        raise_for_status_and_detail(status_code=405, detail="method not allowed", message_prefix="x")
    with pytest.raises(InvalidContentError):
        raise_for_status_and_detail(status_code=413, detail="payload too large", message_prefix="x")
    with pytest.raises(InvalidContentError):
        raise_for_status_and_detail(status_code=415, detail="unsupported media type", message_prefix="x")
    with pytest.raises(DeploymentNotFoundError):
        raise_for_status_and_detail(status_code=410, detail="gone", message_prefix="x")
    with pytest.raises(RateLimitError):
        raise_for_status_and_detail(status_code=429, detail="too many requests", message_prefix="x")
    with pytest.raises(DeploymentTimeoutError):
        raise_for_status_and_detail(status_code=408, detail="timeout", message_prefix="x")
    with pytest.raises(DeploymentTimeoutError):
        raise_for_status_and_detail(status_code=504, detail="gateway timeout", message_prefix="x")
    with pytest.raises(ServiceUnavailableError):
        raise_for_status_and_detail(status_code=502, detail="bad gateway", message_prefix="x")
    with pytest.raises(ServiceUnavailableError):
        raise_for_status_and_detail(status_code=503, detail="service unavailable", message_prefix="x")


def test_raise_for_status_and_detail_uses_detail_heuristics_without_status() -> None:
    with pytest.raises(AuthorizationError):
        raise_for_status_and_detail(status_code=None, detail="permission denied")
    with pytest.raises(InvalidContentError):
        raise_for_status_and_detail(status_code=None, detail="invalid payload")
    with pytest.raises(RateLimitError):
        raise_for_status_and_detail(status_code=None, detail="rate limit exceeded")
    with pytest.raises(DeploymentTimeoutError):
        raise_for_status_and_detail(status_code=None, detail="request timed out")
    with pytest.raises(ServiceUnavailableError):
        raise_for_status_and_detail(status_code=None, detail="service unavailable")


def test_package_exports_base_and_error() -> None:
    from lfx.services.adapters.deployment import BaseDeploymentService, DeploymentError, DeploymentService

    assert BaseDeploymentService is not None
    assert DeploymentError is not None
    assert DeploymentService is not None
