from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
import warnings
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Coroutine, Iterable, Mapping
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

import jwt
from fastapi import HTTPException, Request, WebSocketException, status
from jwt import InvalidTokenError
from lfx.log.logger import logger
from lfx.services.auth.base import BaseAuthService
from lfx.services.model_provider_policy import set_current_model_provider_policy_context
from lfx.services.settings.constants import DEFAULT_SUPERUSER, LEGACY_DEFAULT_SUPERUSER_PASSWORD
from sqlalchemy.exc import IntegrityError

from langflow.helpers.user import get_user_by_flow_id_or_endpoint_name
from langflow.services.auth.constants import AUTO_LOGIN_ERROR, AUTO_LOGIN_SESSION_WARNING, AUTO_LOGIN_WARNING
from langflow.services.auth.context import (
    AUTH_METHOD_AUTO_LOGIN,
    AUTH_METHOD_EXTERNAL,
    AUTH_METHOD_JWT,
    AuthCredentialContext,
    clear_current_auth_context,
    set_current_auth_context,
)
from langflow.services.auth.exceptions import (
    AuthBackendUnavailableError,
    AuthenticationError,
    InactiveUserError,
    InvalidCredentialsError,
    MissingCredentialsError,
    TokenExpiredError,
)
from langflow.services.auth.exceptions import (
    InvalidTokenError as AuthInvalidTokenError,
)
from langflow.services.auth.external import (
    ExternalIdentity,
    _external_username_fallback,
    access_context_from_identity,
    clear_current_external_access_context,
    identity_from_claims,
    resolve_external_identity,
    set_current_external_access_context,
)
from langflow.services.database.models.api_key.crud import authenticate_api_key
from langflow.services.database.models.user.crud import (
    get_user_by_id,
    get_user_by_username,
    update_user_last_login_at,
)
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import session_scope
from langflow.services.schema import ServiceType

_MAX_EXTERNAL_AUTHORIZATION_GROUPS = 500
_MAX_EXTERNAL_AUTHORIZATION_GROUP_LENGTH = 256
_MAX_EXTERNAL_GROUP_CLAIM_PATH_DEPTH = 16
_MAX_DIRECTORY_RECONCILE_CACHE_ENTRIES = 10_000
_MAX_EXTERNAL_AUTH_ATTEMPTS = 3
_EXTERNAL_AUTH_RETRY_BACKOFF_SECONDS = 0.02

# SQLSTATE classes that mean "the transaction was rolled back, retry it": the
# statement never took effect, so nothing the caller sent was rejected.
_RETRYABLE_SQLSTATES = frozenset(
    {
        "40001",  # serialization_failure
        "40P01",  # deadlock_detected
        "55P03",  # lock_not_available
    }
)


def _is_retryable_backend_failure(exc: BaseException) -> bool:
    """Return whether an exception is a transient backend failure, not a verdict.

    A deadlock victim, a serialization failure or a lost connection all mean the
    request never got an answer. Reporting those as an authentication failure
    tells the caller to fix a credential that was never actually rejected.
    """
    from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
    from sqlalchemy.exc import TimeoutError as SQLTimeoutError

    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (InterfaceError, OperationalError, SQLTimeoutError)):
            return True
        if isinstance(current, DBAPIError):
            if current.connection_invalidated:
                return True
            orig = current.orig
            # psycopg3 exposes ``sqlstate``; psycopg2 exposes ``pgcode``.
            sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
            if isinstance(sqlstate, str) and sqlstate in _RETRYABLE_SQLSTATES:
                return True
        current = current.__cause__ or current.__context__
    return False


class _DirectoryReconcileCache:
    """Bounded, short-lived record of the last directory state reconciled per user.

    LE-2109: bearer tokens arrive on every request, and reconciliation opens a
    transaction, takes the authorization plugin's policy locks and appends an
    audit row. Repeating all of that for a directory state that has not moved
    is pure overhead, so one successful *no-op* pass is remembered for a short
    interval.

    The cache holds at most one entry per user: the exact state the last
    confirming pass verified. A request is skipped only while that entry is
    fresh *and* carries the same state, so any claim that differs from the
    last reconciled state misses by construction - including a state that
    was cached earlier and has since been moved past. Keying by state alone
    would let ``[devs]`` cached before a promotion to ``[admins, devs]`` keep
    serving after the IdP revokes ``admins`` again, holding the admin role
    until the entry aged out.

    Two rules keep an entry from outliving the state it verified when passes
    for one user overlap (an old and a new token in flight together):

    * :meth:`begin` records a miss. It drops the user's entry, because the
      claim being reconciled supersedes it, and hands the pass a ticket. Only
      the pass holding the user's *latest* ticket may :meth:`remember`.
    * :meth:`invalidate` is called after a pass changed the stored state. It
      drops the entry and revokes the outstanding ticket, so a concurrent
      no-op pass that verified the *previous* state cannot re-cache it after
      the change landed.

    One slot per user is deliberate: a user alternating between two different
    identities (two providers, or two subjects) simply misses on each switch
    and reconciles - never a stale hit, only less caching for that edge case.

    Entries are per-process and expire on their own, so the worst case is that
    an out-of-band directory change (one that arrives with the *same* claim)
    is observed one interval late.
    """

    def __init__(self, *, max_entries: int = _MAX_DIRECTORY_RECONCILE_CACHE_ENTRIES) -> None:
        self._max_entries = max_entries
        # user key -> (verified state, monotonic deadline)
        self._entries: OrderedDict[str, tuple[tuple[object, ...], float]] = OrderedDict()
        # user key -> ticket of the latest pass that began for the user
        self._tickets: OrderedDict[str, int] = OrderedDict()
        self._last_ticket = 0

    def is_fresh(self, user_key: str, state: tuple[object, ...], *, now: float) -> bool:
        entry = self._entries.get(user_key)
        if entry is None:
            return False
        verified_state, deadline = entry
        if deadline <= now:
            del self._entries[user_key]
            return False
        return verified_state == state

    def begin(self, user_key: str) -> int:
        """Record a cache miss and return the ticket the pass must present to remember its result."""
        self._entries.pop(user_key, None)
        self._last_ticket += 1
        self._tickets.pop(user_key, None)
        self._tickets[user_key] = self._last_ticket
        while len(self._tickets) > self._max_entries:
            self._tickets.popitem(last=False)
        return self._last_ticket

    def remember(
        self,
        user_key: str,
        state: tuple[object, ...],
        *,
        ticket: int,
        now: float,
        ttl_seconds: float,
    ) -> None:
        if ttl_seconds <= 0:
            return
        if self._tickets.get(user_key) != ticket:
            # A newer pass began for this user, or a change landed, after this
            # pass verified its state: that verdict is stale and must not
            # become the entry.
            return
        del self._tickets[user_key]
        self._purge_expired(now)
        self._entries.pop(user_key, None)
        self._entries[user_key] = (state, now + ttl_seconds)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def invalidate(self, user_key: str) -> None:
        """Forget the user's entry and revoke any in-flight ticket after their stored state changed."""
        self._entries.pop(user_key, None)
        self._tickets.pop(user_key, None)

    def _purge_expired(self, now: float) -> None:
        expired = [key for key, (_, deadline) in self._entries.items() if deadline <= now]
        for key in expired:
            del self._entries[key]


def _has_external_group_overage(claims: Mapping[str, object], claim_path: tuple[str, ...]) -> bool:
    """Return whether an Entra-style overage pointer replaces the group claim."""
    claim_names = claims.get("_claim_names")
    # ``_claim_names`` identifies top-level JWT claim names. Joining the path
    # would collapse ("a.b",) and ("a", "b") into the same selector.
    claim_name = claim_path[0]
    return isinstance(claim_names, Mapping) and claim_name in claim_names


def _validated_external_group_claim_path(value: object) -> tuple[str, ...] | None:
    """Validate the plugin-selected path before traversing verified claims."""
    if value is None:
        return None
    if not isinstance(value, tuple) or not value or len(value) > _MAX_EXTERNAL_GROUP_CLAIM_PATH_DEPTH:
        msg = "external groups claim path must contain between 1 and 16 segments"
        raise ValueError(msg)
    if any(
        not isinstance(segment, str)
        or not segment.strip()
        or segment != segment.strip()
        or len(segment) > _MAX_EXTERNAL_AUTHORIZATION_GROUP_LENGTH
        for segment in value
    ):
        msg = "external groups claim path segments must be normalized strings of at most 256 characters"
        raise ValueError(msg)
    return value


def _claim_value_at_path(claims: Mapping[str, object], claim_path: tuple[str, ...]) -> tuple[bool, object]:
    """Resolve a claim path without treating dots inside claim names as separators."""
    current: object = claims
    for segment in claim_path:
        if not isinstance(current, Mapping):
            msg = "external groups claim path traverses a non-object value"
            raise TypeError(msg)
        if segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _audit_audience(claims: Mapping[str, object]) -> str | list[str] | None:
    """Normalize a verified audience claim to a JSON-safe audit value."""
    audience = claims.get("aud")
    if isinstance(audience, str):
        return audience
    if isinstance(audience, (list, tuple)) and all(isinstance(value, str) for value in audience):
        return list(audience)
    return None


async def _safe_audit_directory_reconciliation(
    audit: Callable[..., Awaitable[None]],
    *,
    identity: ExternalIdentity,
    user: User,
    issuer: str | None,
    result: str,
    details: dict[str, object],
) -> None:
    """Record reconciliation without letting audit outages fail authentication."""
    try:
        await audit(
            user_id=user.id,
            action="directory_membership:reconcile",
            obj=f"user:{user.id}",
            result=result,
            details={
                "provider_id": identity.provider,
                "issuer": issuer,
                "subject": identity.subject,
                "audience": _audit_audience(identity.claims),
                "source": "external_bearer",
                **details,
            },
        )
    except Exception:  # noqa: BLE001
        await logger.aexception(
            "Authorization directory reconciliation audit failed for provider=%s user=%s result=%s",
            identity.provider,
            user.id,
            result,
        )


if TYPE_CHECKING:
    from cryptography.fernet import Fernet, MultiFernet
    from lfx.services.settings.service import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession


class AuthService(BaseAuthService):
    """Default Langflow authentication service (implements LFX BaseAuthService)."""

    name = ServiceType.AUTH_SERVICE.value

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
        self._directory_reconcile_cache = _DirectoryReconcileCache()
        self.set_ready()

    @property
    def settings(self) -> SettingsService:
        return self.settings_service

    async def authenticate_with_credentials(
        self,
        token: str | None,
        api_key: str | None,
        db: AsyncSession,
        external_token: str | None = None,
    ) -> User | UserRead:
        """Framework-agnostic authentication method.

        This is the core authentication logic that validates credentials and returns a user.


        Args:
            token: Access token (JWT, OIDC token, etc.)
            api_key: API key for authentication
            db: Database session
            external_token: Separately-extracted external credential to try as a
                fallback when native token authentication fails for any reason
                (expired, invalid, inactive user). When ``None`` behavior is
                unchanged. This lets a valid external credential authenticate even
                when a present-but-invalid native token would otherwise shadow it.


        Returns:
            User or UserRead object


        Raises:
            MissingCredentialsError: If no credentials provided
            InvalidCredentialsError: If credentials are invalid
            InvalidTokenError: If token format/signature is invalid
            TokenExpiredError: If token has expired
            InactiveUserError: If user account is inactive
        """
        clear_current_auth_context()
        clear_current_external_access_context()
        try:
            return await self._authenticate_with_credentials_impl(token, api_key, db, external_token=external_token)
        except Exception:
            # Exceptional-exit invariant: a failed credential attempt may have
            # flushed JIT user/profile rows and populated the identity contexts
            # before a later step (for example an authorization-policy
            # rejection) raised. Callers that swallow authentication errors and
            # let the request complete (``get_optional_user``) share this
            # session, and the request-scoped session auto-commits on clean
            # completion — so no staged state may survive the raise.
            await self._discard_failed_credential_state(db)
            raise

    async def _discard_failed_credential_state(self, db: AsyncSession) -> None:
        """Roll back staged session state and clear the identity contexts."""
        try:
            await db.rollback()
        except Exception as exc:  # noqa: BLE001 - the original credential error must surface
            logger.warning(f"Rollback after a failed credential attempt failed: {exc}")
        finally:
            clear_current_auth_context()
            clear_current_external_access_context()

    async def _authenticate_with_credentials_impl(
        self,
        token: str | None,
        api_key: str | None,
        db: AsyncSession,
        external_token: str | None = None,
    ) -> User | UserRead:
        # Try token authentication first (if token provided)
        if token:
            try:
                return await self._authenticate_with_token(token, db)
            except AuthBackendUnavailableError:
                # A backend outage is not a credential verdict, so there is
                # nothing for the remaining credentials to disambiguate. Retrying
                # them would only widen the outage's blast radius, and answering
                # 401 would blame a token that was never rejected.
                raise
            except (AuthInvalidTokenError, TokenExpiredError, InactiveUserError) as e:
                # Native auth failed. If a *distinct* external credential was
                # extracted, try it before surfacing the native error so a present
                # but invalid/expired native token can't shadow a valid external
                # one. When external_token is None or identical to the token we
                # already tried, behavior is unchanged.
                if external_token and external_token != token:
                    # A recognized auth failure can still follow external JIT
                    # materialization (for example, a later authorization-policy
                    # rejection). Start the distinct credential at a clean
                    # transaction and context boundary so its commit cannot
                    # persist state from the rejected attempt.
                    await db.rollback()
                    clear_current_auth_context()
                    clear_current_external_access_context()
                    external_user = await self._authenticate_with_external_token(external_token, db)
                    if external_user is not None:
                        return external_user
                raise e  # noqa: TRY201
            except Exception as e:
                # Token auth failed for an unexpected reason; try the distinct
                # external credential first, then fall back to API key if provided.
                if external_token and external_token != token:
                    # Token authentication can delegate to external JIT
                    # provisioning, which may flush user/profile state before a
                    # later step fails. Give the distinct external credential a
                    # clean transaction and authentication context.
                    await db.rollback()
                    clear_current_auth_context()
                    clear_current_external_access_context()
                    external_user = await self._authenticate_with_external_token(external_token, db)
                    if external_user is not None:
                        return external_user
                if api_key:
                    # API-key authentication commits its usage bookkeeping. Roll
                    # back both prior credential attempts immediately before it so
                    # that commit cannot persist state they left in the session.
                    await db.rollback()
                    clear_current_auth_context()
                    clear_current_external_access_context()
                    try:
                        user = await self._authenticate_with_api_key(api_key)
                        if user:
                            return user
                        msg = "Invalid API key"
                        raise InvalidCredentialsError(msg)
                    except InvalidCredentialsError:
                        raise
                    except Exception as api_key_err:
                        logger.error(f"Unexpected error during API key authentication: {api_key_err}")
                        msg = "API key authentication failed"
                        raise InvalidCredentialsError(msg) from api_key_err
                logger.error(f"Unexpected error during token authentication: {e}")
                msg = "Token authentication failed"
                raise AuthInvalidTokenError(msg) from e

        # No native token, but a separately-extracted external credential may be
        # present (extractors no longer collapse native/external into one string).
        if external_token:
            external_user = await self._authenticate_with_external_token(external_token, db)
            if external_user is not None:
                return external_user

        # Try API key authentication
        if api_key:
            if external_token:
                # The owned API-key transaction must not coexist with state or
                # a checked-out connection left by the failed external attempt.
                await db.rollback()
                clear_current_auth_context()
                clear_current_external_access_context()
            try:
                user = await self._authenticate_with_api_key(api_key)
                if user:
                    return user
                msg = "Invalid API key"
                raise InvalidCredentialsError(msg)
            except InvalidCredentialsError:
                raise
            except Exception as e:
                logger.error(f"Unexpected error during API key authentication: {e}")
                msg = "API key authentication failed"
                raise InvalidCredentialsError(msg) from e

        # AUTO_LOGIN parity with _api_key_security_impl: when AUTO_LOGIN is
        # enabled and the operator has explicitly opted in via
        # skip_auth_auto_login, fall back to the superuser instead of
        # rejecting the request. Without this, ``get_current_user``-protected
        # endpoints reject unauthenticated requests even though API-key
        # endpoints accept them, breaking ADK/dev integrations that rely on
        # AUTO_LOGIN.
        auth_settings = self.settings.auth_settings
        if auth_settings.AUTO_LOGIN and auth_settings.skip_auth_auto_login:
            if not auth_settings.SUPERUSER:
                msg = "Missing first superuser credentials"
                raise InvalidCredentialsError(msg)
            superuser = await get_user_by_username(db, auth_settings.SUPERUSER)
            if superuser is None:
                msg = "Superuser not found"
                raise InvalidCredentialsError(msg)
            # Mirror the active-user enforcement that token and API-key
            # auth paths apply. ``CurrentActiveUser`` re-checks this for HTTP
            # routes, but ``get_current_user_for_sse``/websocket dependencies
            # call ``authenticate_with_credentials`` directly, so we must
            # reject inactive superusers here too.
            if not superuser.is_active:
                msg = "User account is inactive"
                raise InactiveUserError(msg)
            logger.warning(AUTO_LOGIN_WARNING)
            set_current_auth_context(AuthCredentialContext(method=AUTH_METHOD_AUTO_LOGIN))
            return superuser

        # No credentials provided
        msg = "No authentication credentials provided"
        raise MissingCredentialsError(msg)

    async def _authenticate_with_token(self, token: str, db: AsyncSession) -> User:
        """Internal method to authenticate with token (raises generic exceptions)."""
        from langflow.services.auth.utils import ACCESS_TOKEN_TYPE, get_jwt_verification_key

        settings_service = self.settings
        algorithm = settings_service.auth_settings.ALGORITHM
        verification_key = get_jwt_verification_key(settings_service)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                payload = jwt.decode(token, verification_key, algorithms=[algorithm])
            user_id: UUID = payload.get("sub")  # type: ignore[assignment]
            token_type: str = payload.get("type")  # type: ignore[assignment]

            # Validate token type
            if token_type != ACCESS_TOKEN_TYPE:
                logger.error(f"Token type is invalid: {token_type}. Expected: {ACCESS_TOKEN_TYPE}.")
                msg = "Invalid token type"
                raise AuthInvalidTokenError(msg)

            # Check expiration
            if expires := payload.get("exp", None):
                expires_datetime = datetime.fromtimestamp(expires, timezone.utc)
                if datetime.now(timezone.utc) > expires_datetime:
                    logger.info("Token expired for user")
                    msg = "Token has expired"
                    raise TokenExpiredError(msg)

            # Validate payload
            if user_id is None or token_type is None:
                logger.info(f"Invalid token payload. Token type: {token_type}")
                msg = "Invalid token payload"
                raise AuthInvalidTokenError(msg)

        except (TokenExpiredError, AuthInvalidTokenError):
            raise
        except jwt.ExpiredSignatureError as e:
            logger.info("Token signature has expired")
            msg = "Token has expired"
            raise TokenExpiredError(msg) from e
        except InvalidTokenError as e:
            external_user = await self._authenticate_with_external_token(token, db)
            if external_user is not None:
                return external_user
            logger.debug("JWT validation failed: Invalid token format or signature")
            msg = "Invalid token"
            raise AuthInvalidTokenError(msg) from e
        except Exception as e:
            external_user = await self._authenticate_with_external_token(token, db)
            if external_user is not None:
                return external_user
            logger.error(f"Unexpected error decoding token: {e}")
            msg = "Token validation failed"
            raise AuthInvalidTokenError(msg) from e

        # Get user from database
        user = await get_user_by_id(db, user_id)
        if user is None:
            logger.info("User not found")
            msg = "User not found"
            raise InvalidCredentialsError(msg)

        if not user.is_active:
            logger.info("User is inactive")
            msg = "User account is inactive"
            raise InactiveUserError(msg)

        set_current_auth_context(AuthCredentialContext(method=AUTH_METHOD_JWT))
        return user

    async def _authenticate_with_external_token(self, token: str, db: AsyncSession) -> User | None:
        """Fallback path: try the configured external identity resolver.

        Returns the JIT-provisioned local user when the token resolves to a
        valid external identity, ``None`` otherwise. Callers raise the native
        JWT error if this returns ``None``.
        """
        if not self.settings.auth_settings.EXTERNAL_AUTH_ENABLED:
            return None
        try:
            identity = await resolve_external_identity(token, self.settings.auth_settings)
        except AuthInvalidTokenError as exc:
            logger.debug(f"External credential rejected: {exc}")
            return None
        set_current_auth_context(
            AuthCredentialContext(method=AUTH_METHOD_EXTERNAL, external_provider=identity.provider)
        )
        set_current_external_access_context(access_context_from_identity(identity, self.settings.auth_settings))
        # The credential has already verified here. Materialization and group
        # reconciliation own everything staged on this session, so a conflict
        # that rolled the transaction back can be replayed from scratch: a
        # deadlock victim, a serialization failure, or two concurrent logins
        # racing to create the same row. What must never happen is reporting
        # any of those as a failed authentication — nothing was rejected.
        for attempt in range(1, _MAX_EXTERNAL_AUTH_ATTEMPTS + 1):
            try:
                user = await self._materialize_external_user(identity, db)
                await self._reconcile_verified_external_groups(identity=identity, user=user, db=db)
            except AuthenticationError:
                raise
            except Exception as exc:
                retryable = _is_retryable_backend_failure(exc)
                if not retryable and not isinstance(exc, IntegrityError):
                    raise
                await db.rollback()
                if attempt >= _MAX_EXTERNAL_AUTH_ATTEMPTS:
                    logger.warning(
                        "External identity resolved but its backend work kept failing for provider=%s: %s: %s",
                        identity.provider,
                        type(exc).__name__,
                        exc,
                    )
                    if not retryable:
                        raise
                    raise AuthBackendUnavailableError from exc
                # Jitter so two requests that conflicted do not line up again.
                await asyncio.sleep(_EXTERNAL_AUTH_RETRY_BACKOFF_SECONDS * attempt * (1 + secrets.randbelow(100) / 100))
            else:
                return user
        msg = "unreachable: the final attempt either returns or raises"
        raise AssertionError(msg)

    async def _reconcile_verified_external_groups(
        self,
        *,
        identity: ExternalIdentity,
        user: User,
        db: AsyncSession,
    ) -> None:
        """Send one sanitized verified group-claim state through the authorization seam."""
        from lfx.services.authorization import (
            AuthorizationMutationRejected,
            DirectoryMembershipClaimState,
            DirectoryMembershipSnapshot,
        )

        from langflow.services.authorization.audit import AUDIT_ALLOW, AUDIT_SKIP, audit_decision
        from langflow.services.authorization.lifecycle import safe_directory_membership_committed
        from langflow.services.deps import get_authorization_service

        authorization_service = get_authorization_service()
        issuer_value = identity.claims.get("iss")
        issuer = issuer_value.strip() if isinstance(issuer_value, str) and issuer_value.strip() else None
        path_selector = getattr(authorization_service, "external_groups_claim_path", None)
        if path_selector is None:
            claim_name = await authorization_service.external_groups_claim(
                provider_id=identity.provider,
                issuer=issuer,
            )
            selected_path: object = (claim_name,) if claim_name else None
        else:
            selected_path = await path_selector(provider_id=identity.provider, issuer=issuer)
        claim_path = _validated_external_group_claim_path(selected_path)
        if claim_path is None:
            return
        claim_name = ".".join(claim_path)

        async def audit_reconciliation(*, result: str, details: dict[str, object]) -> None:
            await _safe_audit_directory_reconciliation(
                audit_decision,
                identity=identity,
                user=user,
                issuer=issuer,
                result=result,
                details=details,
            )

        claim_state: DirectoryMembershipClaimState | None = None
        complete = True
        normalized_groups: set[str] = set()
        candidates: Iterable[object] = ()
        if _has_external_group_overage(identity.claims, claim_path):
            claim_state = DirectoryMembershipClaimState.OVERAGE
            complete = False
        else:
            try:
                found, raw_groups = _claim_value_at_path(identity.claims, claim_path)
            except TypeError:
                found = False
                raw_groups = None
                claim_state = DirectoryMembershipClaimState.MALFORMED
                complete = False
            if complete and not found:
                claim_state = DirectoryMembershipClaimState.ABSENT
                complete = False
            elif complete and isinstance(raw_groups, str):
                candidates = (raw_groups,)
            elif complete and isinstance(raw_groups, (list, tuple, set, frozenset)):
                candidates = raw_groups
            elif complete:
                candidates = ()
                claim_state = DirectoryMembershipClaimState.MALFORMED
                complete = False

            if complete:
                for candidate in candidates:
                    if not isinstance(candidate, str):
                        claim_state = DirectoryMembershipClaimState.MALFORMED
                        complete = False
                        break
                    group = candidate.strip()
                    if not group or len(group) > _MAX_EXTERNAL_AUTHORIZATION_GROUP_LENGTH:
                        claim_state = DirectoryMembershipClaimState.MALFORMED
                        complete = False
                        break
                    normalized_groups.add(group)

        groups = tuple(sorted(normalized_groups)) if complete else ()
        if complete and len(groups) > _MAX_EXTERNAL_AUTHORIZATION_GROUPS:
            groups = ()
            claim_state = DirectoryMembershipClaimState.TOO_MANY
            complete = False
        elif complete and not groups:
            claim_state = DirectoryMembershipClaimState.EMPTY

        # LE-2109: bearer tokens arrive on every request. Reconciliation writes
        # rows, takes the plugin's policy locks and appends an audit entry, so
        # a directory state that was verified unchanged a moment ago is skipped
        # until the configured interval elapses. The cache remembers only the
        # *last* reconciled state per user, so a claim whose group set, claim
        # state or identity differs from that state reconciles immediately -
        # even a group set that was itself cached earlier and has since been
        # moved past (a promotion followed by a revocation).
        reconcile_interval = float(self.settings.auth_settings.EXTERNAL_AUTH_GROUP_RECONCILE_INTERVAL_SECONDS)
        cache_user = str(user.id)
        cache_state = (
            identity.provider,
            identity.subject,
            claim_name,
            claim_state.value if claim_state is not None else None,
            complete,
            groups,
        )
        now = time.monotonic()
        if reconcile_interval > 0 and self._directory_reconcile_cache.is_fresh(cache_user, cache_state, now=now):
            # Skipping reconciliation must not skip the JIT/profile bookkeeping
            # that materializing the user staged on this session.
            await db.commit()
            return
        # This claim is about to be reconciled, so whatever the cache holds
        # for the user describes a state that is being superseded: begin()
        # drops it and hands this pass the ticket it must present to be
        # remembered, so an overlapping pass for the same user can never
        # re-cache a state a later pass moved past.
        cache_ticket = self._directory_reconcile_cache.begin(cache_user)

        if not complete:
            assert claim_state is not None  # noqa: S101 - internal state-machine invariant
            logger.warning(
                "External group claim is incomplete for provider=%s user=%s: claim=%s state=%s",
                identity.provider,
                user.id,
                claim_name,
                claim_state.value,
            )

            supports_incomplete = getattr(
                authorization_service,
                "supports_incomplete_directory_membership_snapshots",
                None,
            )
            if supports_incomplete is None or not await supports_incomplete():
                # Preserve the original complete-only plugin contract. Commit
                # JIT/profile bookkeeping before the independent audit writer
                # resolves the user's foreign key, but never present a legacy
                # plugin with an ambiguous empty tuple.
                await db.commit()
                await audit_reconciliation(
                    result=AUDIT_SKIP,
                    details={
                        "claim_name": claim_name,
                        "reason": claim_state.value,
                        "authoritative": False,
                        "complete": False,
                    },
                )
                self._directory_reconcile_cache.remember(
                    cache_user,
                    cache_state,
                    ticket=cache_ticket,
                    now=now,
                    ttl_seconds=reconcile_interval,
                )
                return

        try:
            result = await authorization_service.ingest_directory_membership_snapshot(
                session=db,
                snapshot=DirectoryMembershipSnapshot(
                    provider_id=identity.provider,
                    source="external_bearer",
                    observed_at=datetime.now(timezone.utc),
                    user_id=user.id,
                    provider_user_id=identity.subject,
                    memberships=groups,
                    authoritative=complete,
                    complete=complete,
                    claim_state=claim_state,
                    claim_path=claim_path,
                ),
            )
        except AuthorizationMutationRejected as exc:
            raise AuthInvalidTokenError(exc.public_detail) from exc
        await db.commit()
        if result is None:
            # Compatibility with a plugin built against the initial untyped
            # seam: an unknown result must invalidate, never preserve stale
            # policy by assuming nothing changed.
            logger.warning(
                "Authorization plugin returned no directory ingest result for provider=%s user=%s; "
                "invalidating conservatively",
                identity.provider,
                user.id,
            )
            changed = True
            added = None
            removed = None
        else:
            # The initial seam only documented ``changed`` through caller-side
            # duck typing. Keep older plugin result objects safe after commit
            # while the explicit result contract rolls out.
            changed = bool(getattr(result, "changed", True))
            added = getattr(result, "added", None)
            removed = getattr(result, "removed", None)
        if changed:
            # The stored state just moved. Whatever the cache holds for the
            # user, and any pass still in flight that verified the previous
            # state, must not be served or remembered after this commit.
            self._directory_reconcile_cache.invalidate(cache_user)

        if not complete:
            assert claim_state is not None  # noqa: S101 - internal state-machine invariant
            await audit_reconciliation(
                result=AUDIT_SKIP,
                details={
                    "claim_name": claim_name,
                    "reason": claim_state.value,
                    "authoritative": False,
                    "complete": False,
                },
            )
            if changed:
                await safe_directory_membership_committed(
                    authorization_service,
                    user_id=user.id,
                    changed=True,
                )
            else:
                self._directory_reconcile_cache.remember(
                    cache_user,
                    cache_state,
                    ticket=cache_ticket,
                    now=now,
                    ttl_seconds=reconcile_interval,
                )
            return

        await audit_reconciliation(
            result=AUDIT_ALLOW,
            details={
                "membership_count": len(groups),
                "membership_sha256": hashlib.sha256("\0".join(groups).encode()).hexdigest(),
                "changed": changed,
                "added": added,
                "removed": removed,
                "authoritative": True,
                "complete": True,
            },
        )
        await safe_directory_membership_committed(
            authorization_service,
            user_id=user.id,
            changed=changed,
        )
        if not changed:
            # Only a reconciliation that verified the stored state already
            # matched the claim is safe to skip next time. A pass that changed
            # something gets one confirming pass before the interval starts, so
            # a post-commit propagation retry is never hidden by the cache.
            self._directory_reconcile_cache.remember(
                cache_user,
                cache_state,
                ticket=cache_ticket,
                now=now,
                ttl_seconds=reconcile_interval,
            )

    async def _authenticate_with_api_key(self, api_key: str) -> UserRead | None:
        """Internal method to authenticate with API key (raises generic exceptions).

        The EXTERNAL_AUTH access ceiling block for externally-managed users is
        enforced inside ``authenticate_api_key`` (the shared chokepoint), which
        returns ``None`` for a blocked user so every caller treats it as an auth
        failure. No additional ceiling check is needed here.
        """
        result = await authenticate_api_key(api_key)
        if not result:
            return None

        if isinstance(result.user, User):
            user_read = UserRead.model_validate(result.user, from_attributes=True)
            if not user_read.is_active:
                msg = "User account is inactive"
                raise InactiveUserError(msg)
            set_current_auth_context(AuthCredentialContext.from_api_key_result(result))
            return user_read

        return None

    # ------------------------------------------------------------------
    # JIT user provisioning via BaseAuthService hook
    # ------------------------------------------------------------------

    def extract_user_info_from_claims(self, claims: dict) -> dict:
        """Normalize provider claims using the configured EXTERNAL_AUTH_* mapping.

        Returns a dict with ``provider``, ``subject``, ``username``, ``email``,
        and ``name`` keys; raises :class:`AuthInvalidTokenError` when the
        subject claim is missing.
        """
        identity = identity_from_claims(claims, self.settings.auth_settings)
        return {
            "provider": identity.provider,
            "subject": identity.subject,
            "username": identity.username,
            "email": identity.email,
            "name": identity.name,
        }

    async def get_or_create_user_from_claims(self, claims: dict, db: AsyncSession) -> User:
        """Return the local Langflow user mapped to these external claims.

        Looks up SSOUserProfile by (provider, sso_user_id). On hit, refreshes
        the email + last-login timestamps and returns the existing user. On
        miss, JIT-provisions a fresh user, writes a profile row, and seeds
        the default folder + variables.
        """
        identity = identity_from_claims(claims, self.settings.auth_settings)
        return await self._materialize_external_user(identity, db)

    async def _materialize_external_user(self, identity: ExternalIdentity, db: AsyncSession) -> User:
        """Find-or-create the local user backing an external identity."""
        import secrets
        from datetime import datetime, timezone

        from sqlalchemy.exc import IntegrityError
        from sqlmodel import select

        from langflow.services.database.models.auth import SSOUserProfile

        profile_stmt = select(SSOUserProfile).where(
            SSOUserProfile.sso_provider == identity.provider,
            SSOUserProfile.sso_user_id == identity.subject,
        )
        profile = (await db.exec(profile_stmt)).first()

        if profile is not None:
            user = await get_user_by_id(db, profile.user_id)
            if user is None:
                msg = "Mapped external user was not found"
                raise AuthInvalidTokenError(msg)
            if not user.is_active:
                msg = "User account is inactive"
                raise InactiveUserError(msg)
            now = datetime.now(timezone.utc)
            # Only overwrite the stored email when the token carries one; a later
            # token that omits the email claim must not erase a previously stored
            # address.
            if identity.email is not None:
                profile.email = identity.email
            profile.sso_last_login_at = now
            profile.updated_at = now
            await update_user_last_login_at(user.id, db)
            return user

        username = await self._unique_external_username(db, identity)
        random_password = secrets.token_urlsafe(48)
        now = datetime.now(timezone.utc)
        user = User(
            username=username,
            password=self.get_password_hash(random_password),
            is_active=True,
            is_superuser=False,
            last_login_at=now,
        )
        db.add(user)
        try:
            # Flush `user` on its own before constructing `new_profile`.
            # SSOUserProfile.user_id is a bare FK column - no SQLModel
            # Relationship() ties User and SSOUserProfile together - so
            # SQLAlchemy's unit-of-work can't infer that the user row must be
            # inserted before sso_user_profile in a single flush. Without a
            # declared relationship, the two INSERTs aren't guaranteed to be
            # ordered, and on Postgres that can raise ForeignKeyViolation on
            # sso_user_profile_user_id_fkey. A separate flush here removes the
            # ordering dependency entirely instead of relying on it.
            await db.flush()
            new_profile = SSOUserProfile(
                user_id=user.id,
                sso_provider=identity.provider,
                sso_user_id=identity.subject,
                email=identity.email,
                sso_last_login_at=now,
            )
            db.add(new_profile)
            await db.flush()
            await db.refresh(user)
            await self._initialize_jit_user_defaults(user, db)
        except IntegrityError:
            await db.rollback()
            profile = (await db.exec(profile_stmt)).first()
            if profile is None:
                raise
            user = await get_user_by_id(db, profile.user_id)
            if user is None:
                msg = "Mapped external user was not found"
                raise AuthInvalidTokenError(msg) from None
            if not user.is_active:
                msg = "User account is inactive"
                raise InactiveUserError(msg) from None

        return user

    @staticmethod
    async def _unique_external_username(db: AsyncSession, identity: ExternalIdentity) -> str:
        desired = identity.username
        if await get_user_by_username(db, desired) is None:
            return desired
        fallback = _external_username_fallback(identity.provider, identity.subject)
        if await get_user_by_username(db, fallback) is None:
            return fallback
        # Final tier: fold the desired name into the digest so two providers'
        # subjects that collide on the helper's digest still resolve uniquely.
        import hashlib

        long_digest = hashlib.sha256(f"{identity.provider}:{identity.subject}:{desired}".encode()).hexdigest()[:16]
        normalized_provider = identity.provider[:200] or "external"
        return f"{normalized_provider}-{long_digest}"

    @staticmethod
    async def _initialize_jit_user_defaults(user: User, db: AsyncSession) -> None:
        from langflow.initial_setup.setup import get_or_create_default_folder
        from langflow.services.deps import get_variable_service

        await get_or_create_default_folder(db, user.id)
        await get_variable_service().initialize_user_variables(user.id, db)

    async def api_key_security(
        self, query_param: str | None, header_param: str | None, db: AsyncSession | None = None
    ) -> UserRead | None:
        return await self._api_key_security_impl(query_param, header_param, db, self.settings)

    async def _api_key_security_impl(
        self,
        query_param: str | None,
        header_param: str | None,
        db: AsyncSession | None,
        settings_service,
    ) -> UserRead | None:
        clear_current_auth_context()
        clear_current_external_access_context()

        if settings_service.auth_settings.AUTO_LOGIN:
            if not settings_service.auth_settings.SUPERUSER:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing first superuser credentials",
                )
            if not query_param and not header_param:
                if settings_service.auth_settings.skip_auth_auto_login:
                    if db is not None:
                        result = await get_user_by_username(db, settings_service.auth_settings.SUPERUSER)
                    else:
                        async with session_scope() as auto_login_db:
                            result = await get_user_by_username(auto_login_db, settings_service.auth_settings.SUPERUSER)
                    if result is None:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Superuser not found in database",
                        )
                    if not result.is_active:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="User account is inactive",
                        )
                    logger.warning(AUTO_LOGIN_WARNING)
                    set_current_auth_context(AuthCredentialContext(method=AUTH_METHOD_AUTO_LOGIN))
                    return UserRead.model_validate(result, from_attributes=True)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=AUTO_LOGIN_ERROR,
                )
            # At this point, at least one of query_param or header_param is truthy
            api_key = query_param or header_param
            if api_key is None:  # pragma: no cover - guaranteed by the if-condition above
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing API key")
            api_key_result = await authenticate_api_key(api_key)

        elif not query_param and not header_param:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An API key must be passed as query or header",
            )

        else:
            # At least one of query_param or header_param is truthy
            api_key = query_param or header_param
            if api_key is None:  # pragma: no cover - guaranteed by the elif-condition above
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing API key")
            api_key_result = await authenticate_api_key(api_key)

        if not api_key_result:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing API key",
            )

        if isinstance(api_key_result.user, User):
            set_current_auth_context(AuthCredentialContext.from_api_key_result(api_key_result))
            return UserRead.model_validate(api_key_result.user, from_attributes=True)

        msg = "Invalid result type"
        raise ValueError(msg)

    async def ws_api_key_security(self, api_key: str | None) -> UserRead:
        settings = self.settings
        clear_current_auth_context()
        clear_current_external_access_context()
        api_key_result = None
        if settings.auth_settings.AUTO_LOGIN:
            if not settings.auth_settings.SUPERUSER:
                raise WebSocketException(
                    code=status.WS_1011_INTERNAL_ERROR,
                    reason="Missing first superuser credentials",
                )
            if not api_key:
                if settings.auth_settings.skip_auth_auto_login:
                    async with session_scope() as db:
                        result = await get_user_by_username(db, settings.auth_settings.SUPERUSER)
                    if result is None:
                        raise WebSocketException(
                            code=status.WS_1011_INTERNAL_ERROR,
                            reason="Superuser not found",
                        )
                    if not result.is_active:
                        raise WebSocketException(
                            code=status.WS_1008_POLICY_VIOLATION,
                            reason="User account is inactive",
                        )
                    logger.warning(AUTO_LOGIN_WARNING)
                    set_current_auth_context(AuthCredentialContext(method=AUTH_METHOD_AUTO_LOGIN))
                else:
                    raise WebSocketException(
                        code=status.WS_1008_POLICY_VIOLATION,
                        reason=AUTO_LOGIN_ERROR,
                    )
            else:
                api_key_result = await authenticate_api_key(api_key)
                result = api_key_result.user if api_key_result is not None else None

        else:
            if not api_key:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="An API key must be passed as query or header",
                )
            api_key_result = await authenticate_api_key(api_key)
            result = api_key_result.user if api_key_result is not None else None

        if not result:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid or missing API key",
            )

        if isinstance(result, User):
            if api_key_result is not None:
                set_current_auth_context(AuthCredentialContext.from_api_key_result(api_key_result))
            return UserRead.model_validate(result, from_attributes=True)

        raise WebSocketException(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Authentication subsystem error",
        )

    async def get_current_user(
        self,
        token: str | Coroutine | None,
        query_param: str | None,
        header_param: str | None,
        db: AsyncSession,
        external_token: str | None = None,
    ) -> User | UserRead:
        # Handle coroutine token (FastAPI dependency injection)
        resolved_token: str | None = None
        if isinstance(token, Coroutine):
            resolved_token = await token
        elif isinstance(token, str):
            resolved_token = token

        # Combine API key params
        api_key = query_param or header_param

        # Delegate to framework-agnostic method
        return await self.authenticate_with_credentials(resolved_token, api_key, db, external_token=external_token)

    async def get_current_user_from_access_token(
        self,
        token: str | Coroutine | None,
        db: AsyncSession,
        external_token: str | None = None,
    ) -> User:
        """Get user from access token (raises generic exceptions).

        This method now uses the framework-agnostic _authenticate_with_token() internally.

        ``external_token`` is an optional, separately-extracted external credential
        tried as a fallback when native token authentication fails so a
        present-but-invalid native token cannot shadow a valid external one. When
        ``None`` (or identical to ``token``) behavior is unchanged.
        """
        clear_current_auth_context()
        clear_current_external_access_context()
        try:
            return await self._get_current_user_from_access_token_impl(token, db, external_token=external_token)
        except Exception:
            # Same exceptional-exit invariant as authenticate_with_credentials:
            # no staged session state or populated identity context may survive
            # the raise (see _discard_failed_credential_state).
            await self._discard_failed_credential_state(db)
            raise

    async def _get_current_user_from_access_token_impl(
        self,
        token: str | Coroutine | None,
        db: AsyncSession,
        external_token: str | None = None,
    ) -> User:
        # Handle coroutine token (FastAPI dependency injection)
        resolved_token: str | None
        if token is None:
            resolved_token = None
        elif isinstance(token, Coroutine):
            resolved_token = await token
        elif isinstance(token, str):
            resolved_token = token
        else:
            msg = "Invalid token format"
            raise AuthInvalidTokenError(msg)

        # No native token: try a separately-extracted external credential before
        # rejecting so a valid external credential authenticates on its own. When
        # external_token is None (the default), behavior is unchanged: a missing
        # native token raises MissingCredentialsError.
        if not resolved_token:
            if external_token:
                external_user = await self._authenticate_with_external_token(external_token, db)
                if external_user is not None:
                    return external_user
            msg = "Missing authentication token"
            raise MissingCredentialsError(msg)

        # Use internal authentication method. Try the native token first; on
        # failure fall back to a *distinct* external credential before surfacing
        # the native error so a stale/invalid native token can't shadow a valid
        # external one. When external_token is None or identical, behavior is
        # unchanged.
        try:
            return await self._authenticate_with_token(resolved_token, db)
        except (AuthInvalidTokenError, TokenExpiredError, InactiveUserError, InvalidCredentialsError) as e:
            if external_token and external_token != resolved_token:
                # Match the framework-agnostic credential path: the failed
                # attempt may have staged JIT/profile state before a policy
                # rejection, so the distinct credential needs a clean boundary.
                await db.rollback()
                clear_current_auth_context()
                clear_current_external_access_context()
                external_user = await self._authenticate_with_external_token(external_token, db)
                if external_user is not None:
                    return external_user
            raise e  # noqa: TRY201

    async def get_current_user_for_websocket(
        self,
        token: str | None,
        api_key: str | None,
        db: AsyncSession,
        external_token: str | None = None,
    ) -> User | UserRead:
        """Delegates to authenticate_with_credentials()."""
        return await self.authenticate_with_credentials(token, api_key, db, external_token=external_token)

    async def get_current_user_for_sse(
        self,
        token: str | None,
        api_key: str | None,
        db: AsyncSession,
        external_token: str | None = None,
    ) -> User | UserRead:
        """Delegates to authenticate_with_credentials()."""
        return await self.authenticate_with_credentials(token, api_key, db, external_token=external_token)

    async def get_current_active_user(self, current_user: User | UserRead) -> User | UserRead | None:
        if not current_user.is_active:
            return None
        set_current_model_provider_policy_context(
            user_id=current_user.id,
            attributes={"is_superuser": bool(current_user.is_superuser)},
        )
        return current_user

    async def get_current_active_superuser(self, current_user: User | UserRead) -> User | UserRead | None:
        if not current_user.is_active or not current_user.is_superuser:
            return None
        set_current_model_provider_policy_context(user_id=current_user.id, attributes={"is_superuser": True})
        return current_user

    async def get_webhook_user(self, flow_id: str, request: Request) -> UserRead:
        settings_service = self.settings
        clear_current_auth_context()
        clear_current_external_access_context()

        if not settings_service.auth_settings.WEBHOOK_AUTH_ENABLE:
            try:
                flow_owner = await get_user_by_flow_id_or_endpoint_name(flow_id)
                if flow_owner is None:
                    raise HTTPException(status_code=404, detail="Flow not found")
                return flow_owner  # noqa: TRY300
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=404, detail="Flow not found") from exc

        api_key_header_val = request.headers.get("x-api-key")
        api_key_query_val = request.query_params.get("x-api-key")

        if not api_key_header_val and not api_key_query_val:
            raise HTTPException(status_code=403, detail="API key required when webhook authentication is enabled")

        api_key = api_key_header_val or api_key_query_val

        try:
            result = await authenticate_api_key(api_key)
            if not result:
                logger.warning("Invalid API key provided for webhook")
                raise HTTPException(status_code=403, detail="Invalid API key")

            set_current_auth_context(AuthCredentialContext.from_api_key_result(result))
            authenticated_user = UserRead.model_validate(result.user, from_attributes=True)
            logger.info("Webhook API key validated successfully")
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Webhook API key validation error: {exc}")
            raise HTTPException(status_code=403, detail="API key authentication failed") from exc

        # The helper already enforces ownership and raises 404 if not found or not owned
        await get_user_by_flow_id_or_endpoint_name(flow_id, user_id=authenticated_user.id)

        return authenticated_user

    def verify_password(self, plain_password, hashed_password):
        return self.settings.auth_settings.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password):
        return self.settings.auth_settings.pwd_context.hash(password)

    def create_token(self, data: dict, expires_delta: timedelta):
        from langflow.services.auth.utils import get_jwt_signing_key

        settings_service = self.settings
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode["exp"] = expire

        signing_key = get_jwt_signing_key(settings_service)

        return jwt.encode(
            to_encode,
            signing_key,
            algorithm=settings_service.auth_settings.ALGORITHM,
        )

    async def create_super_user(
        self,
        username: str,
        password: str,
        db: AsyncSession,
    ) -> User:
        super_user = await get_user_by_username(db, username)

        if not super_user:
            super_user = User(
                username=username,
                password=self.get_password_hash(password),
                is_superuser=True,
                is_active=True,
                last_login_at=None,
            )

            db.add(super_user)
            try:
                await db.commit()
                await db.refresh(super_user)
            except IntegrityError:
                await db.rollback()
                super_user = await get_user_by_username(db, username)
                if not super_user:
                    raise
            except Exception:  # noqa: BLE001
                logger.debug("Error creating superuser.", exc_info=True)

        return super_user

    async def create_user_longterm_token(self, db: AsyncSession) -> tuple[UUID, dict]:
        settings_service = self.settings
        if not settings_service.auth_settings.AUTO_LOGIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Auto login required to create a long-term token"
            )

        username = settings_service.auth_settings.SUPERUSER
        super_user = await get_user_by_username(db, username)
        if not super_user:
            from langflow.services.database.models.user.crud import get_all_superusers

            superusers = await get_all_superusers(db)
            super_user = superusers[0] if superusers else None

        if not super_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Super user hasn't been created")

        # Security (GHSA-fjgc-vj2f-77hm): AUTO_LOGIN defaults on, so an
        # unauthenticated GET /api/v1/auto_login reaches this code. It previously
        # minted a 365-day superuser access token (with no refresh token) — i.e.
        # a year-long superuser bearer token handed out without credentials.
        # Issue normally-scoped tokens instead: a short-lived access token plus a
        # refresh token (see create_user_tokens). The auto-login session stays
        # seamless via refresh, but a leaked token is now bounded by
        # ACCESS_TOKEN_EXPIRE_SECONDS instead of a year.
        logger.warning(AUTO_LOGIN_SESSION_WARNING)
        tokens = await self.create_user_tokens(user_id=super_user.id, db=db, update_last_login=True)
        return super_user.id, tokens

    def create_user_api_key(self, user_id: UUID) -> dict:
        access_token = self.create_token(
            data={"sub": str(user_id), "type": "api_key"},
            expires_delta=timedelta(days=365 * 2),
        )

        return {"api_key": access_token}

    def get_user_id_from_token(self, token: str) -> UUID:
        """Extract user ID from a JWT token without verifying the signature.

        This is a utility function for non-security contexts (e.g., logging, debugging).
        It does NOT verify the token signature and should NOT be used for authentication.

        For actual authentication, use get_current_user_from_access_token() which properly verifies
        the token signature.

        Args:
            token: JWT token string (may be invalid or expired)

        Returns:
            UUID: User ID extracted from token, or UUID(int=0) if extraction fails

        Note:
            This function uses verify_signature=False to match the behavior of
            python-jose's jwt.get_unverified_claims(). The signature is intentionally
            not verified as this is a utility function, not an authentication function.
        """
        try:
            claims = jwt.decode(token, options={"verify_signature": False})
            user_id = claims["sub"]
            return UUID(user_id)
        except (KeyError, InvalidTokenError, ValueError):
            return UUID(int=0)

    async def create_user_tokens(self, user_id: UUID, db: AsyncSession, *, update_last_login: bool = False) -> dict:
        settings_service = self.settings

        access_token_expires = timedelta(seconds=settings_service.auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS)
        access_token = self.create_token(
            data={"sub": str(user_id), "type": "access"},
            expires_delta=access_token_expires,
        )

        refresh_token_expires = timedelta(seconds=settings_service.auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS)
        refresh_token = self.create_token(
            data={"sub": str(user_id), "type": "refresh"},
            expires_delta=refresh_token_expires,
        )

        if update_last_login:
            await update_user_last_login_at(user_id, db)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def create_refresh_token(self, refresh_token: str, db: AsyncSession):
        from langflow.services.auth.utils import get_jwt_verification_key

        settings_service = self.settings

        algorithm = settings_service.auth_settings.ALGORITHM
        verification_key = get_jwt_verification_key(settings_service)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                payload = jwt.decode(
                    refresh_token,
                    verification_key,
                    algorithms=[algorithm],
                )
            user_id: UUID = payload.get("sub")  # type: ignore[assignment]
            token_type: str = payload.get("type")  # type: ignore[assignment]

            if user_id is None or token_type != "refresh":  # noqa: S105
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

            user_exists = await get_user_by_id(db, user_id)

            if user_exists is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

            if not user_exists.is_active:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive")

            return await self.create_user_tokens(user_id, db)

        except InvalidTokenError as e:
            logger.exception("JWT decoding error")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            ) from e

    async def authenticate_user(
        self, username: str, password: str, db: AsyncSession, request: Request | None = None
    ) -> User | None:
        user = await get_user_by_username(db, username)

        if not user:
            if request and request.client:
                # Hash username for correlation without exposing PII
                username_hash = hashlib.sha256(username.lower().encode()).hexdigest()[:16]
                logger.warning(
                    "Login failed: user not found",
                    auth_event="login_failed",
                    reason="user_not_found",
                    username_hash=username_hash,
                    client_ip=request.client.host,
                )
            return None

        if not user.is_active:
            if request and request.client:
                logger.warning(
                    "Login failed: inactive user",
                    auth_event="login_failed",
                    reason="user_inactive",
                    auth_id=str(user.id),
                    client_ip=request.client.host,
                )
            if not user.last_login_at:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Waiting for approval")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")

        auth_settings = self.settings.auth_settings
        auto_login_superuser = auth_settings.SUPERUSER or DEFAULT_SUPERUSER
        legacy_superuser_usernames = {DEFAULT_SUPERUSER, auto_login_superuser}
        if username in legacy_superuser_usernames and password == LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value():
            if request and request.client:
                logger.warning(
                    "Login failed: legacy default superuser password is disabled",
                    auth_event="login_failed",
                    reason="legacy_default_password_disabled",
                    auth_id=str(user.id),
                    client_ip=request.client.host,
                )
            return None

        if not self.verify_password(password, user.password):
            if request and request.client:
                logger.warning(
                    "Login failed: incorrect password",
                    auth_event="login_failed",
                    reason="incorrect_password",
                    auth_id=str(user.id),
                    client_ip=request.client.host,
                )
            return None

        # Successful login
        if request and request.client:
            logger.info(
                "Login successful",
                auth_event="login_success",
                auth_id=str(user.id),
                client_ip=request.client.host,
            )
        return user

    def _get_fernet(self) -> Fernet:
        from langflow.services.auth.utils import get_fernet

        return get_fernet(self.settings)

    def _get_decryption_fernet(self) -> Fernet | MultiFernet:
        from langflow.services.auth.utils import get_fernet_for_decryption

        return get_fernet_for_decryption(self.settings)

    def encrypt_api_key(self, api_key: str) -> str:
        fernet = self._get_fernet()
        encrypted_key = fernet.encrypt(api_key.encode())
        return encrypted_key.decode()

    def decrypt_api_key(self, encrypted_api_key: str) -> str:
        """Decrypt an encrypted API key.

        Args:
            encrypted_api_key: The encrypted API key string

        Returns:
            Decrypted API key string, or empty string if decryption fails

        Note:
            - Returns empty string for invalid input (None, empty string)
            - Returns plaintext keys as-is (not starting with "gAAAAA")
            - Logs warnings on decryption failures for security monitoring
        """
        if not isinstance(encrypted_api_key, str) or not encrypted_api_key:
            logger.debug("decrypt_api_key called with invalid input (empty or non-string)")
            return ""

        # Fernet tokens always start with "gAAAAA" - if not, return as-is (plain text)
        if not encrypted_api_key.startswith("gAAAAA"):
            return encrypted_api_key

        fernet = self._get_decryption_fernet()
        try:
            return fernet.decrypt(encrypted_api_key.encode()).decode()
        except Exception as primary_exception:  # noqa: BLE001
            logger.debug(
                "Decryption using UTF-8 encoded API key failed. Error: %r. "
                "Retrying decryption using the raw string input.",
                primary_exception,
            )
            try:
                return fernet.decrypt(encrypted_api_key).decode()
            except Exception as secondary_exception:  # noqa: BLE001
                # Decryption failed completely - log warning and return empty string
                logger.warning(
                    "API key decryption failed after retry. This may indicate a corrupted key or "
                    "SECRET_KEY mismatch. Primary error: %r, Secondary error: %r",
                    primary_exception,
                    secondary_exception,
                )
                return ""

    async def get_current_user_mcp(
        self,
        token: str | Coroutine | None,
        query_param: str | None,
        header_param: str | None,
        db: AsyncSession,
    ) -> User | UserRead:
        clear_current_auth_context()
        clear_current_external_access_context()
        if token:
            return await self.get_current_user_from_access_token(token, db)

        settings_service = self.settings
        result: User | None
        api_key_result = None

        if settings_service.auth_settings.AUTO_LOGIN:
            if not settings_service.auth_settings.SUPERUSER:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing first superuser credentials",
                )
            if not query_param and not header_param:
                # AUTO_LOGIN parity with _api_key_security_impl / ws_api_key_security:
                # AUTO_LOGIN on its own is not a credential. Only an explicit
                # skip_auth_auto_login opt-in may resolve a credential-less caller to
                # the superuser; otherwise the MCP transport endpoints would accept
                # anonymous requests that every other authenticated route rejects.
                if not settings_service.auth_settings.skip_auth_auto_login:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=AUTO_LOGIN_ERROR,
                    )
                result = await get_user_by_username(db, settings_service.auth_settings.SUPERUSER)
                if result:
                    logger.warning(AUTO_LOGIN_WARNING)
                    set_current_auth_context(AuthCredentialContext(method=AUTH_METHOD_AUTO_LOGIN))
                    return result
            else:
                # At least one of query_param or header_param is truthy
                api_key = query_param or header_param
                if api_key is None:  # pragma: no cover - guaranteed by the if-condition above
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing API key")
                api_key_result = await authenticate_api_key(api_key)
                result = api_key_result.user if api_key_result is not None else None

        elif not query_param and not header_param:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An API key must be passed as query or header",
            )

        elif query_param:
            api_key_result = await authenticate_api_key(query_param)
            result = api_key_result.user if api_key_result is not None else None

        else:
            # header_param must be truthy here (query_param is falsy, and we passed the not-both-None check)
            if header_param is None:  # pragma: no cover - guaranteed by the elif chain above
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing API key")
            api_key_result = await authenticate_api_key(header_param)
            result = api_key_result.user if api_key_result is not None else None

        if not result:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing API key",
            )

        if isinstance(result, User):
            if api_key_result is not None:
                set_current_auth_context(AuthCredentialContext.from_api_key_result(api_key_result))
            return result

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid authentication result",
        )

    async def get_current_active_user_mcp(self, current_user: User | UserRead) -> User | UserRead:
        if not current_user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
        set_current_model_provider_policy_context(
            user_id=current_user.id,
            attributes={"is_superuser": bool(current_user.is_superuser)},
        )
        return current_user

    async def teardown(self) -> None:
        """Teardown the auth service (no-op for JWT auth)."""
        logger.debug("Auth service teardown")
