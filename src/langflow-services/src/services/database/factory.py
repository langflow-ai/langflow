"""Factory for the concrete DatabaseService."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from services.database.service import DatabaseService
from services.factory import ServiceFactory

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService

AlembicPathProvider = Callable[[], tuple[Path, Path]]

_alembic_path_provider: AlembicPathProvider | None = None


def set_alembic_path_provider(provider: AlembicPathProvider | None) -> None:
    """Register a host callback that returns ``(script_location, alembic_cfg_path)``.

    Pass ``None`` to clear the provider (tests / partial teardown).
    """
    global _alembic_path_provider
    _alembic_path_provider = provider


def _resolve_alembic_paths() -> tuple[Path, Path]:
    if _alembic_path_provider is not None:
        return _alembic_path_provider()

    # Fallback for direct ``DatabaseService(settings)`` construction when the
    # host has not registered a provider yet (tests, plugins, partial init).
    # Prefer importlib over a static import so this package stays free of
    # ``langflow.*`` import statements.
    import importlib.util

    spec = importlib.util.find_spec("langflow.alembic")
    if spec is not None and spec.submodule_search_locations:
        script_location = Path(next(iter(spec.submodule_search_locations)))
        return script_location, script_location.parent / "alembic.ini"

    msg = (
        "Alembic path provider is not registered and langflow.alembic is not "
        "importable. langflow-base must call set_alembic_path_provider during "
        "service registration, or pass script_location/alembic_cfg_path."
    )
    raise RuntimeError(msg)


class DatabaseServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(DatabaseService)

    def create(self, settings_service: SettingsService):
        if not settings_service.settings.database_url:
            msg = "No database URL provided"
            raise ValueError(msg)
        script_location, alembic_cfg_path = _resolve_alembic_paths()
        return DatabaseService(
            settings_service,
            script_location=script_location,
            alembic_cfg_path=alembic_cfg_path,
        )
