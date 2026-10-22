"""Prove installed metadata, owned runtime discovery and legacy category coexistence."""

import importlib.metadata
import sys
from pathlib import Path

COMPONENT_COUNT = 6
TRIGGER_COUNT = 2


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify(installed, repository):
    sys.path.insert(0, str(installed))
    import lfx_confluence
    from lfx.extension import load_installed_extensions
    from lfx.extension.bundle_registry import BundleRecord, get_default_registry
    from lfx.extension.loader import load_inline_bundle

    require(Path(lfx_confluence.__file__).is_relative_to(installed), "The source bundle shadowed the installed wheel.")
    distribution = importlib.metadata.distribution("lfx-confluence")
    require(distribution.version == "0.1.0", "Unexpected wheel version.")
    loaded = load_installed_extensions([distribution])
    require(len(loaded) == 1 and loaded[0].ok, "Installed extension discovery failed.")
    result = loaded[0]
    require(len(result.components) == COMPONENT_COUNT, "The six supported components were not installed.")
    require(
        {component.bundle for component in result.components} == {"confluence_integrations"},
        "The integration changed the legacy category.",
    )
    legacy = load_inline_bundle(repository / "src/bundles/lfx-bundles/src/lfx_bundles/confluence")
    require(legacy.ok, "The existing Confluence component did not load.")
    require(
        {component.class_name for component in legacy.components} == {"ConfluenceComponent"},
        "The legacy class identity changed.",
    )
    registry = get_default_registry()
    registry.install_bundle(
        BundleRecord(
            bundle="confluence",
            extension_id="lfx-bundles",
            extension_version="0.0.0",
            slot="extra",
            components=tuple(legacy.components),
            manifestless=True,
        )
    )
    registry.install_bundle(
        BundleRecord(
            bundle="confluence_integrations",
            extension_id="lfx-confluence",
            extension_version="0.1.0",
            slot="official",
            components=tuple(result.components),
            integrations=tuple(result.integrations),
            distribution="lfx-confluence",
            source_path=result.source_path,
        )
    )
    require(registry.get_bundle("confluence").class_names == {"ConfluenceComponent"}, "The legacy bundle was replaced.")
    from langflow.services.triggers.providers.registry import get_provider

    provider = get_provider("confluence")
    require(
        provider is not None and len(provider.kinds) == TRIGGER_COUNT, "The owned server adapter was not discovered."
    )
    require(provider.oauth is not None and provider.collect is not None, "OAuth or collection hooks are missing.")
    sys.stdout.write(
        "Installed wheel verified. Six integration components, two server trigger kinds "
        "and unchanged legacy ConfluenceComponent coexist.\n"
    )


if __name__ == "__main__":
    verify(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
