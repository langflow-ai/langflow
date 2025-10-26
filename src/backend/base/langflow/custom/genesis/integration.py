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
from langflow.services.manager import ServiceManager
from langflow.services.auth.utils import get_current_active_user
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from .services import register_genesis_services
from .auth.middleware import AuthMiddleware
from .startup_extensions import initialize_genesis_studio_extensions, initialize_complete_genesis_extensions



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
        auth_enabled = os.getenv("GENESIS_AUTH_ENABLED", "true").lower() == "true"
        if auth_enabled:
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
    """Initialize all Genesis Studio extensions.

    Args:
        app: Optional FastAPI app instance for middleware registration

    Returns:
        bool: True if initialization was successful
    """
    success = True

    try:
        logger.info("🚀 Initializing Genesis Studio Extensions...")

        # 1. Register custom services
        logger.info("\n🔧 Registering Genesis Services...")
        try:
            registered_services = register_genesis_services()
            if registered_services:
                logger.debug(f"✅ Registered Genesis services successfully")
            else:
                logger.warning("⚠️ No Genesis services were registered")
        except Exception as e:
            logger.error(f"❌ Failed to register services: {e}")
            success = False

        # 2. Initialize complete startup extensions (starter projects, component mappings, schema integration)
        logger.info("\n🎯 Initializing Complete Genesis Startup Extensions...")
        try:
            # Import session_getter for database access during startup
            from langflow.services.database.utils import session_getter
            from langflow.services.deps import get_db_service

            # Use session context for database operations
            db_service = get_db_service()
            async with session_getter(db_service) as session:
                startup_success = await initialize_complete_genesis_extensions(session)
                if startup_success:
                    logger.debug("✅ Complete Genesis Startup Extensions initialized")
                else:
                    logger.debug("⚠️ Some startup extensions failed to initialize")
        except Exception as e:
            logger.error(f"❌ Failed to initialize complete startup extensions: {e}")
            success = False

        # Summary
        if success:
            logger.info("\n🎉 Genesis Studio Extensions initialized successfully!")
        else:
            logger.warning("\n⚠️ Genesis Studio Extensions initialized with some failures")

        return success

    except Exception as e:
        logger.error(f"❌ Critical error during Genesis initialization: {e}")
        return False


def is_genesis_extensions_enabled() -> bool:
    """Check if Genesis extensions should be enabled."""
    return os.getenv("GENESIS_ENABLE_EXTENSIONS", "true").lower() == "true"


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
    from langflow.services.auth.utils import get_current_user, get_current_active_user, api_key_security
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

    # Override the dependencies
    app.dependency_overrides[get_current_user] = get_current_user_override
    app.dependency_overrides[get_current_active_user] = get_current_active_user_override
    app.dependency_overrides[api_key_security] = api_key_security_override


__all__ = [
    "initialize_genesis_extensions",
    "is_genesis_extensions_enabled",
    "setup_genesis_middleware",
]