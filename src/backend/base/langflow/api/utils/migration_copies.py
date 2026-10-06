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
# What an admin may decide about a copy. Each decision belongs to one step and answers some codes of its command.
# One that stands for an option of the command adds it to every later run of the step. One without an option
# accepts a failed item of one run as it is, so the item no longer blocks the step. An item can be accepted only
# when running the copy again cannot get past its code and accepting it loses nothing a copy would have saved.
# What can be put right and copied again, such as an ingestion that is still running, has no decision.
DECISIONS: dict[str, dict[str, Any]] = {
    "drop_orphans": {"step": "copy_database", "option": "--drop-orphans", "codes": ("orphans_droppable",)},
    "accept_ranking_change": {
        "step": "copy_knowledge_bases",
        "option": "--allow-metric-change",
        "codes": ("kb_metric_change",),
    },
    # This version has no backend for the store, the store holds fewer chunks than its row says and someone
    # has to look at it, or its row names the destination and its chunks are not there. This instance keeps
    # the knowledge base either way.
    "leave_behind": {
        "step": "copy_knowledge_bases",
        "option": None,
        "codes": ("kb_backend_missing", "kb_short", "kb_target_short"),
    },
    "keep_bucket_file": {"step": "copy_files", "option": None, "codes": ("file_conflict",)},
    # The database names a file that this instance's storage holds no bytes for.
    "accept_missing_attachment": {
        "step": "copy_files",
        "option": None,
        "codes": ("no_source_bytes", "attachment_unmatched"),
    },
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


def copy_command(
    step_id: str, destinations: dict[str, Any], decisions: list[dict[str, Any]], *, dry_run: bool = False
) -> list[str]:
    """The command line of a step. It names no address and no key: any user of the machine can read it.

    destinations is what the record says of where the data goes, which holds no secret,
    and decisions what it says the admin decided.
    """
    argv = [sys.executable, "-m", "langflow", *COPY_COMMANDS[step_id]]
    if step_id == "copy_knowledge_bases":
        # A copy from SQLite is given the destination as its pgvector store (see copy_environment), and the
        # database copy brought each knowledge base's row as it is. A row that already says pgvector then
        # names the destination, whichever store holds its chunks, so the command counts it there before it
        # skips it. On PostgreSQL the copy reads the server's own store, where the check step has counted
        # every such row, so there it is told not to. The option is given either way: the command's own
        # default is for a person who runs it by hand.
        argv.append("--verify-skipped" if "database" in destinations else "--no-verify-skipped")
    if step_id == "copy_files":
        argv += ["--bucket", destinations["files"]["bucket"], "--prefix", destinations["files"]["prefix"]]
    options = [DECISIONS[made["kind"]]["option"] for made in decisions if made["step"] == step_id]
    argv += [option for option in options if option]
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


def copy_outcome(step_id: str, run: dict[str, Any], events: dict[str, dict[str, Any]]) -> dict[str, Any]:
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
        report["attention"] = [_to_decide(step_id, item) for item in report["attention"][:_ATTENTION_KEPT]]
    asked = _as_printed(events.get("decision_needed"))
    if asked:
        asked["decision"] = _answer(step_id, asked["code"], None)
    return {
        "status": run["status"],
        "finished_at": run["finished_at"],
        "report": report,
        "error": error,
        "decision_needed": asked,
    }


def blocking_code(step_id: str, run: dict[str, Any], decisions: list[dict[str, Any]]) -> str | None:
    """Why a run that has ended does not complete its step, or None when it does.

    A knowledge base or a file that was not copied blocks the step until the admin accepts it, with the
    decision the record gave it. A decision that answers another code is on record and accepts nothing.
    Nor does one that was made about the report of an earlier run: each run asks again.
    """
    if run["error"]:
        return run["error"]["code"]
    report = run["report"]
    if report["ok"]:
        return None
    if "attention" in report:
        failed = report["attention"]
        # The record may hold fewer items than failed. The ones it does not hold cannot have been accepted.
        if report["counts"]["failed"] <= len(failed):
            # An option names no item, so it accepts none: it changes the next run.
            accepted = [
                {"kind": made["kind"], "subject": made["subject"]}
                for made in decisions
                if made["step"] == step_id and made["subject"] and made.get("run_id") == run["run_id"]
            ]
            failed = [item for item in failed if item["decision"] not in accepted]
        return failed[0]["code"] if failed else None
    codes = [problem["code"] for problem in report["problems"]]
    # Rows that point at nothing can be left out on the admin's word, once nothing else stands in the way.
    return next((code for code in codes if code != "orphans_droppable"), codes[0])


def _to_decide(step_id: str, item: dict[str, Any]) -> dict[str, Any]:
    """A failed item as the record keeps it: named, and with the decision that answers its code.

    Its name is a knowledge base's id, or a file's owner and name.
    """
    subject = item.get("kb_id") or f"{item['owner']}/{item['file_name']}"
    return {**item, "subject": subject, "decision": _answer(step_id, item["code"], subject)}


def _answer(step_id: str, code: str, subject: str | None) -> dict[str, str | None] | None:
    """The decision that answers a code, as a request to decide names it, or None when none does."""
    for kind, decision in DECISIONS.items():
        if decision["step"] == step_id and code in decision["codes"]:
            # An option is for the whole step. Only accepting an item names one.
            return {"kind": kind, "subject": None if decision["option"] else subject}
    return None


def _as_printed(event: dict[str, Any] | None) -> dict[str, Any] | None:
    """An event without the two fields that only place it in the run's log."""
    return event and {key: value for key, value in event.items() if key not in ("event", "seq")}
