"""Component registry shared by CLI upgrade checks before runtime startup."""

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class UpgradeRegistryError(RuntimeError):
    """The installed component registry cannot support a compatibility check."""


def load_upgrade_registry(components_path: list[str] | None = None) -> dict[str, Any]:
    """Combine the shipped core index with runtime-discoverable bundle templates.

    Without ``components_path`` the bundle folders come from Langflow's settings. With it the
    settings are never built, and the plain custom components under it load too, merged the
    way the server merges them at startup.
    """
    from lfx.constants import BASE_COMPONENTS_PATH
    from lfx.custom.utils import abuild_custom_components
    from lfx.interface.components import (
        _merge_component_sources,
        _read_component_index,
        _resolved_component_path,
        import_extension_components,
    )
    from lfx.services.deps import get_settings_service
    from lfx.utils.async_helpers import run_until_complete

    blob = _read_component_index(None)
    if not blob or not blob.get("entries"):
        msg = (
            "the bundled component registry is empty or missing, so compatibility cannot be checked. "
            "An index built for another lfx version is ignored. "
            "Try reinstalling lfx (e.g. `pip install --force-reinstall lfx`)."
        )
        raise UpgradeRegistryError(msg)

    core: dict[str, Any] = {}
    for category, components in blob["entries"]:
        core.setdefault(category, {}).update(components)

    # The runtime cache is still empty at CLI gate time. Discover bundles through
    # the same loader as startup so canonical identities, aliases and precedence
    # agree. The run/serve gate can be called from an already running event loop.
    custom: dict[str, Any] = {}
    try:
        if components_path is None:
            # Discovery only consumes .settings, which the service protocol supplies.
            settings_service = cast("SettingsService", get_settings_service())
            extensions = run_until_complete(import_extension_components(settings_service))
        else:
            extensions = run_until_complete(import_extension_components(components_path=components_path))
            # The server skips the built-in components folder here: scanning it would replace the index.
            base = _resolved_component_path(BASE_COMPONENTS_PATH)
            custom_paths = [path for path in components_path if _resolved_component_path(path) != base]
            custom = run_until_complete(abuild_custom_components(custom_paths))
    except Exception as exc:
        msg = "could not load the extension component registry. Check the installed extensions and configuration."
        raise UpgradeRegistryError(msg) from exc
    return _merge_component_sources(core, custom.get("components", custom), extensions)
