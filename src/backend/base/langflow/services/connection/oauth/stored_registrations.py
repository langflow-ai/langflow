"""OAuth registrations superusers manage in Settings > Connections > Manage providers.

Each registration is a superuser's Credential variable named
``LANGFLOW_OAUTH_REGISTRATION__<registration id>`` whose value is the registration JSON.
Every superuser manages every saved registration: a save replaces the registration
whoever saved it before. They are merged into ``LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS``,
which every reader of :class:`~langflow.services.connection.oauth.config.OAuthSettings`
already uses, at startup and again in the process that handles each save or removal.
Other processes (more workers, the trigger listener) pick changes up at their next start,
so a change made since this process started is reported as waiting for a restart.
The environment wins for a registration ID it defines.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from pydantic import ValidationError
from sqlmodel import col, select

from langflow.services.auth import utils as auth_utils
from langflow.services.connection.oauth.config import OAuthRegistration, _registration_validation_message
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from langflow.services.deps import session_scope
from langflow.services.variable.constants import CREDENTIAL_TYPE, OAUTH_REGISTRATION_VARIABLE_PREFIX

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

STORED_REGISTRATION_PREFIX = OAUTH_REGISTRATION_VARIABLE_PREFIX
REGISTRATIONS_ENV = "LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS"
# The environment's own registrations, kept before the first merge so a later merge can
# drop a removed registration. An environment variable, so forked or spawned workers and
# the listener subprocess inherit it with the merged value.
ENVIRONMENT_COPY_ENV = "LANGFLOW_CONNECTION_OAUTH_ENVIRONMENT_REGISTRATIONS"
REGISTRATION_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"
SECRET_FIELDS = ("client_secret", "private_key", "signing_secret")
# The saved registrations this process applied when it started. Processes started at the
# same time hold the same ones until they restart, whatever this process applies since.
_STARTED_WITH: dict[str, SavedRegistration] = {}


class SavedRegistrationError(ValueError):
    """The registration cannot be saved as given; the message is safe to show."""


class SavedRegistration:
    def __init__(self, registration_id: str, value: dict[str, Any], saved_by: str, updated_at: datetime | None):
        self.registration_id = registration_id
        self.value = value
        self.saved_by = saved_by
        self.updated_at = updated_at


def _superuser_rows(registration_id: str | None = None):
    names = col(Variable.name)
    return (
        select(Variable, User.username)
        .join(User, col(User.id) == col(Variable.user_id))
        .where(
            col(User.is_superuser).is_(True),
            col(User.is_active).is_(True),
            Variable.type == CREDENTIAL_TYPE,
            names == f"{STORED_REGISTRATION_PREFIX}{registration_id}"
            if registration_id
            else names.startswith(STORED_REGISTRATION_PREFIX, autoescape=True),
        )
        .order_by(col(Variable.updated_at).asc().nulls_first())
    )


async def read_saved_registrations(session: AsyncSession) -> dict[str, SavedRegistration]:
    """Return the newest saved value of each registration ID, secrets included."""
    saved: dict[str, SavedRegistration] = {}
    for variable, username in (await session.exec(_superuser_rows())).all():
        if not variable.name.startswith(STORED_REGISTRATION_PREFIX):
            continue
        registration_id = variable.name.removeprefix(STORED_REGISTRATION_PREFIX)
        if not re.fullmatch(REGISTRATION_ID_PATTERN, registration_id) or len(registration_id) > 120:  # noqa: PLR2004
            continue
        try:
            value = json.loads(auth_utils.decrypt_api_key(variable.value))
        except Exception:  # noqa: BLE001
            await logger.awarning(f"Saved OAuth registration '{registration_id}' could not be read and was skipped.")
            continue
        if isinstance(value, dict):
            # Rows are oldest first, so the newest save wins when two exist for one ID.
            saved[registration_id] = SavedRegistration(registration_id, value, username, variable.updated_at)
    return saved


async def save_registration(
    session: AsyncSession, *, user_id: UUID, registration_id: str, registration: dict[str, Any]
) -> None:
    """Validate and store one registration, replacing any superuser's earlier save of that ID.

    Omitted secret fields keep their saved values. An explicit null clears a secret,
    and changing authentication methods replaces the old client secret or private key.
    """
    if not re.fullmatch(REGISTRATION_ID_PATTERN, registration_id) or len(registration_id) > 120:  # noqa: PLR2004
        msg = "Use lowercase letters, numbers, hyphens or underscores for the registration ID."
        raise SavedRegistrationError(msg)
    value = dict(registration)
    current = (await read_saved_registrations(session)).get(registration_id)
    if current:
        for field in SECRET_FIELDS:
            if field in value or not current.value.get(field):
                continue
            if (field == "client_secret" and value.get("private_key")) or (
                field == "private_key" and value.get("client_secret")
            ):
                continue
            value[field] = current.value[field]
    try:
        OAuthRegistration.model_validate(value)
    except ValidationError as exc:
        raise SavedRegistrationError(_registration_validation_message(exc)) from None
    await delete_registration(session, registration_id)
    session.add(
        Variable(
            name=f"{STORED_REGISTRATION_PREFIX}{registration_id}",
            value=auth_utils.encrypt_api_key(json.dumps(value)),
            type=CREDENTIAL_TYPE,
            default_fields=[],
            user_id=user_id,
            updated_at=datetime.now(timezone.utc),
        )
    )


async def delete_registration(session: AsyncSession, registration_id: str) -> bool:
    """Remove every superuser's saved copy of one registration ID."""
    rows = (await session.exec(_superuser_rows(registration_id))).all()
    for variable, _username in rows:
        await session.delete(variable)
    await session.flush()
    return bool(rows)


def environment_registrations() -> dict[str, Any] | None:
    """Return the registrations the server environment defines, or None when they are not a JSON object."""
    raw = os.environ.get(ENVIRONMENT_COPY_ENV)
    if raw is None:
        raw = os.environ.get(REGISTRATIONS_ENV) or "{}"
        os.environ[ENVIRONMENT_COPY_ENV] = raw
    try:
        configured = json.loads(raw)
    except ValueError:
        return None
    return configured if isinstance(configured, dict) else None


def apply_saved_registrations(saved: dict[str, SavedRegistration]) -> list[str] | None:
    """Make this process use the environment's registrations plus the saved ones.

    Returns the saved IDs now in use, or None when the environment value is not a JSON
    object, in which case it is left untouched.
    """
    configured = environment_registrations()
    if configured is None:
        return None
    added = {
        registration_id: entry.value for registration_id, entry in saved.items() if registration_id not in configured
    }
    os.environ[REGISTRATIONS_ENV] = json.dumps({**configured, **added})
    return sorted(added)


def registration_status(registration_id: str, entry: SavedRegistration) -> str:
    """Say whether the saved value is in use since startup, waits for a restart, or loses to the environment."""
    if registration_id in (environment_registrations() or {}):
        return "overridden"
    started = _STARTED_WITH.get(registration_id)
    return "active" if started is not None and started.value == entry.value else "pending"


def removed_since_startup(saved: dict[str, SavedRegistration]) -> dict[str, SavedRegistration]:
    """Return the registrations this process started with that are no longer saved.

    Processes started with them still use them until they restart.
    """
    return {registration_id: entry for registration_id, entry in _STARTED_WITH.items() if registration_id not in saved}


async def load_stored_oauth_registrations() -> None:
    """Add superuser-saved registrations to this process's environment.

    Only variables owned by active superusers count, so a regular user cannot add a
    registration by creating a variable with the same name. Failures are logged and
    never stop the process from starting.
    """
    try:
        async with session_scope() as session:
            saved = await read_saved_registrations(session)
    except Exception:  # noqa: BLE001
        await logger.aexception("Could not read saved OAuth registrations")
        return

    applied = apply_saved_registrations(saved)
    _STARTED_WITH.clear()
    _STARTED_WITH.update({registration_id: saved[registration_id] for registration_id in applied or []})
    if applied is None:
        await logger.awarning(f"{REGISTRATIONS_ENV} is not a JSON object; saved OAuth registrations were not applied.")
    elif applied:
        await logger.ainfo(f"Applied saved OAuth registrations: {', '.join(applied)}")
