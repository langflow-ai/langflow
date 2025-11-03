"""Unified CRUD operations layer for database models.

This module provides a centralized interface for all database operations,
decoupling database models from API and component code. This enables:
1. Consistent database access patterns across the codebase
2. Easier testing through mockable interfaces
3. Future pluggable services layer support

Usage:
    from langflow.services.database.crud import message_crud, flow_crud

    # Get a message
    message = await message_crud.get(session, message_id)

    # Create a message
    new_message = await message_crud.create(session, message_data)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Generic, TypeVar
from uuid import UUID

from sqlmodel import col, delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from langflow.services.database.models.message.model import MessageCreate, MessageRead, MessageUpdate

# Type variables for generic CRUD operations
ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")
ReadSchemaType = TypeVar("ReadSchemaType")


class BaseCRUD(Generic[ModelType, CreateSchemaType, UpdateSchemaType, ReadSchemaType]):
    """Base class for CRUD operations on database models.

    This provides common database operations for any model type.
    Specific model operations can extend this base class.
    """

    def __init__(self, model: type[ModelType]):
        """Initialize CRUD handler with a specific model type.

        Args:
            model: The SQLModel table class to perform operations on
        """
        self.model = model

    async def get(self, session: AsyncSession, id: UUID | str) -> ModelType | None:
        """Get a single record by ID.

        Args:
            session: Database session
            id: Record ID (UUID or string)

        Returns:
            Model instance or None if not found
        """
        if isinstance(id, str):
            id = UUID(id)
        return await session.get(self.model, id)

    async def get_multi(
        self,
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        **filters: Any,
    ) -> list[ModelType]:
        """Get multiple records with optional filtering.

        Args:
            session: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Field name to order by
            **filters: Field filters (field_name=value)

        Returns:
            List of model instances
        """
        stmt = select(self.model)

        # Apply filters
        for field, value in filters.items():
            if hasattr(self.model, field):
                stmt = stmt.where(getattr(self.model, field) == value)

        # Apply ordering
        if order_by and hasattr(self.model, order_by):
            stmt = stmt.order_by(getattr(self.model, order_by))

        # Apply pagination
        stmt = stmt.offset(skip).limit(limit)

        result = await session.exec(stmt)
        return list(result.all())

    async def create(self, session: AsyncSession, *, obj_in: CreateSchemaType | dict) -> ModelType:
        """Create a new record.

        Args:
            session: Database session
            obj_in: Creation schema or dict with field values

        Returns:
            Created model instance
        """
        if isinstance(obj_in, dict):
            db_obj = self.model(**obj_in)
        else:
            db_obj = self.model(**obj_in.model_dump())

        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def update(
        self,
        session: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | dict,
    ) -> ModelType:
        """Update an existing record.

        Args:
            session: Database session
            db_obj: Existing model instance
            obj_in: Update schema or dict with field values

        Returns:
            Updated model instance
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True, exclude_none=True)

        if hasattr(db_obj, "sqlmodel_update"):
            db_obj.sqlmodel_update(update_data)
        else:
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)

        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def delete(self, session: AsyncSession, *, id: UUID | str) -> None:
        """Delete a record by ID.

        Args:
            session: Database session
            id: Record ID (UUID or string)

        Raises:
            ValueError: If record not found
        """
        if isinstance(id, str):
            id = UUID(id)

        db_obj = await session.get(self.model, id)
        if db_obj is None:
            msg = f"{self.model.__name__} not found"
            raise ValueError(msg)

        await session.delete(db_obj)
        await session.commit()

    async def delete_multi(self, session: AsyncSession, *, ids: list[UUID]) -> None:
        """Delete multiple records by IDs.

        Args:
            session: Database session
            ids: List of record IDs
        """
        stmt = delete(self.model).where(self.model.id.in_(ids))  # type: ignore[attr-defined]
        await session.exec(stmt)
        await session.commit()


class MessageCRUD(BaseCRUD):
    """CRUD operations for Message model."""

    async def get_by_session_id(
        self,
        session: AsyncSession,
        session_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: str = "timestamp",
    ) -> list[ModelType]:
        """Get messages by session ID.

        Args:
            session: Database session
            session_id: Session identifier
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Field to order by (default: timestamp)

        Returns:
            List of message instances
        """
        stmt = select(self.model).where(self.model.session_id == session_id)  # type: ignore[attr-defined]

        if order_by and hasattr(self.model, order_by):
            stmt = stmt.order_by(getattr(self.model, order_by).asc())

        stmt = stmt.offset(skip).limit(limit)
        result = await session.exec(stmt)
        return list(result.all())

    async def get_by_flow_id(
        self,
        session: AsyncSession,
        flow_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: str = "timestamp",
    ) -> list[ModelType]:
        """Get messages by flow ID.

        Args:
            session: Database session
            flow_id: Flow identifier
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Field to order by (default: timestamp)

        Returns:
            List of message instances
        """
        stmt = select(self.model).where(self.model.flow_id == flow_id)  # type: ignore[attr-defined]

        if order_by and hasattr(self.model, order_by):
            stmt = stmt.order_by(getattr(self.model, order_by).asc())

        stmt = stmt.offset(skip).limit(limit)
        result = await session.exec(stmt)
        return list(result.all())

    async def get_sessions(
        self,
        session: AsyncSession,
        *,
        flow_id: UUID | None = None,
    ) -> list[str]:
        """Get distinct session IDs, optionally filtered by flow ID.

        Args:
            session: Database session
            flow_id: Optional flow ID filter

        Returns:
            List of session ID strings
        """
        stmt = select(self.model.session_id).distinct()  # type: ignore[attr-defined]
        stmt = stmt.where(col(self.model.session_id).isnot(None))  # type: ignore[attr-defined]

        if flow_id:
            stmt = stmt.where(self.model.flow_id == flow_id)  # type: ignore[attr-defined]

        result = await session.exec(stmt)
        return list(result.all())

    async def delete_by_session_id(self, session: AsyncSession, session_id: str) -> None:
        """Delete all messages for a session.

        Note: This does not commit the transaction. The caller is responsible for committing.

        Args:
            session: Database session
            session_id: Session identifier
        """
        stmt = (
            delete(self.model)
            .where(col(self.model.session_id) == session_id)  # type: ignore[attr-defined]
            .execution_options(synchronize_session="fetch")
        )
        await session.exec(stmt)

    async def delete_by_flow_id(self, session: AsyncSession, flow_id: UUID) -> None:
        """Delete all messages for a flow.

        Note: This does not commit the transaction. The caller is responsible for committing.

        Args:
            session: Database session
            flow_id: Flow identifier
        """
        stmt = delete(self.model).where(self.model.flow_id == flow_id)  # type: ignore[attr-defined]
        await session.exec(stmt)


class TransactionCRUD(BaseCRUD):
    """CRUD operations for Transaction model."""

    async def get_by_flow_id(
        self,
        session: AsyncSession,
        flow_id: UUID,
        *,
        skip: int = 0,
        limit: int = 1000,
    ) -> list[ModelType]:
        """Get transactions by flow ID.

        Args:
            session: Database session
            flow_id: Flow identifier
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of transaction instances
        """
        stmt = (
            select(self.model)
            .where(self.model.flow_id == flow_id)  # type: ignore[attr-defined]
            .order_by(col(self.model.timestamp))  # type: ignore[attr-defined]
            .offset(skip)
            .limit(limit)
        )
        result = await session.exec(stmt)
        return list(result.all())

    async def delete_by_flow_id(self, session: AsyncSession, flow_id: UUID) -> None:
        """Delete all transactions for a flow.

        Note: This does not commit the transaction. The caller is responsible for committing.

        Args:
            session: Database session
            flow_id: Flow identifier
        """
        stmt = delete(self.model).where(self.model.flow_id == flow_id)  # type: ignore[attr-defined]
        await session.exec(stmt)


class VertexBuildCRUD(BaseCRUD):
    """CRUD operations for VertexBuild model."""

    async def get_by_flow_id(
        self,
        session: AsyncSession,
        flow_id: UUID,
        *,
        limit: int = 1000,
    ) -> list[ModelType]:
        """Get vertex builds by flow ID.

        Args:
            session: Database session
            flow_id: Flow identifier
            limit: Maximum number of builds to return

        Returns:
            List of vertex build instances
        """
        if isinstance(flow_id, str):
            flow_id = UUID(flow_id)

        subquery = (
            select(self.model.id, func.max(self.model.timestamp).label("max_timestamp"))  # type: ignore[attr-defined]
            .where(self.model.flow_id == flow_id)  # type: ignore[attr-defined]
            .group_by(self.model.id)  # type: ignore[attr-defined]
            .subquery()
        )

        stmt = (
            select(self.model)
            .join(
                subquery,
                (self.model.id == subquery.c.id) & (self.model.timestamp == subquery.c.max_timestamp),  # type: ignore[attr-defined]
            )
            .where(self.model.flow_id == flow_id)  # type: ignore[attr-defined]
            .order_by(col(self.model.timestamp))  # type: ignore[attr-defined]
            .limit(limit)
        )

        result = await session.exec(stmt)
        return list(result.all())

    async def delete_by_flow_id(self, session: AsyncSession, flow_id: UUID) -> None:
        """Delete all vertex builds for a flow.

        Note: This does not commit the transaction. The caller is responsible for committing.

        Args:
            session: Database session
            flow_id: Flow identifier
        """
        stmt = delete(self.model).where(self.model.flow_id == flow_id)  # type: ignore[attr-defined]
        await session.exec(stmt)


class FlowCRUD(BaseCRUD):
    """CRUD operations for Flow model."""

    async def get_by_endpoint_name(self, session: AsyncSession, endpoint_name: str) -> ModelType | None:
        """Get flow by endpoint name.

        Args:
            session: Database session
            endpoint_name: Endpoint name

        Returns:
            Flow instance or None if not found
        """
        stmt = select(self.model).where(self.model.endpoint_name == endpoint_name)  # type: ignore[attr-defined]
        result = await session.exec(stmt)
        return result.first()

    async def get_by_user_id(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """Get flows by user ID.

        Args:
            session: Database session
            user_id: User identifier
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of flow instances
        """
        stmt = select(self.model).where(self.model.user_id == user_id).offset(skip).limit(limit)  # type: ignore[attr-defined]
        result = await session.exec(stmt)
        return list(result.all())


class UserCRUD(BaseCRUD):
    """CRUD operations for User model."""

    async def get_by_username(self, session: AsyncSession, username: str) -> ModelType | None:
        """Get user by username.

        Args:
            session: Database session
            username: Username

        Returns:
            User instance or None if not found
        """
        stmt = select(self.model).where(self.model.username == username)  # type: ignore[attr-defined]
        result = await session.exec(stmt)
        return result.first()

    async def get_superusers(self, session: AsyncSession) -> list[ModelType]:
        """Get all superuser accounts.

        Args:
            session: Database session

        Returns:
            List of superuser instances
        """
        stmt = select(self.model).where(self.model.is_superuser == True)  # type: ignore[attr-defined]  # noqa: E712
        result = await session.exec(stmt)
        return list(result.all())

    async def update_last_login(self, session: AsyncSession, user_id: UUID) -> ModelType | None:
        """Update user's last login timestamp.

        Args:
            session: Database session
            user_id: User identifier

        Returns:
            Updated user instance or None if not found
        """
        user = await self.get(session, user_id)
        if user is None:
            return None

        user.last_login_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


class ApiKeyCRUD(BaseCRUD):
    """CRUD operations for ApiKey model."""

    async def get_by_user_id(self, session: AsyncSession, user_id: UUID) -> list[ModelType]:
        """Get API keys by user ID.

        Args:
            session: Database session
            user_id: User identifier

        Returns:
            List of API key instances
        """
        stmt = select(self.model).where(self.model.user_id == user_id)  # type: ignore[attr-defined]
        result = await session.exec(stmt)
        return list(result.all())

    async def get_by_key(self, session: AsyncSession, api_key: str) -> ModelType | None:
        """Get API key by key value.

        Args:
            session: Database session
            api_key: API key string

        Returns:
            API key instance or None if not found
        """
        stmt = select(self.model).where(self.model.api_key == api_key)  # type: ignore[attr-defined]
        result = await session.exec(stmt)
        return result.first()


class VariableCRUD(BaseCRUD):
    """CRUD operations for Variable model."""

    async def get_by_user_id(self, session: AsyncSession, user_id: UUID) -> list[ModelType]:
        """Get variables by user ID.

        Args:
            session: Database session
            user_id: User identifier

        Returns:
            List of variable instances
        """
        stmt = select(self.model).where(self.model.user_id == user_id)  # type: ignore[attr-defined]
        result = await session.exec(stmt)
        return list(result.all())

    async def get_by_name(
        self,
        session: AsyncSession,
        user_id: UUID,
        name: str,
    ) -> ModelType | None:
        """Get variable by name and user ID.

        Args:
            session: Database session
            user_id: User identifier
            name: Variable name

        Returns:
            Variable instance or None if not found
        """
        stmt = (
            select(self.model)
            .where(self.model.user_id == user_id)  # type: ignore[attr-defined]
            .where(self.model.name == name)  # type: ignore[attr-defined]
        )
        result = await session.exec(stmt)
        return result.first()


class FileCRUD(BaseCRUD):
    """CRUD operations for File model."""

    async def get_by_flow_id(
        self,
        session: AsyncSession,
        flow_id: UUID,
    ) -> list[ModelType]:
        """Get files by flow ID.

        Args:
            session: Database session
            flow_id: Flow identifier

        Returns:
            List of file instances
        """
        stmt = select(self.model).where(self.model.flow_id == flow_id)  # type: ignore[attr-defined]
        result = await session.exec(stmt)
        return list(result.all())


class FolderCRUD(BaseCRUD):
    """CRUD operations for Folder model."""

    async def get_by_user_id(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """Get folders by user ID.

        Args:
            session: Database session
            user_id: User identifier
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of folder instances
        """
        stmt = select(self.model).where(self.model.user_id == user_id).offset(skip).limit(limit)  # type: ignore[attr-defined]
        result = await session.exec(stmt)
        return list(result.all())


# Initialize CRUD instances
# Import models lazily to avoid circular imports
def _get_message_crud():
    from langflow.services.database.models.message.model import MessageTable

    return MessageCRUD(MessageTable)


def _get_transaction_crud():
    from langflow.services.database.models.transactions.model import TransactionTable

    return TransactionCRUD(TransactionTable)


def _get_vertex_build_crud():
    from langflow.services.database.models.vertex_builds.model import VertexBuildTable

    return VertexBuildCRUD(VertexBuildTable)


def _get_flow_crud():
    from langflow.services.database.models.flow.model import Flow

    return FlowCRUD(Flow)


def _get_user_crud():
    from langflow.services.database.models.user.model import User

    return UserCRUD(User)


def _get_api_key_crud():
    from langflow.services.database.models.api_key.model import ApiKey

    return ApiKeyCRUD(ApiKey)


def _get_variable_crud():
    from langflow.services.database.models.variable.model import Variable

    return VariableCRUD(Variable)


def _get_file_crud():
    from langflow.services.database.models.file.model import File

    return FileCRUD(File)


def _get_folder_crud():
    from langflow.services.database.models.folder.model import Folder

    return FolderCRUD(Folder)


# Singleton instances
message_crud = _get_message_crud()
transaction_crud = _get_transaction_crud()
vertex_build_crud = _get_vertex_build_crud()
flow_crud = _get_flow_crud()
user_crud = _get_user_crud()
api_key_crud = _get_api_key_crud()
variable_crud = _get_variable_crud()
file_crud = _get_file_crud()
folder_crud = _get_folder_crud()

__all__ = [
    "BaseCRUD",
    "MessageCRUD",
    "TransactionCRUD",
    "VertexBuildCRUD",
    "FlowCRUD",
    "UserCRUD",
    "ApiKeyCRUD",
    "VariableCRUD",
    "FileCRUD",
    "FolderCRUD",
    "message_crud",
    "transaction_crud",
    "vertex_build_crud",
    "flow_crud",
    "user_crud",
    "api_key_crud",
    "variable_crud",
    "file_crud",
    "folder_crud",
]
