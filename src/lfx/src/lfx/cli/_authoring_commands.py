"""Authoring commands: create, requirements, validate."""

import typer


def register(app: typer.Typer) -> None:
    """Register authoring-stage commands on *app*."""

    @app.command(name="create", help="Create a new flow JSON from a built-in template", rich_help_panel="Authoring")
    def create_command_wrapper(
        name: str = typer.Argument(help="Display name for the new flow (also used as the filename)."),
        template: str = typer.Option(
            "hello-world",
            "--template",
            "-t",
            help="Template to use. Run with --list to see all available templates.",
        ),
        output_dir: str = typer.Option(
            "flows",
            "--output-dir",
            "-o",
            help="Directory to write the new flow JSON into (created if absent; default: flows/).",
        ),
        *,
        list_templates: bool = typer.Option(
            False,
            "--list",
            "-l",
            help="Print available templates and exit.",
            is_eager=True,
        ),
        overwrite: bool = typer.Option(
            False,
            "--overwrite",
            help="Overwrite the destination file if it already exists.",
        ),
    ) -> None:
        """Scaffold a new Langflow flow JSON from a built-in template (lazy-loaded)."""
        from pathlib import Path

        from lfx.cli.create import create_command, print_templates

        if list_templates:
            print_templates()
            raise typer.Exit(0)

        create_command(
            name=name,
            template=template,
            output_dir=Path(output_dir),
            overwrite=overwrite,
        )

    @app.command(
        name="requirements",
        help="Generate requirements.txt for a flow",
        no_args_is_help=True,
        rich_help_panel="Authoring",
    )
    def requirements_command_wrapper(
        flow_path: str = typer.Argument(help="Path to the Langflow flow JSON file"),
        output: str | None = typer.Option(
            None,
            "--output",
            "-o",
            help="Output file path (default: stdout)",
        ),
        lfx_package: str = typer.Option(
            "lfx",
            "--lfx-package",
            help="Name of the LFX package (default: lfx)",
        ),
        *,
        no_lfx: bool = typer.Option(
            False,
            "--no-lfx",
            help="Exclude the LFX package from output",
        ),
        no_pin: bool = typer.Option(
            False,
            "--no-pin",
            help="Do not pin package versions (default: pin to currently installed versions)",
        ),
    ) -> None:
        """Generate requirements.txt from a Langflow flow JSON (lazy-loaded)."""
        import json
        from pathlib import Path

        from lfx.utils.flow_requirements import generate_requirements_txt

        path = Path(flow_path)
        if not path.is_file():
            typer.echo(f"Error: File not found: {path}", err=True)
            raise typer.Exit(1)

        try:
            flow = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            typer.echo(f"Error: Could not read flow JSON: {e}", err=True)
            raise typer.Exit(1) from e

        content = generate_requirements_txt(
            flow,
            lfx_package=lfx_package,
            include_lfx=not no_lfx,
            pin_versions=not no_pin,
        )

        if output:
            try:
                Path(output).write_text(content, encoding="utf-8")
            except OSError as e:
                typer.echo(f"Error: Could not write to {output}: {e}", err=True)
                raise typer.Exit(1) from e
            typer.echo(f"Requirements written to {output}")
        else:
            typer.echo(content, nl=False)

    @app.command(name="validate", help="Validate one or more flow JSON files", rich_help_panel="Authoring")
    def validate_command_wrapper(
        flow_paths: list[str] = typer.Argument(
            default=None,
            help="Path(s) to Langflow flow JSON file(s) or directories to validate. Defaults to flows/.",
        ),
        dir_path: str | None = typer.Option(
            None,
            "--dir",
            "-d",
            help="Directory of flow JSON files to validate (validates all *.json files). Defaults to flows/.",
        ),
        level: int = typer.Option(
            4,
            "--level",
            "-l",
            min=1,
            max=4,
            help=(
                "Validation depth: "
                "1=structural JSON, "
                "2=+component existence, "
                "3=+edge type compatibility, "
                "4=+required inputs connected"
            ),
        ),
        skip_components: bool = typer.Option(
            False,
            "--skip-components",
            help="Skip component existence checks (level 2)",
        ),
        skip_edge_types: bool = typer.Option(
            False,
            "--skip-edge-types",
            help="Skip edge type compatibility checks (level 3)",
        ),
        skip_required_inputs: bool = typer.Option(
            False,
            "--skip-required-inputs",
            help="Skip required-inputs checks (level 4)",
        ),
        skip_version_check: bool = typer.Option(
            False,
            "--skip-version-check",
            help="Skip version-mismatch / outdated-component warnings",
        ),
        skip_credentials: bool = typer.Option(
            False,
            "--skip-credentials",
            help="Skip missing-credentials warnings for password/secret fields",
        ),
        strict: bool = typer.Option(
            False,
            "--strict",
            help="Treat warnings as errors (exit 1 if any warnings are found)",
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            "-v",
            help="Print all issues including warnings for passing flows",
        ),
        output_format: str = typer.Option(
            "text",
            "--format",
            "-f",
            help="Output format: text (default) or json",
        ),
    ) -> None:
        """Validate Langflow flow JSON files without executing them (lazy-loaded)."""
        from lfx.cli.validate import validate_command

        # Merge --dir into positional paths for a consistent interface with push
        effective_paths = list(flow_paths or [])
        if dir_path is not None:
            effective_paths.append(dir_path)

        validate_command(
            flow_paths=effective_paths,
            level=level,
            skip_components=skip_components,
            skip_edge_types=skip_edge_types,
            skip_required_inputs=skip_required_inputs,
            skip_version_check=skip_version_check,
            skip_credentials=skip_credentials,
            strict=strict,
            verbose=verbose,
            output_format=output_format,
        )
