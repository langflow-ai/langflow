"""Component registry shared by CLI upgrade checks before runtime startup."""

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class UpgradeRegistryError(RuntimeError):
    """The installed component registry cannot support a compatibility check."""


def load_upgrade_registry() -> dict[str, Any]:
    """Combine the shipped core index with runtime-discoverable bundle templates."""
    from lfx.interface.components import _read_component_index, import_extension_components
    from lfx.services.deps import get_settings_service
    from lfx.utils.async_helpers import run_until_complete

    blob = _read_component_index(None)
    if not blob or not blob.get("entries"):
        msg = (
            "the bundled component registry is empty or missing, so compatibility cannot be checked. "
            "Try reinstalling lfx (e.g. `pip install --force-reinstall lfx`)."
        )
        raise UpgradeRegistryError(msg)

    all_types: dict[str, Any] = {}
    for category, components in blob["entries"]:
        all_types.setdefault(category, {}).update(components)

    # The runtime cache is still empty at CLI gate time. Discover bundles through
    # the same loader as startup so canonical identities, aliases and precedence
    # agree. The run/serve gate can be called from an already running event loop.
    try:
        # Discovery only consumes .settings, which the service protocol supplies.
        settings_service = cast("SettingsService", get_settings_service())
        extensions = run_until_complete(import_extension_components(settings_service))
    except Exception as exc:
        msg = "could not load the extension component registry. Check the installed extensions and configuration."
        raise UpgradeRegistryError(msg) from exc
    for category, components in extensions.items():
        all_types.setdefault(category, {}).update(components)
    return all_types
