import abc
from typing import Optional, Union
from uuid import UUID

from sqlmodel import Session

from langflow.services.base import Service
from langflow.services.database.models.variable.model import Variable


class VariableService(Service):
    """
    Abstract base class for a variable service.
    """

    name = "variable_service"

    @abc.abstractmethod
    def initialize_user_variables(self, user_id: Union[UUID, str], session: Session) -> None:
        """
        Initialize user variables.

        Args:
            user_id: The user ID.
            session: The database session.
        """

    @abc.abstractmethod
    def get_variable(self, user_id: Union[UUID, str], name: str, field: str, session: Session) -> str:
        """
        Get a variable value.

        Args:
            user_id: The user ID.
            name: The name of the variable.
            field: The field of the variable.
            session: The database session.

        Returns:
            The value of the variable.
        """

    @abc.abstractmethod
    def list_variables(self, user_id: Union[UUID, str], session: Session) -> list[Optional[str]]:
        """
        List all variables.

        Args:
            user_id: The user ID.
            session: The database session.

        Returns:
            A list of variable names.
        """

    @abc.abstractmethod
    def update_variable(self, user_id: Union[UUID, str], name: str, value: str, session: Session) -> Variable:
        """
        Update a variable.

        Args:
            user_id: The user ID.
            name: The name of the variable.
            value: The value of the variable.
            session: The database session.

        Returns:
            The updated variable.
        """

    @abc.abstractmethod
    def delete_variable(self, user_id: Union[UUID, str], name: str, session: Session) -> Variable:
        """
        Delete a variable.

        Args:
            user_id: The user ID.
            name: The name of the variable.
            session: The database session.

        Returns:
            The deleted variable.
        """

    @abc.abstractmethod
    def create_variable(
        self,
        user_id: Union[UUID, str],
        name: str,
        value: str,
        default_fields: list[str],
        _type: str,
        session: Session,
    ) -> Variable:
        """
        Create a variable.

        Args:
            user_id: The user ID.
            name: The name of the variable.
            value: The value of the variable.
            default_fields: The default fields of the variable.
            _type: The type of the variable.
            session: The database session.

        Returns:
            The created variable.
        """
