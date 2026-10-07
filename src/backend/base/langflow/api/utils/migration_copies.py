"""What the copy steps of a migration run, and how a run that has ended is read.

A copy is one of Langflow's own commands. The migration endpoints start it and
migration_runs keeps it going. What is here holds no state: the command and the
environment of a step, what the migration record keeps of a run once it has ended,
and why such a run does not complete its step.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from langflow.services.database.sqlite_to_postgres import _sync_postgres_url

# The copy steps in page order, and the command each one runs.
COPY_COMMANDS = {
    "copy_database": ("convert-sqlite-to-postgres", "--json"),
    "copy_knowledge_bases": ("relocate-kb", "--to", "postgres", "--json"),
    "copy_files": ("relocate-files", "--json"),
}
# The events of a run that say how it went. The others say how far it has got.
KEPT_EVENTS = ("report", "error", "decision_needed")
# How many failed items of a report the record keeps. Every one of them is in the run's events.
_ATTENTION_KEPT = 100
# The server's own settings for Langflow and for AWS say where this instance keeps its data, and a
# copy writes somewhere else. So a copy takes none of them, and is told by name the ones it needs.
_OWN_SETTINGS = ("LANGFLOW_", "AWS_", "PGVECTOR_")
# What a copy still reads from this instance.
_SOURCE_SETTINGS = ("LANGFLOW_CONFIG_DIR", "LANGFLOW_KNOWLEDGE_BASES_DIR", "LANGFLOW_SECRET_KEY")


def copy_command(step_id: str, destinations: dict[str, Any], *, dry_run: bool = False) -> list[str]:
    """The command line of a step. It names no address and no key: any user of the machine can read it.

    destinations is what the record says of where the data goes, which holds no secret.
    """
    argv = [sys.executable, "-m", "langflow", *COPY_COMMANDS[step_id]]
    if step_id == "copy_files":
        argv += ["--bucket", destinations["files"]["bucket"], "--prefix", destinations["files"]["prefix"]]
    return [*argv, "--dry-run"] if dry_run else argv


def copy_environment(step_id: str, source_env: dict[str, str], secrets: dict[str, Any]) -> dict[str, str]:
    """The environment a step's command runs in: this instance to read from, and the destination to write to.

    source_env is the server's environment with what points a command at this instance.
    secrets is what this worker was given of the destination. Raises KeyError when the
    step needs one that is not there, because the next place to write would be this instance.
    """
    env = {
        name: value
        for name, value in source_env.items()
        if name in _SOURCE_SETTINGS or not name.startswith(_OWN_SETTINGS)
    }
    own_database = source_env["LANGFLOW_DATABASE_URL"]
    if step_id == "copy_database":
        env["LANGFLOW_MIGRATION_SOURCE_URL"] = own_database
        env["LANGFLOW_MIGRATION_TARGET_URL"] = secrets["database_url"]
        return env
    # The other copies work on the database the new instance will run on, which the first copy filled.
    # An instance already on PostgreSQL keeps its own. The destination's address is read with the driver
    # its test and the database copy read it with, whichever one it was typed for.
    on_postgresql = own_database.startswith("postgres")
    env["LANGFLOW_DATABASE_URL"] = own_database if on_postgresql else _sync_postgres_url(secrets["database_url"])
    if step_id == "copy_knowledge_bases":
        # The vectors go into the same database, as pgvector tables. An instance already on PostgreSQL goes on
        # serving from its database, and reads a knowledge base in pgvector from the store its own environment
        # names. So there the copy writes to that store, whichever database it is.
        env["PGVECTOR_CONNECTION_STRING"] = (
            source_env["PGVECTOR_CONNECTION_STRING"] if on_postgresql else env["LANGFLOW_DATABASE_URL"]
        )
        return env
    files = secrets["files"]
    env["AWS_ACCESS_KEY_ID"] = files["access_key_id"]
    env["AWS_SECRET_ACCESS_KEY"] = files["secret_access_key"]
    # The server's AWS files can name a profile, keys and an endpoint of its own. An empty file takes their place.
    env["AWS_CONFIG_FILE"] = env["AWS_SHARED_CREDENTIALS_FILE"] = os.devnull
    if files["endpoint_url"]:
        env["AWS_ENDPOINT_URL"] = files["endpoint_url"]
    if files["ca_bundle"]:
        env["AWS_CA_BUNDLE"] = files["ca_bundle"]
    return env


def copy_outcome(run: dict[str, Any], events: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """What the record keeps of a run that has ended.

    run is its status from migration_runs, and events the last one of each of KEPT_EVENTS
    that it printed. A run that did not end done is kept with the code that explains it:
    the command's own when it said why it stopped, or crashed, cancelled or interrupted.
    """
    error = None
    if run["status"] == "failed":
        said = events.get("error", {})
        # A command that died without a word leaves only its last lines on stderr.
        error = {"code": said.get("code", "crashed"), "message": said.get("message", run["stderr"])}
    elif run["status"] != "done":
        error = {"code": run["status"]}
    report = _as_printed(events.get("report"))
    if report and "attention" in report:
        # ponytail: a report can list every file of an instance, and the record is read on each request,
        # so it keeps the first of them. The report's counts still say how many failed.
        report["attention"] = report["attention"][:_ATTENTION_KEPT]
    return {
        "status": run["status"],
        "finished_at": run["finished_at"],
        "report": report,
        "error": error,
        "decision_needed": _as_printed(events.get("decision_needed")),
    }


def blocking_code(run: dict[str, Any]) -> str | None:
    """Why a run that has ended does not complete its step, or None when it does."""
    if run["error"]:
        return run["error"]["code"]
    report = run["report"]
    if report["ok"]:
        return None
    if "attention" in report:
        # A knowledge base or a file that was not copied.
        return report["attention"][0]["code"]
    codes = [problem["code"] for problem in report["problems"]]
    # Rows that point at nothing can be left out on the admin's word, once nothing else stands in the way.
    return next((code for code in codes if code != "orphans_droppable"), codes[0])


def _as_printed(event: dict[str, Any] | None) -> dict[str, Any] | None:
    """An event without the two fields that only place it in the run's log."""
    return event and {key: value for key, value in event.items() if key not in ("event", "seq")}
