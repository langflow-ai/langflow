from __future__ import annotations

import base64
import random
import warnings
from collections.abc import Coroutine
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import HTTPException, Request, WebSocketException, status
import jwt
from jwt import InvalidTokenError
from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError

from langflow.helpers.user import get_user_by_flow_id_or_endpoint_name
from langflow.services.auth.base import AuthServiceBase
from langflow.services.database.models.api_key.crud import check_key
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

    from langflow.services.database.models.api_key.model import ApiKey

MINIMUM_KEY_LENGTH = 32
AUTO_LOGIN_WARNING = "In v2.0, LANGFLOW_SKIP_AUTH_AUTO_LOGIN will be removed. Please update your authentication method."
AUTO_LOGIN_ERROR = (
    "Since v1.5, LANGFLOW_AUTO_LOGIN requires a valid API key. "
    "Set LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true to skip this check. "
    "Please update your authentication method."
)


class AuthService(AuthServiceBase):
    """Default Langflow authentication service."""

    name = ServiceType.AUTH_SERVICE.value

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
        self.set_ready()

    @property
    def settings(self) -> SettingsService:
        return self.settings_service

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
        result: ApiKey | User | None

        if settings_service.auth_settings.AUTO_LOGIN:
            if not settings_service.auth_settings.SUPERUSER:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing first superuser credentials",
                )
            if not query_param and not header_param:
                if settings_service.auth_settings.skip_auth_auto_login:
                    result = await get_user_by_username(db, settings_service.auth_settings.SUPERUSER)
                    logger.warning(AUTO_LOGIN_WARNING)
                    return UserRead.model_validate(result, from_attributes=True)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=AUTO_LOGIN_ERROR,
                )
            # At this point, at least one of query_param or header_param is truthy
            api_key = query_param or header_param
            if api_key is None:  # pragma: no cover - guaranteed by the if-condition above
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing API key")
            result = await check_key(db, api_key)

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
            result = await check_key(db, api_key)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing API key",
            )

        if isinstance(result, User):
            return UserRead.model_validate(result, from_attributes=True)

        msg = "Invalid result type"
        raise ValueError(msg)

    async def ws_api_key_security(self, api_key: str | None) -> UserRead:
        settings = self.settings
        async with session_scope() as db:
            if settings.auth_settings.AUTO_LOGIN:
                if not settings.auth_settings.SUPERUSER:
                    raise WebSocketException(
                        code=status.WS_1011_INTERNAL_ERROR,
                        reason="Missing first superuser credentials",
                    )
                if not api_key:
                    if settings.auth_settings.skip_auth_auto_login:
                        result = await get_user_by_username(db, settings.auth_settings.SUPERUSER)
                        logger.warning(AUTO_LOGIN_WARNING)
                    else:
                        raise WebSocketException(
                            code=status.WS_1008_POLICY_VIOLATION,
                            reason=AUTO_LOGIN_ERROR,
                        )
                else:
                    result = await check_key(db, api_key)

            else:
                if not api_key:
                    raise WebSocketException(
                        code=status.WS_1008_POLICY_VIOLATION,
                        reason="An API key must be passed as query or header",
                    )
                result = await check_key(db, api_key)

            if not result:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Invalid or missing API key",
                )

            if isinstance(result, User):
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
    ) -> User | UserRead:
        if token:
            return await self.get_current_user_from_access_token(token, db)
        # Pass db session to api_key_security for transactional consistency
        user = await self.api_key_security(query_param, header_param, db)
        if user:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )

    async def get_current_user_from_access_token(
        self,
        token: str | Coroutine | None,
        db: AsyncSession,
    ) -> User:
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        settings_service = self.settings

        if isinstance(token, Coroutine):
            token = await token

        # At this point token should be a string (awaited if it was a coroutine)
        if not isinstance(token, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        secret_key = settings_service.auth_settings.SECRET_KEY.get_secret_value()
        if secret_key is None:
            logger.error("Secret key is not set in settings.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failure: Verify authentication settings.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                payload = jwt.decode(token, secret_key, algorithms=[settings_service.auth_settings.ALGORITHM])
            user_id: UUID = payload.get("sub")  # type: ignore[assignment]
            token_type: str = payload.get("type")  # type: ignore[assignment]
            if expires := payload.get("exp", None):
                expires_datetime = datetime.fromtimestamp(expires, timezone.utc)
                if datetime.now(timezone.utc) > expires_datetime:
                    logger.info("Token expired for user")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token has expired.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

            if user_id is None or token_type is None:
                logger.info(f"Invalid token payload. Token type: {token_type}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token details.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except InvalidTokenError as e:
            logger.debug("JWT validation failed: Invalid token format or signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        user = await get_user_by_id(db, user_id)
        if user is None or not user.is_active:
            logger.info("User not found or inactive.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or is inactive.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    async def get_current_user_for_websocket(
        self,
        token: str | None,
        api_key: str | None,
        db: AsyncSession,
    ) -> User | UserRead:
        if token:
            user = await self.get_current_user_from_access_token(token, db)
            if user:
                return user

        if api_key:
            user_read = await self.ws_api_key_security(api_key)
            if user_read:
                return user_read

        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Missing or invalid credentials (cookie, token or API key)."
        )

    async def get_current_active_user(self, current_user: User | UserRead) -> User | UserRead:
        if not current_user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
        return current_user

    async def get_current_active_superuser(self, current_user: User | UserRead) -> User | UserRead:
        if not current_user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
        if not current_user.is_superuser:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The user doesn't have enough privileges")
        return current_user

    async def get_webhook_user(self, flow_id: str, request: Request) -> UserRead:
        settings_service = self.settings

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
                result = await check_key(db, api_key)
                if not result:
                    logger.warning("Invalid API key provided for webhook")
                    raise HTTPException(status_code=403, detail="Invalid API key")

                authenticated_user = UserRead.model_validate(result, from_attributes=True)
                logger.info("Webhook API key validated successfully")
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Webhook API key validation error: {exc}")
            raise HTTPException(status_code=403, detail="API key authentication failed") from exc

        try:
            flow_owner = await get_user_by_flow_id_or_endpoint_name(flow_id)
            if flow_owner is None:
                raise HTTPException(status_code=404, detail="Flow not found")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=404, detail="Flow not found") from exc

        if flow_owner.id != authenticated_user.id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: You can only execute webhooks for flows you own",
            )

        return authenticated_user

    def verify_password(self, plain_password, hashed_password):
        return self.settings.auth_settings.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password):
        return self.settings.auth_settings.pwd_context.hash(password)

    def create_token(self, data: dict, expires_delta: timedelta):
        settings_service = self.settings
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode["exp"] = expire

        return jwt.encode(
            to_encode,
            settings_service.auth_settings.SECRET_KEY.get_secret_value(),
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
        access_token_expires_longterm = timedelta(days=365)
        access_token = self.create_token(
            data={"sub": str(super_user.id), "type": "access"},
            expires_delta=access_token_expires_longterm,
        )

        await update_user_last_login_at(super_user.id, db)

        return super_user.id, {
            "access_token": access_token,
            "refresh_token": None,
            "token_type": "bearer",
        }

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
        settings_service = self.settings

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                payload = jwt.decode(
                    refresh_token,
                    settings_service.auth_settings.SECRET_KEY.get_secret_value(),
                    algorithms=[settings_service.auth_settings.ALGORITHM],
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

    async def authenticate_user(self, username: str, password: str, db: AsyncSession) -> User | None:
        user = await get_user_by_username(db, username)

        if not user:
            return None

        if not user.is_active:
            if not user.last_login_at:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Waiting for approval")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")

        return user if self.verify_password(password, user.password) else None

    def _add_padding(self, value: str) -> str:
        padding_needed = 4 - len(value) % 4
        return value + "=" * padding_needed

    def _ensure_valid_key(self, raw_key: str) -> bytes:
        if len(raw_key) < MINIMUM_KEY_LENGTH:
            random.seed(raw_key)
            key = bytes(random.getrandbits(8) for _ in range(32))
            key = base64.urlsafe_b64encode(key)
        else:
            key = self._add_padding(raw_key).encode()
        return key

    def _get_fernet(self) -> Fernet:
        secret_key: str = self.settings.auth_settings.SECRET_KEY.get_secret_value()
        valid_key = self._ensure_valid_key(secret_key)
        return Fernet(valid_key)

    def encrypt_api_key(self, api_key: str) -> str:
        fernet = self._get_fernet()
        encrypted_key = fernet.encrypt(api_key.encode())
        return encrypted_key.decode()

    def decrypt_api_key(self, encrypted_api_key: str) -> str:
        fernet = self._get_fernet()
        if isinstance(encrypted_api_key, str):
            try:
                return fernet.decrypt(encrypted_api_key.encode()).decode()
            except Exception as primary_exception:  # noqa: BLE001
                logger.debug(
                    "Decryption using UTF-8 encoded API key failed. Error: %s. "
                    "Retrying decryption using the raw string input.",
                    primary_exception,
                )
                return fernet.decrypt(encrypted_api_key).decode()
        return ""

    async def get_current_user_mcp(
        self,
        token: str | Coroutine | None,
        query_param: str | None,
        header_param: str | None,
        db: AsyncSession,
    ) -> User | UserRead:
        if token:
            return await self.get_current_user_from_access_token(token, db)

        settings_service = self.settings
        result: ApiKey | User | None

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
                    return result
            else:
                # At least one of query_param or header_param is truthy
                api_key = query_param or header_param
                if api_key is None:  # pragma: no cover - guaranteed by the if-condition above
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing API key")
                result = await check_key(db, api_key)

        elif not query_param and not header_param:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An API key must be passed as query or header",
            )

        elif query_param:
            result = await check_key(db, query_param)

        else:
            # header_param must be truthy here (query_param is falsy, and we passed the not-both-None check)
            if header_param is None:  # pragma: no cover - guaranteed by the elif chain above
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing API key")
            result = await check_key(db, header_param)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing API key",
            )

        if isinstance(result, User):
            return result

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid authentication result",
        )

    async def get_current_active_user_mcp(self, current_user: User | UserRead) -> User | UserRead:
        if not current_user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
        return current_user
