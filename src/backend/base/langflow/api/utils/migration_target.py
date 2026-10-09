"""What the last two steps of a migration need: checking the copy, and starting the new instance.

The check of the copy runs Langflow's own integrity check against what the copies wrote,
before any new instance has started on it, and reads each of its results beside what the
check of this instance said of the same thing. "Start the new instance" hands the admin
the settings a Langflow server has to start with so that it runs on that same place.
What is here holds no state.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from langflow.api.utils.migration_copies import bucket_environment, foreign_environment
from langflow.services.database.sqlite_to_postgres import _sync_postgres_url

# The step that checks what the copies wrote. Its command is a run, like a copy.
CHECK_STEP = "check_target"
# What migration-preflight calls a check that check-integrity runs, when it runs it against this instance.
_HERE = "source: "
# The settings that say which stores this server may dial. The first step checked this instance with them,
# and a store that only they let through would read as out of reach without them.
_DIAL_SETTINGS = (
    "LANGFLOW_SSRF_PROTECTION_ENABLED",
    "LANGFLOW_SSRF_ALLOWED_HOSTS",
    "LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED",
    "LANGFLOW_KB_ALLOWED_HOSTS",
)


def start_settings(
    *,
    database: str | None,
    files: dict[str, Any] | None,
    vectors: str | None,
    auto_login: bool,
    superuser: str,
) -> list[dict[str, Any]]:
    """The settings a new instance starts with, in the order a page prints them.

    database and vectors say where each is ("db.internal:5432/langflow"), with no user and no
    password, and files names the bucket, the prefix and the endpoint. Nothing here is a
    secret. Where the admin has to put something in, the value says what in angle brackets
    and fill is true.
    """
    settings: list[dict[str, Any]] = []

    def add(name: str, value: str, *, fill: bool = False) -> None:
        settings.append({"name": name, "value": value, "fill": fill})

    if database:
        add("LANGFLOW_DATABASE_URL", f"postgresql://<user>:<password>@{database}", fill=True)
    # The new instance opens what this one encrypted, so it has to hold the same key.
    add("LANGFLOW_SECRET_KEY", "<secret key>", fill=True)
    if files:
        add("LANGFLOW_STORAGE_TYPE", "s3")
        add("LANGFLOW_OBJECT_STORAGE_BUCKET_NAME", files["bucket"])
        add("LANGFLOW_OBJECT_STORAGE_PREFIX", files["prefix"])
        add("AWS_ACCESS_KEY_ID", "<access key id>", fill=True)
        add("AWS_SECRET_ACCESS_KEY", "<secret access key>", fill=True)
        if files.get("endpoint_url"):
            add("AWS_ENDPOINT_URL", files["endpoint_url"])
    if vectors:
        add("PGVECTOR_CONNECTION_STRING", f"postgresql+psycopg://<user>:<password>@{vectors}", fill=True)
    # What a first boot does with the default superuser depends on these, so the new instance is given
    # what this one runs with. The check of the default superuser says more.
    add("LANGFLOW_AUTO_LOGIN", "true" if auto_login else "false")
    if not auto_login:
        add("LANGFLOW_SUPERUSER", superuser)
        add("LANGFLOW_SUPERUSER_PASSWORD", "<password>", fill=True)
    return settings


def check_command() -> list[str]:
    """The command that checks an instance against itself. It reads, and writes nothing."""
    return [sys.executable, "-m", "langflow", "check-integrity", "--json"]


def check_environment(
    source_env: dict[str, str],
    secrets: dict[str, Any],
    destinations: dict[str, Any],
    own_bucket: dict[str, Any] | None,
    empty_folder: str,
) -> dict[str, str]:
    """The environment that points the integrity check at what the new instance will run on.

    source_env is the server's environment with what points a command at this instance,
    secrets what this worker was given of the destination, and destinations what the record
    says of it. own_bucket is where this instance already keeps its files, when that is a
    bucket: the new instance reads them there too. empty_folder stands for the new instance's
    own folders, which hold nothing of this one. Raises KeyError when a secret the check needs
    is not there, because the next place to read would be this instance.
    """
    # The key is the same on both sides: the new instance opens what this one encrypted.
    env = foreign_environment(source_env, keep=("LANGFLOW_SECRET_KEY", *_DIAL_SETTINGS))
    env["LANGFLOW_CONFIG_DIR"] = empty_folder
    env["LANGFLOW_KNOWLEDGE_BASES_DIR"] = str(Path(empty_folder) / "knowledge_bases")
    own_database = source_env["LANGFLOW_DATABASE_URL"]
    # An instance already on PostgreSQL keeps its database, and the new instance runs on it.
    on_postgresql = own_database.startswith("postgres")
    env["LANGFLOW_DATABASE_URL"] = own_database if on_postgresql else _sync_postgres_url(secrets["database_url"])
    if "vectors" in destinations and not on_postgresql:
        # The knowledge bases went into the destination database, as pgvector tables.
        env["PGVECTOR_CONNECTION_STRING"] = env["LANGFLOW_DATABASE_URL"]
    elif "PGVECTOR_CONNECTION_STRING" in source_env:
        # The store this server reads knowledge bases in pgvector from, and the new instance after it.
        env["PGVECTOR_CONNECTION_STRING"] = source_env["PGVECTOR_CONNECTION_STRING"]
    bucket = destinations.get("files") or own_bucket
    if bucket:
        env["LANGFLOW_STORAGE_TYPE"] = "s3"
        env["LANGFLOW_OBJECT_STORAGE_BUCKET_NAME"] = bucket["bucket"]
        env["LANGFLOW_OBJECT_STORAGE_PREFIX"] = bucket["prefix"]
    if "files" in destinations:
        env.update(bucket_environment(secrets["files"]))
    elif own_bucket:
        # This instance's own bucket, reached the way this server reaches it.
        env.update({name: value for name, value in source_env.items() if name.startswith("AWS_")})
    return env


def compare(there: list[dict[str, Any]], here: list[dict[str, Any]], accepted: set[str]) -> dict[str, Any]:
    """The destination's checks, each beside what the check of this instance said of the same thing.

    there is what check-integrity printed for the destination. here is the report of the
    check this instance passed, where migration-preflight names each of those checks
    "source: <name>", and accepted the names of the ones that failed there and that the
    admin accepted. Two results are the same when their status and their summary are: a
    summary counts what the check read and names no place. The examples under a failure are
    a sample of at most five, in no fixed order, so they are shown and not compared. An
    accepted failure that reads the same on the destination is the same. One that reads
    otherwise there is a difference.
    """
    mine = {check["name"].removeprefix(_HERE): check for check in here if check["name"].startswith(_HERE)}
    checks = []
    for check in there:
        twin = mine.get(check["name"])
        checks.append(
            {
                "name": check["name"],
                "there": {
                    "status": check["status"],
                    "summary": check["summary"],
                    "problems": check.get("problems", []),
                },
                "here": {"status": twin["status"], "summary": twin["summary"]} if twin else None,
                "same": bool(twin) and (twin["status"], twin["summary"]) == (check["status"], check["summary"]),
                "accepted": f"{_HERE}{check['name']}" in accepted,
            }
        )
    # A report with no check in it says nothing, so it is not one that passed.
    return {"ok": bool(checks) and all(check["same"] for check in checks), "checks": checks}


def check_outcome(
    run: dict[str, Any], events: dict[str, dict[str, Any]], here: list[dict[str, Any]], accepted: set[str]
) -> dict[str, Any]:
    """What the record keeps of a check of the copy that has ended.

    run is its status from migration_runs, and events the last one of each kind it printed.
    check-integrity exits with an error when a check fails. That is a result and no crash,
    so a run that printed its report ended done, whatever its exit code. A run with no
    report is kept with the code that explains it: crashed, cancelled or interrupted.
    """
    report = events.get("report")
    if report and run["status"] in {"done", "failed"}:
        outcome = {"status": "done", "error": None, "report": compare(report["checks"], here, accepted)}
    elif run["status"] in {"done", "failed"}:
        # A command that died without a word leaves only its last lines on stderr.
        outcome = {"status": "failed", "error": {"code": "crashed", "message": run["stderr"]}, "report": None}
    else:
        outcome = {"status": run["status"], "error": {"code": run["status"]}, "report": None}
    return {**outcome, "finished_at": run["finished_at"]}
