"""Sandbox service for managing secure component execution."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from langflow.services.base import Service

if TYPE_CHECKING:
    from langflow.sandbox import SandboxManager
    from langflow.services.settings.service import SettingsService

from loguru import logger


def is_sandbox_enabled() -> bool:
    """Check if sandbox execution is enabled."""
    return os.getenv("LANGFLOW_SANDBOX_ENABLED", "false").lower() == "true"


class SandboxService(Service):
    """Service for managing sandbox execution and security policies."""

    name = "sandbox_service"

    def __init__(self, settings_service: SettingsService | None = None):
        self._manager: SandboxManager | None = None
        self._settings_service = settings_service
        self._enabled = self._check_sandbox_enabled()
        logger.info(f"SandboxService initialized, enabled: {self._enabled}")

    def _check_sandbox_enabled(self) -> bool:
        """Check if sandbox execution is enabled."""
        return is_sandbox_enabled()

    @property
    def enabled(self) -> bool:
        """Check if sandbox is enabled."""
        return self._enabled

    @property
    def manager(self) -> SandboxManager | None:
        """Get the sandbox manager instance."""
        if not self._enabled:
            return None

        if self._manager is None:
            try:
                from langflow.sandbox import get_sandbox_manager
                from langflow.services.deps import get_db_service

                # Get a sync session for signature initialization
                db_service = get_db_service()
                with db_service.with_sync_session() as session:
                    self._manager = get_sandbox_manager(session)
                logger.info("Sandbox manager initialized successfully")
            except ImportError as e:
                logger.warning(f"Sandbox system not available: {e}")
                self._enabled = False
                return None
            except Exception as e:
                logger.warning(f"Failed to initialize sandbox manager: {e}")
                self._enabled = False
                return None

        return self._manager
