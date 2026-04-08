"""Setup commands: init, login."""

import typer


def register(app: typer.Typer) -> None:
    """Register setup-stage commands on *app*."""

    @app.command(name="init", help="Scaffold a new Flow DevOps project", rich_help_panel="Setup")
    def init_command_wrapper(
        project_dir: str = typer.Argument(
            ".",
            help="Directory to scaffold (created if it does not exist; default: current directory).",
        ),
        github_actions: bool = typer.Option(
            True,
            "--github-actions/--no-github-actions",
            help="Copy GitHub Actions workflow templates into .github/workflows/.",
        ),
        overwrite: bool = typer.Option(
            False,
            "--overwrite",
            help="Write files even if the target directory already contains files.",
        ),
        example: bool = typer.Option(
            True,
            "--example/--no-example",
            help="Seed flows/ with a hello-world.json starter flow (default: true).",
        ),
    ) -> None:
        """Scaffold a Flow DevOps project: flows/, tests/, environments config, and CI templates."""
        from pathlib import Path

        from lfx.cli.init import init_command

        init_command(
            project_dir=Path(project_dir),
            github_actions=github_actions,
            overwrite=overwrite,
            example=example,
        )

    @app.command(name="login", help="Validate credentials against a remote Langflow instance", rich_help_panel="Setup")
    def login_command_wrapper(
        env: str | None = typer.Option(
            None,
            "--env",
            "-e",
            help="Environment name from .lfx/environments.yaml. Uses [defaults] if omitted.",
        ),
        environments_file: str | None = typer.Option(
            None,
            "--environments-file",
            help="Path to environments config file (.yaml or .toml; overrides default lookup).",
        ),
        target: str | None = typer.Option(
            None,
            "--target",
            help="Langflow instance URL (inline override — skips config file lookup).",
        ),
        api_key: str | None = typer.Option(
            None,
            "--api-key",
            help="API key for the Langflow instance (used with --target or to override config).",
        ),
    ) -> None:
        """Test connectivity and authentication for a Langflow environment (lazy-loaded)."""
        from lfx.cli.login import login_command

        login_command(
            env=env,
            environments_file=environments_file,
            target=target,
            api_key=api_key,
        )
