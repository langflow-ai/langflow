"""lfx init -- scaffold a new Flow DevOps project.

Creates the standard directory layout, an environments config stub,
example tests, and (optionally) GitHub Actions CI workflows -- everything
a team needs to start treating flows as code.

Examples::

    lfx init my-rag-project
    lfx init .                   # scaffold into the current directory
    lfx init my-project --no-github-actions
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.tree import Tree

console = Console()

# ---------------------------------------------------------------------------
# Templates embedded as strings (environments config and test stubs)
# ---------------------------------------------------------------------------

_ENVIRONMENTS_YAML = """\
# .lfx/environments.yaml
#
# Configure your Langflow instances here.
# Safe to commit — API keys are NEVER stored in this file.
# The api_key_env value is the NAME of an environment variable that holds
# the actual API key; set that variable in your shell or CI secrets.
#
# Quick start:
#   1. Open Langflow → Settings → API Keys → Create a new key
#   2. export LANGFLOW_LOCAL_API_KEY=<your key>
#   3. lfx export --env local --flow-id <uuid> --output-dir flows/

environments:
  local:
    url: http://localhost:7860
    api_key_env: LANGFLOW_LOCAL_API_KEY

  staging:
    url: https://staging.langflow.example.com
    api_key_env: LANGFLOW_STAGING_API_KEY

  production:
    url: https://langflow.example.com
    api_key_env: LANGFLOW_PROD_API_KEY

defaults:
  environment: local
"""

_TEST_FLOWS_PY = '''\
"""Integration tests for Langflow flows.

Run against a local instance (started with ``lfx serve``):

    pytest tests/ --langflow-url http://localhost:8000

Run against a named environment (staging, production, etc.):

    pytest tests/ --langflow-env staging -m integration

The flow_runner fixture auto-skips when no connection is configured,
so these tests are safe to include in any CI pipeline.
"""

import pytest


@pytest.mark.integration
def test_flow_responds(flow_runner):
    """Smoke test: every flow should return a non-empty response."""
    # TODO: replace "my-flow-endpoint" with your flow\'s endpoint name or UUID
    result = flow_runner("my-flow-endpoint", "Hello!")
    assert result.first_text_output() is not None, "Flow returned no output"


@pytest.mark.integration
def test_flow_output_quality(flow_runner):
    """Example: assert on the content of the response."""
    result = flow_runner("my-flow-endpoint", "What is Langflow?")
    text = result.first_text_output()
    assert text is not None
    assert len(text) > 20, f"Response seems too short: {text!r}"
'''

_GITIGNORE = """\
# Langflow credentials -- never commit API keys
# (langflow-environments.toml may contain literal keys; .lfx/environments.yaml is safe to commit)
langflow-environments.toml
"""

# Templates bundled inside the Python package
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(
    path: Path,
    content: str,
    label: str,
    created: list[tuple[str, str]],
    *,
    target: Path,
    overwrite: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return
    path.write_text(content, encoding="utf-8")
    created.append((str(path.relative_to(target)), label))


def _copy_template(
    src: Path, dest: Path, label: str, created: list[tuple[str, str]], *, target: Path, overwrite: bool
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        return
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    created.append((str(dest.relative_to(target)), label))


def _render_tree(target: Path, created: list[tuple[str, str]]) -> None:
    label = f"[bold]{target.name}/[/bold]" if target != Path.cwd() else "[bold].[/bold] (current directory)"
    tree = Tree(label)
    branch_nodes: dict[str, Any] = {}

    for rel_path, annotation in sorted(created, key=lambda x: x[0]):
        parts = Path(rel_path).parts
        node = tree
        for i, part in enumerate(parts[:-1]):
            key = "/".join(parts[: i + 1])
            if key not in branch_nodes:
                branch_nodes[key] = node.add(f"[bold blue]{part}/[/bold blue]")
            node = branch_nodes[key]
        suffix = f"  [dim]{annotation}[/dim]" if annotation else ""
        node.add(f"[green]{parts[-1]}[/green]{suffix}")

    console.print()
    console.print(tree)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


def init_command(
    project_dir: Path,
    *,
    github_actions: bool,
    overwrite: bool,
    example: bool = True,
) -> None:
    """Scaffold a Flow DevOps project at *project_dir*."""
    target = project_dir.resolve()

    if target.exists() and not overwrite:
        existing = [p for p in target.iterdir() if p.name != ".git"]
        if existing:
            msg = f"{target} already exists and is not empty. Use [bold]--overwrite[/bold] to scaffold into it anyway."
            console.print(f"[red]Error:[/red] {msg}")
            raise typer.Exit(1)

    target.mkdir(parents=True, exist_ok=True)
    created: list[tuple[str, str]] = []

    kw: dict[str, Any] = {"target": target, "overwrite": overwrite, "created": created}

    # flows/
    (target / "flows").mkdir(exist_ok=True)
    if example:
        from lfx.cli.create import create_command as _create

        try:
            _create(
                "hello-world",
                template="hello-world",
                output_dir=target / "flows",
                overwrite=overwrite,
            )
            created.append(("flows/hello-world.json", "starter flow — edit or replace"))
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            # Don't let a template failure block the rest of init
            console.print(f"[yellow]Warning:[/yellow] Could not seed starter flow: {exc}")
    else:
        _write(target / "flows" / ".gitkeep", "", "versioned empty directory", **kw)

    # tests/
    _write(target / "tests" / "__init__.py", "", "", **kw)
    _write(target / "tests" / "test_flows.py", _TEST_FLOWS_PY, "flow_runner example tests", **kw)

    # .lfx/environments.yaml
    _write(
        target / ".lfx" / "environments.yaml",
        _ENVIRONMENTS_YAML,
        "edit with your instance URLs + API key env var names (safe to commit)",
        **kw,
    )

    # .gitignore — keep langflow-environments.toml ignored for backward compat
    gitignore = target / ".gitignore"
    if gitignore.exists():
        existing_content = gitignore.read_text(encoding="utf-8")
        if "langflow-environments.toml" not in existing_content:
            gitignore.write_text(existing_content.rstrip() + "\n\n" + _GITIGNORE, encoding="utf-8")
            created.append((".gitignore", "appended credentials ignore rule"))
    else:
        _write(gitignore, _GITIGNORE, "ignores legacy credentials file", **kw)

    # GitHub Actions CI workflows
    if github_actions:
        gha_src = _TEMPLATES_DIR / "github-actions"
        if gha_src.exists():
            for tmpl in sorted(gha_src.glob("*.yml")):
                dest = target / ".github" / "workflows" / tmpl.name
                _copy_template(tmpl, dest, "CI workflow", created, target=target, overwrite=overwrite)
        else:
            console.print("[yellow]Warning:[/yellow] GitHub Actions templates not found; skipping.")

    # Generic shell CI scripts (always scaffolded — work with any CI system)
    shell_src = _TEMPLATES_DIR / "shell"
    if shell_src.exists():
        for tmpl in sorted(shell_src.glob("*.sh")):
            dest = target / "ci" / tmpl.name
            _copy_template(tmpl, dest, "generic CI script", created, target=target, overwrite=overwrite)
            dest.chmod(dest.stat().st_mode | 0o111)  # ensure executable bit

    # Print the created-files tree
    _render_tree(target, created)

    # Next-steps guide
    console.print()
    console.print("[bold green]✓ Project scaffolded.[/bold green]  Next steps:\n")
    console.print("  1. Edit [bold].lfx/environments.yaml[/bold] with your instance URL")
    console.print("  2. [bold]export LANGFLOW_LOCAL_API_KEY=<key>[/bold]   (Settings → API Keys)")
    if example:
        console.print("  3. [bold]lfx validate flows/hello-world.json[/bold]  (check the starter flow)")
        console.print("  4. [bold]lfx serve flows/hello-world.json[/bold]     (run it locally)")
        console.print("  5. [bold]lfx push --dir flows/ --env local[/bold]    (deploy to Langflow)")
    else:
        console.print("  3. [bold]lfx create my-flow --template hello-world[/bold]")
        console.print("  4. [bold]lfx push --dir flows/ --env local[/bold]")
    console.print(f"  {'6' if example else '5'}. [bold]pytest tests/ --langflow-env local[/bold]")
    console.print()
