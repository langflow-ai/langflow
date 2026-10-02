"""The events ``langflow relocate-kb --json`` writes to stdout."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

import typer

from langflow.cli.events import emit

if TYPE_CHECKING:
    from langflow.api.utils.knowledge_base_relocation import KBRelocationResult


def refuse(message: str, code: str, *, as_json: bool) -> None:
    """Say why the run will not start: an error event on stdout with --json, the message on stderr without."""
    if as_json:
        emit("error", code=code, message=message)
    else:
        typer.echo(message, err=True)


def progress(result: KBRelocationResult) -> None:
    """How many of a knowledge base's chunks are copied so far."""
    # Chunks copied from a source that counted none means the count was wrong, so the total is not known.
    total = result.source_count or None
    emit("progress", phase="copying", done=result.copied, total=total, unit="chunks", subject=str(result.kb_id))


def item(result: KBRelocationResult) -> None:
    """One knowledge base's result, written as it finishes."""
    emit("item", item=asdict(result))


def report(results: list[KBRelocationResult], counts: dict[str, int], *, dry_run: bool) -> None:
    """The closing line of a run that reached its end."""
    # Each knowledge base was already written as an item, so the report repeats
    # only the ones that failed, which are the ones to act on.
    attention = [asdict(result) for result in results if result.status == "failed"]
    emit("report", ok=not attention, dry_run=dry_run, counts=counts, attention=attention)
