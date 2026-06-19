"""Pre-warm command: prewarm."""

import typer


def register(app: typer.Typer) -> None:
    """Register the pre-warm command on *app*."""

    @app.command(
        name="prewarm",
        help="Warm core component imports + execution paths (for snapshot capture)",
        rich_help_panel="Setup",
    )
    def prewarm_command_wrapper(
        flow: list[str] | None = typer.Option(
            None,
            "--flow",
            help="Flow JSON path to warm by building it (repeatable). Warms exactly that flow's components.",
        ),
        unsafe_run: bool = typer.Option(
            False,
            "--unsafe-run-may-leak-connections",
            help=(
                "DANGER — only if you know what you're doing. Fully EXECUTES each --flow, firing its REAL "
                "side effects (model calls, DB writes, etc.) and leaving live connections. NOT fork-safe: "
                "never use before a Gunicorn/preload fork — Firecracker snapshot/restore only. You must supply "
                "required credentials and the flow must be idempotent."
            ),
        ),
        freeze: bool = typer.Option(
            False,
            "--freeze",
            help="Run gc.collect()+gc.freeze() afterwards to preserve copy-on-write sharing.",
        ),
        skip_run: bool = typer.Option(
            False,
            "--skip-run",
            help="Import only; skip the model-free hermetic warm-up run.",
        ),
        verbose: bool = typer.Option(
            False,
            "-v",
            "--verbose",
            help="List each imported component and warmed flow.",
        ),
    ) -> None:
        """Warm core component imports, the execution machinery, and (optionally) specific flows.

        Run this in a long-lived process just before capturing a warm snapshot (or before a
        Gunicorn ``--preload`` fork), so the first flow build/run after restore skips the
        lazy-import cost. By default nothing is executed with real side effects — this path is
        fork-safe. The ``--unsafe-run-may-leak-connections`` flag fully executes each ``--flow``
        (Firecracker only — never before a fork); see the warning on that flag.
        """
        from lfx.preload import PrewarmError, freeze_heap, prewarm_core_imports, prewarm_flow, teardown_warm_services

        failed = False

        # Service teardown is centralized below (one pass after ALL warming) so the
        # per-flow layer doesn't re-instantiate services the base layer just disposed.
        # The --unsafe-run path intentionally leaves live connections (Firecracker), so
        # it skips teardown entirely.
        do_teardown = not unsafe_run

        # Base layer: common component imports + model-free execution machinery.
        try:
            core = prewarm_core_imports(warmup_run=not skip_run, freeze=False, teardown_services=False)
        except PrewarmError as exc:
            typer.echo(f"prewarm failed: {exc}", err=True)
            raise typer.Exit(1) from exc

        suffix = " (warm-up run)" if core.warmup_ran else ""
        typer.echo(f"Pre-warmed: {len(core.imported)} component(s) imported{suffix} in {core.elapsed_s:.3f}s")
        if verbose:
            for component in core.imported:
                typer.echo(f"  ok   {component}")
        for component, err in core.failed.items():
            typer.echo(f"  skip {component}: {err}")

        # Per-flow layer: warm exactly the supplied flows (optionally executing them).
        for flow_path in flow or []:
            fr = prewarm_flow(flow_path, run=unsafe_run, freeze=False, teardown_services=False)
            if fr.error:
                failed = True
                typer.echo(f"  FAIL flow {flow_path}: {fr.error}", err=True)
            else:
                state = "built+ran" if fr.ran else "built"
                typer.echo(f"  flow {flow_path}: {state} in {fr.elapsed_s:.3f}s")
                if fr.ghost_threads or fr.ghost_connections:
                    typer.echo(
                        f"    WARNING: run left fork-unsafe state "
                        f"(threads={fr.ghost_threads or '[]'}, connections={fr.ghost_connections or '[]'}). "
                        f"OK for Firecracker restore; do NOT capture this before a Gunicorn/preload fork.",
                        err=True,
                    )

        # Dispose any services warming instantiated so a Gunicorn/preload fork can't
        # inherit a real plugin's live pool/socket/thread. Fatal on failure — a
        # half-disposed process must never be captured into a fork.
        if do_teardown:
            try:
                teardown_warm_services()
            except PrewarmError as exc:
                typer.echo(f"prewarm failed: {exc}", err=True)
                raise typer.Exit(1) from exc
            typer.echo("Disposed warm services (fork-safe).")

        if freeze:
            freeze_heap()
            typer.echo("Heap frozen (gc.freeze).")

        if failed:
            raise typer.Exit(1)
