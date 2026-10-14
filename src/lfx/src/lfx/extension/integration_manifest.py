"""Resolve and validate bundle-owned integration capability manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import ValidationError

from lfx.extension._paths import is_within
from lfx.extension.errors import ExtensionError
from lfx.integrations.capabilities import IntegrationCapabilityManifest

if TYPE_CHECKING:
    from pathlib import Path

    from lfx.extension.manifest import IntegrationManifestRef


@dataclass(frozen=True)
class ResolvedIntegrationManifest:
    """A validated capability catalog paired with its canonical source path."""

    path: Path
    manifest: IntegrationCapabilityManifest


def resolve_integration_manifest(
    bundle_root: Path,
    reference: IntegrationManifestRef,
) -> tuple[ResolvedIntegrationManifest | None, ExtensionError | None]:
    """Load one reference while enforcing bundle ownership and provider identity."""
    try:
        resolved_root = bundle_root.resolve(strict=True)
        candidate = (resolved_root / reference.path).resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as exc:
        return None, ExtensionError(
            code="manifest-unreadable",
            message=f"Could not resolve integration capability manifest: {exc}",
            location=reference.path,
            content=reference.path,
            hint="Check the capability-manifest path and bundle permissions.",
        )

    if not is_within(candidate, resolved_root):
        return None, ExtensionError(
            code="path-escape",
            message=(
                f"Integration capability-manifest path {reference.path!r} resolves outside "
                f"its owning bundle {reference.bundle!r}."
            ),
            location=f"integrations[{reference.provider_id}].path",
            content=reference.path,
            hint="Move the capability manifest inside the bundle directory.",
        )

    try:
        raw = candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        return None, ExtensionError(
            code="manifest-unreadable",
            message=f"Could not read integration capability manifest: {exc}",
            location=str(candidate),
            content=reference.path,
            hint="Create the referenced JSON file inside the bundle and check its permissions.",
        )

    try:
        payload = json.loads(raw)
        manifest = IntegrationCapabilityManifest.model_validate(payload)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        return None, ExtensionError(
            code="manifest-invalid",
            message=f"Integration capability manifest is invalid: {exc}",
            location=str(candidate),
            content=reference.path,
            hint="Fix the referenced capability manifest so it matches the versioned integration schema.",
        )

    if manifest.provider_id != reference.provider_id:
        return None, ExtensionError(
            code="manifest-invalid",
            message=(
                f"Integration provider {reference.provider_id!r} references a capability manifest for "
                f"{manifest.provider_id!r}."
            ),
            location=str(candidate),
            content=manifest.provider_id,
            hint="Make provider_id identical in extension.json and the capability manifest.",
        )

    return ResolvedIntegrationManifest(path=candidate, manifest=manifest), None
