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
from langflow.services.auth.utils import get_current_active_superuser, get_current_user_optional
from langflow.services.authorization.lifecycle import (
    safe_identity_mutation_committed,
    stage_identity_mutation,
    validate_identity_mutation,
)
from langflow.services.authorization.utils import audit_decision
from langflow.services.database.models.user.crud import get_user_by_id, update_user
from langflow.services.database.models.user.model import User, UserCreate, UserRead, UserUpdate
from langflow.services.deps import get_auth_service, get_authorization_service, get_settings_service

router = APIRouter(tags=["Users"], prefix="/users")


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
    * Admin "add user" (authenticated active superuser). Always allowed,
      regardless of the sign up settings, so disabling public sign up does not
      break superuser-driven user creation.

    User activation is controlled by the NEW_USER_IS_ACTIVE setting.
    """
    settings_service = get_settings_service()
    auth_settings = settings_service.auth_settings
    # An authenticated active superuser (the admin "add user" flow) may always
    # create users. For every other caller this endpoint is effectively
    # unauthenticated, so refuse it unless public sign up is intended for this
    # deployment. get_current_user_optional returns None for credential-less
    # requests, so the anonymous path can never be promoted to superuser.
    is_superuser_caller = current_user is not None and current_user.is_active and current_user.is_superuser
    if not is_superuser_caller and (auth_settings.AUTO_LOGIN or not auth_settings.ENABLE_SIGNUP):
        raise HTTPException(status_code=403, detail="Public user registration is disabled.")

    new_user = User.model_validate(user, from_attributes=True)
    authorization_service = get_authorization_service()
    try:
        new_user.password = get_auth_service().get_password_hash(user.password)
        new_user.is_active = settings_service.auth_settings.NEW_USER_IS_ACTIVE
        session.add(new_user)
        await session.flush()
        await session.refresh(new_user)
        folder = await get_or_create_default_folder(session, new_user.id)
        if not folder:
            raise HTTPException(status_code=500, detail="Error creating default project")
    except IntegrityError as e:
        await session.rollback()
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
    try:
        await stage_identity_mutation(authorization_service, session, lifecycle_mutation)
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    await safe_identity_mutation_committed(authorization_service, lifecycle_mutation)
    await audit_decision(
        user_id=current_user.id if current_user is not None else new_user.id,
        action="user:create",
        obj=f"user:{new_user.id}",
        result="allow",
        details={"created_by": "admin" if is_superuser_caller else "signup"},
    )
    return new_user


@router.get("/whoami", response_model=UserRead)
async def read_current_user(
    current_user: CurrentActiveUser,
) -> User:
    """Retrieve the current user's data."""
    return current_user


@router.get("/", dependencies=[Depends(get_current_active_superuser)])
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

    # Prevent users from deactivating their own account to avoid lockout
    if user.id == user_id and user_update.is_active is False:
        raise HTTPException(status_code=403, detail="You can't deactivate your own user account")

    if not user.is_superuser and user_update.is_superuser:
        raise HTTPException(status_code=403, detail="Permission denied")

    if not user.is_superuser and user.id != user_id:
        raise HTTPException(status_code=403, detail="Permission denied")
    if update_password:
        if not user.is_superuser:
            raise HTTPException(status_code=400, detail="You can't change your password here")
        user_update.password = get_auth_service().get_password_hash(user_update.password)

    if user_db := await get_user_by_id(session, user_id):
        authorization_service = get_authorization_service()
        lifecycle_mutation: AuthorizationMutation | None = None
        next_is_active = user_db.is_active if user_update.is_active is None else user_update.is_active
        next_is_superuser = user_db.is_superuser if user_update.is_superuser is None else user_update.is_superuser
        if user_db.is_active and not next_is_active:
            lifecycle_kind = AuthorizationMutationKind.USER_DISABLED
        elif user_db.is_superuser and not next_is_superuser:
            lifecycle_kind = AuthorizationMutationKind.USER_SUPERUSER_DEMOTED
        else:
            lifecycle_kind = None

        if lifecycle_kind is not None:
            changed_fields = tuple(
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
                policy_relevant_fields=changed_fields,
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
        updated_user = await update_user(user_db, user_update, session)
        if lifecycle_mutation is not None:
            await stage_identity_mutation(authorization_service, session, lifecycle_mutation)
            await session.commit()
            await safe_identity_mutation_committed(authorization_service, lifecycle_mutation)
            await audit_decision(
                user_id=user.id,
                action=lifecycle_mutation.kind.value.replace(".", ":"),
                obj=f"user:{user_db.id}",
                result="allow",
                details={"fields_changed": list(lifecycle_mutation.policy_relevant_fields)},
            )
        return updated_user
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
    current_user: Annotated[User, Depends(get_current_active_superuser)],
    session: DbSession,
) -> dict:
    """Delete a user from the database."""
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You can't delete your own user account")
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Permission denied")

    stmt = select(User).where(User.id == user_id)
    user_db = (await session.exec(stmt)).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")

    lifecycle_mutation = AuthorizationMutation(
        kind=AuthorizationMutationKind.USER_DELETED,
        entity_id=user_db.id,
        actor_user_id=current_user.id,
        affected_user_ids=(user_db.id,),
        policy_relevant_fields=("is_active", "is_superuser"),
        user_before=UserAuthorizationSnapshot(
            is_active=user_db.is_active,
            is_superuser=user_db.is_superuser,
        ),
        user_after=None,
    )
    authorization_service = get_authorization_service()
    try:
        await validate_identity_mutation(authorization_service, session, lifecycle_mutation)
    except AuthorizationMutationRejected as exc:
        raise HTTPException(status_code=409, detail=exc.public_detail) from exc

    # IMPORTANT:
    # This endpoint intentionally performs a DB-cascade delete only and does
    # not issue provider-side teardown across all user deployments.
    # The trade-off is to avoid destructive bulk deletion of external
    # deployment resources during user deletion.
    await session.delete(user_db)
    await session.flush()
    await stage_identity_mutation(authorization_service, session, lifecycle_mutation)
    await session.commit()
    await safe_identity_mutation_committed(authorization_service, lifecycle_mutation)
    await audit_decision(
        user_id=current_user.id,
        action="user:delete",
        obj=f"user:{user_id}",
        result="allow",
        details={
            "target_was_active": lifecycle_mutation.user_before.is_active,
            "target_was_superuser": lifecycle_mutation.user_before.is_superuser,
        },
    )
    return {"detail": "User deleted"}
