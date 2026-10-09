"""Tests for what the last two steps of a migration are made of.

The settings a new instance starts with, the environment that points the integrity check
at the destination, and how its report reads beside this instance's. Nothing here starts a
command: the endpoint tests do.
"""

from __future__ import annotations

import os
import sys

import pytest
from langflow.api.utils.migration_target import (
    check_command,
    check_environment,
    check_outcome,
    compare,
    start_settings,
)

DB_PASSWORD = "db-password-9f3a61c2"  # noqa: S105  # pragma: allowlist secret
S3_SECRET = "s3-secret-key-7be04d15"  # noqa: S105  # pragma: allowlist secret
OWN_SECRET = "own-aws-secret-41c0"  # noqa: S105  # pragma: allowlist secret
KEY = "this-instances-secret-key"
# What points a command at this instance, with settings of its own for a bucket and a pgvector store.
SOURCE_ENV = {
    "PATH": "/usr/bin",
    "LANGFLOW_DATABASE_URL": "sqlite:////data/langflow.db",
    "LANGFLOW_CONFIG_DIR": "/data",
    "LANGFLOW_KNOWLEDGE_BASES_DIR": "/data/knowledge_bases",
    "LANGFLOW_SECRET_KEY": KEY,
    "LANGFLOW_AUTO_LOGIN": "false",
    "LANGFLOW_STORAGE_TYPE": "local",
    "AWS_PROFILE": "the-servers-own",
    "AWS_SECRET_ACCESS_KEY": OWN_SECRET,
}
SECRETS = {
    "database_url": f"postgresql://migrator:{DB_PASSWORD}@db.internal:5432/langflow",
    "files": {"access_key_id": "AKIAEXAMPLE", "secret_access_key": S3_SECRET, "endpoint_url": None, "ca_bundle": None},
}
# The address as a command is given it: with the driver that serves the copies and the check alike.
READ_AS = f"postgresql+psycopg://migrator:{DB_PASSWORD}@db.internal:5432/langflow"
DATABASE = {"location": "db.internal:5432/langflow"}
FILES = {"bucket": "langflow-files", "prefix": "files", "endpoint_url": None}


def _printed(settings: list[dict]) -> list[str]:
    return [f"{setting['name']}={setting['value']}" for setting in settings]


def test_the_settings_name_where_the_copies_wrote_and_hold_a_place_for_every_secret():
    settings = start_settings(
        database="db.internal:5432/langflow",
        files={**FILES, "endpoint_url": "https://s3.internal:9000"},
        vectors="db.internal:5432/langflow",
        auto_login=False,
        superuser="admin",
    )

    assert _printed(settings) == [
        "LANGFLOW_DATABASE_URL=postgresql://<user>:<password>@db.internal:5432/langflow",
        "LANGFLOW_SECRET_KEY=<secret key>",
        "LANGFLOW_STORAGE_TYPE=s3",
        "LANGFLOW_OBJECT_STORAGE_BUCKET_NAME=langflow-files",  # pragma: allowlist secret
        "LANGFLOW_OBJECT_STORAGE_PREFIX=files",
        "AWS_ACCESS_KEY_ID=<access key id>",
        "AWS_SECRET_ACCESS_KEY=<secret access key>",
        "AWS_ENDPOINT_URL=https://s3.internal:9000",
        "PGVECTOR_CONNECTION_STRING=postgresql+psycopg://<user>:<password>@db.internal:5432/langflow",
        "LANGFLOW_AUTO_LOGIN=false",
        "LANGFLOW_SUPERUSER=admin",
        "LANGFLOW_SUPERUSER_PASSWORD=<password>",
    ]
    # Every value the admin has to put something into says so, and no other one does.
    assert {setting["name"] for setting in settings if setting["fill"]} == {
        setting["name"] for setting in settings if "<" in setting["value"]
    }


def test_the_settings_leave_out_what_this_instance_did_not_move():
    # Nothing but the database moved, and this instance signs everyone in as the default superuser.
    settings = start_settings(
        database="db.internal:5432/langflow", files=None, vectors=None, auto_login=True, superuser="langflow"
    )

    assert _printed(settings) == [
        "LANGFLOW_DATABASE_URL=postgresql://<user>:<password>@db.internal:5432/langflow",
        "LANGFLOW_SECRET_KEY=<secret key>",
        "LANGFLOW_AUTO_LOGIN=true",
    ]


def test_the_check_is_the_integrity_command_and_names_no_address():
    assert check_command() == [sys.executable, "-m", "langflow", "check-integrity", "--json"]


def test_the_check_reads_the_destination_and_nothing_of_this_instance():
    env = check_environment(SOURCE_ENV, SECRETS, {"database": DATABASE, "vectors": {}, "files": FILES}, None, "/empty")

    assert env == {
        "PATH": "/usr/bin",
        # The same key on both sides: the new instance opens what this one encrypted.
        "LANGFLOW_SECRET_KEY": KEY,
        "LANGFLOW_CONFIG_DIR": "/empty",
        "LANGFLOW_KNOWLEDGE_BASES_DIR": "/empty/knowledge_bases",
        "LANGFLOW_DATABASE_URL": READ_AS,
        "PGVECTOR_CONNECTION_STRING": READ_AS,
        "LANGFLOW_STORAGE_TYPE": "s3",
        "LANGFLOW_OBJECT_STORAGE_BUCKET_NAME": "langflow-files",
        "LANGFLOW_OBJECT_STORAGE_PREFIX": "files",
        "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE",
        "AWS_SECRET_ACCESS_KEY": S3_SECRET,
        "AWS_CONFIG_FILE": os.devnull,
        "AWS_SHARED_CREDENTIALS_FILE": os.devnull,
    }
    # Neither this instance's database and folders, nor the server's own way into AWS.
    assert not {"/data", "/data/knowledge_bases", "sqlite:////data/langflow.db", "the-servers-own", OWN_SECRET} & set(
        env.values()
    )


def test_a_check_with_nothing_but_a_database_moved_reads_no_bucket_and_no_store():
    env = check_environment(SOURCE_ENV, SECRETS, {"database": DATABASE}, None, "/empty")

    assert env["LANGFLOW_DATABASE_URL"] == READ_AS
    assert not [name for name in env if name.startswith(("AWS_", "PGVECTOR_")) or name == "LANGFLOW_STORAGE_TYPE"]


def test_an_instance_on_postgresql_is_checked_on_its_own_database_and_its_own_store():
    own = f"postgresql://langflow:{DB_PASSWORD}@own.internal:5432/langflow"
    store = f"postgresql+psycopg://langflow:{DB_PASSWORD}@own.internal:5432/vectors"
    source_env = {**SOURCE_ENV, "LANGFLOW_DATABASE_URL": own, "PGVECTOR_CONNECTION_STRING": store}

    # It keeps its database, so no address of another one was ever given.
    env = check_environment(source_env, {"files": SECRETS["files"]}, {"vectors": {}, "files": FILES}, None, "/empty")

    assert (env["LANGFLOW_DATABASE_URL"], env["PGVECTOR_CONNECTION_STRING"]) == (own, store)
    assert env["AWS_SECRET_ACCESS_KEY"] == S3_SECRET


def test_files_that_already_live_in_a_bucket_are_read_there_the_way_this_server_reads_them():
    own_bucket = {"storage": "s3", "bucket": "already-there", "prefix": "live", "local": False}

    env = check_environment(SOURCE_ENV, SECRETS, {"database": DATABASE}, own_bucket, "/empty")

    assert (env["LANGFLOW_STORAGE_TYPE"], env["LANGFLOW_OBJECT_STORAGE_BUCKET_NAME"]) == ("s3", "already-there")
    assert env["LANGFLOW_OBJECT_STORAGE_PREFIX"] == "live"
    assert (env["AWS_PROFILE"], env["AWS_SECRET_ACCESS_KEY"]) == ("the-servers-own", OWN_SECRET)


@pytest.mark.parametrize(
    ("secrets", "destinations"),
    [
        # The worker restarted, or was never given the destination.
        ({}, {"database": DATABASE}),
        # It holds the database and not the keys of the bucket.
        ({"database_url": SECRETS["database_url"]}, {"database": DATABASE, "files": FILES}),
    ],
)
def test_a_check_without_a_secret_it_needs_is_refused_before_it_reads_this_instance(secrets, destinations):
    with pytest.raises(KeyError):
        check_environment(SOURCE_ENV, secrets, destinations, None, "/empty")


def _check(name: str, summary: str, status: str = "ok", problems: list[str] | None = None) -> dict:
    return {"name": name, "status": status, "summary": summary, "problems": problems or []}


def test_each_check_of_the_destination_is_read_beside_this_instances():
    here = [
        _check("version", "same version"),
        _check("source: schema", "database at revision abc"),
        _check("source: files", "2 of 12 file rows point at bytes storage does not hold", "fail", ["a.txt", "b.txt"]),
        _check("source: credentials", "8 encrypted values, all open with the configured secret key"),
    ]
    there = [
        _check("schema", "database at revision abc"),
        # The same failure the admin accepted on this instance: nothing was lost on the way.
        _check("files", "2 of 12 file rows point at bytes storage does not hold", "fail", ["a.txt", "b.txt"]),
        _check("credentials", "9 encrypted values, all open with the configured secret key"),
        _check("memory bases", "0 memory bases with ingested messages, each backed by a non-empty knowledge base"),
    ]

    report = compare(there, here, {"source: files"})

    assert [(row["name"], row["same"], row["accepted"]) for row in report["checks"]] == [
        ("schema", True, False),
        ("files", True, True),
        ("credentials", False, False),
        # This instance's check said nothing of it, so it cannot be called the same.
        ("memory bases", False, False),
    ]
    assert report["ok"] is False
    files = report["checks"][1]
    assert files["there"] == {
        "status": "fail",
        "summary": "2 of 12 file rows point at bytes storage does not hold",
        "problems": ["a.txt", "b.txt"],
    }
    assert files["here"] == {"status": "fail", "summary": "2 of 12 file rows point at bytes storage does not hold"}
    assert report["checks"][3]["here"] is None


def test_a_destination_that_reads_the_same_everywhere_passes_and_an_empty_report_does_not():
    here = [_check("source: schema", "database at revision abc"), _check("source: files", "0 file rows")]
    there = [_check("schema", "database at revision abc"), _check("files", "0 file rows")]

    assert compare(there, here, set())["ok"] is True
    assert compare([], here, set())["ok"] is False


def test_an_accepted_failure_that_reads_otherwise_on_the_destination_is_a_difference():
    here = [_check("source: files", "2 of 12 file rows point at bytes storage does not hold", "fail")]
    there = [_check("files", "5 of 12 file rows point at bytes storage does not hold", "fail")]

    report = compare(there, here, {"source: files"})

    assert (report["ok"], report["checks"][0]["same"], report["checks"][0]["accepted"]) == (False, False, True)


HERE = [_check("source: schema", "database at revision abc")]
THERE = {"event": "report", "ok": False, "checks": [_check("schema", "the database could not be reached", "fail")]}
ENDED = {"finished_at": "2026-09-30T02:00:00+00:00", "stderr": "Traceback: no driver\n"}


def test_a_check_that_found_a_failure_ended_done_whatever_its_exit_code():
    # check-integrity exits with an error when a check fails. Its report is the result all the same.
    outcome = check_outcome({**ENDED, "status": "failed"}, {"report": THERE}, HERE, set())

    assert (outcome["status"], outcome["error"], outcome["finished_at"]) == ("done", None, ENDED["finished_at"])
    assert (outcome["report"]["ok"], outcome["report"]["checks"][0]["same"]) == (False, False)


@pytest.mark.parametrize(
    ("status", "error"),
    [
        ("failed", {"code": "crashed", "message": "Traceback: no driver\n"}),
        # It exited as if all went well and printed no report: there is nothing to finish a move on.
        ("done", {"code": "crashed", "message": "Traceback: no driver\n"}),
        ("cancelled", {"code": "cancelled"}),
        ("interrupted", {"code": "interrupted"}),
    ],
)
def test_a_check_that_printed_no_report_is_kept_with_what_explains_it(status, error):
    outcome = check_outcome({**ENDED, "status": status}, {}, HERE, set())

    assert (outcome["error"], outcome["report"]) == (error, None)
    assert outcome["status"] == ("failed" if error["code"] == "crashed" else status)


def test_a_check_that_was_stopped_is_not_read_as_a_result_even_when_it_had_reported():
    outcome = check_outcome({**ENDED, "status": "cancelled"}, {"report": THERE}, HERE, set())

    assert (outcome["status"], outcome["report"]) == ("cancelled", None)


def test_the_check_may_dial_the_stores_that_this_server_may_dial():
    allowed = {
        "LANGFLOW_SSRF_PROTECTION_ENABLED": "true",
        "LANGFLOW_SSRF_ALLOWED_HOSTS": "10.0.3.7",
        "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED": "true",
        "LANGFLOW_KB_ALLOWED_HOSTS": "search.internal",
    }
    source_env = {**SOURCE_ENV, **allowed, "OPENSEARCH_URL": "https://10.0.3.7:9200"}

    env = check_environment(source_env, SECRETS, {"database": DATABASE}, None, "/empty")

    # The first step checked this instance with them. A store that only they let through would read as
    # out of reach without them, which says nothing of the new instance.
    assert {name: env[name] for name in allowed} == allowed
    assert env["OPENSEARCH_URL"] == "https://10.0.3.7:9200"


def test_the_examples_under_a_failure_are_shown_and_not_compared():
    summary = "2 of 12 file rows point at bytes storage does not hold"
    here = [_check("source: files", summary, "fail", ["b.txt", "a.txt"])]
    # The same two files, as another database lists them.
    there = [_check("files", summary, "fail", ["a.txt", "b.txt"])]

    report = compare(there, here, {"source: files"})

    # A check lists at most five examples, in no fixed order. Two samples of one failure can differ.
    assert [(row["same"], row["accepted"]) for row in report["checks"]] == [(True, True)]
    assert report["checks"][0]["there"]["problems"] == ["a.txt", "b.txt"]
