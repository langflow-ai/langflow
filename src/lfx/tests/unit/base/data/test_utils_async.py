"""Tests for the async file-parsing helpers in ``lfx.base.data.utils``."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from lfx.base.data import utils as data_utils
from lfx.base.data.utils import aparallel_load_data, aparse_text_file_to_data
from lfx.schema.data import Data


def _settings(storage_type: str) -> SimpleNamespace:
    return SimpleNamespace(settings=SimpleNamespace(storage_type=storage_type, restrict_local_file_access=False))


class TestAparallelLoadData:
    async def test_results_keep_input_order(self):
        async def load(file_path: str, *, silent_errors: bool) -> Data:  # noqa: ARG001
            # Later files finish first, so gather order alone would not be enough.
            await asyncio.sleep(0.01 * (3 - int(file_path)))
            return Data(data={"file_path": file_path})

        results = await aparallel_load_data(["1", "2", "3"], silent_errors=False, max_concurrency=3, load_function=load)

        assert [result.data["file_path"] for result in results] == ["1", "2", "3"]

    async def test_in_flight_loads_are_bounded(self):
        in_flight = 0
        peak = 0

        async def load(file_path: str, *, silent_errors: bool) -> Data:  # noqa: ARG001
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1
            return Data(data={"file_path": file_path})

        file_paths = [str(i) for i in range(8)]
        await aparallel_load_data(file_paths, silent_errors=False, max_concurrency=2, load_function=load)

        assert peak == 2

    async def test_first_error_is_raised_only_after_every_load_finishes(self):
        finished: list[str] = []

        async def load(file_path: str, *, silent_errors: bool) -> Data:  # noqa: ARG001
            if file_path == "bad":
                msg = "bad file"
                raise ValueError(msg)
            await asyncio.sleep(0.05)
            finished.append(file_path)
            return Data(data={"file_path": file_path})

        with pytest.raises(ValueError, match="bad file"):
            await aparallel_load_data(
                ["bad", "slow-1", "slow-2"], silent_errors=False, max_concurrency=3, load_function=load
            )

        assert sorted(finished) == ["slow-1", "slow-2"]


class TestAparseTextFileToData:
    async def test_local_parse_runs_in_a_worker_thread(self, monkeypatch, tmp_path):
        monkeypatch.setattr(data_utils, "get_settings_service", lambda: _settings("local"))
        text_file = tmp_path / "notes.txt"
        text_file.write_text("local text", encoding="utf-8")
        parse_threads: list[threading.Thread] = []
        real_parse = data_utils.parse_text_file_to_data

        def recording_parse(file_path: str, *, silent_errors: bool):
            parse_threads.append(threading.current_thread())
            return real_parse(file_path, silent_errors=silent_errors)

        monkeypatch.setattr(data_utils, "parse_text_file_to_data", recording_parse)

        result = await aparse_text_file_to_data(str(text_file), silent_errors=False)

        assert result.data["text"] == "local text"
        assert parse_threads
        assert threading.current_thread() not in parse_threads

    async def test_s3_read_is_awaited_without_a_thread_hop(self, monkeypatch):
        storage_service = SimpleNamespace(get_file=AsyncMock(return_value=b'{"key": "value"}'))
        monkeypatch.setattr(data_utils, "get_settings_service", lambda: _settings("s3"))
        monkeypatch.setattr("lfx.base.data.storage_utils.get_settings_service", lambda: _settings("s3"))
        monkeypatch.setattr("lfx.base.data.storage_utils.get_storage_service", lambda: storage_service)

        def _hop(coro):
            coro.close()
            msg = "S3 parse fell back to run_until_complete"
            raise AssertionError(msg)

        monkeypatch.setattr(data_utils, "run_until_complete", _hop)

        result = await aparse_text_file_to_data("user-id/data.json", silent_errors=False)

        assert result.data == {"file_path": "user-id/data.json", "text": '{"key":"value"}'}
        storage_service.get_file.assert_awaited_once_with("user-id", "data.json")
