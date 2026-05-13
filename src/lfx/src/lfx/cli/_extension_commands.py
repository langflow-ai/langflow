"""Extension authoring commands.

Sub-app rather than a flat command so future authoring verbs (``init``,
``dev``, ``reload``, ...) can attach without a top-level naming collision with
the existing ``lfx validate`` (which validates flow JSON, not extensions).

Commands shipped here:

    - ``validate``  -- static manifest + AST checker.
    - ``schema``    -- emit the manifest JSON Schema.
    - ``init``      -- scaffold a basic single-Bundle extension.
    - ``dev``       -- register a local extension and launch Langflow with
                       it loaded.

Each command is implemented as a thin shell over the helpers in
``lfx.extension.*`` so the same code paths are reachable from tests
without going through Typer.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
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

    # Codes that signal "something is wrong but discovery itself succeeded".
    # ``lfx extension list`` should still exit 0 in those cases so CI scripts
    # like ``lfx extension list && ...`` keep flowing -- the warning stays on
    # stderr where humans see it.  Configuration errors that point at a
    # missing seed dir stay as hard failures: that's an operator misconfig,
    # not a runtime warning.
    warn_only_codes = frozenset({"seed-bundle-shadowed"})
    hard_errors = [err for err in all_errors if err.code not in warn_only_codes]

    if output_format == "json":
        payload = {
            "interpreter": {
                "executable": sys.executable,
                "prefix": sys.prefix,
                "version": sys.version.split()[0],
            },
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
        if hard_errors:
            raise typer.Exit(code=1)
        return

    # Print interpreter info up front so an operator who sees an empty
    # listing can immediately spot a wrong-venv mismatch between ``lfx``
    # and ``langflow run`` without a separate "did my bundle install?"
    # debug cycle.
    typer.echo(f"python:     {sys.executable}")
    typer.echo(f"sys.prefix: {sys.prefix}")
    typer.echo("")

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
        if hard_errors:
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
            "Bundle name to reload.  Required until the LE-1019 list endpoint "
            "ships -- the conventional shape is extension id 'lfx-<provider>' "
            "with bundle name '<provider>', so we cannot safely default."
        ),
    ),
    target: str | None = typer.Option(
        None,
        "--target",
        help=("Langflow server URL (default: $LANGFLOW_HOST / http://localhost:7860)."),
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

    if not bundle:
        typer.echo(
            "extension reload requires --bundle until the LE-1019 list endpoint "
            "ships.  Pass --bundle <name>; conventional shape is "
            "lfx-<provider> ext_id with <provider> as the bundle name.",
            err=True,
        )
        raise typer.Exit(code=2)

    bundle_name = bundle
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


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@extension_app.command(
    name="init",
    help="Scaffold a basic single-Bundle extension at the given path.",
)
def init_command(
    target: str = typer.Argument(
        ...,
        help=(
            "Directory to create.  Must NOT already exist as a non-empty "
            "directory; ``init`` refuses to overwrite hand-edited code."
        ),
    ),
    *,
    template: str = typer.Option(
        "basic",
        "--template",
        help=(
            "Template name.  Only 'basic' is accepted in this milestone; "
            "richer templates (full, service, route, multi-bundle, "
            "starter-projects) are deferred and refused with a typed error."
        ),
    ),
    extension_id: str | None = typer.Option(
        None,
        "--id",
        help=(
            "Manifest extension id (lowercase-hyphenated).  Defaults to the "
            "target directory name with non-id characters cleaned up."
        ),
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help=("Human-readable display name shown in Langflow.  Defaults to the title-cased extension id."),
    ),
) -> None:
    """Create a runnable extension skeleton you can iterate on with ``dev``.

    Acceptance criteria for this command (LE-1016):

      - ``init <target>`` followed immediately by ``validate <target>``
        passes with zero errors.
      - The generated test file is a valid pytest module.
      - ``--template <anything-other-than-basic>`` fails cleanly with
        ``template-deferred-in-this-milestone`` and a non-zero exit.
    """
    from lfx.extension import format_extension_error
    from lfx.extension.init_template import (
        BASIC_TEMPLATE,
        InitOptions,
        derive_bundle_name,
        derive_display_name,
        derive_extension_id,
        init_extension,
    )

    target_path = Path(target).expanduser().resolve()
    derived_id = extension_id or derive_extension_id(target_path.name)
    options = InitOptions(
        target=target_path,
        extension_id=derived_id,
        bundle_name=derive_bundle_name(derived_id),
        display_name=name or derive_display_name(derived_id),
        # Pass --template through verbatim; the helper rejects everything
        # but BASIC_TEMPLATE with a typed error so the CLI doesn't have
        # to know the deferred-template list.
        template=template or BASIC_TEMPLATE,
    )

    result = init_extension(options)
    if not result.ok:
        for error in result.errors:
            typer.echo(format_extension_error(error), err=True)
            typer.echo("", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Created extension at {target_path}")
    typer.echo("Next steps:")
    typer.echo(f"  lfx extension validate {target_path}")
    typer.echo(f"  lfx extension dev {target_path}")


# ---------------------------------------------------------------------------
# dev
# ---------------------------------------------------------------------------


def _resolve_langflow_executable() -> str | None:
    """Find the ``langflow`` binary on PATH, if any.

    Returns ``None`` when langflow isn't installed; the dev command then
    falls back to ``python -m langflow.__main__`` so an author with the
    ``lfx`` package alone still gets a usable error message.
    """
    return shutil.which("langflow")


@extension_app.command(
    name="dev",
    help="Register a local extension and launch Langflow with it loaded.",
)
def dev_command(
    target: str = typer.Argument(
        ".",
        help=(
            "Path to the extension root (defaults to the current "
            "directory).  Must contain extension.json or "
            "[tool.langflow.extension] in pyproject.toml."
        ),
    ),
    *,
    skip_validate: bool = typer.Option(
        False,  # noqa: FBT003
        "--skip-validate",
        help=(
            "Skip the pre-launch validate pass.  Useful when you're "
            "iterating on a known-broken manifest and want to see the "
            "loader's runtime error rather than the static one."
        ),
    ),
    skip_launch: bool = typer.Option(
        False,  # noqa: FBT003
        "--skip-launch",
        help=(
            "Register the extension in the dev registry but don't exec "
            "``langflow run``.  Useful for tests and for embedding in "
            "external dev-server scripts."
        ),
    ),
    extra_args: list[str] | None = typer.Argument(  # noqa: B008 - Typer requires call-site default
        None,
        help="Extra arguments forwarded to ``langflow run`` (after a ``--`` separator).",
    ),
) -> None:
    """Register the extension and launch a Langflow dev server.

    Flow:
        1. Resolve the absolute path of the target extension.
        2. (Default) Run ``validate`` and abort on errors.
        3. Register the absolute path in the dev registry state file.
        4. Print reload instructions.
        5. ``exec``-style hand-off to ``langflow run`` (or
           ``python -m langflow``) with the env var
           ``LANGFLOW_LAZY_LOAD_COMPONENTS=false`` so dev-extensions are
           visible in the palette immediately.

    AC #4 ("boots Langflow with the new Extension visible in the palette
    within 5s") is delivered jointly by this command and the startup
    hook in ``langflow.main`` that consults the dev registry.
    """
    from lfx.extension import format_extension_error, register_dev_extension, validate_extension

    target_path = Path(target).expanduser().resolve()
    if not target_path.is_dir():
        typer.echo(f"error: {target_path} is not a directory", err=True)
        raise typer.Exit(code=1)

    if not skip_validate:
        report = validate_extension(target_path)
        if not report.ok:
            for error in report.errors.errors:
                typer.echo(format_extension_error(error), err=True)
                typer.echo("", err=True)
            typer.echo(
                "Refusing to register an extension that fails validate; re-run with --skip-validate to override.",
                err=True,
            )
            raise typer.Exit(code=1)

    entry = register_dev_extension(target_path)
    typer.echo(f"Registered dev extension: {entry.path}")
    typer.echo("Reload instructions:")
    typer.echo("  - Edit any file under components/ in the registered directory.")
    typer.echo("  - Click 'Reload' on the bundle header in the Langflow palette (LE-1019).")

    if skip_launch:
        return

    extras = list(extra_args or [])
    cmd = _build_langflow_run_argv(extras)
    typer.echo("")
    typer.echo("Launching: " + " ".join(shlex.quote(part) for part in cmd))

    env = _build_dev_launch_env(os.environ)

    # Replace the current process so Ctrl-C in the launched langflow
    # propagates without an extra pty/job-control hop.  When ``langflow``
    # isn't on PATH we fall back to python -m via subprocess so the
    # author still gets a meaningful exit code.
    if cmd[0] == sys.executable:
        rc = subprocess.run(cmd, env=env, check=False).returncode  # noqa: S603
        raise typer.Exit(code=rc)
    os.execvpe(cmd[0], cmd, env)  # noqa: S606


def _build_dev_launch_env(base_env: os._Environ[str] | dict[str, str]) -> dict[str, str]:
    """Build the env dict handed to the launched ``langflow run`` process.

    Centralizes the per-flag rationale so the contract is testable in one
    place and a missing flag is caught by a focused unit test rather than
    only manifesting as a runtime UX gap.

    Flags set:
        - ``LANGFLOW_LAZY_LOAD_COMPONENTS=false`` (always, overriding the
          author's shell): dev components must appear in the palette
          eagerly so the AC's 5-second budget holds.
        - ``LANGFLOW_ENABLE_EXTENSION_RELOAD=true`` (setdefault): turns on
          the in-process Bundle reload route AND the ``/config`` flag the
          packaged frontend reads at runtime to surface the palette
          Reload button.  ``setdefault`` so an author intentionally
          testing the off path can pre-export ``=false``.
    """
    env = dict(base_env)
    env["LANGFLOW_LAZY_LOAD_COMPONENTS"] = "false"
    env.setdefault("LANGFLOW_ENABLE_EXTENSION_RELOAD", "true")
    return env


def _build_langflow_run_argv(extra_args: list[str]) -> list[str]:
    """Build the argv list that exec's ``langflow run``.

    Falls back to ``python -m langflow`` when the ``langflow`` binary is
    not on PATH so the dev loop still works inside an ``lfx``-only
    install (author hits a clear failure mode rather than a confusing
    one).
    """
    binary = _resolve_langflow_executable()
    if binary is not None:
        return [binary, "run", *extra_args]
    return [sys.executable, "-m", "langflow", "run", *extra_args]
