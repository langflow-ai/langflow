"""Typer commands for programmatic team and user administration."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

import httpx
import typer
from pydantic import ValidationError
from rich import box
from rich.console import Console
from rich.table import Table

from langflow.cli.admin.client import AdminAPIError, AdminClient
from langflow.cli.admin.config import (
    DEFAULT_PROFILE_FILE,
    ConnectionConfigurationError,
    resolve_connection,
)
from langflow.cli.admin.manifest import dump_admin_state, load_admin_state
from langflow.cli.admin.reconcile import AdminReconciler, ManifestResolutionError

OutputFormat = Literal["table", "json"]

admin_app = typer.Typer(no_args_is_help=True, help="Administer Langflow users, teams, roles, and assignments.")
users_app = typer.Typer(no_args_is_help=True, help="Manage users.")
teams_app = typer.Typer(no_args_is_help=True, help="Manage teams.")
members_app = typer.Typer(no_args_is_help=True, help="Manage team membership.")
roles_app = typer.Typer(no_args_is_help=True, help="Manage roles.")
assignments_app = typer.Typer(no_args_is_help=True, help="Manage user and team role assignments.")


@dataclass
class AdminInvocation:
    url: str | None
    api_key: str | None
    profile: str | None
    profile_file: Path
    output: OutputFormat
    operation_id: str


@admin_app.callback()
def administration_options(
    ctx: typer.Context,
    url: Annotated[str | None, typer.Option("--url", help="Langflow base URL.")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="Langflow API key.")] = None,
    profile: Annotated[str | None, typer.Option("--profile", help="Named non-secret target profile.")] = None,
    profile_file: Annotated[
        Path,
        typer.Option("--profile-file", help="JSON profile file; profiles store only credential environment names."),
    ] = DEFAULT_PROFILE_FILE,
    output: Annotated[OutputFormat, typer.Option("--output", "-o", help="Output as a table or stable JSON.")] = "table",
) -> None:
    """Configure one administration invocation without resolving secrets during help."""
    ctx.obj = AdminInvocation(
        url=url,
        api_key=api_key,
        profile=profile,
        profile_file=profile_file,
        output=output,
        operation_id=f"cli-{uuid4()}",
    )


def _client_from_context(ctx: typer.Context) -> AdminClient:
    invocation: AdminInvocation = ctx.ensure_object(AdminInvocation)
    connection = resolve_connection(
        url=invocation.url,
        api_key=invocation.api_key,
        profile=invocation.profile,
        profile_file=invocation.profile_file,
    )
    return AdminClient(
        url=connection.url,
        api_key=connection.api_key,
        operation_id=invocation.operation_id,
    )


def _reconciler_from_context(ctx: typer.Context) -> AdminReconciler:
    return AdminReconciler(_client_from_context(ctx))


def _emit(ctx: typer.Context, value: Any, *, stderr: bool = False) -> None:
    invocation: AdminInvocation = ctx.ensure_object(AdminInvocation)
    if invocation.output == "json":
        stream = sys.stderr if stderr else sys.stdout
        stream.write(f"{json.dumps(value, default=str, sort_keys=True)}\n")
        return
    console = Console(stderr=stderr)
    records = value if isinstance(value, list) else [value]
    if not records:
        console.print("No results")
        return
    if not all(isinstance(record, dict) for record in records):
        console.print(str(value))
        return
    columns = _table_columns(records)
    table = Table(box=box.SIMPLE_HEAD)
    for column in columns:
        table.add_column(column)
    for record in records:
        table.add_row(*[_display_value(record.get(column)) for column in columns])
    console.print(table)


def _table_columns(records: list[dict[str, Any]]) -> list[str]:
    preferred = ["action", "resource", "key", "id", "username", "adom_name", "team_name", "name", "is_active"]
    available = {key for record in records for key in record}
    ordered = [key for key in preferred if key in available]
    return ordered + sorted(available - set(ordered))


def _display_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str, sort_keys=True)
    return str(value)


def _fail(exc: Exception, *, usage: bool = False) -> None:
    if isinstance(exc, AdminAPIError):
        code = f" [{exc.error_code}]" if exc.error_code else ""
        typer.echo(f"Error{code}: {exc.detail}", err=True)
    else:
        typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(code=2 if usage else 1) from exc


def _api_call(callable_: Any) -> Any:
    try:
        return callable_()
    except ConnectionConfigurationError as exc:
        _fail(exc, usage=True)
    except (AdminAPIError, httpx.HTTPError) as exc:
        _fail(exc)


def _read_password_from_stdin(password_stdin: bool) -> str:
    if not password_stdin:
        msg = "Passwords must be supplied with --password-stdin"
        raise typer.BadParameter(msg)
    password = sys.stdin.readline().rstrip("\r\n")
    if not password:
        msg = "No password was received on standard input"
        raise typer.BadParameter(msg)
    return password


@users_app.command("list")
def users_list(
    ctx: typer.Context,
    search: Annotated[str | None, typer.Option("--search")] = None,
    username: Annotated[str | None, typer.Option("--username", help="Exact username.")] = None,
    role: Annotated[str | None, typer.Option("--role", help="Exact assigned role name.")] = None,
) -> None:
    result = _api_call(lambda: _client_from_context(ctx).list_users(search=search, username=username, role_name=role))
    _emit(ctx, result)


@users_app.command("get")
def users_get(ctx: typer.Context, user: Annotated[str, typer.Argument(help="User UUID or username.")]) -> None:
    _emit(ctx, _api_call(lambda: _client_from_context(ctx).get_user(user)))


@users_app.command("create")
def users_create(
    ctx: typer.Context,
    username: Annotated[str, typer.Argument()],
    password_stdin: Annotated[
        bool, typer.Option("--password-stdin", help="Read the password from standard input.")
    ] = False,
) -> None:
    password = _read_password_from_stdin(password_stdin)
    _emit(ctx, _api_call(lambda: _client_from_context(ctx).create_user(username=username, password=password)))


@users_app.command("update")
def users_update(
    ctx: typer.Context,
    user: Annotated[str, typer.Argument(help="User UUID or current username.")],
    username: Annotated[str | None, typer.Option("--username", help="New username.")] = None,
    active: Annotated[bool | None, typer.Option("--active/--disabled")] = None,
) -> None:
    if username is None and active is None:
        msg = "At least one update option is required"
        raise typer.BadParameter(msg)
    _emit(
        ctx,
        _api_call(lambda: _client_from_context(ctx).update_user(user, username=username, is_active=active)),
    )


@users_app.command("disable")
def users_disable(ctx: typer.Context, user: Annotated[str, typer.Argument(help="User UUID or username.")]) -> None:
    _emit(ctx, _api_call(lambda: _client_from_context(ctx).update_user(user, is_active=False)))


@users_app.command("set-password")
def users_set_password(
    ctx: typer.Context,
    user: Annotated[str, typer.Argument(help="User UUID or username.")],
    password_stdin: Annotated[
        bool, typer.Option("--password-stdin", help="Read the password from standard input.")
    ] = False,
) -> None:
    password = _read_password_from_stdin(password_stdin)
    _emit(ctx, _api_call(lambda: _client_from_context(ctx).update_user(user, password=password)))


@users_app.command("delete")
def users_delete(
    ctx: typer.Context,
    user: Annotated[str, typer.Argument(help="User UUID or username.")],
    hard: Annotated[bool, typer.Option("--hard", help="Perform irreversible deletion.")] = False,
    confirm: Annotated[str | None, typer.Option("--confirm", help="Repeat the exact username.")] = None,
) -> None:
    client = _api_call(lambda: _client_from_context(ctx))
    resolved = _api_call(lambda: client.get_user(user))
    if not hard or confirm != resolved["username"]:
        msg = "Hard deletion requires --hard and --confirm <exact username>"
        raise typer.BadParameter(msg)
    result = _api_call(lambda: client.delete_user(str(resolved["id"])))
    _emit(ctx, result or {"deleted": resolved["username"]})


@teams_app.command("list")
def teams_list(
    ctx: typer.Context,
    search: Annotated[str | None, typer.Option("--search")] = None,
    adom_name: Annotated[str | None, typer.Option("--adom-name", help="Exact administrative-domain name.")] = None,
) -> None:
    _emit(ctx, _api_call(lambda: _client_from_context(ctx).list_teams(search=search, adom_name=adom_name)))


@teams_app.command("get")
def teams_get(ctx: typer.Context, team: Annotated[str, typer.Argument(help="Team UUID or adom_name.")]) -> None:
    _emit(ctx, _api_call(lambda: _client_from_context(ctx).get_team(team)))


@teams_app.command("create")
def teams_create(
    ctx: typer.Context,
    adom_name: Annotated[str, typer.Argument()],
    display_name: Annotated[str, typer.Option("--display-name")],
    description: Annotated[str | None, typer.Option("--description")] = None,
    active: Annotated[bool, typer.Option("--active/--disabled")] = True,
) -> None:
    _emit(
        ctx,
        _api_call(
            lambda: _client_from_context(ctx).create_team(
                adom_name=adom_name,
                display_name=display_name,
                description=description,
                active=active,
            )
        ),
    )


@teams_app.command("update")
def teams_update(
    ctx: typer.Context,
    team: Annotated[str, typer.Argument(help="Team UUID or current adom_name.")],
    adom_name: Annotated[str | None, typer.Option("--adom-name")] = None,
    display_name: Annotated[str | None, typer.Option("--display-name")] = None,
    description: Annotated[str | None, typer.Option("--description")] = None,
    clear_description: Annotated[bool, typer.Option("--clear-description")] = False,
    active: Annotated[bool | None, typer.Option("--active/--disabled")] = None,
) -> None:
    if description is not None and clear_description:
        msg = "--description and --clear-description cannot be used together"
        raise typer.BadParameter(msg)
    if all(value is None for value in (adom_name, display_name, description, active)) and not clear_description:
        msg = "At least one update option is required"
        raise typer.BadParameter(msg)
    changes = {
        key: value
        for key, value in {
            "adom_name": adom_name,
            "display_name": display_name,
            "description": description,
            "active": active,
        }.items()
        if value is not None
    }
    if clear_description:
        changes["description"] = None
    _emit(
        ctx,
        _api_call(lambda: _client_from_context(ctx).update_team(team, **changes)),
    )


@teams_app.command("disable")
def teams_disable(ctx: typer.Context, team: Annotated[str, typer.Argument(help="Team UUID or adom_name.")]) -> None:
    _emit(ctx, _api_call(lambda: _client_from_context(ctx).update_team(team, active=False)))


@teams_app.command("delete")
def teams_delete(ctx: typer.Context, team: Annotated[str, typer.Argument(help="Team UUID or adom_name.")]) -> None:
    _api_call(lambda: _client_from_context(ctx).delete_team(team))
    _emit(ctx, {"deleted": team})


@members_app.command("list")
def members_list(ctx: typer.Context, team: Annotated[str, typer.Argument(help="Team UUID or adom_name.")]) -> None:
    _emit(ctx, _api_call(lambda: _client_from_context(ctx).list_team_members(team)))


@members_app.command("add")
def members_add(
    ctx: typer.Context,
    team: Annotated[str, typer.Argument(help="Team UUID or adom_name.")],
    user: Annotated[str, typer.Argument(help="User UUID or username.")],
) -> None:
    _emit(ctx, _api_call(lambda: _client_from_context(ctx).add_team_member(team, user)))


@members_app.command("remove")
def members_remove(
    ctx: typer.Context,
    team: Annotated[str, typer.Argument(help="Team UUID or adom_name.")],
    user: Annotated[str, typer.Argument(help="User UUID or username.")],
) -> None:
    result = _api_call(lambda: _client_from_context(ctx).remove_team_member(team, user))
    _emit(ctx, result or {"removed": f"{team}/{user}"})


@roles_app.command("list")
def roles_list(
    ctx: typer.Context,
    search: Annotated[str | None, typer.Option("--search")] = None,
    name: Annotated[str | None, typer.Option("--name", help="Exact role name.")] = None,
) -> None:
    _emit(ctx, _api_call(lambda: _client_from_context(ctx).list_roles(search=search, name=name)))


@roles_app.command("get")
def roles_get(ctx: typer.Context, role: Annotated[str, typer.Argument(help="Role UUID or name.")]) -> None:
    _emit(ctx, _api_call(lambda: _client_from_context(ctx).get_role(role)))


@roles_app.command("create")
def roles_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument()],
    permission: Annotated[list[str] | None, typer.Option("--permission", "-p")] = None,
    description: Annotated[str | None, typer.Option("--description")] = None,
    parent: Annotated[str | None, typer.Option("--parent")] = None,
) -> None:
    _emit(
        ctx,
        _api_call(
            lambda: _client_from_context(ctx).create_role(
                name=name,
                permissions=permission or [],
                description=description,
                parent=parent,
            )
        ),
    )


@roles_app.command("update")
def roles_update(
    ctx: typer.Context,
    role: Annotated[str, typer.Argument(help="Role UUID or current name.")],
    name: Annotated[str | None, typer.Option("--name")] = None,
    permission: Annotated[list[str] | None, typer.Option("--permission", "-p")] = None,
    clear_permissions: Annotated[bool, typer.Option("--clear-permissions")] = False,
    description: Annotated[str | None, typer.Option("--description")] = None,
    clear_description: Annotated[bool, typer.Option("--clear-description")] = False,
    parent: Annotated[str | None, typer.Option("--parent")] = None,
    clear_parent: Annotated[bool, typer.Option("--clear-parent")] = False,
) -> None:
    if permission is not None and clear_permissions:
        msg = "--permission and --clear-permissions cannot be used together"
        raise typer.BadParameter(msg)
    if description is not None and clear_description:
        msg = "--description and --clear-description cannot be used together"
        raise typer.BadParameter(msg)
    if parent is not None and clear_parent:
        msg = "--parent and --clear-parent cannot be used together"
        raise typer.BadParameter(msg)
    clear_requested = clear_permissions or clear_description or clear_parent
    if all(value is None for value in (name, permission, description, parent)) and not clear_requested:
        msg = "At least one update option is required"
        raise typer.BadParameter(msg)
    changes = {
        key: value
        for key, value in {
            "name": name,
            "permissions": permission,
            "description": description,
            "parent": parent,
        }.items()
        if value is not None
    }
    if clear_permissions:
        changes["permissions"] = []
    if clear_description:
        changes["description"] = None
    if clear_parent:
        changes["parent"] = None
    _emit(
        ctx,
        _api_call(lambda: _client_from_context(ctx).update_role(role, **changes)),
    )


@roles_app.command("delete")
def roles_delete(ctx: typer.Context, role: Annotated[str, typer.Argument(help="Role UUID or name.")]) -> None:
    _api_call(lambda: _client_from_context(ctx).delete_role(role))
    _emit(ctx, {"deleted": role})


def _validate_subject(user: str | None, team: str | None) -> None:
    if (user is None) == (team is None):
        msg = "Exactly one of --user or --team is required"
        raise typer.BadParameter(msg)


@assignments_app.command("list")
def assignments_list(
    ctx: typer.Context,
    user: Annotated[str | None, typer.Option("--user")] = None,
    team: Annotated[str | None, typer.Option("--team")] = None,
    role: Annotated[str | None, typer.Option("--role")] = None,
) -> None:
    _validate_subject(user, team)
    _emit(ctx, _api_call(lambda: _client_from_context(ctx).list_role_assignments(user=user, team=team, role=role)))


@assignments_app.command("grant")
def assignments_grant(
    ctx: typer.Context,
    role: Annotated[str, typer.Option("--role")],
    user: Annotated[str | None, typer.Option("--user")] = None,
    team: Annotated[str | None, typer.Option("--team")] = None,
    domain: Annotated[Literal["global", "workspace", "project"], typer.Option("--domain")] = "global",
    domain_id: Annotated[str | None, typer.Option("--domain-id")] = None,
) -> None:
    _validate_subject(user, team)
    if (domain == "global") == (domain_id is not None):
        msg = "--domain-id is required for workspace/project and forbidden for global"
        raise typer.BadParameter(msg)
    client = _api_call(lambda: _client_from_context(ctx))
    if team and not _api_call(client.capabilities).get("features", {}).get("team_role_assignments", False):
        _fail(ManifestResolutionError("This target does not support team-role assignments"), usage=True)
    _emit(
        ctx,
        _api_call(
            lambda: client.grant_role(
                role=role,
                user=user,
                team=team,
                domain_type=domain,
                domain_id=domain_id,
            )
        ),
    )


@assignments_app.command("revoke")
def assignments_revoke(
    ctx: typer.Context,
    assignment_id: Annotated[str, typer.Argument()],
    user: Annotated[bool, typer.Option("--user", help="The assignment belongs to a user.")] = False,
    team: Annotated[bool, typer.Option("--team", help="The assignment belongs to a team.")] = False,
) -> None:
    if user == team:
        msg = "Exactly one of --user or --team is required"
        raise typer.BadParameter(msg)
    result = _api_call(lambda: _client_from_context(ctx).revoke_role_assignment(assignment_id, team=team))
    _emit(ctx, result or {"revoked": assignment_id})


@admin_app.command("export")
def export_state(
    ctx: typer.Context,
    format_name: Annotated[Literal["yaml", "json"], typer.Option("--format")] = "yaml",
    file: Annotated[Path | None, typer.Option("--file", help="Write to a file instead of standard output.")] = None,
) -> None:
    state = _api_call(lambda: _reconciler_from_context(ctx).export_state())
    rendered = dump_admin_state(state, format_name=format_name)
    if file is not None:
        file.write_text(rendered, encoding="utf-8")
        return
    typer.echo(rendered, nl=False)


def _load_manifest_or_fail(file: Path):
    try:
        return load_admin_state(file)
    except ValidationError as exc:
        messages = []
        for error in exc.errors(include_input=False, include_url=False):
            location = ".".join(str(part) for part in error["loc"])
            messages.append(f"{location}: {error['msg']}")
        _fail(ValueError("; ".join(messages)), usage=True)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        _fail(exc, usage=True)


@admin_app.command("diff")
def diff_state(
    ctx: typer.Context,
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    prune: Annotated[bool, typer.Option("--prune", help="Include absent manual memberships and grants.")] = False,
) -> None:
    state = _load_manifest_or_fail(file)
    try:
        drift = _reconciler_from_context(ctx).diff(state, prune=prune)
    except ManifestResolutionError as exc:
        _fail(exc, usage=True)
    except (AdminAPIError, httpx.HTTPError, ConnectionConfigurationError) as exc:
        _fail(exc, usage=isinstance(exc, ConnectionConfigurationError))
    _emit(ctx, drift)
    if drift:
        raise typer.Exit(code=3)


@admin_app.command("apply")
def apply_state(
    ctx: typer.Context,
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    prune: Annotated[bool, typer.Option("--prune", help="Remove absent manual memberships and grants.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Confirm a pruning apply.")] = False,
) -> None:
    state = _load_manifest_or_fail(file)
    reconciler = _api_call(lambda: _reconciler_from_context(ctx))
    if prune:
        try:
            drift = reconciler.diff(state, prune=True)
        except ManifestResolutionError as exc:
            _fail(exc, usage=True)
        _emit(ctx, drift, stderr=True)
        if not yes:
            if not sys.stdin.isatty():
                _fail(ValueError("--prune requires --yes in non-interactive use"), usage=True)
            if not typer.confirm("Apply this pruning plan?"):
                raise typer.Abort
    try:
        report = reconciler.apply(state, prune=prune)
    except ManifestResolutionError as exc:
        _fail(exc, usage=True)
    except (AdminAPIError, httpx.HTTPError, ConnectionConfigurationError) as exc:
        _fail(exc, usage=isinstance(exc, ConnectionConfigurationError))
    _emit(ctx, report)
    if report["status"] != "success":
        raise typer.Exit(code=1)


teams_app.add_typer(members_app, name="members")
admin_app.add_typer(users_app, name="users")
admin_app.add_typer(teams_app, name="teams")
admin_app.add_typer(teams_app, name="groups", help="Alias for teams.")
admin_app.add_typer(roles_app, name="roles")
admin_app.add_typer(assignments_app, name="role-assignments")
