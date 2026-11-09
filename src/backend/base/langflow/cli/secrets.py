"""Offline secrets commands; key material is accepted only through named env vars."""

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import create_engine

from langflow.services.secrets.crypto import receipt_fingerprint
from langflow.services.secrets.rotation import RotationError, audit, load_participants, rotate

secrets_app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    help="Audit and rotate root-encrypted secrets while Langflow is stopped.",
)


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        msg = "A required environment variable is unset or empty."
        raise RotationError(msg)
    return value


def _failure(exc: RotationError) -> None:
    payload = {"error": str(exc)}
    if exc.report is not None:
        payload["report"] = asdict(exc.report)
    typer.echo(json.dumps(payload))
    raise typer.Exit(1)


@secrets_app.command("audit")
def audit_command(
    key_env: Annotated[
        str, typer.Option(help="Name of the environment variable containing the current key.")
    ] = "LANGFLOW_SECRET_KEY",
    database_url_env: Annotated[
        str, typer.Option(help="Name of the environment variable containing a synchronous database URL.")
    ] = "LANGFLOW_MIGRATION_TARGET_URL",
) -> None:
    """Report counts and table/row IDs; never return secret values."""
    engine = None
    try:
        key = _env(key_env)
        engine = create_engine(_env(database_url_env), hide_parameters=True)
        participants = load_participants()
        with engine.connect() as conn:
            report = audit(conn, key, participants=participants)
        typer.echo(json.dumps(asdict(report)))
        if report.failures:
            raise typer.Exit(1)
    except RotationError as exc:
        _failure(exc)
    except typer.Exit:
        raise
    except Exception:  # noqa: BLE001 - sanitize driver and plugin errors that can contain secrets
        _failure(RotationError("Secret audit failed. Check the database configuration and schema."))
    finally:
        if engine is not None:
            engine.dispose()


@secrets_app.command("rotate")
def rotate_command(
    *,
    old_key_env: Annotated[str, typer.Option(help="Name of the environment variable containing the old key.")],
    new_key_env: Annotated[str, typer.Option(help="Name of the environment variable containing the new key.")],
    backup_file: Annotated[Path, typer.Option(help="Local database backup artifact.")],
    backup_sha256: Annotated[str, typer.Option(help="Independently recorded SHA-256 of that backup.")],
    instance_uid: Annotated[
        str | None, typer.Option(help="Target instance UID for an operator migration receipt.")
    ] = None,
    receipt_file: Annotated[
        Path | None, typer.Option(help="Write the successful operator receipt to a new local file.")
    ] = None,
    writers_stopped: Annotated[
        bool, typer.Option(help="Attest all web processes, workers, and listeners are stopped.")
    ] = False,
    database_url_env: Annotated[
        str, typer.Option(help="Name of the environment variable containing a synchronous database URL.")
    ] = "LANGFLOW_MIGRATION_TARGET_URL",
) -> None:
    """Atomically rewrap and verify all values; activate the new root before restarting."""
    engine = None
    try:
        if receipt_file is not None and (not instance_uid or receipt_file.exists()):
            msg = "A receipt file requires an instance UID and a path that does not exist."
            raise RotationError(msg)
        old_key, new_key = _env(old_key_env), _env(new_key_env)
        engine = create_engine(_env(database_url_env), hide_parameters=True)
        report = rotate(
            engine=engine,
            old_key=old_key,
            new_key=new_key,
            backup_file=backup_file,
            backup_sha256=backup_sha256,
            writers_stopped=writers_stopped,
            participants=load_participants(),
            instance_uid=instance_uid,
        )
        receipt = {
            "schema_version": 1,
            "instance_uid": instance_uid,
            "previous_key_fingerprint": receipt_fingerprint(old_key),
            "key_fingerprint": receipt_fingerprint(new_key),
            "status": "completed",
            "rotation_id": report.rotation_id,
        }
        if receipt_file is not None:
            try:
                with receipt_file.open("x", encoding="utf-8") as output:
                    json.dump(receipt, output)
            except OSError:
                typer.echo(
                    json.dumps(
                        {
                            "receipt": receipt,
                            "error": "Database rotation committed, but writing the receipt file failed.",
                        }
                    )
                )
                raise typer.Exit(1) from None
        typer.echo(
            json.dumps(
                {
                    "receipt": receipt if instance_uid else None,
                    "database_rotation": asdict(report),
                    "key_activation": "required",
                    "sessions": "HS256 sessions must log in again after activation",
                }
            )
        )
    except RotationError as exc:
        _failure(exc)
    except typer.Exit:
        raise
    except Exception:  # noqa: BLE001 - sanitize driver and plugin errors that can contain secrets
        _failure(RotationError("Rotation failed. Keep writers stopped and inspect the completion receipt safely."))
    finally:
        if engine is not None:
            engine.dispose()
