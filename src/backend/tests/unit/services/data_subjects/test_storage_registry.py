"""Concurrent writers must retain every owner of a shared SaveToFile directory."""

import multiprocessing
import time
from unittest.mock import patch

from lfx.utils import end_user_storage


def _record_in_worker(config_dir, owner, start):
    read_owners = end_user_storage.end_user_folder_owners

    def delayed_read(*args):
        owners = read_owners(*args)
        time.sleep(0.05)
        return owners

    with patch.object(end_user_storage, "end_user_folder_owners", delayed_read):
        if not start.wait(timeout=10):
            msg = "The concurrent writers were not started"
            raise RuntimeError(msg)
        end_user_storage.record_end_user_folder(config_dir, "a_b", owner)


def test_should_keep_all_owners_when_worker_processes_overlap(tmp_path):
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    workers = [context.Process(target=_record_in_worker, args=(tmp_path, owner, start)) for owner in ("a@b", "a_b")]
    try:
        for worker in workers:
            worker.start()
        start.set()
        for worker in workers:
            worker.join(timeout=20)
            assert worker.exitcode == 0
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)

    assert end_user_storage.end_user_folder_owners(tmp_path, "a_b") == frozenset({"a@b", "a_b"})
