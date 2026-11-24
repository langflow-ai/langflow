"""Migration-state reads preserve their bounded regular-file boundary."""

import os

import pytest
from langflow.services.knowledge_base_storage.maintenance import MaintenanceRequiredError
from langflow.services.knowledge_base_storage.migration_io import read_regular_file

pytestmark = pytest.mark.no_blockbuster


def test_state_read_accepts_the_limit_and_rejects_oversized_files(tmp_path):
    state = tmp_path / "inventory.json"
    state.write_bytes(b"1234")
    assert read_regular_file(state, limit=4) == b"1234"
    state.write_bytes(b"12345")
    with pytest.raises(MaintenanceRequiredError, match="size limit"):
        read_regular_file(state, limit=4)


def test_state_read_rejects_symlinks_and_directories(tmp_path):
    state = tmp_path / "inventory.json"
    state.write_bytes(b"{}")
    link = tmp_path / "link"
    link.symlink_to(state)
    for path in (link, tmp_path):
        with pytest.raises(MaintenanceRequiredError):
            read_regular_file(path, limit=4096)


@pytest.mark.skipif(os.name != "posix", reason="POSIX named pipes")
def test_state_read_rejects_fifo_without_waiting_for_a_writer(tmp_path):
    fifo = tmp_path / "inventory.json"
    os.mkfifo(fifo)
    with pytest.raises(MaintenanceRequiredError):
        read_regular_file(fifo, limit=4096)
