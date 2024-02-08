import abc

from pydantic import BaseModel


# Create a base class that is abstract
class CategorySchema(BaseModel, abc.ABC):
    name: str
    """The name of the category."""

    description: str = ""
    """The description of the category. Default is an empty string."""

    icon: str = ""
    """The icon of the category. Default is an empty string."""

    color: str = ""
    """The color of the category. Default is an empty string."""
