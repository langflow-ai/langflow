from __future__ import annotations

from lfx.log.logger import logger

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
    """Return the first ``DeploymentGuardError`` found in an exception chain.

    This intentionally does not parse generic exception messages. Guard failures
    must be raised explicitly as ``DeploymentGuardError``.
    """
    seen: set[int] = set()
    current: BaseException | None = exc

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, DeploymentGuardError):
            return current

        current = current.__cause__ or current.__context__

    return None


def raise_if_deployment_guard_error_or_skip(exc: BaseException) -> None:
    """Raise chained ``DeploymentGuardError`` when present; otherwise do nothing."""
    if guard_error := parse_deployment_guard_error(exc):
        logger.error("Deployment guard error: %s (error code: %s)", guard_error.technical_detail, guard_error.code)
        raise guard_error
