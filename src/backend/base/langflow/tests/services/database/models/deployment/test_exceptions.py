from __future__ import annotations

from langflow.services.database.models.deployment.exceptions import (
    DeploymentGuardError,
    parse_deployment_guard_error,
)


class _SimulatedDbError(Exception):
    """Synthetic DB exception used for parser tests."""


class _OuterWrapperError(Exception):
    """Synthetic wrapper exception used to build a cause chain."""


def _raise_with_cause() -> None:
    guard_message = (
        "DEPLOYMENT_GUARD:PROJECT_HAS_DEPLOYMENTS:Cannot delete project because it contains deployments. "
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
    assert parsed.detail == "Cannot delete project because it contains deployments."


def test_parse_deployment_guard_error_strips_newline_sql_block() -> None:
    message = (
        "sqlite3.IntegrityError: DEPLOYMENT_GUARD:FLOW_VERSION_DEPLOYED:"
        "Cannot delete flow version because it is attached.\n"
        "[SQL: DELETE FROM flow_version WHERE id = ?]"
    )
    exc = _SimulatedDbError(message)

    parsed = parse_deployment_guard_error(exc)

    assert isinstance(parsed, DeploymentGuardError)
    assert parsed.detail == "Cannot delete flow version because it is attached."


def test_parse_deployment_guard_error_deployment_project_move() -> None:
    message = (
        "DEPLOYMENT_GUARD:DEPLOYMENT_PROJECT_MOVE:"
        "Cannot move deployment to a different project. "
        "Re-create it in the target project instead."
    )
    exc = _SimulatedDbError(message)

    parsed = parse_deployment_guard_error(exc)

    assert isinstance(parsed, DeploymentGuardError)
    assert parsed.detail == "Cannot move deployment to a different project. Re-create it in the target project instead."


def test_parse_deployment_guard_error_deployment_provider_account_move() -> None:
    message = (
        "DEPLOYMENT_GUARD:DEPLOYMENT_PROVIDER_ACCOUNT_MOVE:"
        "Cannot move deployment to a different deployment provider account. "
        "Re-create it under the target provider account instead."
    )
    exc = _SimulatedDbError(message)

    parsed = parse_deployment_guard_error(exc)

    assert isinstance(parsed, DeploymentGuardError)
    assert (
        parsed.detail == "Cannot move deployment to a different deployment provider account. "
        "Re-create it under the target provider account instead."
    )


def test_parse_deployment_guard_error_cross_project_attachment() -> None:
    message = (
        "DEPLOYMENT_GUARD:CROSS_PROJECT_ATTACHMENT:Cannot attach a flow version to a deployment in a different project."
    )
    exc = _SimulatedDbError(message)

    parsed = parse_deployment_guard_error(exc)

    assert isinstance(parsed, DeploymentGuardError)
    assert parsed.detail == "Cannot attach a flow version to a deployment in a different project."


def test_parse_deployment_guard_error_returns_none_when_absent() -> None:
    parsed = parse_deployment_guard_error(Exception("plain error"))
    assert parsed is None


def test_parse_deployment_guard_error_from_implicit_context_chain() -> None:
    """Parser should walk __context__ (implicit chaining), not just __cause__."""
    guard_message = "DEPLOYMENT_GUARD:FLOW_VERSION_DEPLOYED:Cannot delete flow version because it is attached."
    try:
        try:
            raise _SimulatedDbError(guard_message)
        except _SimulatedDbError:
            msg = "wrapped"
            raise _OuterWrapperError(msg)  # noqa: B904 — intentional implicit chain
    except _OuterWrapperError as exc:
        parsed = parse_deployment_guard_error(exc)

    assert isinstance(parsed, DeploymentGuardError)
    assert parsed.detail == "Cannot delete flow version because it is attached."


def test_parse_deployment_guard_error_handles_cyclic_chain() -> None:
    """Parser must not loop forever when an exception chain contains a cycle."""
    exc_a = Exception("a")
    exc_b = Exception("b")
    exc_a.__cause__ = exc_b
    exc_b.__cause__ = exc_a

    parsed = parse_deployment_guard_error(exc_a)
    assert parsed is None
