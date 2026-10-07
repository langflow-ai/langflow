"""Regression tests: object-storage reads must fail typed when no storage service exists.

``lfx.services.deps.get_storage_service`` is declared ``StorageServiceProtocol | None`` and
genuinely returns ``None`` in a standalone ``lfx`` run: the only ``StorageServiceFactory``
lives in ``langflow``, so ``ServiceManager`` raises ``NoFactoryRegisteredError`` for
``STORAGE_SERVICE`` and ``get_service`` degrades that to ``None``. Every S3 branch below is
reachable in that state -- ``storage_type`` is plain ``LANGFLOW_STORAGE_TYPE`` on lfx's own
``Settings``, so an operator can select it without langflow installed -- and used to die on
``AttributeError: 'NoneType' object has no attribute ...``.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from lfx.base.data.storage_utils import (
    StorageServiceUnavailableError,
    file_exists,
    get_file_size,
    read_file_bytes,
    read_file_text,
    require_storage_service,
    to_storage_path,
)


def _settings(storage_type: str) -> Mock:
    settings_service = Mock()
    settings_service.settings.storage_type = storage_type
    return settings_service


def _storage_service() -> Mock:
    storage = Mock()
    storage.parse_file_path.side_effect = lambda path: tuple(path.removeprefix("files/").rsplit("/", 1))
    storage.get_file = AsyncMock(return_value=b"payload")
    storage.get_file_size = AsyncMock(return_value=7)
    return storage


def _no_storage(module: str = "lfx.base.data.storage_utils"):
    """Patch ``module`` into the standalone-lfx state: S3 selected, no storage service."""
    return (
        patch(f"{module}.get_settings_service", return_value=_settings("s3")),
        patch(f"{module}.get_storage_service", return_value=None),
    )


class TestRequireStorageService:
    """The shared guard used by every S3 branch."""

    def test_returns_the_service_when_present(self):
        storage = _storage_service()

        assert require_storage_service(storage) is storage

    def test_raises_typed_error_when_absent(self):
        with pytest.raises(StorageServiceUnavailableError, match="no storage service is registered"):
            require_storage_service(None)

    def test_is_a_runtime_error_not_a_value_or_file_error(self):
        """``file_exists`` swallows ValueError/FileNotFoundError; this must not be swallowed."""
        assert issubclass(StorageServiceUnavailableError, RuntimeError)
        assert not issubclass(StorageServiceUnavailableError, (ValueError, FileNotFoundError))


class TestToStoragePath:
    def test_raises_typed_error_without_storage_service(self):
        settings_patch, storage_patch = _no_storage()
        with settings_patch, storage_patch, pytest.raises(StorageServiceUnavailableError):
            to_storage_path("files/flow_123/file.txt")

    def test_local_storage_never_touches_the_storage_service(self):
        """The default ``storage_type`` short-circuits, so standalone lfx stays unaffected."""
        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=_settings("local")):
            assert to_storage_path("flow_123/file.txt") == "flow_123/file.txt"

    def test_still_resolves_when_a_storage_service_is_registered(self):
        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=_settings("s3")),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=_storage_service()),
        ):
            assert to_storage_path("files/flow_123/file.txt") == "flow_123/file.txt"


@pytest.mark.asyncio
class TestReadFileBytes:
    async def test_raises_typed_error_without_storage_service(self):
        settings_patch, storage_patch = _no_storage()
        with settings_patch, storage_patch, pytest.raises(StorageServiceUnavailableError):
            await read_file_bytes("flow_123/file.txt")

    async def test_raises_typed_error_when_caller_passes_none_explicitly(self):
        """``storage_service=get_storage_service()`` is a common call shape and yields None."""
        settings_patch, storage_patch = _no_storage()
        with settings_patch, storage_patch, pytest.raises(StorageServiceUnavailableError):
            await read_file_bytes("flow_123/file.txt", storage_service=None)

    async def test_still_reads_when_a_storage_service_is_registered(self):
        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=_settings("s3")),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=_storage_service()),
        ):
            assert await read_file_bytes("flow_123/file.txt") == b"payload"


@pytest.mark.asyncio
class TestReadFileText:
    async def test_raises_typed_error_without_storage_service(self):
        """Delegates to ``read_file_bytes`` under S3, so it inherits the typed failure."""
        settings_patch, storage_patch = _no_storage()
        with settings_patch, storage_patch, pytest.raises(StorageServiceUnavailableError):
            await read_file_text("flow_123/file.txt")


class TestGetFileSize:
    def test_raises_typed_error_without_storage_service(self):
        settings_patch, storage_patch = _no_storage()
        with settings_patch, storage_patch, pytest.raises(StorageServiceUnavailableError):
            get_file_size("flow_123/file.txt")

    def test_still_sizes_when_a_storage_service_is_registered(self):
        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=_settings("s3")),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=_storage_service()),
        ):
            assert get_file_size("flow_123/file.txt") == 7


class TestFileExists:
    def test_propagates_instead_of_reporting_the_file_as_absent(self):
        """A backend that was never configured is a deployment fault, not a missing file.

        ``file_exists`` swallows ``FileNotFoundError``/``ValueError`` into ``False``. If the
        unavailable-storage error were either of those, an unconfigured deployment would look
        exactly like an empty bucket to every caller.
        """
        settings_patch, storage_patch = _no_storage()
        with settings_patch, storage_patch, pytest.raises(StorageServiceUnavailableError):
            file_exists("flow_123/file.txt")

    def test_absent_file_still_reports_false(self):
        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=_settings("s3")),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=_missing_file_storage()),
        ):
            assert file_exists("flow_123/nope.txt") is False


def _missing_file_storage() -> Mock:
    storage = Mock()
    storage.get_file_size = AsyncMock(side_effect=FileNotFoundError("nope"))
    return storage


@pytest.mark.asyncio
class TestFileComponentDoclingDownload:
    """``FileComponent._get_local_file_for_docling`` downloads S3 objects to a temp file."""

    @staticmethod
    def _component():
        from lfx.components.files_and_knowledge.file import FileComponent

        return FileComponent()

    async def test_raises_typed_error_without_storage_service(self):
        module = "lfx.components.files_and_knowledge.file"
        with (
            patch(f"{module}.get_settings_service", return_value=_settings("s3")),
            patch(f"{module}.get_storage_service", return_value=None),
            pytest.raises(StorageServiceUnavailableError),
        ):
            await self._component()._get_local_file_for_docling("flow_123/file.pdf")

    async def test_local_storage_returns_the_path_untouched(self):
        module = "lfx.components.files_and_knowledge.file"
        with patch(f"{module}.get_settings_service", return_value=_settings("local")):
            assert await self._component()._get_local_file_for_docling("/tmp/f.pdf") == ("/tmp/f.pdf", False)


class TestBaseFileComponentCleanup:
    """``BaseFileComponent._delete_after_processing`` deletes the processed S3 object."""

    @staticmethod
    def _component_and_file():
        from lfx.base.data.base_file import BaseFileComponent

        class _Concrete(BaseFileComponent):
            VALID_EXTENSIONS = ["csv"]

            def process_files(self, file_list):
                return file_list

        component = _Concrete()
        component._user_id = "user-1"
        file = Mock()
        file.delete_after_processing = True
        file.cleanup_local_file = False
        file.path = Path("user-1/report.csv")
        return component, file

    def test_raises_typed_error_without_storage_service(self):
        component, file = self._component_and_file()
        module = "lfx.base.data.base_file"
        with (
            patch(f"{module}.get_settings_service", return_value=_settings("s3")),
            patch(f"{module}.get_storage_service", return_value=None),
            pytest.raises(StorageServiceUnavailableError),
        ):
            component._delete_after_processing(file)
