from __future__ import annotations

import pytest
from langflow.services.database.models.deployment.exceptions import (
    DeploymentGuardError,
    araise_if_deployment_guard_error_or_skip,
    get_friendly_guard_detail,
    parse_deployment_guard_error,
    raise_if_deployment_guard_error_or_skip,
    remap_flow_guard_for_project_delete,
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
            "DEPLOYMENT_TYPE_UPDATE",
            "Cannot modify deployment type on an existing deployment.",
            "The deployment type cannot be modified.",
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
    exc = DeploymentGuardError(
        code=code,
        technical_detail=technical_detail,
        detail=friendly_detail,
    )

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
    parsed = parse_deployment_guard_error(Exception("plain error DEPLOYMENT_GUARD:PROJECT_HAS_DEPLOYMENTS:oops"))
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


def test_raise_if_deployment_guard_error_or_skip_raises_guard_error() -> None:
    guard_error = DeploymentGuardError(
        code="PROJECT_HAS_DEPLOYMENTS",
        technical_detail="DELETE project blocked: dependent deployments exist.",
        detail=get_friendly_guard_detail("PROJECT_HAS_DEPLOYMENTS"),
    )

    with pytest.raises(DeploymentGuardError) as raised:
        raise_if_deployment_guard_error_or_skip(guard_error)

    assert raised.value is guard_error


def test_raise_if_deployment_guard_error_or_skip_is_noop_when_guard_absent() -> None:
    raise_if_deployment_guard_error_or_skip(Exception("not a guard error"))


@pytest.mark.asyncio
async def test_araise_if_deployment_guard_error_or_skip_raises_and_logs_message(monkeypatch) -> None:
    guard_error = DeploymentGuardError(
        code="PROJECT_HAS_DEPLOYMENTS",
        technical_detail="DELETE project blocked: dependent deployments exist.",
        detail=get_friendly_guard_detail("PROJECT_HAS_DEPLOYMENTS"),
    )
    debug_calls: list[tuple[str, tuple[object, ...]]] = []

    async def _fake_adebug(message: str, *args: object) -> None:
        debug_calls.append((message, args))

    monkeypatch.setattr("langflow.services.database.models.deployment.exceptions.logger.adebug", _fake_adebug)

    with pytest.raises(DeploymentGuardError) as raised:
        await araise_if_deployment_guard_error_or_skip(
            guard_error,
            log_message="op=test",
        )

    assert raised.value is guard_error
    assert debug_calls == [
        (
            "%s code=%s technical_detail=%s",
            (
                "op=test",
                "PROJECT_HAS_DEPLOYMENTS",
                "DELETE project blocked: dependent deployments exist.",
            ),
        )
    ]


@pytest.mark.asyncio
async def test_araise_if_deployment_guard_error_or_skip_raises_without_logging_when_message_absent(monkeypatch) -> None:
    guard_error = DeploymentGuardError(
        code="PROJECT_HAS_DEPLOYMENTS",
        technical_detail="DELETE project blocked: dependent deployments exist.",
        detail=get_friendly_guard_detail("PROJECT_HAS_DEPLOYMENTS"),
    )
    debug_calls: list[tuple[str, tuple[object, ...]]] = []

    async def _fake_adebug(message: str, *args: object) -> None:
        debug_calls.append((message, args))

    monkeypatch.setattr("langflow.services.database.models.deployment.exceptions.logger.adebug", _fake_adebug)

    with pytest.raises(DeploymentGuardError):
        await araise_if_deployment_guard_error_or_skip(guard_error)

    assert debug_calls == []


def test_remap_flow_guard_for_project_delete_remaps_flow_guard() -> None:
    flow_guard = DeploymentGuardError(
        code="FLOW_HAS_DEPLOYED_VERSIONS",
        technical_detail="DELETE flow blocked by deployment attachment",
        detail=get_friendly_guard_detail("FLOW_HAS_DEPLOYED_VERSIONS"),
    )

    remapped = remap_flow_guard_for_project_delete(flow_guard)

    assert remapped is not flow_guard
    assert remapped.code == "PROJECT_HAS_DEPLOYMENTS"
    assert remapped.technical_detail == (
        "DELETE folder blocked while deleting project flows: DELETE flow blocked by deployment attachment"
    )
    assert remapped.detail == get_friendly_guard_detail("PROJECT_HAS_DEPLOYMENTS")


def test_remap_flow_guard_for_project_delete_keeps_non_flow_guard() -> None:
    project_guard = DeploymentGuardError(
        code="PROJECT_HAS_DEPLOYMENTS",
        technical_detail="DELETE project blocked by deployment row",
        detail=get_friendly_guard_detail("PROJECT_HAS_DEPLOYMENTS"),
    )

    remapped = remap_flow_guard_for_project_delete(project_guard)

    assert remapped is project_guard
