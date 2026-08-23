"""Tests for base/data/storage_utils.py - storage-aware file utilities."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from lfx.base.data.storage_utils import (
    file_exists,
    get_file_size,
    parse_storage_path,
    read_file_bytes,
    read_file_text,
)
from lfx.utils.file_path_security import LocalFileAccessError, enforce_local_file_access


class TestParseStoragePath:
    """Test parse_storage_path function."""

    def test_parse_valid_path(self):
        """Test parsing a valid storage path."""
        result = parse_storage_path("flow_123/myfile.txt")
        assert result == ("flow_123", "myfile.txt")

    def test_parse_path_with_subdirs(self):
        """Test parsing path with subdirectories in filename."""
        result = parse_storage_path("flow_123/subdir/myfile.txt")
        assert result == ("flow_123", "subdir/myfile.txt")

    def test_parse_empty_path(self):
        """Test parsing empty path returns None."""
        assert parse_storage_path("") is None
        assert parse_storage_path(None) is None

    def test_parse_path_no_slash(self):
        """Test parsing path without slash returns None."""
        assert parse_storage_path("just_a_filename.txt") is None

    def test_parse_path_empty_parts(self):
        """Test parsing path with empty parts returns None."""
        assert parse_storage_path("/filename.txt") is None
        assert parse_storage_path("flow_id/") is None
        assert parse_storage_path("/") is None

    def test_parse_path_with_multiple_subdirs(self):
        """Test parsing path with multiple subdirectory levels."""
        result = parse_storage_path("flow_456/dir1/dir2/dir3/file.pdf")
        assert result == ("flow_456", "dir1/dir2/dir3/file.pdf")

    def test_parse_path_with_spaces(self):
        """Test parsing path with spaces in filename."""
        result = parse_storage_path("flow_789/my file with spaces.txt")
        assert result == ("flow_789", "my file with spaces.txt")

    def test_parse_path_with_special_chars(self):
        """Test parsing path with special characters."""
        result = parse_storage_path("flow_abc/file-name_v2.0.txt")
        assert result == ("flow_abc", "file-name_v2.0.txt")


@pytest.mark.asyncio
class TestReadFileBytes:
    """Test read_file_bytes function."""

    async def test_read_local_file(self, tmp_path):
        """Test reading a local file when storage_type is local."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_content = b"Hello, local file!"
        test_file.write_bytes(test_content)

        # Mock settings
        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_bytes(str(test_file))

        assert content == test_content

    async def test_read_local_file_not_found(self):
        """Test reading non-existent local file raises FileNotFoundError."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):  # noqa: SIM117
            with pytest.raises(FileNotFoundError):
                await read_file_bytes("/nonexistent/file.txt")

    async def test_read_s3_file(self):
        """Test reading a file from S3 storage."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()
        expected_content = b"Hello from S3!"
        mock_storage.get_file.return_value = expected_content

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            content = await read_file_bytes("flow_123/test.txt")

        assert content == expected_content
        mock_storage.get_file.assert_called_once_with("flow_123", "test.txt")

    async def test_read_s3_file_invalid_path(self):
        """Test reading S3 file with invalid path format raises ValueError."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):  # noqa: SIM117
            with pytest.raises(ValueError, match="Invalid S3 path format"):
                await read_file_bytes("invalid_path_no_slash")

    async def test_read_s3_file_with_custom_storage_service(self):
        """Test reading S3 file with provided storage service instance."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()
        expected_content = b"Custom storage!"
        mock_storage.get_file.return_value = expected_content

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_bytes("flow_456/custom.txt", storage_service=mock_storage)

        assert content == expected_content
        mock_storage.get_file.assert_called_once_with("flow_456", "custom.txt")

    async def test_s3_mode_with_subdirectories(self):
        """Test S3 mode correctly handles subdirectories in filename."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()
        mock_storage.get_file.return_value = b"Content from subdir"

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            await read_file_bytes("flow_456/subdir1/subdir2/file.txt")

        mock_storage.get_file.assert_called_once_with("flow_456", "subdir1/subdir2/file.txt")

    async def test_should_read_existing_local_file_when_storage_type_is_s3(self, tmp_path):
        """Regression for #13798: a real local file must be read from disk under S3 mode.

        The Langflow Assistant injects an absolute local path (the installed lfx
        components dir) into a Directory node. That path is not an S3 key, so the
        S3 reader must fall back to a local read instead of raising
        "Invalid S3 path format".
        """
        test_file = tmp_path / "_importing.py"
        test_content = b"x = 1\n"
        test_file.write_bytes(test_content)

        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            content = await read_file_bytes(str(test_file))

        assert content == test_content
        mock_storage.get_file.assert_not_called()

    async def test_should_route_relative_key_to_s3_even_if_cwd_file_collides(self, tmp_path, monkeypatch):
        """A relative S3 key must always go to S3, never to a same-named CWD file.

        S3 keys are relative ("flow_id/filename"). The local-file short-circuit is
        absolute-only so a coincidental file under the process CWD can never hijack
        a legitimate S3 fetch (#13798 hardening).
        """
        (tmp_path / "flow_123").mkdir()
        (tmp_path / "flow_123" / "test.txt").write_bytes(b"local decoy")
        monkeypatch.chdir(tmp_path)

        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()
        mock_storage.get_file.return_value = b"from s3"

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            content = await read_file_bytes("flow_123/test.txt")

        assert content == b"from s3"
        mock_storage.get_file.assert_called_once_with("flow_123", "test.txt")


@pytest.mark.asyncio
class TestReadFileText:
    """Test read_file_text function."""

    async def test_read_text_file_default_encoding(self, tmp_path):
        """Test reading text file with default UTF-8 encoding."""
        test_file = tmp_path / "text.txt"
        test_content = "Hello, UTF-8! 你好"
        test_file.write_text(test_content, encoding="utf-8")

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_text(str(test_file))

        assert content == test_content

    async def test_read_text_file_custom_encoding(self, tmp_path):
        """Test reading text file with custom encoding."""
        test_file = tmp_path / "latin1.txt"
        test_content = "Hello, Latin-1!"
        test_file.write_text(test_content, encoding="latin-1")

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_text(str(test_file), encoding="latin-1")

        assert content == test_content

    async def test_read_text_file_from_s3(self):
        """Test reading text file from S3."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()
        expected_content = "S3 text content"
        mock_storage.get_file.return_value = expected_content.encode("utf-8")

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            content = await read_file_text("flow_789/text.txt")

        assert content == expected_content

    async def test_should_read_existing_local_text_file_when_storage_type_is_s3(self, tmp_path):
        """Regression for #13798: read_file_text must read a real local file under S3 mode."""
        test_file = tmp_path / "notes.txt"
        test_content = "hello from disk"
        test_file.write_text(test_content, encoding="utf-8")

        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            content = await read_file_text(str(test_file))

        assert content == test_content
        mock_storage.get_file.assert_not_called()


class TestGetFileSize:
    """Test get_file_size function."""

    def test_get_local_file_size(self, tmp_path):
        """Test getting size of local file."""
        test_file = tmp_path / "sized.txt"
        test_content = b"X" * 1234
        test_file.write_bytes(test_content)

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            size = get_file_size(str(test_file))

        assert size == 1234

    def test_get_local_file_size_not_found(self):
        """Test getting size of non-existent local file raises FileNotFoundError."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):  # noqa: SIM117
            with pytest.raises(FileNotFoundError):
                get_file_size("/nonexistent/file.txt")

    def test_should_get_existing_local_file_size_when_storage_type_is_s3(self, tmp_path):
        """Regression for #13798: get_file_size must stat a real local file under S3 mode."""
        test_file = tmp_path / "sized.txt"
        test_file.write_bytes(b"X" * 1234)

        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            size = get_file_size(str(test_file))

        assert size == 1234
        mock_storage.get_file_size.assert_not_called()

    def test_get_s3_file_size(self):
        """Test getting size of S3 file."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = Mock()

        # Mock async get_file_size to return via asyncio.run
        async def mock_get_size(_flow_id, _filename):
            return 5678

        mock_storage.get_file_size = mock_get_size

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            size = get_file_size("flow_abc/file.bin")

        assert size == 5678

    def test_get_s3_file_size_invalid_path(self):
        """Test getting S3 file size with invalid path raises ValueError."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):  # noqa: SIM117
            with pytest.raises(ValueError, match="Invalid S3 path format"):
                get_file_size("invalid_no_slash")


class TestFileExists:
    """Test file_exists function."""

    def test_file_exists_local_true(self, tmp_path):
        """Test file_exists returns True for existing local file."""
        test_file = tmp_path / "exists.txt"
        test_file.write_bytes(b"content")

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            assert file_exists(str(test_file)) is True

    def test_file_exists_local_false(self):
        """Test file_exists returns False for non-existent local file."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            assert file_exists("/nonexistent/file.txt") is False

    def test_file_exists_s3_true(self):
        """Test file_exists returns True for existing S3 file."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = Mock()

        async def mock_get_size(_flow_id, _filename):
            return 100

        mock_storage.get_file_size = mock_get_size

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            assert file_exists("flow_def/exists.txt") is True

    def test_file_exists_s3_false(self):
        """Test file_exists returns False for non-existent S3 file."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = Mock()

        async def mock_get_size(_flow_id, _filename):
            raise FileNotFoundError

        mock_storage.get_file_size = mock_get_size

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            assert file_exists("flow_ghi/nonexistent.txt") is False

    def test_file_exists_invalid_path(self):
        """Test file_exists returns False for invalid S3 path."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            assert file_exists("invalid_no_slash") is False


@pytest.mark.asyncio
class TestStorageUtilsEdgeCases:
    """Test edge cases and special scenarios."""

    async def test_read_binary_content(self, tmp_path):
        """Test reading binary content."""
        test_file = tmp_path / "binary.bin"
        binary_content = bytes(range(256))
        test_file.write_bytes(binary_content)

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_bytes(str(test_file))

        assert content == binary_content

    async def test_read_binary_file_with_null_bytes(self, tmp_path):
        """Test reading binary file with null bytes."""
        test_file = tmp_path / "binary.bin"
        binary_content = b"\x00\x01\x02\xff\xfe\xfd"
        test_file.write_bytes(binary_content)

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_bytes(str(test_file))

        assert content == binary_content

    async def test_read_empty_file(self, tmp_path):
        """Test reading empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            content = await read_file_bytes(str(test_file))

        assert content == b""

    async def test_s3_path_with_unicode_filename(self):
        """Test S3 path with unicode characters in filename."""
        mock_settings = Mock()
        mock_settings.settings.storage_type = "s3"

        mock_storage = AsyncMock()
        mock_storage.get_file.return_value = b"Content"

        with (
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=mock_storage),
        ):
            content = await read_file_bytes("flow_123/文件名.txt")

        assert content == b"Content"
        mock_storage.get_file.assert_called_once_with("flow_123", "文件名.txt")


class TestStorageUtilsSyncEdgeCases:
    """Test sync edge cases and special scenarios."""

    def test_get_size_empty_file(self, tmp_path):
        """Test getting size of empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        mock_settings = Mock()
        mock_settings.settings.storage_type = "local"

        with patch("lfx.base.data.storage_utils.get_settings_service", return_value=mock_settings):
            size = get_file_size(str(test_file))

        assert size == 0


class _S3RestrictedEnv:
    """Settings fixture for the S3 + LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS combination.

    ``storage_utils`` and ``file_path_security`` each resolve settings through their own
    module-level ``get_settings_service`` import, so both must be patched to model a
    deployment that runs object storage with local-file containment enabled.
    """

    def __init__(self, config_dir: Path, *, storage_type: str = "s3", restricted: bool = True):
        self.config_dir = config_dir
        self.storage_type = storage_type
        self.restricted = restricted

    def __enter__(self):
        settings = Mock()
        settings.settings.storage_type = self.storage_type
        settings.settings.restrict_local_file_access = self.restricted
        settings.settings.config_dir = str(self.config_dir)
        settings.settings.database_url = ""
        self._patches = [
            patch("lfx.base.data.storage_utils.get_settings_service", return_value=settings),
            patch("lfx.utils.file_path_security.get_settings_service", return_value=settings),
            patch("lfx.base.data.storage_utils.get_storage_service", return_value=AsyncMock()),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()
        return False


def _scoped_resolver(scope_ids):
    """Mimic the ``resolve_path`` callback components hand to the storage-aware readers."""

    def _resolve(path: str) -> str:
        return str(enforce_local_file_access(path, scope_ids=scope_ids))

    return _resolve


@pytest.fixture
def restricted_layout(tmp_path):
    """config_dir with an in-scope upload, a reserved secret, and an out-of-scope target."""
    config_dir = tmp_path / "config"
    (config_dir / "flow-id").mkdir(parents=True)
    (config_dir / "flow-id" / "upload.csv").write_bytes(b"col\nin-scope\n")
    (config_dir / "secret_key").write_bytes(b"fernet-master-key")  # pragma: allowlist secret
    outside = tmp_path / "outside" / "target.csv"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(b"col\nsecret-value\n")
    return config_dir, outside


@pytest.mark.asyncio
class TestRestrictedLocalFileAccessUnderS3:
    """LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS must hold on the S3 storage branch too.

    The S3 reader short-circuits to a direct local read for absolute paths that exist on
    disk (the #13798 escape hatch). That short-circuit must still go through the local-file
    containment control, otherwise the documented hardening flag is a no-op whenever
    ``LANGFLOW_STORAGE_TYPE=s3``.
    """

    async def test_read_file_bytes_denies_out_of_scope_path_with_resolver(self, restricted_layout):
        """A component-supplied resolver must be honored on the S3 local-read branch."""
        config_dir, outside = restricted_layout
        with _S3RestrictedEnv(config_dir), pytest.raises(LocalFileAccessError):
            await read_file_bytes(str(outside), resolve_path=_scoped_resolver(["flow-id"]))

    async def test_read_file_bytes_denies_out_of_scope_path_without_resolver(self, restricted_layout):
        """Callers that pass no resolver must still not escape the storage root."""
        config_dir, outside = restricted_layout
        with _S3RestrictedEnv(config_dir), pytest.raises(LocalFileAccessError):
            await read_file_bytes(str(outside))

    async def test_read_file_bytes_local_storage_negative_control(self, restricted_layout):
        """Negative control: the same read on local storage is already refused."""
        config_dir, outside = restricted_layout
        with _S3RestrictedEnv(config_dir, storage_type="local"), pytest.raises(LocalFileAccessError):
            await read_file_bytes(str(outside), resolve_path=_scoped_resolver(["flow-id"]))

    async def test_read_file_bytes_allows_in_scope_path(self, restricted_layout):
        """Positive case: a path inside the caller's storage scope still reads."""
        config_dir, _ = restricted_layout
        in_scope = config_dir / "flow-id" / "upload.csv"
        with _S3RestrictedEnv(config_dir):
            content = await read_file_bytes(str(in_scope), resolve_path=_scoped_resolver(["flow-id"]))
        assert content == b"col\nin-scope\n"

    async def test_read_file_bytes_denies_reserved_secret_key(self, restricted_layout):
        """The reserved-secret denial must run on the S3 branch.

        ``secret_key`` sits directly under config_dir, so a containment check alone would
        admit it; ``_reserved_secret_paths`` is what refuses it. That logic lives inside
        ``enforce_local_file_access``, so it only runs if the S3 branch calls the control.
        """
        config_dir, _ = restricted_layout
        with _S3RestrictedEnv(config_dir), pytest.raises(LocalFileAccessError):
            await read_file_bytes(str(config_dir / "secret_key"))

    async def test_read_file_text_denies_out_of_scope_path(self, restricted_layout):
        """read_file_text delegates to read_file_bytes under S3 and inherits the guard."""
        config_dir, outside = restricted_layout
        with _S3RestrictedEnv(config_dir), pytest.raises(LocalFileAccessError):
            await read_file_text(str(outside), resolve_path=_scoped_resolver(["flow-id"]), newline="")

    async def test_symlink_alias_cannot_launder_an_out_of_scope_target(self, restricted_layout):
        """A .csv-named symlink inside the storage scope must not reach an outside target."""
        config_dir, outside = restricted_layout
        link = config_dir / "flow-id" / "alias.csv"
        link.symlink_to(outside)
        with _S3RestrictedEnv(config_dir), pytest.raises(LocalFileAccessError):
            await read_file_bytes(str(link), resolve_path=_scoped_resolver(["flow-id"]))

    async def test_unrestricted_s3_still_reads_local_component_paths(self, restricted_layout):
        """#13798 must keep working: with the flag off the escape hatch is unchanged."""
        config_dir, outside = restricted_layout
        with _S3RestrictedEnv(config_dir, restricted=False):
            content = await read_file_bytes(str(outside))
        assert content == b"col\nsecret-value\n"


class TestRestrictedLocalFileAccessUnderS3Sync:
    """The sync size/existence probes share the same short-circuit."""

    def test_get_file_size_denies_out_of_scope_path(self, restricted_layout):
        config_dir, outside = restricted_layout
        with _S3RestrictedEnv(config_dir), pytest.raises(LocalFileAccessError):
            get_file_size(str(outside))

    def test_file_exists_does_not_probe_out_of_scope_paths(self, restricted_layout):
        config_dir, outside = restricted_layout
        with _S3RestrictedEnv(config_dir):
            assert file_exists(str(outside)) is False

    def test_get_file_size_allows_in_scope_path(self, restricted_layout):
        config_dir, _ = restricted_layout
        with _S3RestrictedEnv(config_dir):
            assert get_file_size(str(config_dir / "flow-id" / "upload.csv")) == len(b"col\nin-scope\n")

    def test_unrestricted_s3_size_probe_unchanged(self, restricted_layout):
        config_dir, outside = restricted_layout
        with _S3RestrictedEnv(config_dir, restricted=False):
            assert get_file_size(str(outside)) == len(b"col\nsecret-value\n")
