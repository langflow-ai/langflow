from __future__ import annotations

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


_GUARD_PREFIX = "DEPLOYMENT_GUARD:"
_UNKNOWN_GUARD_FALLBACK_DETAIL = "Operation blocked by deployment guard ({code})."


def get_friendly_guard_detail(code: str) -> str:
    """Map a guard code to the API-facing detail text."""
    return _GUARD_FRIENDLY_DETAILS.get(code, _UNKNOWN_GUARD_FALLBACK_DETAIL.format(code=code))


def parse_deployment_guard_error(exc: BaseException) -> DeploymentGuardError | None:
    """Walk chained exceptions and extract guard messages shaped as ``DEPLOYMENT_GUARD:<CODE>:<DETAIL>``."""
    seen: set[int] = set()
    current: BaseException | None = exc

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, DeploymentGuardError):
            return current
        message = str(current)

        _before_prefix, separator, after_prefix = message.partition(_GUARD_PREFIX)
        # Require the full "DEPLOYMENT_GUARD:<CODE>:<DETAIL>" shape:
        # - `separator` confirms the guard prefix
        # - ":" in `after_prefix` confirms the CODE/DETAIL delimiter
        if separator and ":" in after_prefix:
            error_code, technical_detail = after_prefix.split(":", 1)
            return DeploymentGuardError(
                code=error_code,
                technical_detail=technical_detail,
                detail=get_friendly_guard_detail(error_code),
            )

        current = current.__cause__ or current.__context__

    return None
