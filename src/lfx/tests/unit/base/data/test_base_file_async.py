"""Tests for the async loader chain on ``BaseFileComponent``.

The chain must (a) await storage-service IO on the caller's loop instead of hopping through
``run_until_complete``, (b) keep existing subclasses that only override sync methods working,
and (c) keep serializing concurrent loads on one instance across threads and coroutines.
"""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from lfx.base.data.base_file import BaseFileComponent
from lfx.base.data.storage_utils import read_file_bytes
from lfx.io import Output
from lfx.schema.data import Data
from lfx.utils.async_helpers import delegates_to, run_until_complete

if TYPE_CHECKING:
    from pathlib import Path

_BASE_INPUTS = {
    "path": [],
    "file_path": None,
    "separator": "\n\n",
    "silent_errors": False,
    "delete_server_file_after_processing": True,
    "ignore_unsupported_extensions": True,
    "ignore_unspecified_files": False,
}


class SyncOnlyFileComponent(BaseFileComponent):
    """A subclass written before the async chain existed: it only knows sync ``process_files``."""

    VALID_EXTENSIONS = ["txt", "csv"]

    def __init__(self, **data):
        super().__init__(**data)
        self.set_attributes(dict(_BASE_INPUTS))
        self.process_threads: list[threading.Thread] = []

    def process_files(self, file_list):
        self.process_threads.append(threading.current_thread())
        for file in file_list:
            file.data = [Data(data={"text": file.path.read_text(encoding="utf-8"), "file_path": str(file.path)})]
        return file_list


class SuperCallingOverride(SyncOnlyFileComponent):
    """Mirrors bundle components that override sync ``load_files_base`` and call ``super()``."""

    def __init__(self, **data):
        super().__init__(**data)
        self.override_calls = 0

    def load_files_base(self):
        self.override_calls += 1
        return super().load_files_base()


class StorageBackedFileComponent(BaseFileComponent):
    """A subclass with native async processing that reads through the storage service."""

    VALID_EXTENSIONS = ["txt", "csv"]

    def __init__(self, **data):
        super().__init__(**data)
        self.set_attributes(dict(_BASE_INPUTS))
        self.process_threads: list[threading.Thread] = []

    @delegates_to("aprocess_files")
    def process_files(self, file_list):
        return run_until_complete(self.aprocess_files(file_list))

    async def aprocess_files(self, file_list):
        self.process_threads.append(threading.current_thread())
        for file in file_list:
            content = await read_file_bytes(str(file.path))
            file.data = [Data(data={"text": content.decode(), "file_path": str(file.path)})]
        return file_list


def _forbid_run_until_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if any loader module falls back to a thread-plus-new-loop hop."""

    def _hop(coro):
        coro.close()
        msg = "async loader chain fell back to run_until_complete"
        raise AssertionError(msg)

    for module in ("lfx.base.data.base_file", "lfx.base.data.storage_utils", "lfx.base.data.utils"):
        monkeypatch.setattr(f"{module}.run_until_complete", _hop)


@pytest.fixture(autouse=True)
def _unrestricted_file_access(monkeypatch):
    settings = SimpleNamespace(restrict_local_file_access=False)
    monkeypatch.setattr("lfx.utils.file_path_security.get_settings_service", lambda: SimpleNamespace(settings=settings))


class TestLocalAsyncChain:
    async def test_async_and_sync_loaders_agree(self, tmp_path):
        text_file = tmp_path / "notes.txt"
        text_file.write_text("hello async", encoding="utf-8")

        async_component = SyncOnlyFileComponent()
        async_component.path = [str(text_file)]
        sync_component = SyncOnlyFileComponent()
        sync_component.path = [str(text_file)]

        async_message = await async_component.aload_files_message()
        sync_message = await asyncio.to_thread(sync_component.load_files_message)

        assert async_message.text == sync_message.text == "hello async"
        assert async_message.data["filename"] == "notes.txt"
        assert async_message.data["file_size"] == len("hello async")

    async def test_sync_only_process_files_runs_off_the_loop(self, tmp_path):
        text_file = tmp_path / "notes.txt"
        text_file.write_text("content", encoding="utf-8")
        component = SyncOnlyFileComponent()
        component.path = [str(text_file)]

        await component.aload_files_message()

        assert component.process_threads
        assert threading.current_thread() not in component.process_threads

    async def test_result_assembly_runs_off_the_loop(self, monkeypatch, tmp_path):
        """Joining rows into a Message or DataFrame is O(rows); it must not stall the loop."""
        text_file = tmp_path / "notes.txt"
        text_file.write_text("assembled", encoding="utf-8")
        component = SyncOnlyFileComponent()
        component.path = [str(text_file)]
        assembly_threads: dict[str, threading.Thread] = {}

        for name in ("_join_message_text", "_data_list_to_dataframe"):
            original = getattr(BaseFileComponent, name)

            def recording(self, data_list, _original=original, _name=name):
                assembly_threads[_name] = threading.current_thread()
                return _original(self, data_list)

            monkeypatch.setattr(SyncOnlyFileComponent, name, recording)

        message = await component.aload_files_message()
        frame = await component.aload_files()

        assert message.text == "assembled"
        assert frame.to_dict("records")[0]["text"] == "assembled"
        assert set(assembly_threads) == {"_join_message_text", "_data_list_to_dataframe"}
        assert threading.current_thread() not in assembly_threads.values()

    async def test_sync_load_files_base_override_calling_super_runs_once(self, tmp_path):
        text_file = tmp_path / "notes.txt"
        text_file.write_text("from override", encoding="utf-8")
        component = SuperCallingOverride()
        component.path = [str(text_file)]

        message = await asyncio.wait_for(component.aload_files_message(), timeout=10)

        assert message.text == "from override"
        assert component.override_calls == 1

    async def test_structured_output_reads_rows_off_the_loop(self, tmp_path):
        csv_file = tmp_path / "table.csv"
        csv_file.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
        component = SyncOnlyFileComponent()
        component.path = [str(csv_file)]

        frame = await component.aload_files_structured()

        assert frame.to_dict("records") == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        assert frame.attrs["source_file_path"] == str(csv_file)


class TestConcurrentLoads:
    async def test_concurrent_coroutines_share_one_processing_pass(self, tmp_path):
        server_file = tmp_path / "server.txt"
        server_file.write_text("shared", encoding="utf-8")
        component = SyncOnlyFileComponent()
        component.file_path = Data(data={"file_path": str(server_file)})

        first, second = await asyncio.gather(component.aload_files_base(), component.aload_files_base())

        assert first == second
        assert first[0].data["text"] == "shared"
        assert len(component.process_threads) == 1
        assert not server_file.exists()

    async def test_coroutine_waits_for_a_thread_holding_the_lock_without_blocking_the_loop(self, tmp_path):
        server_file = tmp_path / "server.txt"
        server_file.write_text("from thread", encoding="utf-8")
        component = SyncOnlyFileComponent()
        component.file_path = Data(data={"file_path": str(server_file)})

        in_process = threading.Event()
        release = threading.Event()
        original_process = component.process_files

        def gated_process(file_list):
            in_process.set()
            assert release.wait(timeout=5), "test never released the sync loader"
            return original_process(file_list)

        component.process_files = gated_process
        sync_results: list = []
        worker = threading.Thread(target=lambda: sync_results.append(component.load_files_base()))
        worker.start()
        assert await asyncio.to_thread(in_process.wait, 5)

        waiter = asyncio.create_task(component.aload_files_base())
        ticks = 0
        for _ in range(5):
            await asyncio.sleep(0.01)
            ticks += 1
        assert ticks == 5
        assert not waiter.done(), "the coroutine must wait for the thread holding the lock"

        release.set()
        async_result = await asyncio.wait_for(waiter, timeout=5)
        await asyncio.to_thread(worker.join, 5)

        assert sync_results == [async_result]
        assert async_result[0].data["text"] == "from thread"

    async def test_cancelled_graph_load_keeps_file_and_lock_until_parser_exits(self, tmp_path):
        server_file = tmp_path / "server.txt"
        server_file.write_text("graph content", encoding="utf-8")
        component = SyncOnlyFileComponent()
        component.file_path = Data(data={"file_path": str(server_file)})
        started = threading.Event()
        release = threading.Event()
        original_process = component.process_files

        def gated_process(file_list):
            started.set()
            assert release.wait(timeout=5), "parser was not released by the test"
            return original_process(file_list)

        component.process_files = gated_process
        output = Output(display_name="Message", name="message", method="load_files_message")
        load = asyncio.create_task(component._get_output_result(output))
        assert await asyncio.to_thread(started.wait, 2)

        try:
            load.cancel()
            with pytest.raises(asyncio.CancelledError):
                await load
            assert component._load_files_base_lock.locked()
            assert server_file.exists()
        finally:
            release.set()

        for _ in range(200):
            if not component._load_files_base_lock.locked():
                break
            await asyncio.sleep(0.01)
        assert not component._load_files_base_lock.locked()
        assert not server_file.exists()

    async def test_sync_loader_rejects_a_held_lock_on_the_callers_loop(self, tmp_path):
        text_file = tmp_path / "notes.txt"
        text_file.write_text("content", encoding="utf-8")
        component = SyncOnlyFileComponent()
        component.path = [str(text_file)]
        started = threading.Event()
        release = threading.Event()
        original_process = component.process_files

        def gated_process(file_list):
            started.set()
            assert release.wait(timeout=5), "parser was not released by the test"
            return original_process(file_list)

        component.process_files = gated_process
        load = asyncio.create_task(component.aload_files_base())
        assert await asyncio.to_thread(started.wait, 2)
        try:
            for sync_loader in (component.load_files_base, component.load_files_message):
                with pytest.raises(RuntimeError, match="synchronous file loader cannot run on an event loop"):
                    sync_loader()
        finally:
            release.set()
        await asyncio.wait_for(load, 5)


class TestS3AsyncChain:
    @pytest.fixture
    def storage(self, monkeypatch, tmp_path):
        settings = SimpleNamespace(
            config_dir=str(tmp_path / "config"),
            database_url="",
            restrict_local_file_access=False,
            storage_type="s3",
        )
        settings_service = SimpleNamespace(settings=settings)
        objects = {("user-id", "notes.txt"): b"stored text", ("user-id", "table.csv"): b"a,b\n1,2\n"}
        storage_service = SimpleNamespace(
            get_file=AsyncMock(side_effect=lambda namespace, name: objects[(namespace, name)]),
            get_file_size=AsyncMock(side_effect=lambda namespace, name: len(objects[(namespace, name)])),
            delete_file=AsyncMock(),
        )
        for module in ("lfx.base.data.base_file", "lfx.base.data.storage_utils", "lfx.base.data.utils"):
            monkeypatch.setattr(f"{module}.get_settings_service", lambda: settings_service, raising=False)
        for module in ("lfx.base.data.base_file", "lfx.base.data.storage_utils"):
            monkeypatch.setattr(f"{module}.get_storage_service", lambda: storage_service, raising=False)
        monkeypatch.setattr("lfx.utils.file_path_security.get_settings_service", lambda: settings_service)
        _forbid_run_until_complete(monkeypatch)
        return storage_service

    async def test_message_awaits_storage_reads_sizes_and_deletes_on_the_loop(self, storage):
        component = StorageBackedFileComponent()
        component._user_id = "user-id"
        component.file_path = Data(data={"file_path": "user-id/notes.txt"})

        message = await component.aload_files_message()

        assert message.text == "stored text"
        assert message.data["file_size"] == len(b"stored text")
        storage.get_file.assert_awaited_once_with("user-id", "notes.txt")
        storage.get_file_size.assert_awaited_once_with("user-id", "notes.txt")
        storage.delete_file.assert_awaited_once_with("user-id", "notes.txt")
        assert component.process_threads == [threading.current_thread()]

    async def test_structured_helper_awaits_the_storage_read(self, storage):
        component = StorageBackedFileComponent()

        rows = await component.aload_files_structured_helper("user-id/table.csv")

        assert rows == [{"a": 1, "b": 2}]
        storage.get_file.assert_awaited_once_with("user-id", "table.csv")

    async def test_unsupported_structured_extension_skips_the_download(self, storage):
        component = StorageBackedFileComponent()

        assert await component.aload_files_structured_helper("user-id/notes.txt") is None
        storage.get_file.assert_not_awaited()


def test_sync_wrappers_still_serve_callers_without_a_loop(tmp_path: Path):
    text_file = tmp_path / "notes.txt"
    text_file.write_text("sync caller", encoding="utf-8")
    component = SyncOnlyFileComponent()
    component.path = [str(text_file)]

    assert component.load_files_message().text == "sync caller"
    assert component.load_files().to_dict("records")[0]["text"] == "sync caller"
