"""Stub-state tests for the disabled cloud-connector ingestion sources.

The S3 and Google Drive sources ship as stubs (see each module's
docstring under ``lfx.base.knowledge_bases.ingestion_sources``). OneDrive
and SharePoint left this set in INT-11: they are registered and resolve
their credentials through a Microsoft connection, and
``test_microsoft_graph_source.py`` covers them. These tests pin the
"intentionally disabled" contract for what remains:

* the classes still import (preserves enum + type compatibility),
* the registry does NOT bind them (``create_source('s3')`` raises),
* the connector catalog endpoint is filtered to the registered sources
  only, so the UI picker doesn't surface a non-functional choice.
"""

from __future__ import annotations

import pytest
from lfx.base.knowledge_bases.ingestion_sources import (
    GoogleDriveSource,
    S3Source,
    SourceType,
    create_source,
    registered_sources,
)

_STUBBED_SOURCES = (
    (SourceType.S3, S3Source),
    (SourceType.GOOGLE_DRIVE, GoogleDriveSource),
)


class TestStubbedSourcesNotRegistered:
    @pytest.mark.parametrize(
        ("source_type", "_source_class"),
        _STUBBED_SOURCES,
        ids=lambda v: v.value if isinstance(v, SourceType) else "cls",
    )
    def test_not_in_registry(self, source_type, _source_class):
        assert source_type not in registered_sources()

    @pytest.mark.parametrize(
        ("source_type", "_source_class"),
        _STUBBED_SOURCES,
        ids=lambda v: v.value if isinstance(v, SourceType) else "cls",
    )
    def test_create_source_raises(self, source_type, _source_class):
        with pytest.raises(ValueError, match="not registered"):
            create_source(source_type, user_id=None, source_config={})


class TestStubbedSourceDirectInstantiation:
    """A direct constructor still produces a class whose ``validate_config``.

    raises ``NotImplementedError`` so any caller that bypasses the registry
    fails fast rather than partially executing.
    """

    @pytest.mark.parametrize(
        ("_source_type", "source_class"),
        _STUBBED_SOURCES,
        ids=lambda v: v.value if isinstance(v, SourceType) else v.__name__,
    )
    @pytest.mark.asyncio
    async def test_validate_config_raises(self, _source_type, source_class):
        instance = source_class(user_id=None, source_config={})
        with pytest.raises(NotImplementedError, match="not available in this build"):
            await instance.validate_config()
