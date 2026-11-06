"""Which base each legacy directory holds, by the ledger, its sidecar and its folder name."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.knowledge_base_storage.legacy_sources import (
    LegacyDirectory,
    LegacySourceUnresolvedError,
    attribute,
    evidence_from,
    scan_legacy_sources,
)
from langflow.services.knowledge_base_storage.maintenance import MaintenanceRequiredError

ALICE, BOB, CAROL = uuid4(), uuid4(), uuid4()
JOINED = datetime(2026, 1, 1, tzinfo=timezone.utc)
ACCOUNTS = [(ALICE, "alice", JOINED), (BOB, "bob", JOINED), (CAROL, "carol", JOINED)]


def _row(kb_id, owner, name, run_id=None, *, backend="chroma", config=None, state="migrating", chunks=0):
    return (kb_id, owner, name, run_id, backend, config or {}, state, chunks)


def _attribute(directories, rows, runs=(), **kwargs):
    return attribute(directories, evidence_from(ACCOUNTS, rows, runs), **kwargs)


def _unresolved(attribution, kb_id) -> str:
    with pytest.raises(LegacySourceUnresolvedError) as raised:
        attribution.source_of(kb_id)
    return raised.value.code


def test_scan_reports_sidecars_and_unreadable_entries_and_skips_internal_folders(tmp_path):
    kb_id = uuid4()
    (tmp_path / ".hidden" / "kb").mkdir(parents=True)
    (tmp_path / ".hidden" / "kb" / "chroma.sqlite3").write_bytes(b"")
    (tmp_path / ".hidden" / "kb" / "embedding_metadata.json").write_text(
        json.dumps({"id": str(kb_id), "created_at": "2025-06-01T00:00:00"})
    )
    (tmp_path / "bob" / "broken").mkdir(parents=True)
    (tmp_path / "bob" / "broken" / "embedding_metadata.json").write_text("{")
    (tmp_path / ".migration" / "bindings").mkdir(parents=True)
    # A user named "sqlite" keeps its legacy bases, beside the SQLite stores of every account.
    (tmp_path / "sqlite" / str(uuid4()) / str(uuid4())).mkdir(parents=True)
    (tmp_path / "sqlite" / "knowledge").mkdir()
    # macOS and Windows match folder names regardless of case, so the stores may sit under another spelling.
    (tmp_path / "SQLite" / str(uuid4())).mkdir(parents=True)
    (tmp_path / "linked").symlink_to(tmp_path / "bob", target_is_directory=True)

    directories, unreadable = scan_legacy_sources(tmp_path)

    found = {directory.identity: directory for directory in directories}
    assert set(found) == {".hidden/kb", "bob/broken", "sqlite/knowledge"}
    assert found[".hidden/kb"].has_store
    assert found[".hidden/kb"].recorded_id == kb_id
    # A naive timestamp is read as UTC.
    assert found[".hidden/kb"].created_at == datetime(2025, 6, 1, tzinfo=timezone.utc)
    assert not found["bob/broken"].readable
    assert unreadable == {"linked"}


def test_a_directory_that_the_ledger_and_its_sidecar_give_to_different_bases_is_contested():
    ledger_base, sidecar_base = uuid4(), uuid4()
    attribution = _attribute(
        [LegacyDirectory("alice/kb", has_store=True, recorded_id=sidecar_base)],
        [_row(ledger_base, ALICE, "kb"), _row(sidecar_base, BOB, "kb")],
        runs=[(uuid4(), ledger_base, "alice/kb")],
    )

    assert attribution.claims["alice/kb"] == {ledger_base, sidecar_base}
    for kb_id in (ledger_base, sidecar_base):
        assert _unresolved(attribution, kb_id) == "legacy_source_ambiguous"
        assert attribution.sources_of(kb_id) == frozenset()


def test_a_recorded_directory_is_the_bases_only_one_while_it_is_there():
    run_id, kb_id = uuid4(), uuid4()
    rows, runs = [_row(kb_id, ALICE, "kb", run_id)], [(run_id, kb_id, "former/kb")]
    directories = [LegacyDirectory("alice/kb", has_store=True), LegacyDirectory("former/kb", has_store=True)]

    attribution = _attribute(directories, rows, runs)

    assert attribution.source_of(kb_id) == "former/kb"
    # The directory under the current name is not the base's, so the holder's adoption decides it.
    assert "alice/kb" not in attribution.claims
    assert attribution.unclaimed(ALICE, "kb") == ["alice/kb"]
    # Once the recorded directory is gone, the base is located again.
    assert _attribute(directories[:1], rows, runs).source_of(kb_id) == "alice/kb"


def test_a_copy_that_keeps_the_sidecar_does_not_hide_the_bases_own_directory():
    kb_id = uuid4()
    rows = [_row(kb_id, ALICE, "kb")]
    copy = LegacyDirectory("alice/kb.bak", has_store=True, recorded_id=kb_id)

    attribution = _attribute([LegacyDirectory("alice/kb", has_store=True, recorded_id=kb_id), copy], rows)

    assert attribution.source_of(kb_id) == "alice/kb"
    # Two directories with the base's name are still one too many.
    elsewhere = LegacyDirectory("bob/kb", has_store=True, recorded_id=kb_id)
    assert _unresolved(_attribute([LegacyDirectory("alice/kb", has_store=True), elsewhere], rows), kb_id) == (
        "legacy_source_ambiguous"
    )


def test_a_base_whose_folders_cannot_be_listed_is_not_reported_missing():
    kb_id = uuid4()
    attribution = _attribute([], [_row(kb_id, ALICE, "kb")], unreadable_folders=frozenset({"alice"}))

    with pytest.raises(MaintenanceRequiredError) as raised:
        attribution.source_of(kb_id)
    assert not isinstance(raised.value, LegacySourceUnresolvedError)
    assert attribution.folder_unreadable(ALICE)


def test_only_a_base_that_still_reads_a_legacy_directory_claims_one_by_name():
    older, legacy, native = uuid4(), uuid4(), uuid4()
    # Alice was renamed, as her older base's sidecar shows, and Bob took "alice" and made a new SQLite base.
    accounts = [(ALICE, "alicia", JOINED), (BOB, "alice", JOINED)]
    rows = [_row(older, ALICE, "older"), _row(legacy, ALICE, "kb"), _row(native, BOB, "kb", backend="sqlite")]
    directories = [
        LegacyDirectory("alice/older", has_store=True, recorded_id=older),
        LegacyDirectory("alice/kb", has_store=True),
    ]

    attribution = attribute(directories, evidence_from(accounts, rows, ()))

    assert attribution.claims["alice/kb"] == {legacy}
    assert attribution.source_of(legacy) == "alice/kb"


def test_a_folder_name_claim_is_contested_by_a_base_with_data_that_found_no_directory():
    newcomer_kb, renamed_kb = uuid4(), uuid4()
    directories = [LegacyDirectory("alice/kb", has_store=True)]
    # Carol may have held "alice" before Alice did, and her base of that name lost its directory.
    rows = [_row(newcomer_kb, ALICE, "kb"), _row(renamed_kb, CAROL, "kb", chunks=12)]

    attribution = _attribute(directories, rows)

    assert attribution.claims["alice/kb"] == {newcomer_kb, renamed_kb}
    for kb_id in (newcomer_kb, renamed_kb):
        assert _unresolved(attribution, kb_id) == "legacy_source_ambiguous"
    # A base without data cannot have written the directory.
    empty = _attribute(directories, [rows[0], _row(renamed_kb, CAROL, "kb")])
    assert empty.source_of(newcomer_kb) == "alice/kb"


@pytest.mark.parametrize(
    ("created", "rows", "issue"),
    [
        (JOINED + timedelta(days=1), [], None),
        (None, [], "unattributed_legacy_source"),
        (JOINED - timedelta(days=1), [], "unattributed_legacy_source"),
        # A remote base, or one without data, cannot hold the directory.
        (JOINED + timedelta(days=1), [_row(uuid4(), BOB, "kb", config={"mode": "cloud"}, chunks=3)], None),
        (JOINED + timedelta(days=1), [_row(uuid4(), CAROL, "kb")], None),
        (JOINED + timedelta(days=1), [_row(uuid4(), CAROL, "kb", chunks=3)], "unattributed_legacy_source"),
    ],
)
def test_adoption_needs_a_creation_time_after_the_holder_joined_and_no_base_missing_its_data(created, rows, issue):
    kb_id = uuid4()
    directory = LegacyDirectory("alice/kb", has_store=True, recorded_id=kb_id, created_at=created)
    attribution = _attribute([directory], rows)

    assert attribution.adoption("alice/kb", ALICE) == (issue or (ALICE, kb_id))
    assert attribution.adoption("alice/kb", None) == "missing_source_owner"
