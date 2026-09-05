"""SharePoint ingestion source.

Walks a SharePoint site's default document library through Microsoft
Graph. Credentials come from a Microsoft connection handle in
``source_config["connection"]``; see
:mod:`lfx.base.knowledge_bases.ingestion_sources.microsoft_graph`.
"""

from __future__ import annotations

from lfx.base.knowledge_bases.ingestion_sources.base import SourceType
from lfx.base.knowledge_bases.ingestion_sources.microsoft_graph import MicrosoftGraphSource


class SharePointSource(MicrosoftGraphSource):
    """Ingest files from a SharePoint document library."""

    source_type = SourceType.SHAREPOINT
    display_name = "SharePoint"
    description = "Ingest files from a SharePoint document library through a Microsoft connection."
    icon = "SharePoint"
    requires_credentials = True

    @property
    def site_id(self) -> str:
        value = self.source_config.get("site_id") or ""
        return str(value) if isinstance(value, str) else ""

    @property
    def drive_id(self) -> str:
        value = self.source_config.get("drive_id") or ""
        return str(value) if isinstance(value, str) else ""

    def drive_root(self) -> str:
        if self.drive_id:
            return f"/drives/{self.drive_id}"
        return f"/sites/{self.site_id}/drive"

    def required_connection_scopes(self) -> tuple[str, ...]:
        """A site library is only readable with Sites.Read.All."""
        if self.drive_id:
            return ("Files.Read", "Files.Read.All")
        return ("Files.Read", "Sites.Read.All")

    async def validate_config(self) -> None:
        """A site id (or an explicit drive id) is what names the library."""
        if not self.site_id and not self.drive_id:
            msg = "SharePoint ingestion requires source_config['site_id'] (or an explicit 'drive_id')."
            raise ValueError(msg)
        await super().validate_config()
