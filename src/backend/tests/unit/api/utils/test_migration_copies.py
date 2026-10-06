"""Tests for the parts of a migration copy that hold no state.

What a step runs, the environment it runs in, what the record keeps of a run that
has ended, and why such a run does not complete its step.
"""

from __future__ import annotations

import os
import sys

import pytest
from langflow.api.utils.migration_copies import DECISIONS, blocking_code, copy_command, copy_environment, copy_outcome

DB_PASSWORD = "db-password-9f3a61c2"  # noqa: S105  # pragma: allowlist secret
S3_SECRET = "s3-secret-key-7be04d15"  # noqa: S105  # pragma: allowlist secret
DESTINATION = f"postgresql+psycopg://migrator:{DB_PASSWORD}@db.internal:5432/langflow"
# What the record says of where the files go, and what the worker holds to get there.
BUCKET = {"files": {"bucket": "acme", "prefix": "moved/files", "endpoint_url": "https://s3.internal"}}
S3_KEYS = {
    "access_key_id": "AKIAEXAMPLE",
    "secret_access_key": S3_SECRET,
    "endpoint_url": "https://s3.internal",
    "ca_bundle": "/etc/ssl/s3.pem",
}
# What this machine gives any process, and what points a command at this instance.
MACHINE = {"PATH": "/usr/bin", "HOME": "/home/langflow", "PGSSLROOTCERT": "/etc/ssl/destination.pem"}
INSTANCE = {
    "LANGFLOW_CONFIG_DIR": "/data",
    "LANGFLOW_KNOWLEDGE_BASES_DIR": "/data/knowledge_bases",
    "LANGFLOW_SECRET_KEY": "this-instance-key",  # pragma: allowlist secret
}
# The server's own environment: where it keeps its data, and how it signs in to AWS for its own work.
SERVER = {
    **MACHINE,
    **INSTANCE,
    "LANGFLOW_DATABASE_URL": "sqlite+aiosqlite:////data/langflow.db",
    "LANGFLOW_STORAGE_TYPE": "s3",
    "LANGFLOW_OBJECT_STORAGE_BUCKET_NAME": "the-servers-own-bucket",
    "LANGFLOW_LOG_FILE": "/var/log/langflow.log",
    "PGVECTOR_CONNECTION_STRING": "postgresql://the-servers-own-vectors",
    "AWS_PROFILE": "the-servers-own-profile",
    "AWS_ACCESS_KEY_ID": "the-servers-own-key",
    "AWS_SESSION_TOKEN": "the-servers-own-token",
    "AWS_ENDPOINT_URL": "http://the-servers-own-storage",
}
ENDED = {"status": "done", "finished_at": "2026-10-01T00:05:00+00:00", "stderr": ""}
RUN = "the run that reported"
LANGFLOW = [sys.executable, "-m", "langflow"]
REPORT = {"ok": True, "revision": "head", "tables_copied": 59, "rows_copied": 48, "orphans": [], "problems": []}
ORPHANS = {"table": "message", "column": "flow_id", "parent": "flow", "ondelete": "CASCADE", "rows": 3}


def _refused(*codes: str) -> dict:
    return {"error": None, "report": {**REPORT, "ok": False, "problems": [{"code": code} for code in codes]}}


def _decided(step: str, kind: str, subject: str | None = None, run_id: str = RUN) -> dict:
    """A decision as the record keeps one. Accepting an item is for the run whose report listed it."""
    about = {"subject": subject, "run_id": run_id if subject else None}
    return {"step": step, "kind": kind, **about, "by": "alice", "at": "2026-10-01T00:10:00+00:00"}


def _not_copied(step: str, *items: dict) -> dict:
    """A run of the knowledge base or the file copy that ended with these items failed, as the record keeps it."""
    report = {"event": "report", "seq": 9, "ok": False, "counts": {"failed": len(items)}, "attention": list(items)}
    return {**copy_outcome(step, ENDED, {"report": report}), "run_id": RUN}


def test_each_copy_runs_its_own_command_and_names_no_address_or_key_on_it():
    assert copy_command("copy_database", {}, []) == [*LANGFLOW, "convert-sqlite-to-postgres", "--json"]
    assert copy_command("copy_knowledge_bases", {}, []) == [*LANGFLOW, "relocate-kb", "--to", "postgres", "--json"]
    files = [*LANGFLOW, "relocate-files", "--json", "--bucket", "acme", "--prefix", "moved/files"]
    assert copy_command("copy_files", BUCKET, []) == files
    # A test run is the same command, told to write nothing.
    assert copy_command("copy_files", BUCKET, [], dry_run=True) == [*files, "--dry-run"]


def test_an_option_the_admin_decided_on_is_added_to_the_command_of_its_own_step():
    decisions = [
        _decided("copy_database", "drop_orphans"),
        _decided("copy_knowledge_bases", "accept_ranking_change"),
        # Accepting an item changes what its step makes of a report, and nothing about the command.
        _decided("copy_knowledge_bases", "leave_behind", "kb-2"),
        _decided("copy_files", "keep_bucket_file", "alice/cat.txt"),
    ]

    assert copy_command("copy_database", {}, decisions)[-2:] == ["--json", "--drop-orphans"]
    assert copy_command("copy_knowledge_bases", {}, decisions, dry_run=True)[-3:] == [
        "--json",
        "--allow-metric-change",
        "--dry-run",
    ]
    assert copy_command("copy_files", BUCKET, decisions)[-2:] == ["--prefix", "moved/files"]


def test_the_database_copy_reads_this_instance_and_writes_to_the_destination_and_nowhere_else():
    env = copy_environment("copy_database", SERVER, {"database_url": DESTINATION})

    # Every Langflow and AWS setting it gets is one it was given by name. None of the server's own comes along.
    assert env == {
        **MACHINE,
        **INSTANCE,
        "LANGFLOW_MIGRATION_SOURCE_URL": "sqlite+aiosqlite:////data/langflow.db",
        "LANGFLOW_MIGRATION_TARGET_URL": DESTINATION,
    }


def test_the_knowledge_base_copy_works_on_the_destination_database_and_puts_the_vectors_in_it():
    env = copy_environment("copy_knowledge_bases", SERVER, {"database_url": DESTINATION})

    assert env == {
        **MACHINE,
        **INSTANCE,
        "LANGFLOW_DATABASE_URL": DESTINATION,
        "PGVECTOR_CONNECTION_STRING": DESTINATION,
    }


def test_the_file_copy_signs_in_with_the_keys_it_was_given_and_reads_none_of_the_servers_own():
    env = copy_environment("copy_files", SERVER, {"database_url": DESTINATION, "files": S3_KEYS})

    assert env == {
        **MACHINE,
        **INSTANCE,
        "LANGFLOW_DATABASE_URL": DESTINATION,
        "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE",
        "AWS_SECRET_ACCESS_KEY": S3_SECRET,
        "AWS_ENDPOINT_URL": "https://s3.internal",
        "AWS_CA_BUNDLE": "/etc/ssl/s3.pem",
        # The server's AWS files name its own profile, keys and endpoint. An empty file takes their place.
        "AWS_CONFIG_FILE": os.devnull,
        "AWS_SHARED_CREDENTIALS_FILE": os.devnull,
    }


def test_a_bucket_on_aws_itself_gets_no_endpoint_and_no_certificates():
    keys = {**S3_KEYS, "endpoint_url": None, "ca_bundle": None}

    env = copy_environment("copy_files", SERVER, {"database_url": DESTINATION, "files": keys})

    assert "AWS_ENDPOINT_URL" not in env
    assert "AWS_CA_BUNDLE" not in env


def test_the_copies_read_the_destination_address_with_the_driver_its_test_read_it_with():
    # The test of a destination and the database copy read any spelling of a PostgreSQL address with one driver.
    # A copy that took the address as it was typed would look for whichever driver it names.
    typed = f"postgresql+asyncpg://migrator:{DB_PASSWORD}@db.internal:5432/langflow"
    read_as = f"postgresql+psycopg://migrator:{DB_PASSWORD}@db.internal:5432/langflow"

    knowledge_bases = copy_environment("copy_knowledge_bases", SERVER, {"database_url": typed})
    files = copy_environment("copy_files", SERVER, {"database_url": typed, "files": S3_KEYS})

    assert knowledge_bases["LANGFLOW_DATABASE_URL"] == knowledge_bases["PGVECTOR_CONNECTION_STRING"] == read_as
    assert files["LANGFLOW_DATABASE_URL"] == read_as


def test_an_instance_already_on_postgresql_keeps_its_database_and_the_copies_work_on_it():
    own = "postgresql+psycopg://langflow:own-password@db.internal:5432/langflow"  # pragma: allowlist secret
    server = {**SERVER, "LANGFLOW_DATABASE_URL": own}

    knowledge_bases = copy_environment("copy_knowledge_bases", server, {})
    files = copy_environment("copy_files", server, {"files": S3_KEYS})

    # The instance goes on serving from its database, and reads its knowledge bases from the store its own
    # environment names. The copy is sent to that store, which need not be the database.
    assert (knowledge_bases["LANGFLOW_DATABASE_URL"], knowledge_bases["PGVECTOR_CONNECTION_STRING"]) == (
        own,
        "postgresql://the-servers-own-vectors",
    )
    assert files["LANGFLOW_DATABASE_URL"] == own
    # A server that names no store could not read them afterwards, so there is no environment to copy them in.
    unnamed = {name: value for name, value in server.items() if name != "PGVECTOR_CONNECTION_STRING"}
    with pytest.raises(KeyError):
        copy_environment("copy_knowledge_bases", unnamed, {})


@pytest.mark.parametrize(
    ("step", "held"),
    [
        ("copy_database", {}),
        ("copy_knowledge_bases", {}),
        ("copy_files", {"files": S3_KEYS}),
        ("copy_files", {"database_url": DESTINATION}),
    ],
)
def test_a_copy_has_no_environment_without_the_destination_it_writes_to(step, held):
    # What a worker holds after a restart. Falling back to this instance's own database would write to it.
    with pytest.raises(KeyError):
        copy_environment(step, SERVER, held)


def test_the_record_keeps_the_report_of_a_run_and_not_its_place_in_the_log():
    asked = {"code": "orphans_droppable", "flag": "--drop-orphans", "details": {"orphans": [ORPHANS]}}
    events = {
        "report": {"event": "report", "seq": 150, **REPORT},
        "decision_needed": {"event": "decision_needed", "seq": 149, **asked},
        # The command also says each problem as an error. The report already holds them.
        "error": {"event": "error", "seq": 148, "code": "orphans_droppable", "message": "3 rows point at nothing"},
    }

    assert copy_outcome("copy_database", ENDED, events) == {
        "status": "done",
        "finished_at": ENDED["finished_at"],
        "report": REPORT,
        "error": None,
        # What the command asked comes with the decision that answers it: an option, which is for the whole step.
        "decision_needed": {**asked, "decision": {"kind": "drop_orphans", "subject": None}},
    }


@pytest.mark.parametrize(
    ("status", "events", "error"),
    [
        # The command said why it stopped.
        (
            "failed",
            {"error": {"event": "error", "seq": 2, "code": "schema_mismatch", "message": "the database is at none"}},
            {"code": "schema_mismatch", "message": "the database is at none"},
        ),
        # It died without a word on stdout, so its last lines on stderr are all there is.
        ("failed", {}, {"code": "crashed", "message": "Traceback (most recent call last):"}),
        ("cancelled", {}, {"code": "cancelled"}),
        ("interrupted", {}, {"code": "interrupted"}),
        # Stopped after it had reported, by a server that was shutting down. It is run again all the same.
        ("interrupted", {"report": {"event": "report", "seq": 150, **REPORT}}, {"code": "interrupted"}),
    ],
)
def test_a_run_that_did_not_end_done_is_kept_with_the_code_that_explains_it(status, events, error):
    run = {**ENDED, "status": status, "stderr": "Traceback (most recent call last):"}

    kept = copy_outcome("copy_database", run, events)

    assert (kept["status"], kept["error"]) == (status, error)
    assert blocking_code("copy_database", kept, []) == error["code"]


def test_a_run_that_reported_ok_completes_its_step():
    run = copy_outcome("copy_database", ENDED, {"report": {"event": "report", "seq": 150, **REPORT}})

    assert blocking_code("copy_database", run, []) is None


@pytest.mark.parametrize(
    ("codes", "code"),
    [
        (["target_not_empty"], "target_not_empty"),
        (["orphans_droppable", "orphans_droppable"], "orphans_droppable"),
        # Dropping orphans is offered only when nothing else stands in the way.
        (["orphans_droppable", "orphans_no_rule"], "orphans_no_rule"),
    ],
)
def test_a_database_copy_that_was_refused_blocks_with_what_the_command_found(codes, code):
    assert blocking_code("copy_database", _refused(*codes), []) == code
    # Deciding to drop the orphans changes the next run. This one copied nothing.
    assert blocking_code("copy_database", _refused(*codes), [_decided("copy_database", "drop_orphans")]) == code


# A knowledge base and a file as each command reports one that failed, and the name each has in the record.
ITEMS = {
    "copy_knowledge_bases": {"kb_id": "0b6c5a0e-kb", "kb_name": "handbook", "owner": "alice"},
    "copy_files": {"owner": "0b6c5a0e-user", "file_name": "cat.txt", "key": ""},
}
NAMED = {"copy_knowledge_bases": "0b6c5a0e-kb", "copy_files": "0b6c5a0e-user/cat.txt"}


@pytest.mark.parametrize(
    ("step", "code", "kind", "names_the_item"),
    [
        # Copying again gets past neither: this version has no backend for the store, or the store holds fewer
        # chunks than its row says and someone has to look. Left behind, the knowledge base stays where it is.
        ("copy_knowledge_bases", "kb_backend_missing", "leave_behind", True),
        ("copy_knowledge_bases", "kb_short", "leave_behind", True),
        # An option of the command is for the whole step, so it names no item.
        ("copy_knowledge_bases", "kb_metric_change", "accept_ranking_change", False),
        ("copy_files", "file_conflict", "keep_bucket_file", True),
        # The database names a file that this instance holds no bytes for.
        ("copy_files", "no_source_bytes", "accept_missing_attachment", True),
        ("copy_files", "attachment_unmatched", "accept_missing_attachment", True),
    ],
)
def test_the_record_says_which_decision_answers_a_failed_item(step, code, kind, names_the_item):
    item = {**ITEMS[step], "code": code}

    [kept] = _not_copied(step, item)["report"]["attention"]

    assert kept == {
        **item,
        "subject": NAMED[step],
        "decision": {"kind": kind, "subject": NAMED[step] if names_the_item else None},
    }


@pytest.mark.parametrize(
    ("step", "code"),
    [
        # Each of these is put right, on this instance or at the destination, and the copy is run again.
        ("copy_knowledge_bases", "kb_upgrade_pending"),
        ("copy_knowledge_bases", "kb_ingesting"),
        ("copy_knowledge_bases", "kb_target_unreachable"),
        ("copy_knowledge_bases", "kb_metric_unknown"),
        ("copy_knowledge_bases", "kb_no_vectors"),
        ("copy_knowledge_bases", "kb_read_short"),
        ("copy_knowledge_bases", "kb_target_more"),
        ("copy_knowledge_bases", "kb_changed"),
        ("copy_knowledge_bases", "kb_routing_changed"),
        ("copy_knowledge_bases", "kb_deleted"),
        ("copy_knowledge_bases", "kb_failed"),
        ("copy_files", "bad_name"),
        ("copy_files", "bucket_error"),
        ("copy_files", "verify_failed"),
        ("copy_files", "copy_failed"),
        # A decision answers a code of its own step's command, and of no other.
        ("copy_files", "kb_backend_missing"),
        ("copy_knowledge_bases", "file_conflict"),
    ],
)
def test_a_failed_item_that_no_decision_answers_blocks_its_step_whatever_the_admin_decides(step, code):
    run = _not_copied(step, {**ITEMS[step], "code": code})
    everything = [_decided(decision["step"], kind, NAMED[step]) for kind, decision in DECISIONS.items()]

    assert blocking_code(step, run, everything) == code
    # And the record offers the admin nothing to decide about it.
    assert run["report"]["attention"][0]["decision"] is None


def test_a_failed_item_blocks_its_step_until_the_admin_accepts_it():
    run = _not_copied(
        "copy_knowledge_bases",
        {"kb_id": "kb-1", "code": "kb_short"},
        {"kb_id": "kb-2", "code": "kb_backend_missing"},
    )
    first, second = (_decided("copy_knowledge_bases", "leave_behind", subject) for subject in ("kb-1", "kb-2"))

    assert blocking_code("copy_knowledge_bases", run, []) == "kb_short"
    assert blocking_code("copy_knowledge_bases", run, [first]) == "kb_backend_missing"
    assert blocking_code("copy_knowledge_bases", run, [second, first]) is None
    # A decision is about its own step. Another step's item of the same name is still to be decided.
    assert blocking_code("copy_knowledge_bases", run, [second, _decided("copy_files", "keep_bucket_file", "kb-1")]) == (
        "kb_short"
    )


def test_a_decision_accepts_only_an_item_whose_code_it_answers():
    run = _not_copied(
        "copy_files",
        {"owner": "alice", "file_name": "cat.txt", "code": "file_conflict"},
        {"owner": "alice", "file_name": "gone.txt", "code": "no_source_bytes"},
    )
    kept = _decided("copy_files", "keep_bucket_file", "alice/cat.txt")
    let_go = _decided("copy_files", "accept_missing_attachment", "alice/gone.txt")
    # Each decision made about the other one's file. Both are on record, and neither file is accepted.
    crossed = [
        _decided("copy_files", "keep_bucket_file", "alice/gone.txt"),
        _decided("copy_files", "accept_missing_attachment", "alice/cat.txt"),
    ]

    assert blocking_code("copy_files", run, crossed) == "file_conflict"
    assert blocking_code("copy_files", run, [*crossed, kept]) == "no_source_bytes"
    assert blocking_code("copy_files", run, [*crossed, kept, let_go]) is None


def test_accepting_an_item_is_for_the_report_that_listed_it():
    run = _not_copied("copy_files", {"owner": "alice", "file_name": "cat.txt", "code": "file_conflict"})
    kept = _decided("copy_files", "keep_bucket_file", "alice/cat.txt")
    assert blocking_code("copy_files", run, [kept]) is None

    # The copy is made again, to another bucket say, and that one holds something under the same name too.
    again = {**run, "run_id": "another run"}

    # Nobody has seen that report yet, so nobody has accepted what it says.
    assert blocking_code("copy_files", again, [kept]) == "file_conflict"
    here = _decided("copy_files", "keep_bucket_file", "alice/cat.txt", run_id="another run")
    assert blocking_code("copy_files", again, [kept, here]) is None


def test_an_option_of_the_command_accepts_no_item_of_the_run_that_asked_for_it():
    run = _not_copied("copy_knowledge_bases", {"kb_id": "kb-1", "code": "kb_metric_change"})
    decisions = [
        # Accepting the change of ranking changes the next run. This one did not copy the knowledge base.
        _decided("copy_knowledge_bases", "accept_ranking_change"),
        # Nor is it one to leave behind: it can be copied.
        _decided("copy_knowledge_bases", "leave_behind", "kb-1"),
    ]

    assert blocking_code("copy_knowledge_bases", run, decisions) == "kb_metric_change"


def test_the_record_keeps_the_first_hundred_failed_items_and_they_cannot_stand_for_the_rest():
    failed = [{"owner": "alice", "file_name": f"{number}.txt", "code": "no_source_bytes"} for number in range(250)]
    report = {"event": "report", "seq": 600, "ok": False, "counts": {"copied": 7, "failed": 250}, "attention": failed}

    run = {**copy_outcome("copy_files", ENDED, {"report": report}), "run_id": RUN}

    kept = run["report"]["attention"]
    assert [item["subject"] for item in kept] == [f"alice/{number}.txt" for number in range(100)]
    assert run["report"]["counts"] == {"copied": 7, "failed": 250}
    # Accepting every item the record holds leaves 150 that nobody was shown.
    accepted = [_decided("copy_files", "accept_missing_attachment", item["subject"]) for item in kept]
    assert blocking_code("copy_files", run, accepted) == "no_source_bytes"
    # With all of them on record, the same decisions complete the step.
    shown = {**run, "report": {**run["report"], "counts": {"failed": 100}}}
    assert blocking_code("copy_files", shown, accepted) is None
