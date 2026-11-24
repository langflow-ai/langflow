"""First-start safety and crash recovery for application database backups."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.knowledge_base_storage import automatic

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("disabled", "automatic_upgrade_disabled"),
        ("multiworker", "single_host_required"),
        ("orchestrated", "single_host_required"),
        ("other_process", "legacy_workers_running"),
        ("shared_disk", "local_filesystem_required"),
        ("unknown_disk", "local_filesystem_required"),
        ("local", None),
    ],
)
def test_automatic_upgrade_requires_exclusive_local_storage(tmp_path, monkeypatch, case, code):
    for key in automatic._ORCHESTRATORS:
        monkeypatch.delenv(key, raising=False)
    settings = SimpleNamespace(
        knowledge_base_auto_migrate=case != "disabled", workers=2 if case == "multiworker" else 1
    )
    if case == "orchestrated":
        monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "cluster")
    monkeypatch.setattr(
        automatic.psutil,
        "Process",
        lambda: SimpleNamespace(parents=lambda: [SimpleNamespace(pid=42)], children=lambda **_kwargs: []),
    )

    def other_processes(*, excluded_pids):
        assert excluded_pids == {42}
        return [SimpleNamespace(pid=43)] if case == "other_process" else []

    monkeypatch.setattr(automatic, "remaining_legacy_workers", other_processes)
    monkeypatch.setattr(
        automatic.psutil,
        "disk_partitions",
        lambda **_kwargs: []
        if case == "unknown_disk"
        else [SimpleNamespace(mountpoint=str(tmp_path), fstype="nfs" if case == "shared_disk" else "apfs")],
    )
    if code:
        with pytest.raises(automatic.AutomaticUpgradeUnavailableError) as failure:
            automatic.check_local_upgrade(tmp_path, settings)
        assert failure.value.code == code
    else:
        automatic.check_local_upgrade(tmp_path, settings)


def test_application_backup_recovers_partial_copy_and_is_shared_across_bases(tmp_path):
    database = tmp_path / "app.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE data(value TEXT)")
        connection.execute("INSERT INTO data VALUES ('before upgrade')")
    migration_root = tmp_path / ".migration"
    backup_directory = migration_root / "application-backups"
    backup_directory.mkdir(parents=True)
    identity = hashlib.sha256(str(database).encode()).hexdigest()
    incomplete = backup_directory / f"application-before-upgrade-{identity}.incomplete"
    incomplete.write_bytes(b"partial copy left by a restart")
    references = []
    for name in ("first", "second"):
        directory = migration_root / str(uuid4()) / str(uuid4())
        directory.mkdir(parents=True)
        row = SimpleNamespace(model_dump=lambda name=name, **_kwargs: {"name": name, "backend_type": "chroma"})
        automatic.preserve_routing(directory, row, database, backup_directory=backup_directory)
        assert json.loads((directory / "routing-before-upgrade.json").read_text())["name"] == name
        references.append(json.loads((directory / "application-backup.json").read_text())["backup"])
        # A later base must reuse the original rollback backup, even if normal
        # app usage has changed the metadata database in the meantime.
        with sqlite3.connect(database) as connection:
            connection.execute("INSERT INTO data VALUES ('while using Langflow')")
    assert references[0] == references[1]
    assert not incomplete.exists()
    assert len(list(backup_directory.glob("*.sqlite3"))) == 1
    with sqlite3.connect(migration_root / references[0]) as backup:
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert backup.execute("SELECT value FROM data").fetchall() == [("before upgrade",)]


def test_backup_requires_free_space_without_publishing_an_incomplete_copy(tmp_path, monkeypatch):
    database = tmp_path / "app.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE data(value TEXT)")
    directory = tmp_path / ".migration" / str(uuid4()) / str(uuid4())
    directory.mkdir(parents=True)
    backups = tmp_path / ".migration" / "application-backups"
    backups.mkdir()
    row = SimpleNamespace(model_dump=lambda **_kwargs: {})
    monkeypatch.setattr(automatic.shutil, "disk_usage", lambda _path: SimpleNamespace(free=0))
    with pytest.raises(automatic.MaintenanceRequiredError, match="Insufficient disk space"):
        automatic.preserve_routing(directory, row, database, backup_directory=backups)
    assert list(backups.iterdir()) == []
    assert not (directory / "application-backup.json").exists()
