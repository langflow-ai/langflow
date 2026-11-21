"""Bundle capability metadata and connection requirements."""

from functools import lru_cache
from pathlib import Path

from lfx.custom.custom_component.component import Component  # noqa: F401
from lfx.integrations.capabilities import IntegrationCapabilityManifest
from lfx.io import ConnectionRefInput


@lru_cache(maxsize=1)
def load_manifest():
    return IntegrationCapabilityManifest.model_validate_json(
        (Path(__file__).parent / "components/confluence_integrations/capabilities.v1.json").read_text()
    )


def connection_input(capability, *, required=True):
    declared = next(item for item in load_manifest().capabilities if item.id == capability)
    return ConnectionRefInput(
        name="connection",
        display_name="Confluence Connection",
        provider="confluence",
        auth_profile_id="user",
        identity_kind="user",
        ownership_mode="user",
        required_scopes=list(declared.required_scopes),
        capabilities=[capability],
        required=required,
        info="Use an owned Confluence Cloud OAuth connection for the operator-configured site.",
    )
