"""Shared component base, connection inputs, and identity guard for ``lfx-slack``.

Slack is the only wave-1 provider with two executing identities behind one
provider key, and its user and bot scopes share names (``chat:write`` is both a
User Token Scope and a Bot Token Scope).  Granted scopes therefore cannot tell
the identities apart, so this module fails closed *before* the first HTTP call
when a bot action is handed a user token or the reverse.  Two signals are
checked, each one that is present must agree with the action, and at least one
must be present:

* :attr:`~lfx.integrations.models.ResolvedCredential.identity`, populated from
  the connection row's ``executing_identity`` when the host knows it.
* The token's own type prefix (``xoxb-`` bot, ``xoxp-`` user, optionally behind
  the ``xoxe.`` rotation marker), which is what Slack itself acts on.

Headless connections resolved from ``LF_CONNECTION__SLACK__<NAME>`` carry no
recorded identity (the wire format has no place to declare one), so for them
the prefix is the only proof.  A credential that proves neither is refused:
Slack's ``not_allowed_token_type`` cannot be the backstop, because
``chat.postMessage`` accepts both token types.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any, ClassVar, Literal

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

# Slack prefixes every token with its type; a token issued with rotation
# enabled carries ``xoxe.`` in front of that (``xoxe.xoxb-``, ``xoxe.xoxp-``).
_TOKEN_PREFIX = {USER_IDENTITY: "xoxp-", BOT_IDENTITY: "xoxb-"}
_ROTATING_TOKEN_MARKER = "xoxe."  # noqa: S105 - Slack token type marker, not a credential

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


class SlackIdentityUnverifiedError(ConnectionNotAuthorizedError):
    """A Slack credential whose token identity cannot be established at all.

    Raised when the connection records no identity and the token carries no
    recognizable Slack type prefix, so running the action would post under
    whichever identity the token happens to hold.
    """

    def __init__(self, *, expected: str) -> None:
        expected_label = _IDENTITY_LABEL.get(expected, expected)
        prefix = _TOKEN_PREFIX.get(expected)
        IntegrationError.__init__(
            self,
            f"The type of this Slack connection's token could not be verified; "
            f"this action requires a {expected_label} token.",
            hint=(
                f"Supply a Slack {expected_label} token ({prefix}...), or use a connection "
                f"created with the {expected_label} authorization profile."
            ),
            provider=PROVIDER_ID,
            http_status=403,
        )
        self.expected = expected


def _connection_input(
    *,
    auth_profile_id: str,
    capability: str,
    required_scopes: list[str],
    conditional_scopes: list[dict[str, Any]] | None,
    identity_kind: Literal["user", "instance"],
    info: str,
) -> ConnectionRefInput:
    return ConnectionRefInput(
        name=CONNECTION_FIELD,
        display_name="Slack Connection",
        provider=PROVIDER_ID,
        auth_profile_id=auth_profile_id,
        required_scopes=required_scopes,
        conditional_scopes=conditional_scopes or [],
        identity_kind=identity_kind,
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
        identity_kind="user",
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
        # The picker's vocabulary, which maps bot and service identities to
        # "instance" (see lfx_microsoft.manifest._IDENTITY_KIND).
        identity_kind="instance",
        info=(
            "A Slack connection created from a workspace installation (bot token). "
            "The action runs as the app's bot user, which must be a member of the channel."
        ),
    )


def token_identity(token: str) -> str | None:
    """Return the identity a Slack token's type prefix proves, or ``None``."""
    bare = token.removeprefix(_ROTATING_TOKEN_MARKER)
    for identity, prefix in _TOKEN_PREFIX.items():
        if bare.startswith(prefix):
            return identity
    return None


def require_identity(credential: ResolvedCredential, *, expected: str) -> None:
    """Fail closed unless the resolved Slack credential proves ``expected``.

    The recorded identity and the token prefix must each agree with the action
    when present, and at least one of them must be present.
    """
    recorded = getattr(credential, "identity", None)
    if recorded is not None and recorded != expected:
        raise SlackIdentityMismatchError(expected=expected, actual=recorded)
    proven = token_identity(credential.access_token.get_secret_value())
    if proven is not None and proven != expected:
        raise SlackIdentityMismatchError(expected=expected, actual=proven)
    if recorded is None and proven is None:
        raise SlackIdentityUnverifiedError(expected=expected)


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

    def _pre_run_setup(self) -> None:
        """Drop the per-build response memo before each build of this vertex.

        ``Component._build_results`` calls this once per build, and the graph
        reuses one component instance across builds -- a cycle vertex, a Loop
        body, or any other rebuild. Without this the memo below would survive
        into the next iteration and a write action would report the first
        response forever while making no further request. Clearing it here
        keeps the intended sharing *within* one build (a component's Matches
        and Pagination outputs still cost one Slack call) and restores
        freshness *between* builds.
        """
        self.__dict__.pop(_CACHE_KEY, None)

    def connection_lease(self) -> CredentialLease:
        """Return the lazy lease for this component's connection field."""
        return self.resolve_connection(CONNECTION_FIELD)

    async def run_action(self, action: Callable[[SlackClient], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
        """Resolve the connection, guard its identity, and run one traced call.

        The result is memoized for the duration of one build so a component
        with more than one output does not spend a second call against Slack's
        per-method rate tier; :meth:`_pre_run_setup` clears the memo when the
        vertex is rebuilt.
        """
        cached = self.__dict__.get(_CACHE_KEY)
        if cached is not None:
            return cached

        lease = self.connection_lease()
        credential = await lease.get_credential()
        client = SlackClient(lease, credential_validator=partial(require_identity, expected=self.slack_identity))
        async with integration_action(
            self,
            provider=PROVIDER_ID,
            capability=self.capability_id,
            owner_kind=credential.owner_kind,
        ):
            # The client checks the identity of the actual token before every
            # request, including after a proactive or reactive refresh. Keep
            # those checks inside the span so denials are counted in telemetry.
            body = await action(client)
        self.__dict__[_CACHE_KEY] = body
        return body
