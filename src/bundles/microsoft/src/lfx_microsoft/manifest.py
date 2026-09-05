"""Access to the bundle-owned integration capability manifest.

The manifest shipped at ``components/microsoft/capabilities.v1.json`` is the
single source of truth for scopes: the components build their
``ConnectionRefInput`` from it, so a component can never require a scope the
manifest (and therefore governance and the connection picker) does not know
about.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from lfx.integrations.capabilities import IntegrationCapability, IntegrationCapabilityManifest
from lfx.io import ConnectionRefInput

PROVIDER_ID = "microsoft"
MANIFEST_PATH = Path(__file__).resolve().parent / "components" / "microsoft" / "capabilities.v1.json"

_IDENTITY_KIND = {"user_delegated": "user", "bot": "instance", "service": "instance"}


@lru_cache(maxsize=1)
def load_manifest() -> IntegrationCapabilityManifest:
    """Load and validate the bundle's capability manifest once per process."""
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return IntegrationCapabilityManifest.model_validate(payload)


def capability(capability_id: str) -> IntegrationCapability:
    """Return one declared capability by id."""
    for entry in load_manifest().capabilities:
        if entry.id == capability_id:
            return entry
    msg = f"Unknown Microsoft capability id: {capability_id!r}"
    raise KeyError(msg)


def connection_input(capability_id: str, *, info: str | None = None) -> ConnectionRefInput:
    """Build the connection field for one capability straight from the manifest."""
    declared = capability(capability_id)
    scopes = ", ".join(declared.required_scopes)
    return ConnectionRefInput(
        name="connection",
        display_name="Microsoft Connection",
        provider=PROVIDER_ID,
        auth_profile_id=declared.auth_profile_id,
        required_scopes=list(declared.required_scopes),
        conditional_scopes=list(declared.conditional_scopes),
        identity_kind=_IDENTITY_KIND[declared.identity],
        capabilities=[declared.id],
        required=True,
        info=info or f"Microsoft connection handle, for example microsoft/work. Requires {scopes}.",
    )
