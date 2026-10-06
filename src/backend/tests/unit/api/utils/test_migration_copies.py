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
LANGFLOW = [sys.executable, "-m", "langflow"]
REPORT = {"ok": True, "revision": "head", "tables_copied": 59, "rows_copied": 48, "orphans": [], "problems": []}
ORPHANS = {"table": "message", "column": "flow_id", "parent": "flow", "ondelete": "CASCADE", "rows": 3}


def _refused(*codes: str) -> dict:
    return {"error": None, "report": {**REPORT, "ok": False, "problems": [{"code": code} for code in codes]}}


def _decided(step: str, kind: str, subject: str | None = None) -> dict:
    return {"step": step, "kind": kind, "subject": subject, "by": "alice", "at": "2026-10-01T00:10:00+00:00"}


def _not_copied(*items: dict, failed: int | None = None) -> dict:
    """A run of the knowledge base or the file copy that ended with these items failed, as the record keeps it."""
    count = len(items) if failed is None else failed
    report = {"event": "report", "seq": 9, "ok": False, "counts": {"failed": count}, "attention": list(items)}
    return copy_outcome(ENDED, {"report": report})


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


def test_every_decision_is_an_option_of_the_command_or_the_acceptance_of_one_item():
    assert DECISIONS == {
        "copy_database": {"drop_orphans": "--drop-orphans"},
        "copy_knowledge_bases": {"accept_ranking_change": "--allow-metric-change", "leave_behind": None},
        "copy_files": {"keep_bucket_file": None, "accept_missing_attachment": None},
    }


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

    assert copy_outcome(ENDED, events) == {
        "status": "done",
        "finished_at": ENDED["finished_at"],
        "report": REPORT,
        "error": None,
        "decision_needed": asked,
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

    kept = copy_outcome(run, events)

    assert (kept["status"], kept["error"]) == (status, error)
    assert blocking_code("copy_database", kept, []) == error["code"]


def test_a_run_that_reported_ok_completes_its_step():
    run = copy_outcome(ENDED, {"report": {"event": "report", "seq": 150, **REPORT}})

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


def test_the_record_names_each_failed_item_the_way_a_decision_about_it_does():
    knowledge_base = {"kb_id": "0b6c5a0e-kb", "kb_name": "handbook", "owner": "alice", "code": "kb_short"}
    file = {"owner": "0b6c5a0e-user", "file_name": "cat.txt", "key": "", "code": "no_source_bytes"}

    kept = _not_copied(knowledge_base, file)["report"]["attention"]

    assert kept == [{**knowledge_base, "subject": "0b6c5a0e-kb"}, {**file, "subject": "0b6c5a0e-user/cat.txt"}]


def test_a_failed_item_blocks_its_step_until_the_admin_accepts_it():
    run = _not_copied({"kb_id": "kb-1", "code": "kb_short"}, {"kb_id": "kb-2", "code": "kb_backend_missing"})
    first, second = (_decided("copy_knowledge_bases", "leave_behind", subject) for subject in ("kb-1", "kb-2"))

    assert blocking_code("copy_knowledge_bases", run, []) == "kb_short"
    assert blocking_code("copy_knowledge_bases", run, [first]) == "kb_backend_missing"
    assert blocking_code("copy_knowledge_bases", run, [second, first]) is None
    # A decision is about its own step. Another step's item of the same name is still to be decided.
    assert blocking_code("copy_knowledge_bases", run, [second, _decided("copy_files", "keep_bucket_file", "kb-1")]) == (
        "kb_short"
    )
    # Accepting the change of ranking is an option for the next run, and accepts no item of this one.
    ranked = _not_copied({"kb_id": "kb-1", "code": "kb_metric_change"})
    assert blocking_code(
        "copy_knowledge_bases", ranked, [_decided("copy_knowledge_bases", "accept_ranking_change")]
    ) == ("kb_metric_change")


def test_the_record_keeps_the_first_hundred_failed_items_and_they_cannot_stand_for_the_rest():
    failed = [{"owner": "alice", "file_name": f"{number}.txt", "code": "bucket_error"} for number in range(250)]
    report = {"event": "report", "seq": 600, "ok": False, "counts": {"copied": 7, "failed": 250}, "attention": failed}

    run = copy_outcome(ENDED, {"report": report})

    kept = run["report"]["attention"]
    assert [item["subject"] for item in kept] == [f"alice/{number}.txt" for number in range(100)]
    assert run["report"]["counts"] == {"copied": 7, "failed": 250}
    # Accepting every item the record holds leaves 150 that nobody was shown.
    accepted = [_decided("copy_files", "accept_missing_attachment", item["subject"]) for item in kept]
    assert blocking_code("copy_files", run, accepted) == "bucket_error"
