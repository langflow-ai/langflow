"""Capability metadata supplies each component's connection requirements."""

import json
from functools import lru_cache
from pathlib import Path

from lfx.integrations.capabilities import IntegrationCapabilityManifest


@lru_cache(maxsize=1)
def manifest() -> IntegrationCapabilityManifest:
    path = Path(__file__).parent / "components" / "servicenow" / "capabilities.v1.json"
    return IntegrationCapabilityManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))


def connection_input(capability_id: str, *, required: bool = True):
    from lfx.io import ConnectionRefInput

    capability = next(item for item in manifest().capabilities if item.id == capability_id)
    return ConnectionRefInput(
        name="connection",
        display_name="ServiceNow Connection",
        provider="servicenow",
        auth_profile_id="user",
        identity_kind="user",
        ownership_mode="user",
        required_scopes=list(capability.required_scopes),
        capabilities=[capability.id],
        required=required,
        info="Use an owned OAuth connection for this instance. Triggers require background consent.",
    )
