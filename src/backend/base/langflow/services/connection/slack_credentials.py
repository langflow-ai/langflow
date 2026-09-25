"""Rules for manually entered Slack credentials, and the app-level token in particular.

Slack issues three kinds of token and Langflow stores two of them manually:

* a **bot token** (``xoxb-``), which the "as app" actions call the Web API with -
  on Desktop, where there is no bot OAuth, it is pasted in;
* an **app-level token** (``xapp-``), the third named Slack profile
  (``slack-app-token``, trigger-contract section 6). It is issued per app in the
  app's own settings, never through OAuth, carries only ``connections:write``,
  and exists for exactly one purpose: opening Slack Socket Mode sockets.

The app-level token is special twice over, and this module is where both are
enforced:

1. **It is marked, server-side.** An app-level token connection is stored with
   ``granted_scopes == ["connections:write"]`` whatever the client sent, and
   that scope is refused on any other token. Flow-save reconciliation reads the
   marker to decide a Slack trigger runs on Socket Mode - without decrypting
   anything - and because only this code can write it, the marker cannot be
   forged onto a bot token to point it at the wrong transport.
2. **It resolves only inside the listener process** (:func:`refuse_outside_listener`).
   Socket Mode is the only thing it is for, and the listener is the only process
   that holds Socket Mode sockets. A flow component that names the connection -
   in a triggered run or an interactive one - is refused, so the token never
   reaches a graph, a log or a tool call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.integrations.errors import ConnectionNotAuthorizedError

from langflow.services.database.models.connection.schemas import ConnectionOwnershipMode

if TYPE_CHECKING:
    from langflow.services.database.models.connection.model import Connection
    from langflow.services.database.models.connection.schemas import ConnectionCreate

PROVIDER_SLACK = "slack"
APP_TOKEN_PREFIX = "xapp-"  # noqa: S105 - Slack's app-level token type prefix, not a credential
#: The only scope an app-level token carries, and the server-set marker that a
#: connection holds one.
APP_TOKEN_SCOPE = "connections:write"  # noqa: S105 - an OAuth scope name, not a credential


class ManualCredentialError(ValueError):
    """A manually entered credential that Langflow will not store."""


def is_app_token_connection(row: Connection) -> bool:
    """True for a Slack connection holding an app-level token.

    Reads the non-secret marker only, so callers that must not decrypt (flow
    save, the dispatcher) can still tell the two Slack transports apart.
    """
    return row.provider_key == PROVIDER_SLACK and APP_TOKEN_SCOPE in (row.granted_scopes or [])


def prepare_manual_credential(payload: ConnectionCreate, *, context: str) -> ConnectionCreate:
    """Validate a manually entered Slack credential; return what to store.

    Everything but Slack passes through untouched. For Slack:

    * an app-level token must be the caller's own connection, recorded as the
      app's ``bot`` identity, with no refresh token or expiry (app-level tokens
      have neither); it is refused on hosted, where Socket Mode is not
      available; and its scopes are *set here*, never taken from the request;
    * any other Slack token is refused the app-level scope, so the marker above
      means what it says.
    """
    if payload.provider_key != PROVIDER_SLACK:
        return payload
    token = payload.credentials.access_token.get_secret_value() if payload.credentials is not None else ""
    if not token.startswith(APP_TOKEN_PREFIX):
        if APP_TOKEN_SCOPE in payload.granted_scopes:
            msg = f"The {APP_TOKEN_SCOPE} scope belongs to Slack app-level tokens (xapp-) only."
            raise ManualCredentialError(msg)
        return payload

    if context == "hosted":
        msg = (
            "Slack app-level tokens are for Socket Mode, which hosted Langflow does not offer: a Slack app "
            "listed in the Slack Marketplace cannot use it. Hosted Slack triggers receive events through the "
            "Events API instead."
        )
        raise ManualCredentialError(msg)
    if payload.ownership_mode != ConnectionOwnershipMode.USER:
        msg = "An app-level token backs your own Slack triggers, so it must be your own connection."
        raise ManualCredentialError(msg)
    if payload.executing_identity.identity != "bot":
        msg = "A Slack app-level token acts as the app, so its identity must be 'bot'."
        raise ManualCredentialError(msg)
    credentials = payload.credentials
    if credentials is None or credentials.refresh_token is not None or credentials.expires_at is not None:
        msg = "Slack app-level tokens neither expire nor refresh; remove refresh_token and expires_at."
        raise ManualCredentialError(msg)
    return payload.model_copy(update={"granted_scopes": [APP_TOKEN_SCOPE]})


def refuse_outside_listener(row: Connection, *, access_token: str | None = None) -> None:
    """Raise unless this process is the listener, for an app-level token.

    Checked on the non-secret marker before decryption and on the token prefix
    after it, so a row that somehow lacks the marker is still caught.
    """
    holds_app_token = is_app_token_connection(row) or (
        row.provider_key == PROVIDER_SLACK and bool(access_token) and access_token.startswith(APP_TOKEN_PREFIX)
    )
    if not holds_app_token:
        return
    # Imported here: the trigger package imports this service, so a module-level
    # import would be a cycle.
    from langflow.services.triggers.listeners.guard import is_listener_process

    if not is_listener_process():
        raise ConnectionNotAuthorizedError(provider=PROVIDER_SLACK, reason="listener-only")
