"""Slack Web API client and the provider error normalizer for ``lfx-slack``.

Two things live here:

* :class:`SlackClient` -- a thin wrapper over ``slack_sdk``'s
  :class:`~slack_sdk.web.async_client.AsyncWebClient` that takes its bearer
  token from a :class:`~lfx.integrations.models.CredentialLease` and performs
  the single reactive re-resolve the connection contract allows when Slack
  rejects a cached token.
* :func:`normalize_slack_error` -- registered with lfx through
  ``register_error_normalizer("slack", ...)``.  It is required, not optional:
  Slack answers **HTTP 200 with ``{"ok": false, "error": "..."}``** for
  application-level failures, so lfx's status-code-only fallback would map an
  expired token or a missing scope to ``provider-unavailable`` and the
  frontend's code-keyed reconnect/grant affordances would never fire.

SSRF posture
------------
``SLACK_API_BASE_URL`` is a module constant and no component exposes a URL,
host, or proxy input, so this bundle has no user-controllable request target.
That is why it does not reach for ``lfx.utils.ssrf_transport``: those helpers
build *httpx* clients with DNS pinning, and ``AsyncWebClient`` speaks aiohttp,
for which lfx ships no equivalent transport.  Removing the SSRF surface
entirely is a stronger guarantee than pinning DNS for a URL a flow author can
set.  ``tests/test_slack_client_errors.py`` pins the constant and
``tests/test_slack_capability_manifest.py`` pins that no component declares a
request-target input.

This module and its siblings (``_base.py``, ``_chat.py``) live at the package
root rather than inside ``components/slack`` because the bundle directory is
scanned by ``lfx extension validate``: a shared abstract ``Component`` base
inside it is reported as ``build-method-missing``, since it deliberately has no
output method of its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.integrations.errors import (
    ActionUnsupportedError,
    AuthExpiredError,
    ConnectionNotAuthorizedError,
    IntegrationError,
    InvalidRequestError,
    ProviderUnavailableError,
    RateLimitedError,
    ScopeMissingError,
    normalize_integration_error,
    register_error_normalizer,
)
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

if TYPE_CHECKING:
    from collections.abc import Callable

    from lfx.integrations.models import CredentialLease, ResolvedCredential
    from slack_sdk.web.async_slack_response import AsyncSlackResponse

PROVIDER_ID = "slack"

# Fixed, non-configurable API root. See the module docstring.
SLACK_API_BASE_URL = "https://slack.com/api/"

DEFAULT_TIMEOUT_SECONDS = 30

HTTP_BAD_REQUEST = 400
HTTP_TOO_MANY_REQUESTS = 429
HTTP_UNAUTHORIZED = 401

# Slack ``ok:false`` error codes that mean "this token will never work again";
# the connection must be reconnected (or, for a rotated token, re-resolved).
_AUTH_ERROR_CODES = frozenset(
    {
        "account_inactive",
        "invalid_auth",
        "not_authed",
        "token_expired",
        "token_revoked",
    }
)

_RATE_LIMIT_ERROR_CODES = frozenset(
    {
        "message_limit_exceeded",
        "rate_limited",
        "ratelimited",
    }
)

# The channel id is wrong, or the connection's identity cannot see or post in
# it. Slack answers ``channel_not_found`` for a private channel the token is not
# a member of, so both codes share one remedy.
_CHANNEL_NOT_FOUND = "channel_not_found"
_NOT_IN_CHANNEL = "not_in_channel"

# Codes Slack documents as the caller's fault for the methods this bundle calls
# (``chat.postMessage``, ``reactions.add``, ``conversations.replies``,
# ``conversations.members``, ``search.messages``, ``canvases.create``,
# ``users.info``): the inputs must change, so retrying cannot help.
_INVALID_REQUEST_ERROR_CODES = frozenset(
    {
        "already_reacted",
        "as_user_not_supported",
        "attachment_payload_limit_exceeded",
        "bad_timestamp",
        "cannot_reply_to_message",
        "duplicate_channel_not_found",
        "duplicate_message_not_found",
        "free_team_canvas_tab_already_exists",
        "invalid_arg_name",
        "invalid_arguments",
        "invalid_array_arg",
        "invalid_blocks",
        "invalid_blocks_format",
        "invalid_charset",
        "invalid_cursor",
        "invalid_form_data",
        "invalid_limit",
        "invalid_metadata_filter_keys",
        "invalid_metadata_format",
        "invalid_metadata_schema",
        "invalid_name",
        "invalid_post_type",
        "invalid_ts_latest",
        "invalid_ts_oldest",
        "is_archived",
        "markdown_text_conflict",
        "message_not_found",
        "metadata_must_be_sent_from_app",
        "metadata_too_large",
        "missing_post_type",
        "msg_blocks_too_long",
        "no_item_specified",
        "no_query",
        "no_text",
        "not_reactable",
        "restricted_action_non_threadable_channel",
        "restricted_action_read_only_channel",
        "restricted_action_thread_locked",
        "restricted_action_thread_only_channel",
        "team_not_found",
        "thread_locked",
        "thread_not_found",
        "too_many_attachments",
        "too_many_contact_cards",
        "too_many_emoji",
        "too_many_reactions",
        "user_not_found",
        "user_not_visible",
    }
)

# Slack or a workspace administrator refused the action for this account.
# Neither retrying nor changing the inputs helps.
_PROVIDER_DENIED_ERROR_CODES = frozenset(
    {
        "access_denied",
        "accesslimited",
        "app_access_restricted",
        "ekm_access_denied",
        "no_access",
        "no_permission",
        "restricted_action",
        "send_on_behalf_not_allowed",
        "slack_connect_canvas_sharing_blocked",
        "slack_connect_file_link_sharing_blocked",
        "slack_connect_lists_sharing_blocked",
        "team_access_not_granted",
        "two_factor_setup_required",
    }
)

# Codes that mean "the workspace, plan, channel type, or token type cannot do
# this", i.e. retrying or re-granting scopes will not help.
_UNSUPPORTED_ERROR_CODES = frozenset(
    {
        "canvas_disabled_user_team",
        "deprecated_endpoint",
        "enterprise_is_restricted",
        "free_team_not_allowed",
        "free_teams_cannot_create_standalone_canvases",
        "method_deprecated",
        "method_not_supported_for_channel_type",
        "not_allowed_token_type",
        "unknown_method",
    }
)


def _header(headers: Any, name: str) -> str | None:
    """Case-insensitively read one header from a mapping-ish object."""
    if not headers:
        return None
    try:
        items = headers.items()
    except AttributeError:
        return None
    wanted = name.casefold()
    for key, value in items:
        if str(key).casefold() == wanted:
            return value if isinstance(value, str) else (value[0] if value else None)
    return None


def _retry_after(headers: Any) -> float | None:
    raw = _header(headers, "retry-after")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _error_status(status: Any) -> int | None:
    """Return Slack's HTTP status only when it is itself an error status.

    ``ok:false`` bodies arrive with HTTP 200. A terminal run handler answers
    with the typed error's ``http_status``, so forwarding that 200 would report
    a failed run as a success.
    """
    return status if isinstance(status, int) and status >= HTTP_BAD_REQUEST else None


def _channel_error(code: str, status: int | None) -> InvalidRequestError:
    if code == _NOT_IN_CHANNEL:
        message = "This Slack connection is not a member of the channel."
        hint = "Invite the app to the channel (or join it, for actions that run as you), then try again."
    else:
        message = "Slack could not find the channel, or this connection cannot see it."
        hint = (
            "Check the channel ID. If the channel is private, invite the app to it "
            "(or join it, for actions that run as you)."
        )
    return InvalidRequestError(message, hint=hint, provider=PROVIDER_ID, http_status=status or HTTP_BAD_REQUEST)


def normalize_slack_error(exc: BaseException) -> IntegrationError | None:
    """Map a ``slack_sdk`` failure onto lfx's sanitized error vocabulary.

    Returns ``None`` for exceptions this bundle has no opinion about, which
    lets ``normalize_integration_error`` fall through to its status-code rules.
    A Slack code this bundle does not recognize stays ``provider-unavailable``.
    """
    if not isinstance(exc, SlackApiError):
        return None
    response = getattr(exc, "response", None)
    raw_status = getattr(response, "status_code", None)
    status = _error_status(raw_status)
    headers = getattr(response, "headers", None)
    data = getattr(response, "data", None)
    code = data.get("error") if isinstance(data, dict) else None

    if code in _AUTH_ERROR_CODES or raw_status == HTTP_UNAUTHORIZED:
        return AuthExpiredError(provider=PROVIDER_ID, http_status=status or HTTP_UNAUTHORIZED)
    if code == "missing_scope":
        needed = data.get("needed") if isinstance(data, dict) else None
        missing = frozenset(part for part in str(needed or "").replace(",", " ").split() if part)
        return ScopeMissingError(missing, provider=PROVIDER_ID)
    if code in _RATE_LIMIT_ERROR_CODES or raw_status == HTTP_TOO_MANY_REQUESTS:
        return RateLimitedError(
            provider=PROVIDER_ID,
            retry_after=_retry_after(headers),
            http_status=status or HTTP_TOO_MANY_REQUESTS,
        )
    if code in {_CHANNEL_NOT_FOUND, _NOT_IN_CHANNEL}:
        return _channel_error(code, status)
    if code in _INVALID_REQUEST_ERROR_CODES:
        return InvalidRequestError(provider=PROVIDER_ID, http_status=status or HTTP_BAD_REQUEST)
    if code in _PROVIDER_DENIED_ERROR_CODES:
        return ConnectionNotAuthorizedError(provider=PROVIDER_ID, reason="provider")
    if code in _UNSUPPORTED_ERROR_CODES:
        return ActionUnsupportedError(provider=PROVIDER_ID, http_status=status)
    return ProviderUnavailableError(provider=PROVIDER_ID, http_status=status)


register_error_normalizer(PROVIDER_ID, normalize_slack_error)


class SlackClient:
    """Connection-backed Slack Web API client.

    One instance wraps one :class:`CredentialLease`.  Every call goes through
    :meth:`call`, which normalizes provider failures and performs at most one
    reactive re-resolve after an ``auth-expired`` rejection -- Slack tokens
    have no expiry unless the app opted into rotation, so a rejected token is
    the only signal a rotation happened.
    """

    def __init__(
        self,
        lease: CredentialLease,
        *,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        credential_validator: Callable[[ResolvedCredential], None] | None = None,
    ) -> None:
        self._lease = lease
        self._timeout = timeout
        self._credential_validator = credential_validator
        self._client: AsyncWebClient | None = None

    async def _web_client(self) -> AsyncWebClient:
        credential = await self._lease.get_credential()
        if self._credential_validator is not None:
            self._credential_validator(credential)
        token = credential.access_token.get_secret_value()
        if self._client is None:
            self._client = AsyncWebClient(
                token=token,
                base_url=SLACK_API_BASE_URL,
                timeout=self._timeout,
            )
        else:
            # Multi-call actions can outlive a token. Always use the same
            # credential that was just resolved and identity-checked.
            self._client.token = token
        return self._client

    async def _invoke(self, method: str, **kwargs: Any) -> AsyncSlackResponse:
        client = await self._web_client()
        api_method = getattr(client, method, None)
        if api_method is None:  # pragma: no cover - guarded by the method constants
            msg = f"slack_sdk has no Web API method {method!r}"
            raise AttributeError(msg)
        try:
            return await api_method(**kwargs)
        except Exception as exc:
            raise normalize_integration_error(exc, provider=PROVIDER_ID) from exc

    async def call(self, method: str, **kwargs: Any) -> dict[str, Any]:
        """Call one Slack Web API method and return its parsed body.

        ``kwargs`` with a ``None`` value are dropped so optional component
        inputs never turn into empty query parameters.
        """
        payload = {key: value for key, value in kwargs.items() if value is not None}
        try:
            response = await self._invoke(method, **payload)
        except AuthExpiredError as exc:
            # Raises the original error when the single allowed re-resolve has
            # already been spent, so a permanently rejected token cannot loop.
            await self._lease.get_token_after_auth_error(exc)
            response = await self._invoke(method, **payload)
        body = response.data
        return dict(body) if isinstance(body, dict) else {}


def next_cursor(body: dict[str, Any]) -> str | None:
    """Return the cursor for the next page, or ``None`` on the last page."""
    metadata = body.get("response_metadata")
    if not isinstance(metadata, dict):
        return None
    cursor = metadata.get("next_cursor")
    return cursor if isinstance(cursor, str) and cursor else None
