"""Flow-component ingestion source.

Marker source for the ``KnowledgeIngestion`` flow component. The
component drives ingestion itself — DataFrame rows feed directly into
the vector store, no per-item enumeration via ``list_items`` happens.
This class exists solely as a metadata holder so flow-driven ingestions
log through the same ``ingestion_run_service`` seam as file uploads
and folder walks, and therefore show up in the run-history UI.

``list_items`` / ``fetch_content`` are stubbed because they're never
invoked: ``perform_ingestion`` is the only caller that drives them, and
the flow component bypasses ``perform_ingestion`` to write its own
DataFrame-shaped chunks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItem,
    IngestionItemContent,
    KBIngestionSource,
    SourceType,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class FlowComponentSource(KBIngestionSource):
    """Run-history marker for ``KnowledgeIngestion`` flow-component invocations."""

    source_type = SourceType.FLOW_COMPONENT
    display_name = "Knowledge Ingestion Component"
    description = "DataFrame rows ingested via the KnowledgeIngestion flow component."
    icon = "upload"
    requires_credentials = False

    async def list_items(self) -> AsyncIterator[IngestionItem]:
        """Never iterated — the component handles its own item loop."""
        if False:  # pragma: no cover — make this an async generator
            yield  # type: ignore[unreachable]

    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:
        """Never called — the component bypasses fetch_content entirely."""
        msg = "FlowComponentSource does not support fetch_content; the component drives ingestion directly."
        raise NotImplementedError(msg)
