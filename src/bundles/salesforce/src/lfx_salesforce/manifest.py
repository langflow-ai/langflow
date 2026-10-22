"""Bundle-owned capabilities and connection requirements."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from lfx.custom.custom_component.component import Component  # noqa: F401
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx.io import ConnectionRefInput


@lru_cache(maxsize=1)
def load_manifest() -> IntegrationCapabilityManifest:
    return IntegrationCapabilityManifest.model_validate_json(
        (Path(__file__).parent / "components/salesforce/capabilities.v1.json").read_text()
    )


def connection_input(capability_id: str, *, required: bool = True) -> ConnectionRefInput:
    declared = next(item for item in load_manifest().capabilities if item.id == capability_id)
    return ConnectionRefInput(
        name="connection",
        display_name="Salesforce Connection",
        provider="salesforce",
        auth_profile_id="user",
        identity_kind="user",
        ownership_mode="user",
        required_scopes=list(declared.required_scopes),
        capabilities=[declared.id],
        required=required,
        info="Use an owned connection for the operator-configured Salesforce org.",
    )
