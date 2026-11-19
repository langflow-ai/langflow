"""Control database maintenance without starting servers or running migrations."""

import asyncio
import json
import os
from typing import Annotated

import typer
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.maintenance import REASON_MAX_LENGTH
from langflow.services.maintenance.state import maintenance_status, set_maintenance

maintenance_app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)
DatabaseEnv = Annotated[str, typer.Option(help="Environment variable containing the database URL.")]


async def _operate(database_url: str, *, enabled: bool | None, reason: str | None) -> dict:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        url = url.set(drivername="sqlite+aiosqlite")
    elif url.get_backend_name() in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    else:
        msg = "Maintenance supports SQLite and PostgreSQL databases."
        raise ValueError(msg)
    engine = create_async_engine(url, hide_parameters=True)
    try:
        async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
            if enabled is not None:
                await set_maintenance(session, enabled=enabled, reason=reason)
                await session.commit()
            return (await maintenance_status(session)).model_dump(mode="json")
    finally:
        await engine.dispose()


def _run(database_url_env: str, *, enabled: bool | None = None, reason: str | None = None) -> None:
    database_url = os.environ.get(database_url_env)
    if not database_url:
        msg = "Set the named database URL environment variable."
        raise typer.BadParameter(msg)
    if reason is not None and len(reason) > REASON_MAX_LENGTH:
        msg = f"The reason must contain at most {REASON_MAX_LENGTH} characters."
        raise typer.BadParameter(msg)
    try:
        state = asyncio.run(_operate(database_url, enabled=enabled, reason=reason))
    except Exception:  # noqa: BLE001 - database errors can contain credentials
        typer.echo("Maintenance control failed. Check the database URL and apply the required migrations.", err=True)
        raise typer.Exit(1) from None
    typer.echo(json.dumps(state))


@maintenance_app.command("on")
def maintenance_on(
    database_url_env: DatabaseEnv = "LANGFLOW_DATABASE_URL",
    reason: Annotated[str | None, typer.Option(help="Reason for the maintenance window.")] = None,
) -> None:
    """Freeze ordinary writes and new runs across all pods."""
    _run(database_url_env, enabled=True, reason=reason)


@maintenance_app.command("off")
def maintenance_off(database_url_env: DatabaseEnv = "LANGFLOW_DATABASE_URL") -> None:
    """Allow ordinary writes again without restarting the servers."""
    _run(database_url_env, enabled=False)


@maintenance_app.command("status")
def maintenance_state(database_url_env: DatabaseEnv = "LANGFLOW_DATABASE_URL") -> None:
    """Show the shared flag and queued and running job counts."""
    _run(database_url_env)
