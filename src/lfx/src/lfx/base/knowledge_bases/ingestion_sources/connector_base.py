"""Shared base for cloud-connector ingestion sources.

Cloud connectors (S3, Google Drive, OneDrive, SharePoint, IBM COS)
differ from ``FileUploadSource`` / ``FolderSource`` in two ways:

1. They need **credentials** — resolved from Langflow's
   ``variable_service`` by variable-name reference, not embedded in
   the request payload. Storing variable *names* in ``source_config``
   (instead of the secrets themselves) means the ``ingestion_run``
   row can safely echo the config back to the UI without leaking
   material.

2. They perform **network I/O** to list + fetch items, so per-item
   failures are more common. The generic per-item fetch error-handling
   in ``perform_ingestion`` already records those as FAILED and moves
   on — connectors don't need to reinvent that.

This base class gives connectors a single ``resolve_secret`` helper so
every provider talks to the variable service the same way. No shared
OAuth plumbing here: Phase 3B+ adds a dedicated ``OAuthConnectorBase``
subclass with token-refresh logic once the first OAuth provider lands.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from lfx.base.knowledge_bases.ingestion_sources.base import KBIngestionSource
from lfx.log.logger import logger


class KBConnectorSource(KBIngestionSource):
    """Base class for third-party / cloud ingestion sources."""

    requires_credentials = True

    async def resolve_secret(self, variable_name: str) -> str | None:
        """Return the value of a Langflow variable, or ``None`` if absent.

        Order of resolution:

        1. Langflow's ``variable_service`` scoped to ``self.user_id``.
        2. Process env var of the same name (fallback so desktop /
           single-user deployments can skip the UI step).

        Returns ``None`` when neither source has the value; callers
        decide whether that's fatal. Never raises — config validation
        is the place for hard credential-required errors.
        """
        if not variable_name:
            return None

        user_uuid = self._coerce_user_uuid()
        if user_uuid is not None:
            value = await self._lookup_variable(user_uuid, variable_name)
            if value:
                return value

        env_value = os.environ.get(variable_name)
        return env_value or None

    async def resolve_required_secret(self, variable_name: str) -> str:
        """Like ``resolve_secret`` but raises if missing.

        Use from ``validate_config`` to surface credential errors
        before a background job is spawned.
        """
        value = await self.resolve_secret(variable_name)
        if not value:
            msg = (
                f"Required credential variable {variable_name!r} is not "
                "configured. Set it via Langflow's variable settings or as "
                "an environment variable on the server."
            )
            raise ValueError(msg)
        return value

    def _coerce_user_uuid(self) -> UUID | None:
        """Turn ``self.user_id`` into a ``UUID`` when possible."""
        if self.user_id is None:
            return None
        if isinstance(self.user_id, UUID):
            return self.user_id
        try:
            return UUID(str(self.user_id))
        except (ValueError, TypeError, AttributeError):
            return None

    async def _lookup_variable(self, user_uuid: UUID, variable_name: str) -> str | None:
        """Look up ``variable_name`` through Langflow's variable service.

        Isolated so tests can patch a single seam. Wrapped in a broad
        try/except because the variable service can raise a handful of
        domain errors (missing variable, decryption failure, DB
        unavailable) and the caller treats all of them the same way —
        fall through to the env-var lookup.
        """
        try:
            from lfx.services.deps import get_variable_service, session_scope

            variable_service = get_variable_service()
            if variable_service is None:
                return None
            async with session_scope() as session:
                value = await variable_service.get_variable(
                    user_id=user_uuid,
                    name=variable_name,
                    field="",
                    session=session,
                )
                return str(value) if value else None
        except Exception as exc:  # noqa: BLE001 — any failure → fall back to env
            logger.debug("variable_service lookup for %s failed: %s", variable_name, exc)
            return None

    def describe(self) -> dict[str, Any]:
        """UI snapshot, redacting credential *values* from the config.

        Since connectors store credential *references* in
        ``source_config`` (e.g. ``{"access_key_variable":
        "AWS_ACCESS_KEY_ID"}``), the default describe already leaks
        only variable names. Subclasses can override if they carry
        additional secret-adjacent fields.
        """
        return super().describe()
