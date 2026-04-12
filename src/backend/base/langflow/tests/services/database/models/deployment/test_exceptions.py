from __future__ import annotations

import pytest
from langflow.services.database.models.deployment.exceptions import (
    DeploymentGuardError,
    get_friendly_guard_detail,
    parse_deployment_guard_error,
)


class _SimulatedDbError(Exception):
    """Synthetic DB exception used for parser tests."""


class _OuterWrapperError(Exception):
    """Synthetic wrapper exception used to build a cause chain."""


def _raise_with_cause() -> None:
    guard_message = (
        "DEPLOYMENT_GUARD:PROJECT_HAS_DEPLOYMENTS:"
        "DELETE folder blocked: dependent rows exist in deployment for the target project. "
        "[SQL: DELETE FROM folder WHERE id = ?] "
        "(Background on this error at: https://sqlalche.me/e/20/gkpj)"
    )
    try:
        raise _SimulatedDbError(guard_message)
    except Exception as exc:
        raise _OuterWrapperError from exc


def test_parse_deployment_guard_error_from_cause_chain() -> None:
    try:
        _raise_with_cause()
    except _OuterWrapperError as exc:
        parsed = parse_deployment_guard_error(exc)

    assert isinstance(parsed, DeploymentGuardError)
    assert parsed.code == "PROJECT_HAS_DEPLOYMENTS"
    assert (
        parsed.technical_detail == "DELETE folder blocked: dependent rows exist in deployment for the target project. "
        "[SQL: DELETE FROM folder WHERE id = ?] "
        "(Background on this error at: https://sqlalche.me/e/20/gkpj)"
    )
    assert parsed.detail == (
        "This project cannot be deleted because it has deployments. Please delete its deployments first."
    )


def test_parse_deployment_guard_error_preserves_raw_technical_detail() -> None:
    message = (
        "sqlite3.IntegrityError: DEPLOYMENT_GUARD:FLOW_HAS_DEPLOYED_VERSIONS:"
        "DELETE flow_version blocked: dependent rows exist in flow_version_deployment_attachment for the target flow.\n"
        "[SQL: DELETE FROM flow_version WHERE id = ?]"
    )
    exc = _SimulatedDbError(message)

    parsed = parse_deployment_guard_error(exc)

    assert isinstance(parsed, DeploymentGuardError)
    assert parsed.code == "FLOW_HAS_DEPLOYED_VERSIONS"
    assert (
        parsed.technical_detail
        == "DELETE flow_version blocked: dependent rows exist in flow_version_deployment_attachment "
        "for the target flow.\n"
        "[SQL: DELETE FROM flow_version WHERE id = ?]"
    )
    assert (
        parsed.detail == "This flow cannot be deleted because it has deployed versions. "
        "Please remove its versions from deployments first."
    )


@pytest.mark.parametrize(
    ("code", "technical_detail", "friendly_detail"),
    [
        (
            "FLOW_DEPLOYED_IN_PROJECT",
            "UPDATE flow.folder_id blocked: versions of this flow remain attached to deployments in the current "
            "project scope (OLD.folder_id). Remove rows from flow_version_deployment_attachment for this flow in the "
            "current project before changing flow.folder_id.",
            "This flow cannot be moved to another project until its versions are removed from deployments "
            "in its current project.",
        ),
        (
            "DEPLOYMENT_PROJECT_MOVE",
            "UPDATE deployment.project_id blocked: project scope is immutable for existing deployments. "
            "Re-create the deployment in the target project.",
            "This deployment cannot be moved to a different project. Re-create it in the target project instead.",
        ),
        (
            "DEPLOYMENT_PROVIDER_ACCOUNT_MOVE",
            "UPDATE deployment.deployment_provider_account_id blocked: provider account scope is immutable "
            "for existing deployments. Re-create the deployment under the target provider account.",
            "This deployment cannot be moved to a different provider account. Re-create it under the target "
            "provider account.",
        ),
        (
            "CROSS_PROJECT_ATTACHMENT",
            "INSERT flow_version_deployment_attachment blocked: flow project scope (flow.folder_id) does not match "
            "deployment project scope (deployment.project_id).",
            "Flow versions can only be in deployments in the same project.",
        ),
        (
            "DEPLOYMENT_RESOURCE_KEY_UPDATE",
            "Cannot modify deployment resource key on an existing deployment. Re-create it instead.",
            "This deployment resource key cannot be modified on an existing deployment. Re-create it instead.",
        ),
        (
            "DEPLOYMENT_PROVIDER_ACCOUNT_IDENTITY_UPDATE",
            "UPDATE deployment_provider_account blocked: provider_key, provider_tenant_id, and provider_url "
            "are immutable on existing accounts. Re-create the account instead.",
            "This deployment provider account identity cannot be modified. Re-create the account instead.",
        ),
    ],
)
def test_parse_deployment_guard_error_maps_code_to_friendly_detail(
    code: str,
    technical_detail: str,
    friendly_detail: str,
) -> None:
    message = f"DEPLOYMENT_GUARD:{code}:{technical_detail}"
    exc = _SimulatedDbError(message)

    parsed = parse_deployment_guard_error(exc)

    assert isinstance(parsed, DeploymentGuardError)
    assert parsed.code == code
    assert parsed.technical_detail == technical_detail
    assert parsed.detail == friendly_detail


def test_get_friendly_guard_detail_falls_back_to_generic_code_message() -> None:
    assert (
        get_friendly_guard_detail("SOME_UNKNOWN_CODE") == "Operation blocked by deployment guard (SOME_UNKNOWN_CODE)."
    )


def test_parse_deployment_guard_error_returns_none_when_absent() -> None:
    parsed = parse_deployment_guard_error(Exception("plain error"))
    assert parsed is None


def test_parse_deployment_guard_error_from_implicit_context_chain() -> None:
    """Parser should walk __context__ (implicit chaining), not just __cause__."""
    guard_message = (
        "DEPLOYMENT_GUARD:FLOW_HAS_DEPLOYED_VERSIONS:"
        "DELETE flow_version blocked: dependent rows exist in flow_version_deployment_attachment for the target flow."
    )
    try:
        try:
            raise _SimulatedDbError(guard_message)
        except _SimulatedDbError:
            msg = "wrapped"
            raise _OuterWrapperError(msg)  # noqa: B904 — intentional implicit chain
    except _OuterWrapperError as exc:
        parsed = parse_deployment_guard_error(exc)

    assert isinstance(parsed, DeploymentGuardError)
    assert parsed.code == "FLOW_HAS_DEPLOYED_VERSIONS"
    assert (
        parsed.detail == "This flow cannot be deleted because it has deployed versions. "
        "Please remove its versions from deployments first."
    )


def test_parse_deployment_guard_error_handles_cyclic_chain() -> None:
    """Parser must not loop forever when an exception chain contains a cycle."""
    exc_a = Exception("a")
    exc_b = Exception("b")
    exc_a.__cause__ = exc_b
    exc_b.__cause__ = exc_a

    parsed = parse_deployment_guard_error(exc_a)
    assert parsed is None


def test_deployment_guard_error_supports_manual_technical_and_code() -> None:
    err = DeploymentGuardError(
        code="FLOW_HAS_DEPLOYED_VERSIONS",
        technical_detail="DELETE flow_version blocked due to dependent rows.",
        detail=(
            "This flow cannot be deleted because it has deployed versions. "
            "Please remove its versions from deployments first."
        ),
    )
    assert err.code == "FLOW_HAS_DEPLOYED_VERSIONS"
    assert err.technical_detail == "DELETE flow_version blocked due to dependent rows."
    assert (
        err.detail == "This flow cannot be deleted because it has deployed versions. "
        "Please remove its versions from deployments first."
    )
