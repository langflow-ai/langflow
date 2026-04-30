"""Extension authoring commands: ``lfx extension validate`` and ``lfx extension schema``.

Sub-app rather than a flat command so that future tickets (LE-1016: ``init``,
``dev``; LE-1018: ``reload``; etc.) can attach without a top-level naming
collision with the existing ``lfx validate`` (which validates flow JSON, not
extensions).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

extension_app = typer.Typer(
    name="extension",
    help="Author and inspect Langflow Extensions (LE-1014 foundation).",
    no_args_is_help=True,
    add_completion=False,
)


def register(app: typer.Typer) -> None:
    """Mount the ``extension`` sub-app on *app* under the Authoring help panel."""
    app.add_typer(extension_app, name="extension", rich_help_panel="Authoring")


@extension_app.command(
    name="validate",
    help="Statically validate an extension manifest and bundle (offline by default).",
)
def validate_command(
    root: str = typer.Argument(
        ".",
        help=(
            "Path to the extension root (the directory containing extension.json "
            "or pyproject.toml). Defaults to the current directory."
        ),
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        "-f",
        help="Output format: text (default) or json.",
    ),
    *,
    execute_imports: bool = typer.Option(
        False,  # noqa: FBT003 - typer Option requires positional default
        "--execute-imports",
        help=(
            "Additionally run each bundle module in a fresh subprocess to "
            "surface import-time errors. Opt-in only: never invoked in pack, "
            "publish, install, or registry-ingest pipelines."
        ),
    ),
) -> None:
    """Run the offline LE-1014 validator and exit non-zero on any error.

    By default this performs:
      1. Manifest discovery and Pydantic schema validation.
      2. Path-safety checks on every declared bundle path.
      3. AST-level inspection of every Python source file in each bundle.

    With ``--execute-imports``, additionally imports each bundle module in a
    subprocess with a temporary Langflow state directory.
    """
    from lfx.extension import format_extension_error, validate_extension

    target = Path(root)
    report = validate_extension(target, execute_imports=execute_imports)

    if output_format not in {"text", "json"}:
        typer.echo("Invalid --format. Expected one of: text, json.", err=True)
        raise typer.Exit(code=2)

    if output_format == "json":
        payload = {
            "ok": report.ok,
            "root": str(report.root),
            "manifest": report.manifest.model_dump(by_alias=True, mode="json") if report.manifest is not None else None,
            "errors": [e.to_dict() for e in report.errors.errors],
            "warnings": [w.to_dict() for w in report.errors.warnings],
            "bundle_files_scanned": report.bundle_files_scanned,
        }
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if report.ok:
            typer.echo(f"validate: ok ({report.bundle_files_scanned} file(s) scanned)")
        else:
            for error in report.errors.errors:
                typer.echo(format_extension_error(error), err=True)
                typer.echo("", err=True)
        for warning in report.errors.warnings:
            typer.echo(format_extension_error(warning), err=True)

    if not report.ok:
        raise typer.Exit(code=1)


@extension_app.command(
    name="schema",
    help="Print the JSON Schema for the extension manifest (writeable to disk).",
)
def schema_command(
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the schema to this path instead of stdout.",
    ),
) -> None:
    """Emit the v1 manifest JSON Schema.

    Use to vendor a copy under ``schemas/`` or to confirm the canonical shape
    for editor tooling.  The schema's ``$id`` always points at
    ``schemas.langflow.org/extension/v1.json``; the release pipeline uploads
    this same artifact.
    """
    from lfx.extension.schema import build_schema_json

    payload = build_schema_json()
    if output:
        Path(output).write_text(payload, encoding="utf-8")
        typer.echo(f"Schema written to {output}")
    else:
        sys.stdout.write(payload)
