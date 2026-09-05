"""Stub-state tests for the disabled cloud-connector ingestion sources.

The S3 / OneDrive / SharePoint sources ship as stubs in this phase (see
each module's docstring under
``lfx.base.knowledge_bases.ingestion_sources``). These tests pin the
"intentionally disabled" contract:

* the classes still import (preserves enum + type compatibility),
* the registry does NOT bind them (``create_source('s3')`` raises),
* the connector catalog endpoint is filtered to the registered sources
  only, so the UI picker doesn't surface a non-functional choice.

Google Drive left this list in INT-10: it is implemented against managed
connections, but stays unregistered by default until execution principals are
stamped on background jobs. Its own behaviour is covered in
``src/lfx/tests/unit/base/knowledge_bases/test_google_drive_source.py``; what is
kept here is the half that still holds — the picker must not offer it.
"""

from __future__ import annotations

import pytest
from lfx.base.knowledge_bases.ingestion_sources import (
    GOOGLE_DRIVE_SOURCE_REGISTERED,
    GoogleDriveSource,
    OneDriveSource,
    S3Source,
    SharePointSource,
    SourceType,
    create_source,
    registered_sources,
)

_STUBBED_SOURCES = (
    (SourceType.S3, S3Source),
    (SourceType.ONEDRIVE, OneDriveSource),
    (SourceType.SHAREPOINT, SharePointSource),
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


class TestGoogleDriveSourceIsImplementedButUnregistered:
    """Google Drive is real code that the picker still must not offer.

    Registering it before background jobs carry an execution principal would put
    an entry in the connector catalog whose every run fails closed. The opt-in
    switch is documented in ``ingestion_sources/__init__.py``.
    """

    def test_not_in_the_default_registry(self):
        """Registration is decided at import, so compare against that decision.

        ``LANGFLOW_KB_GOOGLE_DRIVE_ENABLED`` is read once when the registry module is
        imported and a test cannot undo the result, so a machine with the opt-in switch
        set would fail a bare "not registered" assertion for a legitimate reason.
        """
        assert GOOGLE_DRIVE_SOURCE_REGISTERED is False, (
            "This suite pins the default build. Unset LANGFLOW_KB_GOOGLE_DRIVE_ENABLED to run it."
        )
        assert SourceType.GOOGLE_DRIVE not in registered_sources()

    def test_create_source_raises(self):
        assert GOOGLE_DRIVE_SOURCE_REGISTERED is False, (
            "This suite pins the default build. Unset LANGFLOW_KB_GOOGLE_DRIVE_ENABLED to run it."
        )
        with pytest.raises(ValueError, match="not registered"):
            create_source(SourceType.GOOGLE_DRIVE, user_id=None, source_config={})

    @pytest.mark.asyncio
    async def test_validate_config_asks_for_a_connection_rather_than_raising_not_implemented(self):
        instance = GoogleDriveSource(user_id=None, source_config={})
        with pytest.raises(ValueError, match="requires a managed Google connection"):
            await instance.validate_config()
