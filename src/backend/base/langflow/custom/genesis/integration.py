"""Genesis Studio Integration with Langflow.

This module provides the main integration point for Genesis Studio extensions
into Langflow 1.6.0, including components, services, auth, and startup hooks.
"""

import os
from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from sqlmodel import select
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_session
from langflow.services.auth.utils import get_current_active_user
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from .auth.middleware import AuthMiddleware



def setup_genesis_middleware(app: FastAPI) -> bool:
    """Setup Genesis middleware during app creation.

    Args:
        app: FastAPI app instance

    Returns:
        bool: True if middleware setup was successful
    """
    try:
        logger.info("🔐 Setting up Genesis Auth Middleware...")

        # Check if auth middleware should be enabled
        if is_genesis_auth_enabled():
            # Check if required environment variables are present
            genesis_client_id = os.getenv("GENESIS_CLIENT_ID")
            genesis_auth_url = os.getenv("GENESIS_SERVICE_AUTH_URL")

            if not genesis_client_id or not genesis_auth_url:
                logger.warning("⚠️ Genesis Auth Middleware skipped: Missing required environment variables")
                logger.debug(f"   GENESIS_CLIENT_ID: {'✅' if genesis_client_id else '❌'}")
                logger.debug(f"   GENESIS_SERVICE_AUTH_URL: {'✅' if genesis_auth_url else '❌'}")
            else:
                # Add the middleware
                app.add_middleware(AuthMiddleware)
                logger.debug("✅ Genesis Auth Middleware enabled")
                logger.debug(f"   Client ID: {genesis_client_id}")
                logger.debug(f"   Auth URL: {genesis_auth_url}")

                # Override Langflow's authentication dependencies
                _setup_auth_dependency_overrides(app)
                logger.debug("✅ Auth dependencies overridden with Genesis auth")
        else:
            logger.info("ℹ️ Genesis Auth Middleware disabled via environment variable")

        return True
    except Exception as e:
        logger.error(f"❌ Failed to setup auth middleware: {e}")
        import traceback
        logger.error(f"   Error details: {traceback.format_exc()}")
        return False


async def initialize_genesis_extensions(app: Optional[FastAPI] = None) -> bool:
    """Initialize Genesis Studio extensions.

    Args:
        app: Optional FastAPI app instance for middleware registration

    Returns:
        bool: True if initialization was successful
    """
    try:
        logger.info("🚀 Initializing Genesis Studio Extensions...")

        # Genesis services are now auto-registered via ServiceType enum
        # No additional initialization needed beyond auth middleware

        logger.info("🎉 Genesis Studio Extensions initialized successfully!")
        return True

    except Exception as e:
        logger.error(f"❌ Critical error during Genesis initialization: {e}")
        return False


def is_genesis_extensions_enabled() -> bool:
    """Check if Genesis extensions should be enabled."""
    return os.getenv("GENESIS_ENABLE_EXTENSIONS", "true").lower() == "true"


def is_genesis_auth_enabled() -> bool:
    """Check if Genesis authentication should be enabled."""
    # If extensions are disabled, auth is also disabled
    if not is_genesis_extensions_enabled():
        return False

    # Check specific auth enablement
    return os.getenv("GENESIS_AUTH_ENABLED", "true").lower() == "true"


def _setup_auth_dependency_overrides(app):
    """Set up dependency overrides to replace Langflow's auth with Genesis auth."""
    from typing import Annotated
    from fastapi import Depends, HTTPException, Request
    from langflow.services.database.models.user.model import User
    from langflow.services.deps import get_session
    from sqlmodel.ext.asyncio.session import AsyncSession
    from sqlmodel import select

    async def get_current_user_override(
        request: Request,
        db: Annotated[AsyncSession, Depends(get_session)]
    ) -> User:
        """Override Langflow's get_current_user to use Genesis authentication or fall back to Langflow auth.

        This function:
        1. Gets the user from request.state (set by Genesis AuthMiddleware) for JWT auth
        2. Falls back to Langflow's original authentication for API keys
        3. Creates or updates the user in Langflow's database
        4. Returns a Langflow User object
        """
        # Check if Genesis AuthMiddleware set the user (JWT authentication)
        if not hasattr(request.state, "user"):
            # No Genesis user set - check for API key or other auth
            api_key = request.headers.get("x-api-key") or request.query_params.get("x-api-key")
            auth_header = request.headers.get("authorization")

            if api_key:
                # Use Langflow's original API key authentication
                from langflow.services.auth.utils import api_key_security as original_api_key_security
                user_read = await original_api_key_security(
                    query_param=request.query_params.get("x-api-key", ""),
                    header_param=request.headers.get("x-api-key", "")
                )
                # Convert UserRead back to User (they should have the same fields)
                stmt = select(User).where(User.id == user_read.id)
                user = (await db.exec(stmt)).first()
                if user:
                    return user
                else:
                    raise HTTPException(status_code=401, detail="User not found")

            elif auth_header:
                # Use Langflow's original JWT authentication
                from langflow.services.auth.utils import get_current_user_by_jwt
                return await get_current_user_by_jwt(auth_header.replace("Bearer ", ""), db)

            # If auth is disabled or user not set, create a default user
            # This handles cases where auth is disabled for development
            elif os.getenv("GENESIS_AUTH_ENABLED", "true").lower() == "false":
                # Create or get a default development user
                username = "genesis_dev_user"
                stmt = select(User).where(User.username == username)
                existing_user = (await db.exec(stmt)).first()

                if existing_user:
                    return existing_user
                else:
                    dev_user = User(
                        username=username,
                        is_active=True,
                        is_superuser=True,
                        password="",  # External auth
                    )
                    db.add(dev_user)
                    await db.commit()
                    await db.refresh(dev_user)
                    return dev_user
            else:
                # Auth is enabled but no valid auth found
                raise HTTPException(
                    status_code=401,
                    detail="Could not validate credentials"
                )

        # Get the Genesis user from request state
        genesis_user = request.state.user

        # Get the user ID from Genesis user (this should be the JWT sub claim)
        user_id = None
        if hasattr(genesis_user, 'id'):
            user_id = genesis_user.id
        elif hasattr(genesis_user, 'genesis_user_id'):
            user_id = genesis_user.genesis_user_id

        # Convert to UUID if it's a string
        if user_id and isinstance(user_id, str):
            try:
                user_id = UUID(user_id)
            except ValueError:
                logger.warning(f"Invalid UUID format for user_id: {user_id}")
                user_id = None

        # Get the username (handle different user object structures)
        if hasattr(genesis_user, 'username'):
            username = genesis_user.username
        elif hasattr(genesis_user, 'genesis_user_id'):
            username = f"genesis_{genesis_user.genesis_user_id}"
        else:
            username = "genesis_user"

        # Check if user exists in Langflow's database using the actual user ID
        if user_id:
            stmt = select(User).where(User.id == user_id)
        else:
            stmt = select(User).where(User.username == username)
        existing_user = (await db.exec(stmt)).first()

        if existing_user:
            # Update existing user with latest data from Genesis
            if hasattr(genesis_user, 'is_active'):
                existing_user.is_active = genesis_user.is_active
            if hasattr(genesis_user, 'is_superuser'):
                existing_user.is_superuser = genesis_user.is_superuser
            elif hasattr(genesis_user, 'is_admin'):
                existing_user.is_superuser = genesis_user.is_admin

            db.add(existing_user)
            await db.commit()
            await db.refresh(existing_user)
            return existing_user
        else:
            # Create new user in Langflow's database
            is_active = True
            is_superuser = False

            if hasattr(genesis_user, 'is_active'):
                is_active = genesis_user.is_active
            if hasattr(genesis_user, 'is_superuser'):
                is_superuser = genesis_user.is_superuser
            elif hasattr(genesis_user, 'is_admin'):
                is_superuser = genesis_user.is_admin

            langflow_user = User(
                username=username,
                is_active=is_active,
                is_superuser=is_superuser,
                password="",  # Using external auth, no password needed
            )

            # Set the user ID to match the JWT sub claim if available
            if user_id:
                langflow_user.id = user_id
            db.add(langflow_user)
            await db.commit()
            await db.refresh(langflow_user)
            return langflow_user

    async def get_current_active_user_override(
        current_user: Annotated[User, Depends(get_current_user_override)]
    ) -> User:
        """Override Langflow's get_current_active_user."""
        if not current_user.is_active:
            raise HTTPException(status_code=401, detail="Inactive user")
        return current_user

    # Import Langflow's original auth functions
    from langflow.services.auth.utils import (
        get_current_user,
        get_current_active_user,
        api_key_security,
        get_current_user_mcp,
        get_current_active_user_mcp,
    )
    from langflow.services.database.models.user.model import UserRead

    async def api_key_security_override(
        request: Request,
        db: Annotated[AsyncSession, Depends(get_session)]
    ) -> UserRead:
        """Override api_key_security to use Genesis authentication or fall back to Langflow API key auth.

        This is used by flow execution endpoints and needs to return a UserRead object.
        """
        # Check if Genesis middleware set a user (JWT authentication)
        if hasattr(request.state, "user"):
            # Get the actual User object from our override
            user = await get_current_user_override(request, db)
            return UserRead.model_validate(user, from_attributes=True)

        # Fall back to Langflow's original API key authentication
        from langflow.services.auth.utils import api_key_security as original_api_key_security
        return await original_api_key_security(
            query_param=request.query_params.get("x-api-key", ""),
            header_param=request.headers.get("x-api-key", "")
        )

    async def get_current_user_mcp_override(
        request: Request,
        db: Annotated[AsyncSession, Depends(get_session)],
    ) -> User:
        """
        Override MCP-specific get_current_user_mcp to support Genesis Bearer auth and x-api-key.

        Behaviour:
        - If Genesis middleware already set request.state.user from a validated Bearer token,
          reuse get_current_user_override so the Langflow User is created/updated.
        - Otherwise, fall back to Langflow's original MCP auth (JWT + API key).
        """
        # If Genesis middleware set a user, trust it
        if hasattr(request.state, "user"):
            return await get_current_user_override(request, db)

        # Fallback to original MCP auth (Langflow JWT / x-api-key)
        from langflow.services.auth.utils import get_current_user_mcp as original_get_current_user_mcp

        auth_header = request.headers.get("authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
        query_param = request.query_params.get("x-api-key", "")
        header_param = request.headers.get("x-api-key", "")

        return await original_get_current_user_mcp(
            token=token,
            query_param=query_param,
            header_param=header_param,
            db=db,
        )

    async def get_current_active_user_mcp_override(
        current_user: Annotated[User, Depends(get_current_user_mcp_override)],
    ) -> User:
        """Override MCP-specific get_current_active_user_mcp to use Genesis/Langflow blended auth."""
        if not current_user.is_active:
            raise HTTPException(status_code=401, detail="Inactive user")
        return current_user

    # Override the dependencies
    app.dependency_overrides[get_current_user] = get_current_user_override
    app.dependency_overrides[get_current_active_user] = get_current_active_user_override
    app.dependency_overrides[api_key_security] = api_key_security_override
    app.dependency_overrides[get_current_user_mcp] = get_current_user_mcp_override
    app.dependency_overrides[get_current_active_user_mcp] = get_current_active_user_mcp_override


__all__ = [
    "initialize_genesis_extensions",
    "is_genesis_extensions_enabled",
    "is_genesis_auth_enabled",
    "setup_genesis_middleware",
]