"""SaaS plugin entry point.

Langflow calls ``register(app_wrapper)`` at startup via the
``langflow.plugins`` entry-point group declared in pyproject.toml.

What this function does:
  1. Runs SaaS database migrations (saas_* tables) on every startup — safe
     because Alembic is idempotent.
  2. Registers three ASGI middleware classes on the real FastAPI app:
       a. RateLimitMiddleware       (outermost)
       b. TenantContextMiddleware   (resolves org context)
       c. QuotaEnforcementMiddleware (innermost, checks execution quotas)
  3. Mounts all SaaS REST routes under /api/saas/v1/.
  4. Registers a startup handler that auto-creates personal organisations
     for any existing Langflow users who don't yet have one (idempotent).

Upgrade safety:
  This file calls only two things from Langflow:
    - app_wrapper.add_middleware()     (added in plugin_routes.py)
    - app_wrapper.include_router()     (already present in plugin_routes.py)
  If Langflow changes either of these signatures, update only here.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("langflow_saas.plugin")


# ---------------------------------------------------------------------------
# Migration helper
# ---------------------------------------------------------------------------


def _run_migrations() -> None:
    """Run SaaS Alembic migrations synchronously at startup.

    Safe to call on every startup — Alembic no-ops when already up to date.
    """
    try:
        from pathlib import Path

        from alembic import command
        from alembic.config import Config

        ini_path = Path(__file__).parent.parent.parent / "alembic.ini"
        if not ini_path.exists():
            # Installed as a wheel: resolve relative to the package.
            ini_path = Path(__file__).parent.parent / "alembic.ini"

        if not ini_path.exists():
            logger.warning("langflow-saas: alembic.ini not found at %s — skipping migrations.", ini_path)
            return

        alembic_cfg = Config(str(ini_path))

        # Ensure the migrations folder is discoverable regardless of CWD.
        migrations_dir = Path(__file__).parent / "migrations"
        alembic_cfg.set_main_option("script_location", str(migrations_dir))

        from langflow_saas.settings import get_saas_settings

        db_url = get_saas_settings().database_url
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        command.upgrade(alembic_cfg, "heads")
        logger.info("langflow-saas: migrations applied.")
    except Exception:
        logger.exception("langflow-saas: migration failed — SaaS features may not work correctly.")


# ---------------------------------------------------------------------------
# Personal-org auto-creation
# ---------------------------------------------------------------------------


async def _ensure_personal_orgs() -> None:
    """Create personal orgs for any existing Langflow users that don't have one.

    Idempotent: skips users who already have a personal org.
    """
    from langflow_saas.settings import get_saas_settings

    if not get_saas_settings().auto_create_personal_org:
        return

    try:
        import re
        from datetime import datetime, timezone

        from langflow.services.database.models.user.model import User
        from langflow.services.deps import session_scope
        from sqlmodel import select

        from langflow_saas.models import Organization, OrgRole, UserOrganization

        async with session_scope() as db:
            users_result = await db.exec(select(User))
            all_users = users_result.all()

            for user in all_users:
                uid = user.id
                # Check for existing personal org.
                existing_personal = await db.exec(
                    select(Organization).where(
                        Organization.owner_id == uid,
                        Organization.is_personal == True,  # noqa: E712
                    )
                )
                if existing_personal.first():
                    continue

                # Generate a unique slug from username.
                base_slug = re.sub(r"[^a-z0-9]+", "-", user.username.lower()).strip("-")[:50]
                slug = base_slug
                attempt = 0
                while True:
                    collision = await db.exec(select(Organization).where(Organization.slug == slug))
                    if not collision.first():
                        break
                    attempt += 1
                    slug = f"{base_slug}-{attempt}"

                now = datetime.now(timezone.utc)
                org = Organization(
                    name=f"{user.username}'s workspace",
                    slug=slug,
                    owner_id=uid,
                    is_personal=True,
                    created_at=now,
                    updated_at=now,
                )
                db.add(org)
                await db.flush()

                membership = UserOrganization(user_id=uid, org_id=org.id, role=OrgRole.OWNER, created_at=now)
                db.add(membership)

            await db.commit()
            logger.info("langflow-saas: personal orgs ensured for all users.")
    except Exception:
        logger.exception("langflow-saas: failed to ensure personal orgs.")


# ---------------------------------------------------------------------------
# Plugin registration — the ONLY function called by Langflow
# ---------------------------------------------------------------------------


def register(app) -> None:  # ``app`` is _PluginAppWrapper from plugin_routes.py
    """Called by Langflow's load_plugin_routes() at startup.

    Parameters
    ----------
    app:
        A ``_PluginAppWrapper`` instance that exposes ``include_router`` and
        ``add_middleware`` (the latter added by our one-line patch to
        plugin_routes.py).
    """
    logger.info("langflow-saas: registering SaaS plugin…")

    # 1. Run DB migrations (sync — happens before the ASGI server starts
    #    accepting requests, so there is no race condition).
    _run_migrations()

    # 2. Register middleware.  Order matters: add_middleware() inserts at the
    #    outermost position each time, so the last add_middleware call wraps
    #    everything.  We want:
    #       QuotaEnforcement  (innermost — only fires on execution paths)
    #       TenantContext     (resolves org for all API paths)
    #       RateLimit         (outermost — fast Redis check, no DB)
    #
    #    Because add_middleware() inserts outermost each time, we add them
    #    in REVERSE order of desired execution:
    from langflow_saas.middleware import (
        FlowOwnershipMiddleware,
        QuotaEnforcementMiddleware,
        RateLimitMiddleware,
        TenantContextMiddleware,
        UserRegistrationMiddleware,
    )

    # Desired execution order (outermost → innermost):
    #   RateLimit → UserRegistration → TenantContext → FlowOwnership → QuotaEnforcement
    # add_middleware() inserts at the outermost position each call, so we add
    # in reverse order:
    app.add_middleware(QuotaEnforcementMiddleware)  # innermost — quota gate on executions
    app.add_middleware(FlowOwnershipMiddleware)  # auto-assigns new flows to creator's org
    app.add_middleware(TenantContextMiddleware)  # resolves org context from JWT
    app.add_middleware(UserRegistrationMiddleware)  # provisions org on signup
    app.add_middleware(RateLimitMiddleware)  # outermost — fast Redis check

    # 3. Mount SaaS API routes under /api/saas/v1/.
    from langflow_saas.api.router import router as saas_router

    app.include_router(saas_router)

    # 4. Register startup hook for personal-org auto-creation.
    #    We access the real FastAPI app via the wrapper's private _app attribute
    #    to use the @app.on_event pattern.  This is the only place we touch
    #    the private attribute; if Langflow ever changes the wrapper, update here.
    try:
        real_app = app._app  # _PluginAppWrapper stores the real FastAPI app here

        @real_app.on_event("startup")
        async def _saas_startup():
            await _ensure_personal_orgs()

    except AttributeError:
        logger.warning(
            "langflow-saas: could not register startup hook "
            "(wrapper._app not accessible). Personal orgs will not be auto-created."
        )

    logger.info("langflow-saas: plugin registered. Routes at /api/saas/v1/")
