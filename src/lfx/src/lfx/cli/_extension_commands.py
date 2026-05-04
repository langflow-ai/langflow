"""Extension authoring commands: ``lfx extension validate`` and ``lfx extension schema``.

Sub-app rather than a flat command so future authoring verbs (``init``,
``dev``, ``reload``, ...) can attach without a top-level naming collision with
the existing ``lfx validate`` (which validates flow JSON, not extensions).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

extension_app = typer.Typer(
    name="extension",
    help="Author and inspect Langflow Extensions.",
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
    """Run the offline extension validator and exit non-zero on any error.

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
    name="list",
    help="List installed and seed-directory Extensions discovered at startup.",
)
def list_command(
    output_format: str = typer.Option(
        "text",
        "--format",
        "-f",
        help="Output format: text (default) or json.",
    ),
    seed_dir: str | None = typer.Option(
        None,
        "--seed-dir",
        help=(
            "Override $LANGFLOW_SEED_DIR for this invocation. "
            "Use os.pathsep (':' on POSIX) to pass multiple roots. "
            "Pass an empty string to skip the seed-directory pass entirely."
        ),
    ),
) -> None:
    """Print every Extension currently visible to production discovery.

    Read-only.  Mutation verbs (enable, disable, install, uninstall) are
    intentionally absent in this milestone; they ship in B3/B4 follow-up
    epics, and the router-trust CI guard (LE-1017) blocks them from
    sneaking in via HTTP routes.

    Output (text mode) is one row per Extension::

        ID                  VERSION   BUNDLE              SLOT       SOURCE   STATUS
        lfx-openai          1.2.0     openai              @official  installed  discovered
        lfx-anthropic       0.4.1     anthropic           @official  seed       discovered

    Errors from discovery (malformed manifests, missing seed dirs) are
    appended after the table, separated by a blank line, and rendered with
    :func:`~lfx.extension.format_extension_error`.

    JSON mode emits a stable structure that downstream tooling can pin to::

        {
          "extensions": [...],
          "errors":     [...]
        }
    """
    from lfx.extension import (
        build_registry_from_discovery,
        discover_all_extensions,
        format_extension_error,
    )

    if output_format not in {"text", "json"}:
        typer.echo("Invalid --format. Expected one of: text, json.", err=True)
        raise typer.Exit(code=2)

    extensions, errors = discover_all_extensions(seed_dir_env=seed_dir)
    registry, dup_errors = build_registry_from_discovery(extensions)
    all_errors = errors + dup_errors
    rows = registry.list_extensions()

    if output_format == "json":
        payload = {
            "extensions": [
                {
                    "id": ext.extension_id,
                    "version": ext.version,
                    "bundle": ext.bundle_name,
                    "slot": ext.namespaced_slot,
                    "source_kind": ext.source_kind,
                    "source": ext.source,
                    "extension_root": str(ext.extension_root),
                    "auto_update": ext.auto_update,
                    "load_status": ext.load_status.value,
                }
                for ext in rows
            ],
            "errors": [err.to_dict() for err in all_errors],
        }
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        if all_errors:
            raise typer.Exit(code=1)
        return

    if not rows and not all_errors:
        typer.echo("No installed or seed-directory Extensions discovered.")
        return

    if rows:
        # Compute column widths from the data; cap each so a malicious manifest
        # cannot blow up the terminal.  Widths are clamped well above the
        # documented identifier limits (64 chars) so normal entries align.
        def _w(values: list[str], header: str, *, cap: int = 48) -> int:
            return min(cap, max(len(header), *(len(v) for v in values)))

        ids = [r.extension_id for r in rows]
        versions = [r.version for r in rows]
        bundles = [r.bundle_name for r in rows]
        slots = [r.namespaced_slot for r in rows]
        sources = [r.source_kind for r in rows]
        statuses = [r.load_status.value for r in rows]

        cols = (
            ("ID", _w(ids, "ID")),
            ("VERSION", _w(versions, "VERSION", cap=24)),
            ("BUNDLE", _w(bundles, "BUNDLE")),
            ("SLOT", _w(slots, "SLOT", cap=16)),
            ("SOURCE", _w(sources, "SOURCE", cap=12)),
            ("STATUS", _w(statuses, "STATUS", cap=12)),
        )
        header = "  ".join(name.ljust(width) for name, width in cols)
        typer.echo(header)
        for row in rows:
            cells = (
                row.extension_id,
                row.version,
                row.bundle_name,
                row.namespaced_slot,
                row.source_kind,
                row.load_status.value,
            )
            line = "  ".join(value.ljust(width) for value, (_, width) in zip(cells, cols, strict=False))
            typer.echo(line.rstrip())

    if all_errors:
        if rows:
            typer.echo("", err=True)
        for err in all_errors:
            typer.echo(format_extension_error(err), err=True)
            typer.echo("", err=True)
        raise typer.Exit(code=1)


@extension_app.command(
    name="reload",
    help="Trigger an atomic-swap reload for an installed Bundle (LE-1018).",
)
def reload_command(
    extension_id: str = typer.Argument(
        ...,
        help="ID of the extension whose Bundle should be reloaded (e.g. lfx-pilot).",
    ),
    bundle: str | None = typer.Option(
        None,
        "--bundle",
        "-b",
        help=(
            "Bundle name to reload. Defaults to the extension id when the "
            "extension ships a single Bundle (the v0 supported case)."
        ),
    ),
    target: str | None = typer.Option(
        None,
        "--target",
        help=("Langflow server URL (default: $LANGFLOW_HOST / $LANGFLOW_SERVER_URL / http://localhost:7860)."),
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="API key for the Langflow server (default: $LANGFLOW_API_KEY).",
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        "-f",
        help="Output format: text (default) or json.",
    ),
    *,
    reload_all: bool = typer.Option(
        False,  # noqa: FBT003 - typer Option requires positional default
        "--all",
        help=(
            "Reload every installed Bundle. Requires the LE-1019 list endpoint and is not yet wired in this milestone."
        ),
    ),
) -> None:
    """POST to the reload endpoint and surface the typed result.

    Exit codes:
        0 -- reload succeeded and the registry now reflects the new code.
        1 -- reload failed (broken bundle, source missing, name mismatch,
             or the dev server returned a typed error).
        2 -- argument error (e.g. ``--all`` requested before LE-1019 lands).
    """
    from lfx.cli._extension_reload_client import reload_via_http
    from lfx.extension.errors import ExtensionError, format_extension_error

    if reload_all:
        typer.echo(
            "extension reload --all requires the LE-1019 list endpoint and is not yet implemented in this milestone.",
            err=True,
        )
        raise typer.Exit(code=2)

    if output_format not in {"text", "json"}:
        typer.echo("Invalid --format. Expected one of: text, json.", err=True)
        raise typer.Exit(code=2)

    bundle_name = bundle or extension_id
    response = reload_via_http(
        target=target,
        api_key=api_key,
        extension_id=extension_id,
        bundle_name=bundle_name,
    )

    if output_format == "json":
        typer.echo(json.dumps(response.payload, indent=2, sort_keys=True))
        raise typer.Exit(code=response.exit_code())

    if response.ok:
        added = response.payload.get("components_added") or []
        removed = response.payload.get("components_removed") or []
        typer.echo(f"reload: ok bundle={bundle_name}")
        if added:
            typer.echo(f"  added:   {', '.join(added)}")
        if removed:
            typer.echo(f"  removed: {', '.join(removed)}")
        raise typer.Exit(code=0)

    # Failure path: render typed errors when present, fall back to status text.
    raw_errors = response.payload.get("errors") or []
    if not raw_errors and "detail" in response.payload:
        # FastAPI wraps HTTPException bodies in {"detail": {...}}.
        detail = response.payload["detail"]
        if isinstance(detail, dict):
            raw_errors = [detail]
    rendered_any = False
    for raw in raw_errors:
        if not isinstance(raw, dict):
            continue
        code = raw.get("code")
        if not code:
            continue
        try:
            err = ExtensionError(
                code=code,
                message=str(raw.get("message", "")),
                hint=str(raw.get("hint") or "Run `lfx extension validate` for details."),
                location=raw.get("location"),
                content=raw.get("content"),
            )
        except ValueError:
            typer.echo(f"error[{code}]: {raw.get('message', '<no message>')}", err=True)
            rendered_any = True
            continue
        typer.echo(format_extension_error(err), err=True)
        typer.echo("", err=True)
        rendered_any = True
    if not rendered_any:
        typer.echo(
            f"reload: failed (HTTP {response.status} bundle={bundle_name})",
            err=True,
        )
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
