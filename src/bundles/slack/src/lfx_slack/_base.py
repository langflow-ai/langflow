"""Shared component base, connection inputs, and identity guard for ``lfx-slack``.

Slack is the only wave-1 provider with two executing identities behind one
provider key, and its user and bot scopes share names (``chat:write`` is both a
User Token Scope and a Bot Token Scope).  Granted scopes therefore cannot tell
the identities apart, so this module checks
:attr:`~lfx.integrations.models.ResolvedCredential.identity` -- populated from
the connection row's ``executing_identity`` -- and fails closed *before* the
first HTTP call when a bot action is handed a user connection or the reverse.

Headless connections resolved from ``LF_CONNECTION__SLACK__<NAME>`` carry no
identity (the wire format has no place to declare one), so ``identity is None``
is treated as "the operator vouched for this token" and the guard defers to
Slack's own ``not_allowed_token_type`` error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from lfx.custom.custom_component.component import Component
from lfx.integrations.errors import ConnectionNotAuthorizedError, IntegrationError
from lfx.integrations.telemetry import integration_action
from lfx.io import ConnectionRefInput

from lfx_slack._client import PROVIDER_ID, SlackClient

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from lfx.integrations.models import CredentialLease, ResolvedCredential

CONNECTION_FIELD = "connection"

USER_PROFILE_ID = "slack-user-oauth"
BOT_PROFILE_ID = "slack-bot-install"

USER_IDENTITY = "user_delegated"
BOT_IDENTITY = "bot"

_IDENTITY_LABEL = {USER_IDENTITY: "user", BOT_IDENTITY: "bot"}

_CACHE_KEY = "_slack_cached_payload"


class SlackIdentityMismatchError(ConnectionNotAuthorizedError):
    """A Slack connection whose token identity cannot run the requested action.

    Keeps the ``connection-not-authorized`` code so hosts, the frontend, and
    telemetry treat it exactly like any other connection authorization denial,
    while saying which identity the action needs.
    """

    def __init__(self, *, expected: str, actual: str) -> None:
        expected_label = _IDENTITY_LABEL.get(expected, expected)
        actual_label = _IDENTITY_LABEL.get(actual, actual)
        IntegrationError.__init__(
            self,
            f"This Slack connection holds a {actual_label} token; this action requires a {expected_label} token.",
            hint=f"Use a Slack connection created with the {expected_label} authorization profile.",
            provider=PROVIDER_ID,
            http_status=403,
        )
        self.expected = expected
        self.actual = actual


def _connection_input(
    *,
    auth_profile_id: str,
    capability: str,
    required_scopes: list[str],
    conditional_scopes: list[dict[str, Any]] | None,
    info: str,
) -> ConnectionRefInput:
    return ConnectionRefInput(
        name=CONNECTION_FIELD,
        display_name="Slack Connection",
        provider=PROVIDER_ID,
        auth_profile_id=auth_profile_id,
        required_scopes=required_scopes,
        conditional_scopes=conditional_scopes or [],
        identity_kind="any",
        capabilities=[capability],
        required=True,
        info=info,
    )


def user_connection_input(
    *,
    capability: str,
    required_scopes: list[str],
    conditional_scopes: list[dict[str, Any]] | None = None,
) -> ConnectionRefInput:
    """Connection field for an action that runs as the connected Slack user."""
    return _connection_input(
        auth_profile_id=USER_PROFILE_ID,
        capability=capability,
        required_scopes=required_scopes,
        conditional_scopes=conditional_scopes,
        info="A Slack connection authorized with user token scopes. The action runs as that Slack user.",
    )


def bot_connection_input(
    *,
    capability: str,
    required_scopes: list[str],
    conditional_scopes: list[dict[str, Any]] | None = None,
) -> ConnectionRefInput:
    """Connection field for an action that runs as the app's bot user."""
    return _connection_input(
        auth_profile_id=BOT_PROFILE_ID,
        capability=capability,
        required_scopes=required_scopes,
        conditional_scopes=conditional_scopes,
        info=(
            "A Slack connection created from a workspace installation (bot token). "
            "The action runs as the app's bot user, which must be a member of the channel."
        ),
    )


def require_identity(credential: ResolvedCredential, *, expected: str) -> None:
    """Fail closed when a resolved Slack credential is the wrong identity."""
    actual = getattr(credential, "identity", None)
    if actual is not None and actual != expected:
        raise SlackIdentityMismatchError(expected=expected, actual=actual)


class SlackBaseComponent(Component):
    """Base for every ``lfx-slack`` component.

    Subclasses declare :attr:`capability_id` (the manifest capability id, which
    is also the telemetry capability label) and :attr:`slack_identity`, then
    run their single Web API call through :meth:`run_action`.
    """

    icon = "Slack"
    documentation = "https://docs.langflow.org/bundles-slack"

    capability_id: ClassVar[str] = ""
    slack_identity: ClassVar[str] = USER_IDENTITY

    def connection_lease(self) -> CredentialLease:
        """Return the lazy lease for this component's connection field."""
        return self.resolve_connection(CONNECTION_FIELD)

    async def run_action(self, action: Callable[[SlackClient], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
        """Resolve the connection, guard its identity, and run one traced call.

        The result is memoized on the instance so a component with more than
        one output does not spend a second call against Slack's per-method
        rate tier.
        """
        cached = self.__dict__.get(_CACHE_KEY)
        if cached is not None:
            return cached

        lease = self.connection_lease()
        credential = await lease.get_credential()
        require_identity(credential, expected=self.slack_identity)
        client = SlackClient(lease)
        async with integration_action(
            self,
            provider=PROVIDER_ID,
            capability=self.capability_id,
            owner_kind=credential.owner_kind,
        ):
            body = await action(client)
        self.__dict__[_CACHE_KEY] = body
        return body
