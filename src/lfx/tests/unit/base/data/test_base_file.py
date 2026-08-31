"""Tests for BaseFileComponent.load_files_message method."""

import json
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from lfx.base.data.base_file import BaseFileComponent
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.utils.file_path_security import LocalFileAccessError, StorageNamespaceError


class TestFileComponent(BaseFileComponent):
    """Test implementation of BaseFileComponent for testing."""

    VALID_EXTENSIONS = ["txt", "json", "csv"]

    def __init__(self, **data):
        """Initialize with proper component setup."""
        super().__init__(**data)
        # Initialize the inputs to avoid AttributeError
        self.set_attributes(
            {
                "path": [],
                "file_path": None,
                "separator": "\n\n",
                "silent_errors": False,
                "delete_server_file_after_processing": True,
                "ignore_unsupported_extensions": True,
                "ignore_unspecified_files": False,
            }
        )

    def process_files(self, file_list):
        """Test implementation that creates Data objects from file content."""
        processed_files = []
        for file in file_list:
            if file.path.exists():
                content = file.path.read_text(encoding="utf-8")
                # Create Data objects based on file extension
                if file.path.suffix == ".json":
                    try:
                        json_data = json.loads(content)
                        data = Data(data=json_data)
                    except json.JSONDecodeError:
                        data = Data(data={"text": content, "file_path": str(file.path)})
                else:
                    data = Data(data={"text": content, "file_path": str(file.path)})

                file.data = [data]
            processed_files.append(file)
        return processed_files


class TestLoadFilesMessage:
    """Test cases for BaseFileComponent.load_files_message method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.component = TestFileComponent()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def teardown_method(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_load_files_message_empty_data(self):
        """Test load_files_message with no files returns empty Message."""
        # Set empty path
        self.component.path = []
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        # When no files are provided, load_files_core returns [Data()] which has data={}
        # When get_text() returns None/empty, the method falls back to orjson.dumps({})
        assert result.text in {"{}", ""}

    def test_load_files_message_with_simple_text_file(self):
        """Test load_files_message with a simple text file."""
        # Create a simple text file
        text_file = self.temp_path / "simple.txt"
        text_file.write_text("Hello world", encoding="utf-8")

        self.component.path = [str(text_file)]
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        assert result.text == "Hello world"

    def test_load_files_message_with_json_dict_content(self):
        """Test load_files_message with JSON file containing dict (simulates get_text() returning dict)."""
        # Create JSON file with dict content
        json_content = {"content": "dict content", "metadata": "extra info", "type": "test"}
        json_file = self.temp_path / "test.json"
        json_file.write_text(json.dumps(json_content), encoding="utf-8")

        self.component.path = [str(json_file)]
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        # Should contain the JSON content as string
        result_text = result.text
        assert "content" in result_text
        assert "dict content" in result_text
        assert "metadata" in result_text

    def test_load_files_message_with_multiple_files(self):
        """Test load_files_message with multiple files."""
        # Create multiple text files
        file1 = self.temp_path / "first.txt"
        file1.write_text("First text", encoding="utf-8")

        file2 = self.temp_path / "second.txt"
        file2.write_text("Second text", encoding="utf-8")

        self.component.path = [str(file1), str(file2)]
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        assert "First text" in result.text
        assert "Second text" in result.text
        assert "\n\n" in result.text  # Default separator

    def test_load_files_message_with_custom_separator(self):
        """Test load_files_message with custom separator."""
        self.component.separator = " | "

        # Create two text files
        file1 = self.temp_path / "first.txt"
        file1.write_text("First", encoding="utf-8")

        file2 = self.temp_path / "second.txt"
        file2.write_text("Second", encoding="utf-8")

        self.component.path = [str(file1), str(file2)]
        result = self.component.load_files_message()

        assert result.text == "First | Second"

    def test_load_files_message_with_json_complex_structure(self):
        """Test load_files_message with complex JSON structure."""
        complex_data = {
            "metadata": {"type": "document", "version": 1},
            "properties": {"author": "test", "date": "2024-01-01"},
            "content": "This should be extracted",
        }
        json_file = self.temp_path / "complex.json"
        json_file.write_text(json.dumps(complex_data), encoding="utf-8")

        self.component.path = [str(json_file)]
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        # Should contain the extracted content field
        assert "This should be extracted" in result.text

    def test_load_files_message_with_json_no_common_fields(self):
        """Test with JSON that has no common text fields (should use orjson.dumps)."""
        complex_data = {
            "metadata": {"type": "document", "version": 1},
            "properties": {"author": "test", "date": "2024-01-01"},
            # No "text", "content", "value", or "message" fields
        }
        json_file = self.temp_path / "no_text_fields.json"
        json_file.write_text(json.dumps(complex_data), encoding="utf-8")

        self.component.path = [str(json_file)]
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        # Should contain JSON representation since no common text fields found
        assert "metadata" in result.text
        assert "properties" in result.text
        assert "author" in result.text

    def test_load_files_message_with_none_separator(self):
        r"""Test load_files_message when separator is None (should default to \\n\\n)."""
        self.component.separator = None

        file1 = self.temp_path / "first.txt"
        file1.write_text("First", encoding="utf-8")

        file2 = self.temp_path / "second.txt"
        file2.write_text("Second", encoding="utf-8")

        self.component.path = [str(file1), str(file2)]
        result = self.component.load_files_message()

        # Should default to "\n\n" when separator is None
        assert result.text == "First\n\nSecond"

    def test_load_files_message_ensures_all_parts_are_strings(self):
        """Test that the method never tries to join non-string elements (core bug test)."""
        # Create a mixed content scenario - JSON with dict content
        dict_content = {"nested": {"data": "value"}, "another": "dict"}
        json_file = self.temp_path / "mixed_content.json"
        json_file.write_text(json.dumps(dict_content), encoding="utf-8")

        self.component.path = [str(json_file)]

        # This should not raise "sequence item 0: expected str instance, dict found"
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        assert isinstance(result.text, str)
        # Verify the content was properly converted to string
        assert len(result.text) > 0
        assert "nested" in result.text or "another" in result.text

    def test_load_files_message_extract_common_text_fields(self):
        """Test extraction of common text fields like 'content', 'value', 'message'."""
        test_cases = [
            ({"content": "Content text"}, "Content text"),
            ({"value": "Value text"}, "Value text"),
            ({"message": "Message text"}, "Message text"),
            ({"some_field": "ignored", "content": "Content wins"}, "Content wins"),
        ]

        for i, (data_dict, expected_text) in enumerate(test_cases):
            json_file = self.temp_path / f"test_field_{i}.json"
            json_file.write_text(json.dumps(data_dict), encoding="utf-8")

            self.component.path = [str(json_file)]
            result = self.component.load_files_message()

            assert isinstance(result, Message)
            assert expected_text in result.text

    def test_load_files_message_mixed_file_types(self):
        """Test mixed scenarios with text files and JSON files."""
        # Create text file
        text_file = self.temp_path / "text_response.txt"
        text_file.write_text("String response", encoding="utf-8")

        # Create JSON file with dict content
        json_file = self.temp_path / "json_response.json"
        json_file.write_text(json.dumps({"parsed": "Dict content"}), encoding="utf-8")

        # Create JSON file with content field
        content_file = self.temp_path / "content_response.json"
        content_file.write_text(json.dumps({"content": "Field extraction"}), encoding="utf-8")

        self.component.path = [str(text_file), str(json_file), str(content_file)]
        result = self.component.load_files_message()

        assert isinstance(result, Message)
        result_text = result.text
        assert "String response" in result_text
        assert "Field extraction" in result_text
        # JSON content should be present in some form
        assert "parsed" in result_text or "Dict content" in result_text


class TestDeleteAfterProcessingRaceCondition:
    """Tests for race condition when delete_server_file_after_processing=True."""

    def setup_method(self):
        """Set up test fixtures."""
        self.component = TestFileComponent()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def teardown_method(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_concurrent_output_calls_share_processed_result_when_delete_after_processing(self):
        """Concurrent output calls share the cached parsed result after the server file is gone.

        When delete_after_processing=True and the server file has already been deleted by a
        prior output call on the same component instance, load_files_base must return the cached
        processed result so downstream outputs receive the same parsed data instead of empty Data.

        This covers the race condition where a File component with multiple connected outputs
        invokes load_files_base() more than once: the first call processes and deletes the
        server file; the second call must neither raise nor silently drop output data.
        """
        # Create a real file with known content
        server_file = self.temp_path / "server_file.txt"
        server_file.write_text("content", encoding="utf-8")

        # Set up the component with the server file path via file_path Data input
        file_data = Data(data={"file_path": str(server_file)})
        self.component.file_path = file_data
        self.component.delete_server_file_after_processing = True
        self.component.silent_errors = False  # Ensure errors would normally propagate

        # First call: processes and deletes the file
        first_result = self.component.load_files_base()
        assert not server_file.exists(), "File should have been deleted after first call"
        assert first_result, "First call should return non-empty parsed data"

        # Second call: file is already gone; should NOT raise and must NOT drop the data.
        # The cached processed result from the first call should be returned so a second
        # downstream output sees the same content rather than an empty Data wrapper.
        second_result = self.component.load_files_base()
        assert second_result == first_result, (
            "Second call on deleted server file must return the cached processed data "
            "(not an empty list), to preserve output correctness for concurrent outputs."
        )

    def test_validate_raises_for_missing_file_when_not_delete_after_processing(self):
        """When delete_after_processing=False, a missing file should still raise ValueError.

        Exercises the ``file_path`` decision branch in load_files_base (not the ``self.path``
        branch) so the non-race-condition error path is covered for server-file inputs.
        """
        missing_path = self.temp_path / "nonexistent.txt"

        self.component.file_path = Data(data={"file_path": str(missing_path)})
        self.component.delete_server_file_after_processing = False
        self.component.silent_errors = False

        import pytest

        with pytest.raises(ValueError, match="File not found"):
            self.component.load_files_base()

    def test_concurrent_output_calls_are_serialized(self):
        """Concurrent load_files_base() calls on the same instance must share parsed data.

        Exercises the lock + keyed cache path: two threads enter load_files_base at the
        same time. Only one should execute the read+process+delete cycle; the other must
        observe the cached parsed result rather than racing past validation and producing
        empty output.
        """
        server_file = self.temp_path / "concurrent_file.txt"
        server_file.write_text("concurrent-content", encoding="utf-8")

        self.component.file_path = Data(data={"file_path": str(server_file)})
        self.component.delete_server_file_after_processing = True
        self.component.silent_errors = False

        results: list[list[Data]] = []
        errors: list[BaseException] = []
        barrier = threading.Barrier(2)

        def worker():
            try:
                barrier.wait(timeout=5)
                results.append(self.component.load_files_base())
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Concurrent load_files_base() raised: {errors!r}"
        assert len(results) == 2
        assert results[0], "First completed call should return non-empty parsed data"
        assert results[0] == results[1], (
            "Concurrent calls must return identical parsed data — neither caller should "
            "silently fall through to empty output when the other deletes the server file."
        )
        assert not server_file.exists(), "Server file should have been deleted exactly once"

    def test_cache_does_not_pollute_legitimate_empty_input(self):
        """An empty validation result (no input configured) must not return stale cached data.

        Covers the secondary blocker: race-recovery should only activate when validation
        actually skipped a missing ``delete_after_processing=True`` server file, not for
        every empty validation result.
        """
        # Configure a fresh component with no inputs at all.
        self.component.file_path = None
        self.component.path = []
        self.component.delete_server_file_after_processing = True

        # First call has no input → returns empty without populating recovery cache.
        first = self.component.load_files_base()
        assert first == [], "Empty input should yield empty output, not stale cache"

        # Now simulate that a *different* prior call did populate the cache for some
        # other set of paths. The empty-input call must not pick that up.
        cached_data = [Data(data={"text": "stale", "file_path": "/tmp/old.txt"})]
        self.component._load_files_base_processed_cache = {  # type: ignore[attr-defined]
            ((), ("/tmp/old.txt",), False): cached_data,
        }

        second = self.component.load_files_base()
        assert second == [], (
            "Race-recovery must be keyed to the current paths and gated on the "
            "validation-skip flag; an empty input must not return a stale cached result."
        )


class TestS3DeleteAfterProcessingSecurity:
    """Regression tests for storage-aware cleanup of S3-backed server files."""

    @pytest.fixture(autouse=True)
    def _s3_settings(self, monkeypatch, tmp_path):
        settings = SimpleNamespace(
            config_dir=str(tmp_path / "config"),
            database_url="",
            restrict_local_file_access=False,
            storage_type="s3",
        )
        settings_service = SimpleNamespace(settings=settings)
        monkeypatch.setattr("lfx.base.data.base_file.get_settings_service", lambda: settings_service)
        monkeypatch.setattr("lfx.utils.file_path_security.get_settings_service", lambda: settings_service)
        self.settings = settings

    def test_restricted_s3_rejects_out_of_scope_absolute_local_file(self, tmp_path):
        canary = tmp_path / "outside.txt"
        canary.write_text("SAFE_CANARY", encoding="utf-8")

        component = TestFileComponent()
        component._user_id = "user-id"
        component.file_path = Data(data={"file_path": str(canary)})
        component.delete_server_file_after_processing = True
        self.settings.restrict_local_file_access = True

        with pytest.raises(LocalFileAccessError):
            component.load_files_base()

        assert canary.read_text(encoding="utf-8") == "SAFE_CANARY"

    def test_unrestricted_s3_local_file_is_read_but_never_deleted(self, tmp_path):
        canary = tmp_path / "local-input.txt"
        canary.write_text("SAFE_CANARY", encoding="utf-8")

        component = TestFileComponent()
        component.file_path = Data(data={"file_path": str(canary)})
        component.delete_server_file_after_processing = True

        result = component.load_files_base()

        assert result[0].data["text"] == "SAFE_CANARY"
        assert canary.read_text(encoding="utf-8") == "SAFE_CANARY"

    def test_s3_component_temp_file_uses_explicit_local_cleanup(self, monkeypatch, tmp_path):
        temp_file = tmp_path / "component-download.txt"
        temp_file.write_text("SAFE_CANARY", encoding="utf-8")
        storage_service = SimpleNamespace(delete_file=AsyncMock())
        monkeypatch.setattr("lfx.base.data.base_file.get_storage_service", lambda: storage_service, raising=False)

        component = TestFileComponent()
        base_file = BaseFileComponent.BaseFile(
            Data(data={"file_path": str(temp_file)}),
            temp_file,
            delete_after_processing=True,
            cleanup_local_file=True,
        )

        component._delete_after_processing(base_file)

        assert not temp_file.exists()
        storage_service.delete_file.assert_not_awaited()

    def test_s3_user_key_cleanup_uses_storage_service_without_local_unlink(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        local_collision = tmp_path / "user-id" / "file.txt"
        local_collision.parent.mkdir()
        local_collision.write_text("SAFE_CANARY", encoding="utf-8")

        storage_service = SimpleNamespace(delete_file=AsyncMock())
        monkeypatch.setattr("lfx.base.data.base_file.get_storage_service", lambda: storage_service, raising=False)

        component = TestFileComponent()
        component._user_id = "user-id"
        component.file_path = Data(data={"file_path": "user-id/file.txt"})
        component.delete_server_file_after_processing = True

        component.load_files_base()

        storage_service.delete_file.assert_awaited_once_with("user-id", "file.txt")
        assert local_collision.read_text(encoding="utf-8") == "SAFE_CANARY"

    def test_s3_key_cleanup_skips_unscoped_caller(self, monkeypatch):
        """A graph with no user/flow scope keeps the legacy read path but never deletes."""
        storage_service = SimpleNamespace(delete_file=AsyncMock())
        monkeypatch.setattr("lfx.base.data.base_file.get_storage_service", lambda: storage_service, raising=False)

        component = TestFileComponent()
        component.file_path = Data(data={"file_path": "victim-id/file.txt"})
        component.delete_server_file_after_processing = True

        component.load_files_base()

        storage_service.delete_file.assert_not_awaited()

    def test_s3_key_outside_caller_scope_is_rejected_before_any_storage_call(self, monkeypatch):
        """A scoped caller may not address another principal's object prefix at all.

        Cleanup was already scope-gated; the read itself is now rejected too, so the key never
        reaches the storage service.
        """
        storage_service = SimpleNamespace(delete_file=AsyncMock(), get_file=AsyncMock())
        monkeypatch.setattr("lfx.base.data.base_file.get_storage_service", lambda: storage_service, raising=False)

        component = TestFileComponent()
        component._user_id = "attacker-id"
        component.file_path = Data(data={"file_path": "victim-id/file.txt"})
        component.delete_server_file_after_processing = True

        with pytest.raises(StorageNamespaceError, match="outside the authenticated user's"):
            component.load_files_base()

        storage_service.get_file.assert_not_awaited()
        storage_service.delete_file.assert_not_awaited()

    def test_s3_key_cleanup_rejects_flow_id_collision_with_other_user(self, monkeypatch):
        storage_service = SimpleNamespace(delete_file=AsyncMock())
        monkeypatch.setattr("lfx.base.data.base_file.get_storage_service", lambda: storage_service, raising=False)

        component = TestFileComponent()
        component._user_id = "attacker-id"
        component._vertex = SimpleNamespace(
            graph=SimpleNamespace(user_id="attacker-id", flow_id="victim-id"),
        )
        component.file_path = Data(data={"file_path": "victim-id/file.txt"})
        component.delete_server_file_after_processing = True

        component.load_files_base()

        storage_service.delete_file.assert_not_awaited()


class TestStorageKeyNamespaceOwnership:
    """Regression tests for cross-user reads through the ``<namespace>/<file>`` storage key.

    A component input of that shape is resolved against the storage backend rather than the
    local filesystem, so the namespace segment must be checked against the executing graph's
    own scopes. Without that check a caller can read any other user's upload by storage key.
    """

    VICTIM_ID = "11111111-1111-1111-1111-111111111111"
    ATTACKER_ID = "22222222-2222-2222-2222-222222222222"

    @pytest.fixture
    def storage(self, monkeypatch, tmp_path):
        """Local storage rooted at tmp_path with a victim upload already in place."""
        config_dir = tmp_path / "config"
        (config_dir / self.VICTIM_ID).mkdir(parents=True)
        (config_dir / self.VICTIM_ID / "secret.txt").write_text("VICTIM_SECRET", encoding="utf-8")
        (config_dir / self.ATTACKER_ID).mkdir(parents=True)
        (config_dir / self.ATTACKER_ID / "own.txt").write_text("ATTACKER_OWN", encoding="utf-8")
        # A server-managed secret sits alongside the per-principal upload dirs.
        (config_dir / "secret_key").write_text("MASTER_KEY", encoding="utf-8")

        settings = SimpleNamespace(
            config_dir=str(config_dir),
            database_url="",
            # OSS default: local-file containment is OFF. Namespace ownership must hold anyway.
            restrict_local_file_access=False,
            storage_type="local",
        )
        settings_service = SimpleNamespace(settings=settings)
        monkeypatch.setattr("lfx.base.data.base_file.get_settings_service", lambda: settings_service)
        monkeypatch.setattr("lfx.utils.file_path_security.get_settings_service", lambda: settings_service)

        class LocalStorage:
            data_dir = config_dir

            def build_full_path(self, flow_id, file_name):
                return str(Path(config_dir) / flow_id / file_name)

        monkeypatch.setattr("lfx.custom.custom_component.custom_component.get_storage_service", lambda: LocalStorage())
        return settings

    def _attacker_component(self):
        component = TestFileComponent()
        component._user_id = self.ATTACKER_ID
        component.delete_server_file_after_processing = False
        return component

    @pytest.mark.usefixtures("storage")
    def test_other_users_storage_key_is_denied(self):
        component = self._attacker_component()
        component.path = [f"{self.VICTIM_ID}/secret.txt"]

        with pytest.raises(StorageNamespaceError, match="outside the authenticated user's"):
            component.load_files_base()

    @pytest.mark.usefixtures("storage")
    def test_denial_is_not_downgraded_to_a_local_path_read(self):
        """The denial must not fall back to ``resolve_path``, nor be muted by silent_errors."""
        component = self._attacker_component()
        component.silent_errors = True
        component.path = [f"{self.VICTIM_ID}/secret.txt"]

        with pytest.raises(StorageNamespaceError):
            component.load_files_base()

    @pytest.mark.usefixtures("storage")
    def test_traversal_out_of_own_namespace_is_denied(self):
        """An in-scope namespace with a traversal file name would still escape."""
        component = self._attacker_component()
        component.path = [f"{self.ATTACKER_ID}/../{self.VICTIM_ID}/secret.txt"]

        with pytest.raises(StorageNamespaceError, match="path separators or traversal"):
            component.load_files_base()

    @pytest.mark.usefixtures("storage")
    def test_traversal_to_server_secret_is_denied(self):
        component = self._attacker_component()
        component.path = [f"{self.ATTACKER_ID}/../secret_key"]

        with pytest.raises(StorageNamespaceError, match="path separators or traversal"):
            component.load_files_base()

    @pytest.mark.usefixtures("storage")
    def test_own_storage_key_still_resolves(self):
        """The legitimate case must keep working: a user reading their own upload."""
        component = self._attacker_component()
        component.path = [f"{self.ATTACKER_ID}/own.txt"]

        result = component.load_files_base()

        assert [data.data["text"] for data in result] == ["ATTACKER_OWN"]

    @pytest.mark.usefixtures("storage")
    def test_executing_flow_namespace_still_resolves(self, tmp_path):
        """Legacy per-flow uploads are addressed by flow id, which is also an owned scope."""
        flow_id = "33333333-3333-3333-3333-333333333333"
        flow_dir = tmp_path / "config" / flow_id
        flow_dir.mkdir(parents=True)
        (flow_dir / "flow.txt").write_text("FLOW_UPLOAD", encoding="utf-8")

        component = self._attacker_component()
        component._vertex = SimpleNamespace(
            graph=SimpleNamespace(user_id=self.ATTACKER_ID, flow_id=flow_id, source_flow_id=None)
        )
        component.path = [f"{flow_id}/flow.txt"]

        result = component.load_files_base()

        assert [data.data["text"] for data in result] == ["FLOW_UPLOAD"]

    def test_s3_object_key_outside_namespace_is_denied(self, monkeypatch, tmp_path):
        """S3 keys never touch the filesystem, so they need the same namespace check."""
        settings = SimpleNamespace(
            config_dir=str(tmp_path / "config"),
            database_url="",
            restrict_local_file_access=False,
            storage_type="s3",
        )
        monkeypatch.setattr("lfx.base.data.base_file.get_settings_service", lambda: SimpleNamespace(settings=settings))
        monkeypatch.setattr(
            "lfx.utils.file_path_security.get_settings_service", lambda: SimpleNamespace(settings=settings)
        )

        component = self._attacker_component()
        component.path = [f"{self.VICTIM_ID}/secret.txt"]

        with pytest.raises(StorageNamespaceError, match="outside the authenticated user's"):
            component.load_files_base()
