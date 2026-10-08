"""Real disposable processes qualify controller stop, backup, launch and resume."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sqlite3
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest
from langflow.services.knowledge_base_storage import controller, maintenance

pytestmark = [pytest.mark.no_blockbuster, pytest.mark.skipif(os.name != "posix", reason="POSIX controller")]

# File existence signals readiness, so subprocesses must publish complete JSON atomically.
_SERVER = """
import http.server, json, os, pathlib, sys
port, ready, environment = int(sys.argv[1]), pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
names = ('LANGFLOW_DATABASE_URL', 'LANGFLOW_KNOWLEDGE_BASES_DIR')
pending = environment.with_suffix('.tmp')
pending.write_text(json.dumps({k: v for k, v in os.environ.items() if k.startswith('LANGFLOW_KB_') or k in names}))
pending.replace(environment)
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if ready.exists() else 503)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}' if ready.exists() else b'{"status":"pending"}')
    def log_message(self, *args): pass
http.server.HTTPServer(('127.0.0.1', port), Handler).serve_forever()
"""
_SUPERVISOR = """
import json, pathlib, subprocess, sys, time
import psutil
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])
identity = pathlib.Path(sys.argv[1])
pending = identity.with_suffix('.tmp')
pending.write_text(json.dumps({'pid': child.pid, 'created': psutil.Process(child.pid).create_time()}))
pending.replace(identity)
time.sleep(300)
"""


async def _until(predicate, timeout=10):
    """Wait with a deadline for a disposable process to reach the required state."""
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            pytest.fail("Disposable process did not reach the expected state")
        await asyncio.sleep(0.025)


@pytest.fixture
async def installation(tmp_path, monkeypatch):
    """Create an isolated supervisor family, storage source and replacement listener."""
    if os.getuid() == 0:
        pytest.skip("The production controller deliberately requires the non-root application account")
    root = tmp_path / "vectors"
    root.mkdir()
    database = tmp_path / "metadata.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE marker (value TEXT)")
        connection.execute("INSERT INTO marker VALUES ('preserved')")
    source = root / "owner" / "knowledge"
    source.mkdir(parents=True)
    (source / "chroma.sqlite3").write_bytes(b"synthetic retained source")
    old = await asyncio.create_subprocess_exec(
        sys.executable, "-c", _SUPERVISOR, str(tmp_path / "child.json"), start_new_session=True
    )
    await _until(lambda: (tmp_path / "child.json").exists())
    child = json.loads((tmp_path / "child.json").read_text())
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    ready = tmp_path / "ready"
    environment = tmp_path / "environment.json"
    options = {
        "root": root,
        "database": database,
        "state": tmp_path / "state",
        "supervisor": {"pid": old.pid, "created": psutil.Process(old.pid).create_time()},
        "command": [sys.executable, "-c", _SERVER, str(port), str(ready), str(environment)],
        "cwd": tmp_path,
        "port": port,
        "stop_timeout": 0.5,
        "readiness_timeout": 8,
        "external_restarts_disabled": True,
    }
    staged = []

    async def stage():
        """Record that helper staging occurs while the old supervisor is still alive."""
        staged.append(controller._process(options["supervisor"]) is not None)

    monkeypatch.setattr(controller, "stage_helper", stage)
    process_iter = psutil.process_iter

    def installation_processes():
        """Keep the real process checks inside this disposable installation."""
        selected = {old.pid, child["pid"]}
        sessions = {old.pid}
        if options["state"].exists():
            sessions.update(controller._read(path)["pid"] for path in options["state"].glob("launch-*.json"))
        for process in process_iter():
            try:
                if process.pid in selected or os.getsid(process.pid) in sessions:
                    yield process
            except (psutil.NoSuchProcess, ProcessLookupError):
                continue

    monkeypatch.setattr(psutil, "process_iter", installation_processes)
    monkeypatch.setenv(
        "LANGFLOW_KB_MIGRATION_HELPER_IMAGE", "ghcr.io/langflow-ai/langflow-chroma-migration@sha256:" + "a" * 64
    )
    for name in controller._HELPER_ENV[1:]:
        monkeypatch.delenv(name, raising=False)
    yield options, ready, environment, child, staged
    # Teardown is restricted to this fixture's exact recorded identities.
    identities = [options["supervisor"], child]
    if options["state"].exists():
        identities.extend(controller._read(path) for path in options["state"].glob("launch-*.json"))
    for identity in identities:
        process = controller._process(identity)
        if process is not None:
            process.kill()
    await old.wait()
    await asyncio.sleep(0.1)


async def test_real_worker_family_backup_launch_and_idempotent_resume(installation):
    """Stop the exact worker family, verify backups and resume without another launch."""
    options, ready, environment, child, staged = installation
    ready.touch()
    result = await controller.upgrade(**options)
    assert result["phase"] == "ready"
    assert staged == [True]
    assert controller._process(options["supervisor"]) is None
    assert controller._process(child) is None
    receipt = maintenance.validate_receipt(
        root=options["root"], database=options["database"], receipt=Path(result["receipt"])
    )
    assert {item["pid"] for item in receipt["stopped_processes"]} == {options["supervisor"]["pid"], child["pid"]}
    with sqlite3.connect(receipt["backup"]) as connection:
        assert connection.execute("SELECT value FROM marker").fetchone() == ("preserved",)
    assert receipt["sources"]["owner/knowledge"] == maintenance.tree_fingerprint(options["root"] / "owner/knowledge")
    received = json.loads(environment.read_text())
    assert received["LANGFLOW_KB_UPGRADE_RECEIPT"] == result["receipt"]
    assert received["LANGFLOW_DATABASE_URL"] == f"sqlite:///{options['database']}"
    assert received["LANGFLOW_KNOWLEDGE_BASES_DIR"] == str(options["root"])
    assert (
        received["LANGFLOW_KB_MIGRATION_HELPER_IMAGE"]
        == result["config"]["helper"]["LANGFLOW_KB_MIGRATION_HELPER_IMAGE"]
    )
    resumed = await controller.upgrade(**options)
    assert resumed["application"] == result["application"]
    assert len(list(options["state"].glob("launch-*.json"))) == 1


async def test_stale_pid_and_current_session_cannot_stop_processes(installation):
    """Reject stale identities and the controller's own session before stopping workers."""
    options, _, _, child, staged = installation
    with pytest.raises(controller.UpgradeControllerError, match="stale"):
        await controller.upgrade(**{**options, "supervisor": {**options["supervisor"], "created": 1}})
    with pytest.raises(controller.UpgradeControllerError, match="independent"):
        await controller.upgrade(**{**options, "supervisor": controller._identity(psutil.Process())})
    assert not staged
    assert controller._process(options["supervisor"]) is not None
    assert controller._process(child) is not None


async def test_signature_staging_failure_occurs_before_downtime(installation, monkeypatch):
    """Leave the old service running when helper signature verification fails."""
    options, _, _, child, _ = installation

    async def fail():
        """Reject helper staging before any worker termination."""
        msg = "signature rejected"
        raise controller.helper.MigrationHelperError(msg)

    monkeypatch.setattr(controller, "stage_helper", fail)
    with pytest.raises(controller.helper.MigrationHelperError, match="signature"):
        await controller.upgrade(**options)
    assert controller._process(options["supervisor"]) is not None
    assert controller._process(child) is not None
    assert controller._read(options["state"] / "upgrade.json")["phase"] == "prepared"


async def test_readiness_requires_owned_listener_and_recovers_same_new_process(installation):
    """Resume readiness checks against the same recorded replacement process."""
    options, ready, _, _, _ = installation
    with pytest.raises(controller.UpgradeControllerError, match="Readiness timed out"):
        await controller.upgrade(**{**options, "readiness_timeout": 1})
    journal = controller._read(options["state"] / "upgrade.json")
    assert journal["phase"] == "started"
    assert controller._process(journal["application"]) is not None
    ready.touch()
    resumed = await controller.upgrade(**options)
    assert resumed["application"] == journal["application"]


async def test_cancellation_during_readiness_resumes_without_duplicate_launch(installation):
    """Preserve the replacement identity when readiness waiting is cancelled."""
    options, ready, environment, _, _ = installation
    task = asyncio.create_task(controller.upgrade(**options))
    await _until(environment.exists)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    journal = controller._read(options["state"] / "upgrade.json")
    ready.touch()
    resumed = await controller.upgrade(**options)
    assert resumed["application"] == controller._read(Path(journal["launch"]))
    assert len(list(options["state"].glob("launch-*.json"))) == 1


async def test_backup_failure_retains_stopped_state_and_resumes(installation, monkeypatch):
    """Resume from a durable stopped state after backup creation fails."""
    options, ready, _, _, _ = installation
    original = maintenance.create_receipt

    def fail(**_kwargs):
        """Simulate a failed backup after the old worker family has stopped."""
        msg = "backup failed"
        raise maintenance.MaintenanceRequiredError(msg)

    monkeypatch.setattr(maintenance, "create_receipt", fail)
    with pytest.raises(maintenance.MaintenanceRequiredError, match="backup failed"):
        await controller.upgrade(**options)
    journal = controller._read(options["state"] / "upgrade.json")
    assert journal["phase"] == "stopped"
    assert controller._process(options["supervisor"]) is None
    assert not list(options["state"].glob("launch-*.json"))
    monkeypatch.setattr(maintenance, "create_receipt", original)
    ready.touch()
    assert (await controller.upgrade(**options))["phase"] == "ready"


async def test_changed_instance_or_command_cannot_resume_journal(installation, monkeypatch):
    """Require the original instance and launch command when resuming a journal."""
    options, _, _, _, _ = installation

    async def fail():
        """Stop preparation at helper staging so resume configuration can be checked."""
        msg = "staging failed"
        raise controller.helper.MigrationHelperError(msg)

    monkeypatch.setattr(controller, "stage_helper", fail)
    with pytest.raises(controller.helper.MigrationHelperError):
        await controller.upgrade(**options)
    with pytest.raises(controller.UpgradeControllerError, match="original instance"):
        await controller.upgrade(**{**options, "command": [sys.executable, "-c", "pass"]})
    assert controller._process(options["supervisor"]) is not None


async def test_busy_unrelated_port_does_not_stop_old_workers(installation):
    """Reject an occupied readiness port before taking the old service down."""
    options, _, _, _, _ = installation
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", options["port"]))
        listener.listen()
        with pytest.raises(OSError, match="Address already in use"):
            await controller.upgrade(**options)
    assert controller._process(options["supervisor"]) is not None


async def test_external_restart_contract_is_required(installation):
    """Require external restarters to be disabled before controlled shutdown."""
    options, _, _, _, _ = installation
    with pytest.raises(controller.UpgradeControllerError, match="restarters"):
        await controller.upgrade(**{**options, "external_restarts_disabled": False})
    assert controller._process(options["supervisor"]) is not None


async def test_atomic_exclusive_launch_record_rejects_duplicate(tmp_path):
    """Preserve the first launch identity when an exclusive write is repeated."""
    path = tmp_path / "launch.json"
    identity = controller._identity(psutil.Process())
    controller._write(path, identity, exclusive=True)
    with pytest.raises(FileExistsError):
        controller._write(path, {"pid": 12, "created": 123}, exclusive=True)
    assert controller._read(path) == identity


async def test_cancellation_drains_worker_stop_and_resumes_after_barrier(installation, monkeypatch):
    """Finish the worker stop barrier before cancellation releases controller ownership."""
    options, ready, _, _, _ = installation
    entered, release = threading.Event(), threading.Event()
    original = controller._stop

    def delayed(*args):
        """Hold worker termination until the test releases the cancellation barrier."""
        entered.set()
        assert release.wait(10)
        original(*args)

    monkeypatch.setattr(controller, "_stop", delayed)
    task = asyncio.create_task(controller.upgrade(**options))
    await _until(entered.is_set)
    task.cancel()
    await asyncio.sleep(0.05)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    journal = controller._read(options["state"] / "upgrade.json")
    assert journal["phase"] == "stopped"
    assert controller._process(options["supervisor"]) is None
    ready.touch()
    assert (await controller.upgrade(**options))["phase"] == "ready"


async def test_dead_new_process_requires_explicit_forward_restart(installation):
    """Require an explicit restart after a recorded replacement exits."""
    options, ready, _, _, _ = installation
    ready.touch()
    first = await controller.upgrade(**options)
    process = controller._process(first["application"])
    process.kill()
    await _until(lambda: controller._process(first["application"]) is None)
    with pytest.raises(controller.UpgradeControllerError, match="exited"):
        await controller.upgrade(**options)
    resumed = await controller.upgrade(**options, restart_new=True)
    assert resumed["application"] != first["application"]
    assert resumed["receipt"] == first["receipt"]
    assert len(list(options["state"].glob("launch-*.json"))) == 2


async def test_new_application_cannot_claim_unrelated_listener(installation):
    """Refuse readiness attribution to a listener outside the recorded worker family."""
    options, _, _, _, _ = installation
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", options["port"]))
        listener.listen()
        assert not controller._owns_listener(options["supervisor"], options["port"])


async def test_session_escape_is_rejected_before_any_termination(installation, monkeypatch):
    """Reject a child that escaped its supervisor session before stopping any process."""
    options, _, _, child, _ = installation
    original = controller.os.getsid

    def escaped(pid):
        """Report an escaped session only for the fixture's recorded child."""
        return child["pid"] if pid == child["pid"] else original(pid)

    monkeypatch.setattr(controller.os, "getsid", escaped)
    with pytest.raises(controller.UpgradeControllerError, match="escaped"):
        await controller.upgrade(**options)
    assert controller._process(options["supervisor"]).status() != psutil.STATUS_STOPPED
    assert controller._process(child) is not None
    assert controller._read(options["state"] / "upgrade.json")["phase"] == "prepared"


@pytest.mark.parametrize(
    ("status", "expected"), [(psutil.STATUS_ZOMBIE, False), (psutil.STATUS_DEAD, False), (psutil.STATUS_RUNNING, True)]
)
def test_receipt_worker_barrier_accepts_exited_unreaped_workers(monkeypatch, status, expected):
    """Treat dead and zombie workers as stopped despite their unreaped identities."""
    process = SimpleNamespace(status=lambda: status, create_time=lambda: 1234)
    monkeypatch.setattr(maintenance.psutil, "Process", lambda _pid: process)
    assert maintenance._process_matches({"pid": 123, "created": 1234}) is expected


async def test_forward_restart_rejects_surviving_new_workers(installation):
    """Prevent a replacement restart while its orphaned workers remain alive."""
    options, ready, _, _, _ = installation
    child_file = options["cwd"] / "new-child.json"
    spawn = "\n".join(
        [
            "import subprocess, psutil, json, pathlib, sys",
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])",
            "identity = {'pid': child.pid, 'created': psutil.Process(child.pid).create_time()}",
            f"pathlib.Path({str(child_file)!r}).write_text(json.dumps(identity))",
        ]
    )
    options["command"][2] = spawn + "\n" + _SERVER
    ready.touch()
    first = await controller.upgrade(**options)
    child = json.loads(child_file.read_text())
    try:
        controller._process(first["application"]).kill()
        await _until(lambda: controller._process(first["application"]) is None)
        with pytest.raises(controller.UpgradeControllerError, match="outlived"):
            await controller.upgrade(**options, restart_new=True)
        assert controller._process(child) is not None
        assert len(list(options["state"].glob("launch-*.json"))) == 1
    finally:
        if (process := controller._process(child)) is not None:
            process.kill()


async def test_ipv6_listener_cannot_attest_unrelated_ipv4_readiness(installation):
    """Reject IPv6 ownership as proof of readiness on an unrelated IPv4 listener."""
    if not socket.has_ipv6:
        pytest.skip("IPv6 loopback is unavailable")
    options, _, _, _, _ = installation
    marker = options["cwd"] / "ipv6-ready"
    code = "\n".join(  # noqa: FLY002 -- separate literal lines form the disposable child program
        [
            "import socket, pathlib, sys, time",
            "listener = socket.socket(socket.AF_INET6)",
            "listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)",
            "listener.bind(('::1', int(sys.argv[1])))",
            "listener.listen()",
            "pathlib.Path(sys.argv[2]).touch()",
            "time.sleep(300)",
        ]
    )
    with socket.socket() as unrelated:
        unrelated.bind(("127.0.0.1", options["port"]))
        unrelated.listen()
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-c", code, str(options["port"]), str(marker), start_new_session=True
        )
        try:
            await _until(marker.exists)
            identity = controller._identity(psutil.Process(process.pid))
            assert not controller._owns_listener(identity, options["port"])
        finally:
            process.kill()
            await process.wait()


async def test_helper_isolation_profile_is_created_and_removed_before_downtime(monkeypatch):
    """Verify the helper isolation profile with a disposable container before shutdown."""
    selected = "sha256:" + "2" * 64
    image = "ghcr.io/langflow-ai/langflow-chroma-migration@sha256:" + "0" * 64
    monkeypatch.setenv("LANGFLOW_KB_MIGRATION_HELPER_IMAGE", image)
    monkeypatch.setattr(controller.shutil, "which", lambda name: name)
    monkeypatch.setattr(controller.helper.os, "cpu_count", lambda: 1)

    async def staged(*_args):
        """Return the digest selected by successful helper verification."""
        return selected

    calls = []

    async def command(*args, **_kwargs):
        """Record Docker isolation checks without launching a container."""
        calls.append(args)
        return b""

    monkeypatch.setattr(controller.helper, "_stage_verified_helper", staged)
    monkeypatch.setattr(controller.helper, "_command", command)
    await controller.stage_helper()
    assert [call[1] for call in calls] == ["image", "create", "rm"]
    created = calls[1]
    assert "--network=none" in created
    assert "--cpus=1" in created
    assert "--read-only" in created
    assert selected in created
    assert "--rm" not in created
    name = created[created.index("--name") + 1]
    assert calls[2] == ("docker", "rm", "--force", name)
