from __future__ import annotations

import hashlib
import warnings
from collections.abc import Coroutine
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

import jwt
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request, WebSocketException, status
from jwt import InvalidTokenError
from lfx.log.logger import logger
from lfx.services.auth.base import BaseAuthService
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

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession


class AuthService(BaseAuthService):
    """Default Langflow authentication service (implements LFX BaseAuthService)."""

    name = ServiceType.AUTH_SERVICE.value

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
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

        # Try token authentication first (if token provided)
        if token:
            try:
                return await self._authenticate_with_token(token, db)
            except (AuthInvalidTokenError, TokenExpiredError, InactiveUserError) as e:
                # Native auth failed. If a *distinct* external credential was
                # extracted, try it before surfacing the native error so a present
                # but invalid/expired native token can't shadow a valid external
                # one. When external_token is None or identical to the token we
                # already tried, behavior is unchanged.
                if external_token and external_token != token:
                    external_user = await self._authenticate_with_external_token(external_token, db)
                    if external_user is not None:
                        return external_user
                raise e  # noqa: TRY201
            except Exception as e:
                # Token auth failed for an unexpected reason; try the distinct
                # external credential first, then fall back to API key if provided.
                if external_token and external_token != token:
                    external_user = await self._authenticate_with_external_token(external_token, db)
                    if external_user is not None:
                        return external_user
                if api_key:
                    try:
                        user = await self._authenticate_with_api_key(api_key, db)
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
            try:
                user = await self._authenticate_with_api_key(api_key, db)
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
        return await self._materialize_external_user(identity, db)

    async def _authenticate_with_api_key(self, api_key: str, db: AsyncSession) -> UserRead | None:
        """Internal method to authenticate with API key (raises generic exceptions).

        The EXTERNAL_AUTH access ceiling block for externally-managed users is
        enforced inside ``authenticate_api_key`` (the shared chokepoint), which
        returns ``None`` for a blocked user so every caller treats it as an auth
        failure. No additional ceiling check is needed here.
        """
        result = await authenticate_api_key(db, api_key)
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
        new_profile = SSOUserProfile(
            user_id=user.id,
            sso_provider=identity.provider,
            sso_user_id=identity.subject,
            email=identity.email,
            sso_last_login_at=now,
        )
        db.add(user)
        db.add(new_profile)
        try:
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
        settings_service = self.settings

        # Use provided session or create a new one
        if db is not None:
            return await self._api_key_security_impl(query_param, header_param, db, settings_service)

        async with session_scope() as new_db:
            return await self._api_key_security_impl(query_param, header_param, new_db, settings_service)

    async def _api_key_security_impl(
        self,
        query_param: str | None,
        header_param: str | None,
        db: AsyncSession,
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
                    result = await get_user_by_username(db, settings_service.auth_settings.SUPERUSER)
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
            api_key_result = await authenticate_api_key(db, api_key)

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
            api_key_result = await authenticate_api_key(db, api_key)

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
        async with session_scope() as db:
            api_key_result = None
            if settings.auth_settings.AUTO_LOGIN:
                if not settings.auth_settings.SUPERUSER:
                    raise WebSocketException(
                        code=status.WS_1011_INTERNAL_ERROR,
                        reason="Missing first superuser credentials",
                    )
                if not api_key:
                    if settings.auth_settings.skip_auth_auto_login:
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
                    api_key_result = await authenticate_api_key(db, api_key)
                    result = api_key_result.user if api_key_result is not None else None

            else:
                if not api_key:
                    raise WebSocketException(
                        code=status.WS_1008_POLICY_VIOLATION,
                        reason="An API key must be passed as query or header",
                    )
                api_key_result = await authenticate_api_key(db, api_key)
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
        return current_user

    async def get_current_active_superuser(self, current_user: User | UserRead) -> User | UserRead | None:
        if not current_user.is_active or not current_user.is_superuser:
            return None
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
            async with session_scope() as db:
                result = await authenticate_api_key(db, api_key)
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
        from langflow.services.auth.utils import ensure_fernet_key

        secret_key: str = self.settings.auth_settings.SECRET_KEY.get_secret_value()
        return Fernet(ensure_fernet_key(secret_key))

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

        fernet = self._get_fernet()
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
                api_key_result = await authenticate_api_key(db, api_key)
                result = api_key_result.user if api_key_result is not None else None

        elif not query_param and not header_param:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An API key must be passed as query or header",
            )

        elif query_param:
            api_key_result = await authenticate_api_key(db, query_param)
            result = api_key_result.user if api_key_result is not None else None

        else:
            # header_param must be truthy here (query_param is falsy, and we passed the not-both-None check)
            if header_param is None:  # pragma: no cover - guaranteed by the elif chain above
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing API key")
            api_key_result = await authenticate_api_key(db, header_param)
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
        return current_user

    async def teardown(self) -> None:
        """Teardown the auth service (no-op for JWT auth)."""
        logger.debug("Auth service teardown")
