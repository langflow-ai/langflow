"""The events ``convert-sqlite-to-postgres --json`` writes, one JSON object per line."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from langflow.cli.events import emit

if TYPE_CHECKING:
    from langflow.services.database.sqlite_to_postgres import ConversionReport, TableCopy


def emit_progress(phase: str, done: int, total: int | None, table: str | None) -> None:
    # Before the copy there is no total and no table yet: total is null, never a placeholder 0.
    subject = {} if table is None else {"subject": table}
    emit("progress", phase=phase, done=done, total=total, unit="rows", **subject)


def emit_table(table: TableCopy) -> None:
    emit("item", item={"table": table.name, "source_rows": table.source_rows, "target_rows": table.target_rows})


def emit_report(report: ConversionReport) -> None:
    """Emit what was refused or failed, then the report line that ends every --json run."""
    if report.problems and all(problem.code == "orphans_droppable" for problem in report.problems):
        # The one refusal a rerun settles, so the caller gets the flag and the rows it is deciding about.
        emit(
            "decision_needed",
            code="orphans_droppable",
            message=f"{len(report.problems)} foreign key(s) point at rows that are gone. Rerun with --drop-orphans to "
            "leave out the rows ON DELETE CASCADE would have deleted and clear the keys ON DELETE SET NULL "
            "would have cleared.",
            flag="--drop-orphans",
            details={"orphans": [asdict(problem.orphans) for problem in report.problems if problem.orphans]},
        )
    else:
        for problem in report.problems:
            emit("error", code=problem.code, message=str(problem))
    # A failed copy is rolled back, so the tables it had counted hold no rows.
    tables = report.tables if report.ok else []
    emit(
        "report",
        ok=report.ok,
        revision=report.revision,
        tables_copied=len(tables),
        rows_copied=sum(table.target_rows for table in tables),
        orphans=[asdict(orphans) for orphans in report.orphans],
        problems=[{"code": problem.code, "message": str(problem)} for problem in report.problems],
    )
