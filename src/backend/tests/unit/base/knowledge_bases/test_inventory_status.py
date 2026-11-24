"""Storage discovery reports orphaned folders even without registered bases."""

import json
import shutil

import pytest
from langflow.api.v1.knowledge_base_storage import retry_inventory, storage_status
from langflow.services.knowledge_base_storage import coordinator
from langflow.services.knowledge_base_storage.inventory import inventory_recovery_details

from . import test_storage_upgrade as storage_tests

database = storage_tests.database

pytestmark = pytest.mark.no_blockbuster


async def test_empty_storage_has_no_inventory_issues(database):
    await coordinator.run_pending()
    database.user.is_superuser = True
    async with database.sessions() as session:
        status = await storage_status(session, database.user)
    assert status["stores"] == []
    assert status["inventory"] == {"complete": True, "issues": 0}
    assert not status["running"]


async def test_orphaned_folders_report_issues_without_registered_bases(database):
    for index in range(17):
        source = database.root / "former-owner" / f"base-{index}"
        source.mkdir(parents=True)
        (source / "chroma.sqlite3").write_bytes(b"retained legacy data")
    await coordinator.run_pending()
    database.user.is_superuser = True
    async with database.sessions() as session:
        status = await storage_status(session, database.user)
    assert status["stores"] == []
    assert status["inventory"]["issues"] == 17
    assert status["inventory"]["storage_directory"] == str(database.root)
    assert {item["source"] for item in status["inventory"]["details"]} == {
        f"former-owner/base-{index}" for index in range(17)
    }
    assert {item["code"] for item in status["inventory"]["details"]} == {"missing_source_owner"}
    assert not status["running"]

    database.user.is_superuser = False
    async with database.sessions() as session:
        regular = await storage_status(session, database.user)
    assert regular["inventory"] is None

    shutil.move(database.root / "former-owner", database.root.parent / "preserved-sources")
    database.user.is_superuser = True
    assert await retry_inventory(database.user) == {"status": "scheduled"}
    await coordinator.wait_for_upgrade()
    async with database.sessions() as session:
        recovered = await storage_status(session, database.user)
    assert recovered["inventory"] == {"complete": True, "issues": 0}
    assert (database.root.parent / "preserved-sources" / "base-0" / "chroma.sqlite3").read_bytes() == (
        b"retained legacy data"
    )


async def test_a_failed_rescan_stops_naming_folders_from_an_earlier_scan(database):
    for index in range(2):
        source = database.root / "former-owner" / f"base-{index}"
        source.mkdir(parents=True)
        (source / "chroma.sqlite3").write_bytes(b"retained legacy data")
    await coordinator.run_pending()
    database.user.is_superuser = True
    async with database.sessions() as session:
        listed = await storage_status(session, database.user)
    assert len(listed["inventory"]["details"]) == 2
    assert not listed["inventory"]["scan_failed"]

    # The named folders are recovered, but an unrelated owner symlink stops the next scan.
    shutil.move(database.root / "former-owner", database.root.parent / "preserved-sources")
    elsewhere = database.root.parent / "elsewhere"
    elsewhere.mkdir()
    linked = database.root / "linked-owner"
    linked.symlink_to(elsewhere, target_is_directory=True)
    assert await retry_inventory(database.user) == {"status": "scheduled"}
    await coordinator.wait_for_upgrade()
    async with database.sessions() as session:
        failed = await storage_status(session, database.user)
    assert failed["inventory"]["issues"]
    assert failed["inventory"]["details"] == []
    assert failed["inventory"]["scan_failed"]

    linked.unlink()
    await retry_inventory(database.user)
    await coordinator.wait_for_upgrade()
    async with database.sessions() as session:
        recovered = await storage_status(session, database.user)
    assert recovered["inventory"] == {"complete": True, "issues": 0}


async def test_a_read_only_report_cannot_republish_recovered_folders(database, monkeypatch):
    source = database.root / "former-owner" / "recovered-base"
    source.mkdir(parents=True)
    (source / "chroma.sqlite3").write_bytes(b"retained legacy data")
    await coordinator.run_pending()
    database.user.is_superuser = True
    report = database.root / ".migration" / "inventory.json"
    previous_report = report.read_bytes()
    shutil.move(database.root / "former-owner", database.root.parent / "preserved-sources")
    report.chmod(0o400)
    try:
        await retry_inventory(database.user)
        await coordinator.wait_for_upgrade()
        async with database.sessions() as session:
            failed = await storage_status(session, database.user)
        assert failed["inventory"]["details"] == []
        assert failed["inventory"]["scan_failed"]
        assert report.read_bytes() == previous_report

        # A different worker must not need the failed coordinator's process state.
        with monkeypatch.context() as peer:
            peer.setattr(coordinator, "_inventory_scan_failed", False)
            async with database.sessions() as session:
                shared = await storage_status(session, database.user)
            assert shared["inventory"]["details"] == []
            assert shared["inventory"]["scan_failed"]
    finally:
        report.chmod(0o600)

    await retry_inventory(database.user)
    await coordinator.wait_for_upgrade()
    async with database.sessions() as session:
        recovered = await storage_status(session, database.user)
    assert recovered["inventory"] == {"complete": True, "issues": 0}
    assert (database.root.parent / "preserved-sources" / "recovered-base" / "chroma.sqlite3").read_bytes() == (
        b"retained legacy data"
    )


@pytest.mark.parametrize("contents", ["{", "[]", '{"issues": null}', '{"issues": [null]}'])
async def test_unreadable_inventory_details_leave_retry_available(database, contents):
    directory = database.root / ".migration"
    directory.mkdir()
    (directory / "inventory.json").write_text(contents)
    details = await inventory_recovery_details()
    assert details == {"storage_directory": str(database.root), "details": [], "scan_failed": False}


async def test_inventory_details_are_bounded_and_exclude_unsafe_sources_and_private_fields(database):
    directory = database.root / ".migration"
    directory.mkdir()
    issue = {"source": "owner/base", "code": "missing_source_owner", "owner_id": "private", "secret": "private"}
    invalid = [
        {"source": source, "code": "missing_source_owner"}
        for source in ("/absolute", "../escape", "owner/../../escape", "owner\\base/name", None)
    ]
    (directory / "inventory.json").write_text(json.dumps({"issues": [*invalid, *([issue] * 600)]}))
    result = await inventory_recovery_details()
    assert result["details"]
    assert len(result["details"]) <= 500
    assert all(item == {"source": "owner/base", "code": "missing_source_owner"} for item in result["details"])
