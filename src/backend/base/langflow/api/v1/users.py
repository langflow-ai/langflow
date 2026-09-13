from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from lfx.services.authorization import (
    AuthorizationMutation,
    AuthorizationMutationKind,
    AuthorizationMutationRejected,
    UserAuthorizationSnapshot,
)
from lfx.utils.util_strings import escape_like_pattern
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.sql.expression import SelectOfScalar

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.schemas import PasswordResetRequest, UsersResponse
from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.auth.utils import get_current_user_optional
from langflow.services.authorization.audit import (
    AUDIT_EVENT_ACCESS,
    AUDIT_EVENT_MUTATION,
    audit_decision,
    stage_audit_decision,
)
from langflow.services.authorization.fetch import load_mutation_actor
from langflow.services.authorization.lifecycle import (
    acquire_identity_mutation_lock,
    owned_resource_impact,
    safe_identity_mutation_committed,
    safe_share_rules_removed,
    stage_identity_mutation,
    validate_identity_mutation,
)
from langflow.services.authorization.team_management import (
    TeamManagementError,
    UserTeamLifecycleLockContext,
    UserTeamLifecycleResult,
    acquire_user_team_lifecycle_locks,
    actor_can_administer_platform,
    apply_user_team_lifecycle,
    prepare_user_team_lifecycle_lock_hint,
)
from langflow.services.database.lock_retry import run_with_lock_retry
from langflow.services.database.models.user.crud import update_user
from langflow.services.database.models.user.model import User, UserCreate, UserRead, UserUpdate
from langflow.services.deps import get_auth_service, get_authorization_service, get_settings_service

router = APIRouter(tags=["Users"], prefix="/users")


async def _get_current_platform_admin(current_user: CurrentActiveUser) -> User:
    """Require effective platform authority for user-directory operations."""
    if not actor_can_administer_platform(current_user):
        raise HTTPException(status_code=403, detail="Platform administrator access required")
    return current_user


async def _audit_deny(
    *,
    user_id: UUID | None,
    action: str,
    obj: str,
    status_code: int,
    reason: str,
    session: DbSession | None = None,
) -> None:
    if session is not None:
        # A denied mutation must release its writer lock before the independent
        # durable audit writer persists the denial.
        await session.rollback()
    await audit_decision(
        user_id=user_id,
        action=action,
        obj=obj,
        result="deny",
        details={"event": AUDIT_EVENT_ACCESS, "status_code": status_code, "reason": reason},
    )


@router.post("/", response_model=UserRead, status_code=201)
async def add_user(
    user: UserCreate,
    session: DbSession,
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    """Add a new user to the database.

    This endpoint backs two flows that share the same route:

    * Public sign up (unauthenticated). Allowed only when public registration is
      enabled for the deployment, i.e. AUTO_LOGIN is off (multi-user mode) and
      ENABLE_SIGNUP is True.
    * Admin "add user" (authenticated Platform Admin). Always allowed,
      regardless of the sign up settings, so disabling public sign up does not
      break administrator-driven user creation.

    User activation is controlled by the NEW_USER_IS_ACTIVE setting.
    """
    settings_service = get_settings_service()
    auth_settings = settings_service.auth_settings
    # An authenticated Platform Admin (the admin "add user" flow) may always
    # create users. For every other caller this endpoint is effectively
    # unauthenticated, so refuse it unless public sign up is intended for this
    # deployment. get_current_user_optional returns None for credential-less
    # requests, so the anonymous path can never be promoted to superuser.
    is_platform_admin_caller = current_user is not None and actor_can_administer_platform(current_user)
    if not is_platform_admin_caller and (auth_settings.AUTO_LOGIN or not auth_settings.ENABLE_SIGNUP):
        await _audit_deny(
            user_id=current_user.id if current_user is not None else None,
            action="user:create",
            obj="user:*",
            status_code=403,
            reason="public_registration_disabled",
        )
        raise HTTPException(status_code=403, detail="Public user registration is disabled.")

    new_user = User.model_validate(user, from_attributes=True)
    authorization_service = get_authorization_service()
    try:
        new_user.password = get_auth_service().get_password_hash(user.password)
        new_user.is_active = settings_service.auth_settings.NEW_USER_IS_ACTIVE
        await acquire_identity_mutation_lock(
            authorization_service,
            session,
            kind=AuthorizationMutationKind.USER_CREATED,
            entity_id=new_user.id,
            affected_user_ids=(new_user.id,),
        )
        if current_user is not None:
            # Authentication can precede a committed demotion while this writer
            # waits. Only current canonical authority can bypass signup settings.
            actor = await load_mutation_actor(session, current_user.id)
            is_platform_admin_caller = actor_can_administer_platform(actor)
            if not is_platform_admin_caller and (auth_settings.AUTO_LOGIN or not auth_settings.ENABLE_SIGNUP):
                await _audit_deny(
                    user_id=actor.id,
                    action="user:create",
                    obj="user:*",
                    status_code=403,
                    reason="platform_authority_revoked",
                    session=session,
                )
                raise HTTPException(status_code=403, detail="Public user registration is disabled.")
        session.add(new_user)
        await session.flush()
        await session.refresh(new_user)
        folder = await get_or_create_default_folder(session, new_user.id)
        if not folder:
            await session.rollback()
            await _audit_deny(
                user_id=current_user.id if current_user is not None else None,
                action="user:create",
                obj=f"user:{new_user.id}",
                status_code=500,
                reason="default_project_creation_failed",
            )
            raise HTTPException(status_code=500, detail="Error creating default project")
    except IntegrityError as e:
        await session.rollback()
        await _audit_deny(
            user_id=current_user.id if current_user is not None else None,
            action="user:create",
            obj="user:*",
            status_code=400,
            reason="username_unavailable",
        )
        raise HTTPException(status_code=400, detail="This username is unavailable.") from e

    lifecycle_mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.USER_CREATED,
        entity_id=new_user.id,
        actor_user_id=current_user.id if current_user is not None else None,
        affected_user_ids=(new_user.id,),
        policy_relevant_fields=("is_active", "is_superuser"),
        user_before=None,
        user_after=UserAuthorizationSnapshot(
            is_active=new_user.is_active,
            is_superuser=new_user.is_superuser,
        ),
    )
    audit_details = {
        "event": AUDIT_EVENT_MUTATION,
        "created_by": "admin" if is_platform_admin_caller else "signup",
    }
    try:
        await stage_identity_mutation(authorization_service, session, lifecycle_mutation)
        audit_staged = stage_audit_decision(
            session=session,
            user_id=current_user.id if current_user is not None else new_user.id,
            action="user:create",
            obj=f"user:{new_user.id}",
            result="allow",
            details=audit_details,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    await safe_identity_mutation_committed(authorization_service, lifecycle_mutation)
    if not audit_staged:
        await audit_decision(
            user_id=current_user.id if current_user is not None else new_user.id,
            action="user:create",
            obj=f"user:{new_user.id}",
            result="allow",
            details=audit_details,
        )
    return new_user


@router.get("/whoami", response_model=UserRead)
async def read_current_user(
    current_user: CurrentActiveUser,
) -> User:
    """Retrieve the current user's data."""
    return current_user


@router.get("/", dependencies=[Depends(_get_current_platform_admin)])
async def read_all_users(
    *,
    skip: int = 0,
    limit: int = 10,
    search: str | None = None,
    session: DbSession,
) -> UsersResponse:
    """Retrieve a list of users from the database with pagination."""
    query: SelectOfScalar = select(User)
    count_query = select(func.count()).select_from(User)

    if search:
        search_filter = User.username.ilike(f"%{escape_like_pattern(search)}%", escape="\\")  # type: ignore[attr-defined]
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    query = query.offset(skip).limit(limit)
    users = (await session.exec(query)).fetchall()
    total_count = (await session.exec(count_query)).first()

    return UsersResponse(
        total_count=total_count,
        users=[UserRead(**user.model_dump()) for user in users],
    )


@router.patch("/{user_id}", response_model=UserRead)
async def patch_user(
    user_id: UUID,
    user_update: UserUpdate,
    user: CurrentActiveUser,
    session: DbSession,
) -> User:
    """Update an existing user's data."""
    update_password = bool(user_update.password)
    is_platform_admin = actor_can_administer_platform(user)

    # Prevent users from deactivating their own account to avoid lockout
    if user.id == user_id and user_update.is_active is False:
        await _audit_deny(
            user_id=user.id,
            action="user:update",
            obj=f"user:{user_id}",
            status_code=403,
            reason="self_deactivation_forbidden",
        )
        raise HTTPException(status_code=403, detail="You can't deactivate your own user account")

    if not is_platform_admin and user_update.is_superuser:
        await _audit_deny(
            user_id=user.id,
            action="user:update",
            obj=f"user:{user_id}",
            status_code=403,
            reason="superuser_required",
        )
        raise HTTPException(status_code=403, detail="Permission denied")

    if not is_platform_admin and user.id != user_id:
        await _audit_deny(
            user_id=user.id,
            action="user:update",
            obj=f"user:{user_id}",
            status_code=403,
            reason="cross_user_update_forbidden",
        )
        raise HTTPException(status_code=403, detail="Permission denied")
    if update_password:
        if not is_platform_admin:
            await _audit_deny(
                user_id=user.id,
                action="user:update",
                obj=f"user:{user_id}",
                status_code=400,
                reason="password_update_forbidden",
            )
            raise HTTPException(status_code=400, detail="You can't change your password here")
        user_update.password = get_auth_service().get_password_hash(user_update.password)

    authorization_service = get_authorization_service()
    # Pre-read lock hint; canonical user state may produce a different staged kind.
    possible_lifecycle_kind: AuthorizationMutationKind | None = None
    if user_update.is_active is not None:
        possible_lifecycle_kind = (
            AuthorizationMutationKind.USER_ENABLED if user_update.is_active else AuthorizationMutationKind.USER_DISABLED
        )
    elif user_update.is_superuser is not None:
        possible_lifecycle_kind = (
            AuthorizationMutationKind.USER_SUPERUSER_PROMOTED
            if user_update.is_superuser
            else AuthorizationMutationKind.USER_SUPERUSER_DEMOTED
        )
    lifecycle_lock_context: UserTeamLifecycleLockContext | None = None
    if possible_lifecycle_kind is not None:

        async def acquire_lifecycle_locks(_attempt: int) -> UserTeamLifecycleLockContext:
            hint = await prepare_user_team_lifecycle_lock_hint(session, user_id=user_id)
            await acquire_identity_mutation_lock(
                authorization_service,
                session,
                kind=possible_lifecycle_kind,
                entity_id=user_id,
                affected_user_ids=hint.affected_user_ids,
            )
            return await acquire_user_team_lifecycle_locks(session, user_id=user_id, hint=hint)

        try:
            lifecycle_lock_context = await run_with_lock_retry(
                acquire_lifecycle_locks,
                session=session,
                description=f"prepare user lifecycle update {user_id}",
            )
        except TeamManagementError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    else:

        async def acquire_update_lock(_attempt: int) -> None:
            await authorization_service.acquire_resource_mutation_lock(session=session)

        await run_with_lock_retry(acquire_update_lock, session=session, description=f"prepare user update {user_id}")

    # Authentication precedes the writer lock. A concurrent demotion or disable
    # must take effect before this request can update another identity.
    actor = await load_mutation_actor(session, user.id)
    if not actor_can_administer_platform(actor) and (user.id != user_id or user_update.is_superuser or update_password):
        await _audit_deny(
            user_id=user.id,
            action="user:update",
            obj=f"user:{user_id}",
            status_code=403,
            reason="platform_authority_revoked",
            session=session,
        )
        raise HTTPException(status_code=403, detail="Permission denied")

    user_db = (
        lifecycle_lock_context.users.get(user_id)
        if lifecycle_lock_context is not None
        else (await session.exec(select(User).where(User.id == user_id))).first()
    )
    if user_db is not None:
        lifecycle_mutation: AuthorizationMutation | None = None
        team_lifecycle = UserTeamLifecycleResult((), (), (), ())
        fields_changed = sorted(
            field
            for field in user_update.model_fields_set
            if field != "password"
            and getattr(user_update, field) is not None
            and getattr(user_db, field, None) != getattr(user_update, field)
        )
        next_is_active = user_db.is_active if user_update.is_active is None else user_update.is_active
        next_is_superuser = user_db.is_superuser if user_update.is_superuser is None else user_update.is_superuser
        if user_db.is_active and not next_is_active:
            lifecycle_kind = AuthorizationMutationKind.USER_DISABLED
        elif not user_db.is_active and next_is_active:
            lifecycle_kind = AuthorizationMutationKind.USER_ENABLED
        elif user_db.is_superuser and not next_is_superuser:
            lifecycle_kind = AuthorizationMutationKind.USER_SUPERUSER_DEMOTED
        elif not user_db.is_superuser and next_is_superuser:
            lifecycle_kind = AuthorizationMutationKind.USER_SUPERUSER_PROMOTED
        else:
            lifecycle_kind = None

        if lifecycle_kind is not None:
            policy_relevant_fields = tuple(
                field
                for field, before, after in (
                    ("is_active", user_db.is_active, next_is_active),
                    ("is_superuser", user_db.is_superuser, next_is_superuser),
                )
                if before != after
            )
            lifecycle_mutation = AuthorizationMutation(
                kind=lifecycle_kind,
                entity_id=user_db.id,
                actor_user_id=user.id,
                affected_user_ids=(user_db.id,),
                policy_relevant_fields=policy_relevant_fields,
                user_before=UserAuthorizationSnapshot(
                    is_active=user_db.is_active,
                    is_superuser=user_db.is_superuser,
                ),
                user_after=UserAuthorizationSnapshot(
                    is_active=next_is_active,
                    is_superuser=next_is_superuser,
                ),
            )
            try:
                await validate_identity_mutation(authorization_service, session, lifecycle_mutation)
            except AuthorizationMutationRejected as exc:
                raise HTTPException(status_code=409, detail=exc.public_detail) from exc

        if not update_password:
            user_update.password = user_db.password
        try:
            updated_user = await update_user(user_db, user_update, session)
        except HTTPException as exc:
            await _audit_deny(
                user_id=user.id,
                action="user:update",
                obj=f"user:{user_id}",
                status_code=exc.status_code,
                reason="update_rejected",
                session=session,
            )
            raise
        if lifecycle_mutation is not None and lifecycle_mutation.kind is AuthorizationMutationKind.USER_DISABLED:
            if lifecycle_lock_context is None:
                msg = "user lifecycle locks were not acquired"
                raise RuntimeError(msg)
            team_lifecycle = await apply_user_team_lifecycle(
                session,
                actor_id=user.id,
                user_id=user_db.id,
                remove_memberships=False,
                lock_context=lifecycle_lock_context,
            )
        if lifecycle_mutation is not None:
            await stage_identity_mutation(authorization_service, session, lifecycle_mutation)
        audit_details = {
            "event": AUDIT_EVENT_MUTATION,
            "fields_changed": fields_changed,
            "lifecycle_kind": lifecycle_mutation.kind.value if lifecycle_mutation is not None else None,
            "teams_deactivated": [str(team_id) for team_id in team_lifecycle.deactivated_team_ids],
        }
        try:
            audit_staged = stage_audit_decision(
                session=session,
                user_id=user.id,
                action="user:update",
                obj=f"user:{user_db.id}",
                result="allow",
                details=audit_details,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        if lifecycle_mutation is not None:
            await safe_identity_mutation_committed(authorization_service, lifecycle_mutation)
        for team_event in team_lifecycle.events:
            await safe_identity_mutation_committed(authorization_service, team_event)
        if not audit_staged:
            await audit_decision(
                user_id=user.id,
                action="user:update",
                obj=f"user:{user_db.id}",
                result="allow",
                details=audit_details,
            )
        return updated_user
    await _audit_deny(
        user_id=user.id,
        action="user:update",
        obj=f"user:{user_id}",
        status_code=404,
        reason="user_not_found",
        session=session,
    )
    raise HTTPException(status_code=404, detail="User not found")


@router.patch("/{user_id}/reset-password", response_model=UserRead)
async def reset_password(
    user_id: UUID,
    password_reset: PasswordResetRequest,
    user: CurrentActiveUser,
    session: DbSession,
) -> User:
    """Change the current user's password after verifying the existing password."""
    if user_id != user.id:
        raise HTTPException(status_code=404, detail="You can't change another user's password")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    auth = get_auth_service()
    if not auth.verify_password(password_reset.current_password, user.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if auth.verify_password(password_reset.password, user.password):
        raise HTTPException(status_code=400, detail="You can't use your current password")

    new_password = auth.get_password_hash(password_reset.password)
    user.password = new_password

    await session.flush()
    await session.refresh(user)

    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Delete a user from the database."""
    actor_user_id = current_user.id
    if actor_user_id == user_id:
        await _audit_deny(
            user_id=actor_user_id,
            action="user:delete",
            obj=f"user:{user_id}",
            status_code=400,
            reason="self_deletion_forbidden",
        )
        raise HTTPException(status_code=400, detail="You can't delete your own user account")
    if not actor_can_administer_platform(current_user):
        await _audit_deny(
            user_id=actor_user_id,
            action="user:delete",
            obj=f"user:{user_id}",
            status_code=403,
            reason="superuser_required",
        )
        raise HTTPException(status_code=403, detail="Permission denied")

    authorization_service = get_authorization_service()

    async def acquire_lifecycle_locks(_attempt: int) -> UserTeamLifecycleLockContext:
        hint = await prepare_user_team_lifecycle_lock_hint(session, user_id=user_id)
        await acquire_identity_mutation_lock(
            authorization_service,
            session,
            kind=AuthorizationMutationKind.USER_DELETED,
            entity_id=user_id,
            affected_user_ids=hint.affected_user_ids,
        )
        return await acquire_user_team_lifecycle_locks(session, user_id=user_id, hint=hint)

    try:
        lifecycle_lock_context = await run_with_lock_retry(
            acquire_lifecycle_locks,
            session=session,
            description=f"prepare user deletion {user_id}",
        )
    except TeamManagementError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    actor = await load_mutation_actor(session, actor_user_id)
    if not actor_can_administer_platform(actor):
        await _audit_deny(
            user_id=actor_user_id,
            action="user:delete",
            obj=f"user:{user_id}",
            status_code=403,
            reason="platform_authority_revoked",
            session=session,
        )
        raise HTTPException(status_code=403, detail="Permission denied")
    user_db = lifecycle_lock_context.users.get(user_id)
    if not user_db:
        await _audit_deny(
            user_id=actor_user_id,
            action="user:delete",
            obj=f"user:{user_id}",
            status_code=404,
            reason="user_not_found",
            session=session,
        )
        raise HTTPException(status_code=404, detail="User not found")

    impact = await owned_resource_impact(session, user_id=user_id)
    if impact.exists:
        await session.rollback()
        await _audit_deny(
            user_id=actor_user_id,
            action="user:delete",
            obj=f"user:{user_id}",
            status_code=409,
            reason="resource_ownership_requires_disposition",
        )
        raise HTTPException(status_code=409, detail=impact.public_detail())

    lifecycle_mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.USER_DELETED,
        entity_id=user_db.id,
        actor_user_id=actor_user_id,
        affected_user_ids=(user_db.id,),
        policy_relevant_fields=("is_active", "is_superuser"),
        user_before=UserAuthorizationSnapshot(
            is_active=user_db.is_active,
            is_superuser=user_db.is_superuser,
        ),
        user_after=None,
    )
    try:
        await validate_identity_mutation(authorization_service, session, lifecycle_mutation)
    except AuthorizationMutationRejected as exc:
        raise HTTPException(status_code=409, detail=exc.public_detail) from exc

    try:
        team_lifecycle = await apply_user_team_lifecycle(
            session,
            actor_id=actor_user_id,
            user_id=user_id,
            remove_memberships=True,
            lock_context=lifecycle_lock_context,
        )
        # Provider-side deployments are not deleted here. The ownership gate
        # above requires their explicit disposition before account deletion.
        await session.delete(user_db)
        await session.flush()
        await stage_identity_mutation(authorization_service, session, lifecycle_mutation)
        audit_details = {
            "event": AUDIT_EVENT_MUTATION,
            "target_was_active": lifecycle_mutation.user_before.is_active,
            "target_was_superuser": lifecycle_mutation.user_before.is_superuser,
            "teams_deactivated": [str(team_id) for team_id in team_lifecycle.deactivated_team_ids],
            "teams_retired": [str(team_id) for team_id in team_lifecycle.retired_team_ids],
            "recipient_shares_removed": len(team_lifecycle.removed_share_snapshots),
        }
        audit_staged = stage_audit_decision(
            session=session,
            user_id=actor_user_id,
            action="user:delete",
            obj=f"user:{user_id}",
            result="allow",
            details=audit_details,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await safe_identity_mutation_committed(authorization_service, lifecycle_mutation)
    for team_event in team_lifecycle.events:
        await safe_identity_mutation_committed(authorization_service, team_event)
    await safe_share_rules_removed(authorization_service, team_lifecycle.removed_share_snapshots)
    if not audit_staged:
        await audit_decision(
            user_id=actor_user_id,
            action="user:delete",
            obj=f"user:{user_id}",
            result="allow",
            details=audit_details,
        )
    return {"detail": "User deleted"}
