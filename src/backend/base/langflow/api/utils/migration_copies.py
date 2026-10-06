"""What the copy steps of a migration run, and how a run that has ended is read.

A copy is one of Langflow's own commands. The migration endpoints start it and
migration_runs keeps it going. What is here holds no state: the command and the
environment of a step, what the migration record keeps of a run once it has ended,
and why such a run does not complete its step.
"""

from __future__ import annotations

import sys
from typing import Any

# The copy steps in page order, and the command each one runs.
COPY_COMMANDS = {
    "copy_database": ("convert-sqlite-to-postgres", "--json"),
}
# The events of a run that say how it went. The others say how far it has got.
KEPT_EVENTS = ("report", "error", "decision_needed")
# The server's own settings for Langflow and for AWS say where this instance keeps its data, and a
# copy writes somewhere else. So a copy takes none of them, and is told by name the ones it needs.
_OWN_SETTINGS = ("LANGFLOW_", "AWS_", "PGVECTOR_")
# What a copy still reads from this instance.
_SOURCE_SETTINGS = ("LANGFLOW_CONFIG_DIR", "LANGFLOW_KNOWLEDGE_BASES_DIR", "LANGFLOW_SECRET_KEY")


def copy_command(step_id: str) -> list[str]:
    """The command line of a step. It names no address and no key: any user of the machine can read it."""
    return [sys.executable, "-m", "langflow", *COPY_COMMANDS[step_id]]


def copy_environment(source_env: dict[str, str], secrets: dict[str, Any]) -> dict[str, str]:
    """The environment a copy runs in: this instance to read from, and the destination to write to.

    source_env is the server's environment with what points a command at this instance.
    secrets is what this worker was given of the destination. Raises KeyError when the
    copy needs one that is not there, because the next place to write would be this instance.
    """
    env = {
        name: value
        for name, value in source_env.items()
        if name in _SOURCE_SETTINGS or not name.startswith(_OWN_SETTINGS)
    }
    env["LANGFLOW_MIGRATION_SOURCE_URL"] = source_env["LANGFLOW_DATABASE_URL"]
    env["LANGFLOW_MIGRATION_TARGET_URL"] = secrets["database_url"]
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
    return {
        "status": run["status"],
        "finished_at": run["finished_at"],
        "report": _as_printed(events.get("report")),
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
    codes = [problem["code"] for problem in report["problems"]]
    # Rows that point at nothing can be left out on the admin's word, once nothing else stands in the way.
    return next((code for code in codes if code != "orphans_droppable"), codes[0])


def _as_printed(event: dict[str, Any] | None) -> dict[str, Any] | None:
    """An event without the two fields that only place it in the run's log."""
    return event and {key: value for key, value in event.items() if key not in ("event", "seq")}
