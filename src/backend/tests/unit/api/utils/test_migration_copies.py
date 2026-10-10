"""Tests for the parts of a migration copy that hold no state.

What a step runs, the environment it runs in, what the record keeps of a run that
has ended, and why such a run does not complete its step.
"""

from __future__ import annotations

import sys

import pytest
from langflow.api.utils.migration_copies import blocking_code, copy_command, copy_environment, copy_outcome

DB_PASSWORD = "db-password-9f3a61c2"  # noqa: S105  # pragma: allowlist secret
DESTINATION = f"postgresql://migrator:{DB_PASSWORD}@db.internal:5432/langflow"
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
REPORT = {"ok": True, "revision": "head", "tables_copied": 59, "rows_copied": 48, "orphans": [], "problems": []}
ORPHANS = {"table": "message", "column": "flow_id", "parent": "flow", "ondelete": "CASCADE", "rows": 3}


def _refused(*codes: str) -> dict:
    return {"error": None, "report": {**REPORT, "ok": False, "problems": [{"code": code} for code in codes]}}


def test_the_database_copy_names_no_address_on_its_command_line():
    assert copy_command("copy_database") == [sys.executable, "-m", "langflow", "convert-sqlite-to-postgres", "--json"]


def test_the_database_copy_reads_this_instance_and_writes_to_the_destination_and_nowhere_else():
    env = copy_environment(SERVER, {"database_url": DESTINATION})

    # Every Langflow and AWS setting it gets is one it was given by name. None of the server's own comes along.
    assert env == {
        **MACHINE,
        **INSTANCE,
        "LANGFLOW_MIGRATION_SOURCE_URL": "sqlite+aiosqlite:////data/langflow.db",
        "LANGFLOW_MIGRATION_TARGET_URL": DESTINATION,
    }


def test_a_copy_has_no_environment_without_the_destination_it_writes_to():
    # What a worker holds after a restart. Falling back to this instance's own database would write to it.
    with pytest.raises(KeyError):
        copy_environment(SERVER, {})


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
    assert blocking_code(kept) == error["code"]


def test_a_run_that_reported_ok_completes_its_step():
    assert blocking_code(copy_outcome(ENDED, {"report": {"event": "report", "seq": 150, **REPORT}})) is None


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
    assert blocking_code(_refused(*codes)) == code
