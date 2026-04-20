from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable

_GUARD_FRIENDLY_DETAILS: dict[str, str] = {
    "FLOW_HAS_DEPLOYED_VERSIONS": (
        "This flow cannot be deleted because it has deployed versions. "
        "Please remove its versions from deployments first."
    ),
    "PROJECT_HAS_DEPLOYMENTS": (
        "This project cannot be deleted because it has deployments. Please delete its deployments first."
    ),
    "FLOW_DEPLOYED_IN_PROJECT": (
        "This flow cannot be moved to another project until its versions "
        "are removed from deployments in its current project."
    ),
    "DEPLOYMENT_PROJECT_MOVE": (
        "This deployment cannot be moved to a different project. Re-create it in the target project instead."
    ),
    "DEPLOYMENT_TYPE_UPDATE": ("The deployment type cannot be modified."),
    "DEPLOYMENT_RESOURCE_KEY_UPDATE": (
        "This deployment resource key cannot be modified on an existing deployment. Re-create it instead."
    ),
    "DEPLOYMENT_PROVIDER_ACCOUNT_MOVE": (
        "This deployment cannot be moved to a different provider account. Re-create it under the "
        "target provider account."
    ),
    "DEPLOYMENT_PROVIDER_ACCOUNT_IDENTITY_UPDATE": (
        "This deployment provider account identity cannot be modified. Re-create the account instead."
    ),
    "CROSS_PROJECT_ATTACHMENT": "Flow versions can only be in deployments in the same project.",
}


class DeploymentGuardError(Exception):
    """Raised when a deployment guard blocks an operation."""

    def __init__(
        self,
        *,
        code: str,
        technical_detail: str,
        detail: str,
    ):
        self.code = code
        self.technical_detail = technical_detail
        self.detail = detail
        super().__init__(detail)


_UNKNOWN_GUARD_FALLBACK_DETAIL = "Operation blocked by deployment guard ({code})."


def get_friendly_guard_detail(code: str) -> str:
    """Map a guard code to the API-facing detail text."""
    return _GUARD_FRIENDLY_DETAILS.get(code, _UNKNOWN_GUARD_FALLBACK_DETAIL.format(code=code))


def parse_deployment_guard_error(exc: BaseException) -> DeploymentGuardError | None:
    """Return ``exc`` when it is a ``DeploymentGuardError``; otherwise ``None``.

    Guard failures must be raised explicitly as ``DeploymentGuardError`` by the
    operation that enforces the guard.
    """
    return exc if isinstance(exc, DeploymentGuardError) else None


def raise_if_deployment_guard_error_or_skip(exc: BaseException) -> None:
    """Raise ``DeploymentGuardError`` when ``exc`` is one; otherwise do nothing."""
    if not isinstance(exc, DeploymentGuardError):
        return

    raise exc


async def araise_if_deployment_guard_error_or_skip(
    exc: BaseException,
    *,
    log_message: str | None = None,
    remap: Callable[[DeploymentGuardError], DeploymentGuardError] | None = None,
) -> None:
    """Raise ``DeploymentGuardError`` and optionally log/remap it; otherwise do nothing."""
    if not isinstance(exc, DeploymentGuardError):
        return

    guard_error = remap(exc) if remap is not None else exc

    if log_message is not None:
        await logger.adebug(
            "%s code=%s technical_detail=%s",
            log_message,
            guard_error.code,
            guard_error.technical_detail,
        )

    if guard_error is exc:
        raise exc
    raise guard_error from exc


def remap_flow_guard_for_project_delete(exc: DeploymentGuardError) -> DeploymentGuardError:
    """Map flow-scoped guard code to a project-scoped code for project deletes."""
    if exc.code != "FLOW_HAS_DEPLOYED_VERSIONS":
        return exc

    return DeploymentGuardError(
        code="PROJECT_HAS_DEPLOYMENTS",
        technical_detail=(f"DELETE folder blocked while deleting project flows: {exc.technical_detail}"),
        detail=get_friendly_guard_detail("PROJECT_HAS_DEPLOYMENTS"),
    )
