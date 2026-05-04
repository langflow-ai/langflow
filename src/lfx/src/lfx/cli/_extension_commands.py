"""Extension authoring commands.

Sub-app rather than a flat command so that future tickets (LE-1018: ``reload``;
LE-1022: ``list`` / installed-pkg discovery; etc.) can attach without a
top-level naming collision with the existing ``lfx validate`` (which validates
flow JSON, not extensions).

Commands shipped here:

    - ``validate``  -- LE-1014; static manifest + AST checker.
    - ``schema``    -- LE-1014; emit the manifest JSON Schema.
    - ``init``      -- LE-1016; scaffold a basic single-Bundle extension.
    - ``dev``       -- LE-1016; register a local extension and launch
                       Langflow with it loaded.

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
    help="Author and inspect Langflow Extensions (LE-1014/1015/1016).",
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

    env = os.environ.copy()
    # Force eager loading so dev-extension components show up in the
    # palette within AC #4's 5s budget.  Use unconditional assignment
    # (not setdefault) so a developer who has lazy loading exported in
    # their shell does not silently lose dev components from the palette
    # -- the dev workflow needs eager loading regardless of the global
    # default.
    env["LANGFLOW_LAZY_LOAD_COMPONENTS"] = "false"

    # Replace the current process so Ctrl-C in the launched langflow
    # propagates without an extra pty/job-control hop.  When ``langflow``
    # isn't on PATH we fall back to python -m via subprocess so the
    # author still gets a meaningful exit code.
    if cmd[0] == sys.executable:
        rc = subprocess.run(cmd, env=env, check=False).returncode  # noqa: S603
        raise typer.Exit(code=rc)
    os.execvpe(cmd[0], cmd, env)  # noqa: S606


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
