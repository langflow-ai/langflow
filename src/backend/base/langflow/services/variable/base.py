import abc
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.base import Service
from langflow.services.database.models.variable.model import Variable, VariableRead


class VariableService(Service):
    """Abstract base class for a variable service."""

    name = "variable_service"

    @abc.abstractmethod
    async def initialize_user_variables(self, user_id: UUID | str, session: AsyncSession) -> None:
        """Initialize user variables.

        Args:
            user_id: The user ID.
            session: The database session.
        """

    @abc.abstractmethod
    async def get_variable(self, user_id: UUID | str, name: str, field: str, session: AsyncSession) -> str:
        """Async get a variable value.

        Args:
            user_id: The user ID.
            name: The name of the variable.
            field: The field of the variable.
            session: The database session.

        Returns:
            The value of the variable.
        """

    @abc.abstractmethod
    async def list_variables(self, user_id: UUID | str, session: AsyncSession) -> list[str | None]:
        """List all variables.

        Args:
            user_id: The user ID.
            session: The database session.

        Returns:
            A list of variable names.
        """

    @abc.abstractmethod
    async def update_variable(self, user_id: UUID | str, name: str, value: str, session: AsyncSession) -> Variable:
        """Update a variable.

        Args:
            user_id: The user ID.
            name: The name of the variable.
            value: The value of the variable.
            session: The database session.

        Returns:
            The updated variable.
        """

    @abc.abstractmethod
    async def delete_variable(self, user_id: UUID | str, name: str, session: AsyncSession) -> None:
        """Delete a variable.

        Args:
            user_id: The user ID.
            name: The name of the variable.
            session: The database session.

        Returns:
            The deleted variable.
        """

    @abc.abstractmethod
    async def delete_variable_by_id(self, user_id: UUID | str, variable_id: UUID, session: AsyncSession) -> None:
        """Delete a variable by ID.

        Args:
            user_id: The user ID.
            variable_id: The ID of the variable.
            session: The database session.
        """

    @abc.abstractmethod
    async def create_variable(
        self,
        user_id: UUID | str,
        name: str,
        value: str,
        *,
        default_fields: list[str],
        type_: str,
        session: AsyncSession,
    ) -> Variable:
        """Create a variable.

        Args:
            user_id: The user ID.
            name: The name of the variable.
            value: The value of the variable.
            default_fields: The default fields of the variable.
            type_: The type of the variable.
            session: The database session.

        Returns:
            The created variable.
        """

    @abc.abstractmethod
    async def get_all(self, user_id: UUID | str, session: AsyncSession) -> list[VariableRead]:
        """Get all variables.

        Args:
            user_id: The user ID.
            session: The database session.
        """
