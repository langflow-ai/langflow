"""OneDrive ingestion source.

Walks the connected user's OneDrive, or another drive by id, through
Microsoft Graph. Credentials come from a Microsoft connection handle in
``source_config["connection"]``; see
:mod:`lfx.base.knowledge_bases.ingestion_sources.microsoft_graph`.
"""

from __future__ import annotations

from lfx.base.knowledge_bases.ingestion_sources.base import SourceType
from lfx.base.knowledge_bases.ingestion_sources.microsoft_graph import MicrosoftGraphSource


class OneDriveSource(MicrosoftGraphSource):
    """Ingest files from OneDrive."""

    source_type = SourceType.ONEDRIVE
    display_name = "OneDrive"
    description = "Ingest files from a OneDrive folder through a Microsoft connection."
    icon = "OneDrive"
    requires_credentials = True

    @property
    def drive_id(self) -> str:
        value = self.source_config.get("drive_id") or ""
        return str(value) if isinstance(value, str) else ""

    def drive_root(self) -> str:
        return f"/drives/{self.drive_id}" if self.drive_id else "/me/drive"

    def required_connection_scopes(self) -> tuple[str, ...]:
        """A drive other than the signed-in user's needs Files.Read.All."""
        if self.drive_id:
            return ("Files.Read", "Files.Read.All")
        return ("Files.Read",)
