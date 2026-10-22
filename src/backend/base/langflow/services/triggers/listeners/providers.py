"""Load installed trigger owners without building the API component palette."""

from __future__ import annotations

import logging
from importlib import metadata

from lfx.extension.bundle_registry import BundleRecord, get_default_registry
from lfx.extension.integration_conflicts import IntegrationConflictError
from lfx.extension.loader import load_installed_extensions

from langflow.services.triggers.providers.registry import ENTRY_POINT_GROUP

logger = logging.getLogger(__name__)


def load_installed_trigger_providers() -> None:
    """Validate only distributions declaring server-side trigger hooks.

    The ordinary extension loader owns manifest, version, path, catalog, and
    component validation. Reuse it rather than trusting an entry point alone.
    No component templates or API caches are built in this process.
    """
    distributions = [
        distribution
        for distribution in metadata.distributions()
        if any(entry.group == ENTRY_POINT_GROUP for entry in distribution.entry_points)
    ]
    registry = get_default_registry()
    for result in load_installed_extensions(distributions):
        if not result.ok or not result.bundle or not result.components or result.slot is None:
            logger.warning(
                "Listener trigger bundle %s was unavailable (%s)",
                result.distribution,
                ", ".join(error.code for error in result.errors) or "missing-components",
            )
            continue
        record = BundleRecord(
            bundle=result.bundle,
            extension_id=result.extension_id or result.bundle,
            extension_version=result.extension_version or "0.0.0",
            slot=result.slot,
            components=tuple(result.components),
            integrations=tuple(result.integrations),
            distribution=result.distribution,
            source_path=result.source_path,
        )
        existing = registry.get_bundle(record.bundle)
        if existing is not None:
            if existing.distribution != record.distribution or existing.source_path != record.source_path:
                logger.warning("Listener trigger bundle %s has a conflicting installed owner", record.bundle)
            continue
        try:
            registry.install_bundle(record)
        except IntegrationConflictError:
            logger.warning("Listener trigger bundle %s has conflicting integration identities", record.bundle)
