"""Tests for lfx.fork — fork-safety detection helpers."""

from __future__ import annotations

import threading

import pytest


def test_find_ghost_threads_detects_non_benign_thread():
    from lfx.fork import find_ghost_threads

    stop = threading.Event()
    ghost = threading.Thread(target=stop.wait, name="my-ghost-thread")
    ghost.start()
    try:
        names = [t.name for t in find_ghost_threads()]
        assert "my-ghost-thread" in names
    finally:
        stop.set()
        ghost.join()


def test_benign_named_thread_is_not_a_ghost():
    from lfx.fork import find_ghost_threads

    stop = threading.Event()
    benign = threading.Thread(target=stop.wait, name="OTel-export-worker")
    benign.start()
    try:
        names = [t.name for t in find_ghost_threads()]
        assert "OTel-export-worker" not in names
    finally:
        stop.set()
        benign.join()


def test_fork_safety_report_flags_a_ghost_thread():
    from lfx.fork import fork_safety_report

    stop = threading.Event()
    ghost = threading.Thread(target=stop.wait, name="report-ghost")
    ghost.start()
    try:
        report = fork_safety_report()
        assert "report-ghost" in report.ghost_threads
        assert report.is_clean is False
    finally:
        stop.set()
        ghost.join()


def test_find_ghost_connections_detects_a_real_open_connection():
    """The connection detector must actually flag a live non-LISTEN socket.

    The other connection tests only cover the empty/clean path (no psutil, inspection
    failure). This proves the safety net catches a genuinely fork-hostile connection —
    the exact state the prewarm run path checks for before allowing a fork/snapshot.
    """
    import socket

    pytest.importorskip("psutil")
    from lfx.fork import find_ghost_connections

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(server.getsockname())
    accepted, _ = server.accept()
    try:
        ghosts = find_ghost_connections()
        # The established (non-LISTEN) connection must be reported; the LISTEN socket must not.
        assert ghosts, "expected the open established connection to be detected"
        assert all("LISTEN" not in g for g in ghosts)
    finally:
        accepted.close()
        client.close()
        server.close()


def test_find_ghost_connections_returns_list_without_psutil(monkeypatch):
    import builtins

    from lfx import fork as fork_mod

    real_import = builtins.__import__

    def _no_psutil(name, *args, **kwargs):
        if name == "psutil":
            msg = "no psutil"
            raise ImportError(msg)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_psutil)

    assert fork_mod.find_ghost_connections() == []


def test_fork_safety_report_swallows_connection_inspection_failure(monkeypatch):
    from lfx import fork as fork_mod

    def _boom():
        msg = "permission denied"
        raise RuntimeError(msg)

    monkeypatch.setattr(fork_mod, "find_ghost_connections", _boom)

    report = fork_mod.fork_safety_report()

    assert report.ghost_connections == []


def test_fork_safe_teardown_runs_all_closers_in_order():
    from lfx.fork import fork_safe_teardown

    calls = []
    with fork_safe_teardown(lambda: calls.append("a"), lambda: calls.append("b")):
        calls.append("body")

    assert calls == ["body", "a", "b"]


def test_fork_safe_teardown_runs_closers_even_on_exception():
    from lfx.fork import fork_safe_teardown

    calls = []
    msg = "boom"
    with pytest.raises(ValueError, match="boom"), fork_safe_teardown(lambda: calls.append("closed")):
        raise ValueError(msg)

    assert calls == ["closed"]


def test_fork_safe_teardown_continues_when_a_closer_raises():
    from lfx.fork import fork_safe_teardown

    calls = []

    def bad():
        msg = "closer failed"
        raise RuntimeError(msg)

    with fork_safe_teardown(bad, lambda: calls.append("ok")):
        pass

    assert calls == ["ok"]  # first closer failed (logged), second still ran
