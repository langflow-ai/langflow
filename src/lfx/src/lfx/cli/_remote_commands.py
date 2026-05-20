"""Remote commands: status, push, pull, export."""

import typer


def register(app: typer.Typer) -> None:
    """Register remote-stage commands on *app*."""

    @app.command(
        name="status", help="Compare local flow files against a remote Langflow instance", rich_help_panel="Remote"
    )
    def status_command_wrapper(
        flow_paths: list[str] = typer.Argument(
            default=None,
            help="Specific flow JSON file(s) to check. Omit to scan --dir (default: flows/).",
        ),
        env: str | None = typer.Option(
            None,
            "--env",
            "-e",
            help="Environment name from .lfx/environments.yaml. Uses [defaults] if omitted.",
        ),
        dir_path: str | None = typer.Option(
            None,
            "--dir",
            "-d",
            help="Directory of flow JSON files to compare (default: flows/ in cwd).",
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
        show_remote_only: bool = typer.Option(
            False,
            "--remote-only",
            help="Also list flows that exist on the server but have no local file.",
        ),
    ) -> None:
        """Show whether local flow files are in sync, ahead, or missing vs the remote instance."""
        from lfx.cli.status import status_command

        status_command(
            dir_path=dir_path,
            flow_paths=flow_paths or [],
            env=env,
            environments_file=environments_file,
            target=target,
            api_key=api_key,
            show_remote_only=show_remote_only,
        )

    @app.command(
        name="push",
        help="Push flow JSON to a remote Langflow instance (upsert by stable ID)",
        rich_help_panel="Remote",
    )
    def push_command_wrapper(
        flow_paths: list[str] = typer.Argument(
            default=None,
            help="Path(s) to flow JSON file(s) to push. Use --dir for a whole directory.",
        ),
        env: str | None = typer.Option(
            None,
            "--env",
            "-e",
            help="Environment name from .lfx/environments.yaml. Use --target for inline configuration.",
        ),
        dir_path: str | None = typer.Option(
            None,
            "--dir",
            "-d",
            help="Directory of flow JSON files to push (pushes all *.json files). Defaults to flows/.",
        ),
        project: str | None = typer.Option(
            None,
            "--project",
            "-p",
            help="Target project name on the remote instance. Created if it does not exist.",
        ),
        project_id: str | None = typer.Option(
            None,
            "--project-id",
            help="Target project UUID (alternative to --project).",
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
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            help="Show what would be pushed without making any changes.",
        ),
        normalize: bool = typer.Option(
            True,
            "--normalize/--no-normalize",
            help="Normalize (strip volatile fields, sort keys) before pushing.",
        ),
        strip_secrets: bool = typer.Option(
            True,
            "--strip-secrets/--keep-secrets",
            help="Clear password/load_from_db field values before pushing.",
        ),
    ) -> None:
        """Push Langflow flows to a remote instance using stable IDs for upsert (lazy-loaded)."""
        from lfx.cli.push import push_command

        push_command(
            flow_paths=flow_paths or [],
            env=env,
            dir_path=dir_path,
            project=project,
            project_id=project_id,
            environments_file=environments_file,
            target=target,
            api_key=api_key,
            dry_run=dry_run,
            normalize=normalize,
            strip_secrets=strip_secrets,
        )

    @app.command(
        name="pull", help="Pull flows from a remote Langflow instance to local files", rich_help_panel="Remote"
    )
    def pull_command_wrapper(
        env: str | None = typer.Option(
            None,
            "--env",
            "-e",
            help="Environment name from .lfx/environments.yaml. Uses [defaults] if omitted.",
        ),
        output_dir: str | None = typer.Option(
            None,
            "--output-dir",
            "-d",
            help="Directory to write pulled flows into (default: flows/).",
        ),
        flow_id: str | None = typer.Option(
            None,
            "--flow-id",
            help="Pull a single flow by UUID.",
        ),
        project: str | None = typer.Option(
            None,
            "--project",
            "-p",
            help="Pull all flows in a named project.",
        ),
        project_id: str | None = typer.Option(
            None,
            "--project-id",
            help="Pull all flows in a project by UUID.",
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
        strip_secrets: bool = typer.Option(
            True,
            "--strip-secrets/--keep-secrets",
            help="Clear password/load_from_db field values (default: strip).",
        ),
        indent: int = typer.Option(
            2,
            "--indent",
            help="JSON indentation level.",
        ),
    ) -> None:
        """Pull and normalize flows from a remote Langflow instance (lazy-loaded)."""
        from lfx.cli.pull import pull_command

        pull_command(
            env=env,
            output_dir=output_dir,
            flow_id=flow_id,
            project=project,
            project_id=project_id,
            environments_file=environments_file,
            target=target,
            api_key=api_key,
            strip_secrets=strip_secrets,
            indent=indent,
        )

    @app.command(
        name="export",
        help="Normalize flow JSON for git (local) or pull from a remote instance",
        rich_help_panel="Remote",
    )
    def export_command_wrapper(
        flow_paths: list[str] = typer.Argument(
            default=None,
            help="Path(s) to local flow JSON file(s) to normalize. Omit when using --flow-id or --project-id.",
        ),
        output: str | None = typer.Option(
            None,
            "--output",
            "-o",
            help="Output file path (single-file local mode only).",
        ),
        output_dir: str | None = typer.Option(
            None,
            "--output-dir",
            "-d",
            help="Directory to write exported flows into (remote mode or multi-file).",
        ),
        env: str | None = typer.Option(
            None,
            "--env",
            "-e",
            help="Environment name from .lfx/environments.yaml (required for remote mode unless --target is used).",
        ),
        flow_id: str | None = typer.Option(
            None,
            "--flow-id",
            help="Pull and export a single flow by UUID from the remote instance.",
        ),
        project_id: str | None = typer.Option(
            None,
            "--project-id",
            help="Pull and export all flows in a project by UUID from the remote instance.",
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
        in_place: bool = typer.Option(
            False,
            "--in-place",
            "-i",
            help="Overwrite each input file with its normalized version.",
        ),
        strip_volatile: bool = typer.Option(
            True,
            "--strip-volatile/--keep-volatile",
            help="Strip instance-specific fields (updated_at, user_id, folder_id).",
        ),
        strip_secrets: bool = typer.Option(
            True,
            "--strip-secrets/--keep-secrets",
            help="Clear values of password/load_from_db template fields.",
        ),
        code_as_lines: bool = typer.Option(
            False,
            "--code-as-lines",
            help="Convert code-type template field values to a list of lines.",
        ),
        strip_node_volatile: bool = typer.Option(
            True,
            "--strip-node-volatile/--keep-node-volatile",
            help="Strip transient node keys (positionAbsolute, dragging, selected).",
        ),
        indent: int = typer.Option(
            2,
            "--indent",
            help="JSON indentation level.",
        ),
    ) -> None:
        """Export and normalize Langflow flow JSON for version control (lazy-loaded)."""
        from lfx.cli.export import export_command

        export_command(
            flow_paths=flow_paths or [],
            output=output,
            output_dir=output_dir,
            env=env,
            flow_id=flow_id,
            project_id=project_id,
            environments_file=environments_file,
            target=target,
            api_key=api_key,
            in_place=in_place,
            strip_volatile=strip_volatile,
            strip_secrets=strip_secrets,
            code_as_lines=code_as_lines,
            strip_node_volatile=strip_node_volatile,
            indent=indent,
        )
