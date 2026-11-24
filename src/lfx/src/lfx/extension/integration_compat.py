"""Runtime and packaging floor for bundle-owned integration manifest references.

Keep this module independent of the extension loader so the CI guard can use
the same version contract without installing lfx or importing provider code.
"""

from __future__ import annotations

from importlib.metadata import version
from typing import TYPE_CHECKING, Any

from packaging.version import Version

if TYPE_CHECKING:
    from packaging.requirements import Requirement

INTEGRATIONS_MIN_LFX_VERSION = "1.13.0.dev0"


class IntegrationVersionError(ValueError):
    """The running lfx predates the integration reference schema."""


def check_integration_runtime(manifest_data: dict[str, Any]) -> None:
    """Explain version skew before strict schema parsing can obscure it."""
    if "integrations" not in manifest_data:
        return
    installed = version("lfx")
    if Version(installed) < Version(INTEGRATIONS_MIN_LFX_VERSION):
        msg = (
            f"The integrations field requires lfx>={INTEGRATIONS_MIN_LFX_VERSION}; "
            f"installed lfx is {installed}. Upgrade lfx and the bundle together."
        )
        raise IntegrationVersionError(msg)


def supports_integration_manifests(requirement: Requirement) -> bool:
    """Whether an unconditional lfx requirement guarantees the feature floor.

    Require an explicit lower bound. Exclusions and upper bounds alone cannot
    prove that older releases are excluded; conditional and URL dependencies
    cannot guarantee a runtime version on every supported install.
    """
    if requirement.name.lower() != "lfx" or requirement.marker is not None or requirement.url is not None:
        return False
    floor = Version(INTEGRATIONS_MIN_LFX_VERSION)
    for specifier in requirement.specifier:
        if specifier.operator not in {">=", ">", "~=", "=="}:
            continue
        lower_bound = Version(specifier.version.removesuffix(".*"))
        if lower_bound >= floor:
            return True
    return False
