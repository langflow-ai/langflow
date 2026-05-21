"""``langflow authz dry-run`` — simulate every flow guard against a stub policy.

The OSS ``LangflowAuthorizationService`` always allows, so a real install can't
demonstrate enforcement without the enterprise Casbin plugin. This subcommand
replaces the live authorization service with a small in-memory stub for one
invocation, walks every flow-CRUD guard site, and prints what *would* happen
under the chosen policy — including the Casbin tuple, the audit row that
would have been written, and the resulting HTTP outcome. Useful for:

* Validating that ``AUTHZ_ENABLED=true`` + a future Casbin policy will produce
  the expected behaviour before shipping it to production.
* Showing operators what the audit log will look like.
* Smoke-testing the guard wiring after a refactor.

The command never hits the network or writes to the real database; it patches
the helpers in :mod:`langflow.services.authorization.utils` for the duration
of the run and restores them on exit.
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path  # noqa: TC003 — typer resolves this annotation at runtime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import typer
from fastapi import HTTPException
from rich import box
from rich.console import Console
from rich.table import Table

authz_app = typer.Typer(
    name="authz",
    help="Authorization (RBAC) utilities.",
    no_args_is_help=True,
)

_console = Console()


# --------------------------------------------------------------------------- #
# Stub policies
# --------------------------------------------------------------------------- #


class StubPolicy(str, Enum):
    """Built-in stand-ins for an enterprise Casbin policy."""

    ALLOW_ALL = "allow-all"
    DENY_NON_OWNER = "deny-non-owner"
    DENY_WRITES = "deny-writes"
    OWNER_ONLY = "owner-only"


_POLICY_DESCRIPTIONS = {
    StubPolicy.ALLOW_ALL: "Pass-through (matches the OSS default).",
    StubPolicy.DENY_NON_OWNER: "Owners and superusers allowed; everyone else denied.",
    StubPolicy.DENY_WRITES: "Read/execute allowed; write/create/delete denied.",
    StubPolicy.OWNER_ONLY: "Only the flow owner allowed (no superuser bypass).",
}


class _StubAuthorizationService:
    """Configurable enforce stub used only during ``dry-run``."""

    def __init__(self, policy: StubPolicy) -> None:
        self.policy = policy

    async def enforce(
        self,
        *,
        user_id: UUID,
        domain: str,  # noqa: ARG002
        obj: str,  # noqa: ARG002
        act: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Decide allow/deny per the configured stub policy."""
        ctx = context or {}
        if self.policy is StubPolicy.ALLOW_ALL:
            return True
        if self.policy is StubPolicy.DENY_NON_OWNER:
            if ctx.get("is_superuser"):
                return True
            return ctx.get("flow_user_id") == user_id
        if self.policy is StubPolicy.DENY_WRITES:
            return act in {"read", "execute"}
        if self.policy is StubPolicy.OWNER_ONLY:
            return ctx.get("flow_user_id") == user_id
        return True

    async def batch_enforce(
        self,
        *,
        user_id: UUID,
        domain: str,
        requests: list[tuple[str, str]],
        context: dict[str, Any] | None = None,
    ) -> list[bool]:
        """Apply :meth:`enforce` to each request, returning a parallel list."""
        return [
            await self.enforce(user_id=user_id, domain=domain, obj=obj, act=act, context=context)
            for obj, act in requests
        ]


# --------------------------------------------------------------------------- #
# Scenario definitions
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _GuardSite:
    """Static description of one ``ensure_flow_permission`` call site in flows.py."""

    name: str
    route: str
    action: str  # FlowAction value
    has_flow_id: bool  # True ⇒ obj=flow:{id}, False ⇒ obj=flow:*
    has_owner: bool  # True ⇒ flow_user_id is provided


_FLOW_GUARDS: tuple[_GuardSite, ...] = (
    _GuardSite("create_flow", "POST /flows/", "create", has_flow_id=False, has_owner=False),
    _GuardSite("read_flow", "GET /flows/{id}", "read", has_flow_id=True, has_owner=True),
    _GuardSite("update_flow", "PATCH /flows/{id}", "write", has_flow_id=True, has_owner=True),
    _GuardSite("upsert_flow (existing)", "PUT /flows/{id}", "write", has_flow_id=True, has_owner=True),
    _GuardSite("upsert_flow (new)", "PUT /flows/{id}", "create", has_flow_id=False, has_owner=False),
    _GuardSite("delete_flow", "DELETE /flows/{id}", "delete", has_flow_id=True, has_owner=True),
    _GuardSite("create_flows (batch)", "POST /flows/batch/", "create", has_flow_id=False, has_owner=False),
    _GuardSite("upload_file", "POST /flows/upload/", "create", has_flow_id=False, has_owner=False),
    _GuardSite("delete_multiple_flows", "DELETE /flows/", "delete", has_flow_id=True, has_owner=True),
    _GuardSite("download_multiple_file", "POST /flows/download/", "read", has_flow_id=True, has_owner=True),
)


@dataclass(frozen=True)
class _Actor:
    """Simulated caller of a flow route."""

    name: str
    is_superuser: bool
    is_flow_owner: bool


@dataclass
class DryRunResult:
    """One row in the dry-run report."""

    scenario: str
    route: str
    actor: str
    action: str
    obj: str
    domain: str
    decision: str  # allow / deny / owner_override
    http_status: int
    audit_action: str


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #


@contextmanager
def _install_stubs(stub: _StubAuthorizationService, audit_sink: list[dict[str, Any]]):
    """Swap the live authz helpers for the dry-run stubs for the duration of the run."""
    from langflow.services.authorization import utils as authz_utils

    settings = SimpleNamespace(
        auth_settings=SimpleNamespace(
            AUTHZ_ENABLED=True,
            AUTHZ_AUDIT_ENABLED=True,
            AUTHZ_SUPERUSER_BYPASS=True,
        )
    )

    async def _record_audit(**kwargs: Any) -> None:
        audit_sink.append(kwargs)

    saved_settings = authz_utils.get_settings_service
    saved_authz = authz_utils.get_authorization_service
    saved_audit = authz_utils.audit_decision

    authz_utils.get_settings_service = lambda: settings  # type: ignore[assignment]
    authz_utils.get_authorization_service = lambda: stub  # type: ignore[assignment]
    authz_utils.audit_decision = _record_audit  # type: ignore[assignment]

    try:
        yield
    finally:
        authz_utils.get_settings_service = saved_settings  # type: ignore[assignment]
        authz_utils.get_authorization_service = saved_authz  # type: ignore[assignment]
        authz_utils.audit_decision = saved_audit  # type: ignore[assignment]


async def _run_one(
    guard: _GuardSite,
    actor: _Actor,
    *,
    owner_id: UUID,
    flow_id: UUID,
    workspace_id: UUID,
    folder_id: UUID,
    audit_sink: list[dict[str, Any]],
) -> DryRunResult:
    """Invoke ``ensure_flow_permission`` for one (guard, actor) pair and record the outcome."""
    from langflow.services.authorization import utils as authz_utils
    from langflow.services.authorization.actions import FlowAction

    actor_id = owner_id if actor.is_flow_owner else uuid4()
    user_proxy = SimpleNamespace(id=actor_id, is_superuser=actor.is_superuser)

    kwargs: dict[str, Any] = {
        "workspace_id": workspace_id,
        "folder_id": folder_id,
    }
    if guard.has_flow_id:
        kwargs["flow_id"] = flow_id
    if guard.has_owner:
        kwargs["flow_user_id"] = owner_id

    audit_before = len(audit_sink)
    http_status = 200

    try:
        await authz_utils.ensure_flow_permission(
            user_proxy,  # type: ignore[arg-type]
            FlowAction(guard.action),
            **kwargs,
        )
    except HTTPException as exc:
        http_status = exc.status_code

    rows_written = audit_sink[audit_before:]
    decision = rows_written[-1]["result"] if rows_written else "skipped"
    audit_action = rows_written[-1]["action"] if rows_written else ""
    obj = rows_written[-1]["obj"] if rows_written else (f"flow:{flow_id}" if guard.has_flow_id else "flow:*")
    # Reach for the audited domain first; only fall back when no audit row was written
    # (rare — AUTHZ_ENABLED is forced True in dry-run). The fallback mirrors what
    # `_resolve_flow_domain` would emit given both ids: project wins.
    domain = (
        rows_written[-1]["details"].get("domain", "")
        if rows_written and isinstance(rows_written[-1].get("details"), dict)
        else f"project:{folder_id}"
    )

    return DryRunResult(
        scenario=guard.name,
        route=guard.route,
        actor=actor.name,
        action=guard.action,
        obj=obj,
        domain=domain,
        decision=decision,
        http_status=http_status,
        audit_action=audit_action,
    )


async def _run_all(policy: StubPolicy) -> list[DryRunResult]:
    """Run every guard x actor combo under ``policy`` and return result rows."""
    owner_id = uuid4()
    flow_id = uuid4()
    workspace_id = uuid4()
    folder_id = uuid4()

    actors = (
        _Actor("alice (owner)", is_superuser=False, is_flow_owner=True),
        _Actor("bob (non-owner)", is_superuser=False, is_flow_owner=False),
        _Actor("carol (superuser)", is_superuser=True, is_flow_owner=False),
    )

    stub = _StubAuthorizationService(policy)
    audit_sink: list[dict[str, Any]] = []

    rows: list[DryRunResult] = []
    with _install_stubs(stub, audit_sink):
        for guard in _FLOW_GUARDS:
            for actor in actors:
                row = await _run_one(
                    guard,
                    actor,
                    owner_id=owner_id,
                    flow_id=flow_id,
                    workspace_id=workspace_id,
                    folder_id=folder_id,
                    audit_sink=audit_sink,
                )
                rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# Output formatters
# --------------------------------------------------------------------------- #


_DECISION_STYLE = {
    "allow": "green",
    "deny": "red",
    "owner_override": "cyan",
    "skipped": "dim",
}


_UUID_PREFIX_LEN = 8


def _short_uuid(value: str) -> str:
    """Trim a UUID-bearing string to its first 8 hex characters for table readability."""
    if ":" in value:
        prefix, _, suffix = value.partition(":")
        if len(suffix) >= _UUID_PREFIX_LEN and "-" in suffix:
            return f"{prefix}:{suffix[:_UUID_PREFIX_LEN]}…"
    return value


def _render_table(policy: StubPolicy, rows: list[DryRunResult]) -> Table:
    """Build a Rich table summarising every dry-run result."""
    table = Table(
        title=f"authz dry-run · policy={policy.value} · {_POLICY_DESCRIPTIONS[policy]}",
        box=box.SIMPLE_HEAVY,
        show_lines=False,
    )
    table.add_column("Scenario", style="bold")
    table.add_column("Route")
    table.add_column("Actor")
    table.add_column("Action")
    table.add_column("Domain")
    table.add_column("Obj")
    table.add_column("Decision")
    table.add_column("HTTP", justify="right")
    for row in rows:
        style = _DECISION_STYLE.get(row.decision, "white")
        table.add_row(
            row.scenario,
            row.route,
            row.actor,
            row.action,
            _short_uuid(row.domain),
            _short_uuid(row.obj),
            f"[{style}]{row.decision}[/{style}]",
            str(row.http_status),
        )
    return table


def _summary_counts(rows: list[DryRunResult]) -> dict[str, int]:
    """Aggregate decisions across all rows for the footer line."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.decision] = counts.get(row.decision, 0) + 1
    return counts


def _emit_json(policy: StubPolicy, rows: list[DryRunResult], output: Path | None) -> None:
    """Serialise the report as JSON to stdout (or a file)."""
    payload = {
        "policy": policy.value,
        "policy_description": _POLICY_DESCRIPTIONS[policy],
        "results": [asdict(r) for r in rows],
        "summary": _summary_counts(rows),
    }
    text = json.dumps(payload, indent=2, default=str)
    if output is not None:
        output.write_text(text)
        _console.print(f"[green]wrote[/green] {output} ({len(rows)} rows)")
    else:
        sys.stdout.write(text + "\n")


def _emit_table(policy: StubPolicy, rows: list[DryRunResult], output: Path | None) -> None:
    """Render the report as a Rich table to stdout (or a plain-text file)."""
    table = _render_table(policy, rows)
    summary = _summary_counts(rows)
    summary_line = "  ".join(
        f"[{_DECISION_STYLE.get(k, 'white')}]{v} {k}[/{_DECISION_STYLE.get(k, 'white')}]"
        for k, v in sorted(summary.items())
    )
    if output is not None:
        with output.open("w") as fh:
            file_console = Console(file=fh, force_terminal=False, width=200)
            file_console.print(table)
            file_console.print(f"summary: {summary_line}")
        _console.print(f"[green]wrote[/green] {output} ({len(rows)} rows)")
    else:
        _console.print(table)
        _console.print(f"summary: {summary_line}")


# --------------------------------------------------------------------------- #
# Typer command
# --------------------------------------------------------------------------- #


@authz_app.command(name="dry-run")
def dry_run(
    policy: StubPolicy = typer.Option(
        StubPolicy.DENY_NON_OWNER,
        "--policy",
        "-p",
        help="Which stub policy to simulate.",
        case_sensitive=False,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the report to this file instead of stdout.",
    ),
    *,
    as_json: bool = typer.Option(
        False,  # noqa: FBT003 — typer requires positional default value
        "--json",
        help="Emit structured JSON instead of the Rich table.",
    ),
) -> None:
    """Simulate every flow guard under a stub policy and print what *would* happen.

    The command runs entirely in-process. No HTTP request is made, no row is
    written to the real ``authz_audit_log`` table — the report describes the
    Casbin tuple and audit row that *would* be produced if an enterprise
    plugin enforcing ``--policy`` were registered.
    """
    rows = asyncio.run(_run_all(policy))
    if as_json:
        _emit_json(policy, rows, output)
    else:
        _emit_table(policy, rows, output)
