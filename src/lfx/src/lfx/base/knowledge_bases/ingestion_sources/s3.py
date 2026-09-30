"""AWS S3 ingestion source — stub.

The full S3 implementation has been removed for this phase. Only
``file_upload`` and ``folder`` are exposed in the UI. The ``SourceType.S3``
enum value is preserved so existing ``ingestion_run`` rows referencing
``source_type='s3'`` keep round-tripping, but the class is not
registered with
:func:`lfx.base.knowledge_bases.ingestion_sources.create_source` and
attempting to use it raises ``NotImplementedError``.

When S3 support is reinstated, restore the boto3-backed implementation
(bucket walk, ``fetch_content`` pulling object bytes, credential
resolution via ``variable_service``) and re-register it in
``ingestion_sources/__init__.py``.
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


_DISABLED_MESSAGE = (
    "The S3 knowledge-base ingestion source is not available in this build. "
    "Use the file or folder upload paths instead."
)


class S3Source(KBIngestionSource):
    """Stub kept for type-and-enum compatibility only."""

    source_type = SourceType.S3
    display_name = "Amazon S3"
    description = "Bucket ingestion is disabled in this build."
    icon = "s3"
    requires_credentials = True

    async def validate_config(self) -> None:
        raise NotImplementedError(_DISABLED_MESSAGE)

    async def list_items(self) -> AsyncIterator[IngestionItem]:  # type: ignore[override]
        raise NotImplementedError(_DISABLED_MESSAGE)
        if False:  # pragma: no cover — keeps this an async generator
            yield IngestionItem(item_id="", display_name="")

    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:
        raise NotImplementedError(_DISABLED_MESSAGE)
