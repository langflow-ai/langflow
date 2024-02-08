# Create an enum with the following categories:
# - Inputs / Outputs
# - Data
# - Language Models
from enum import Enum

from langflow.template.category.schema import CategorySchema


class Category(str, Enum):
    """The category of the Component."""

    INPUTS_OUTPUTS = "Inputs / Outputs"
    """Inputs / Outputs"""

    DATA = "Data"
    """Data"""

    LANGUAGE_MODELS = "Language Models"
    """Language Models"""

    OTHER = "Other"
    """Other"""


class InputsOutputsCategorySchema(CategorySchema):
    name: str = Category.INPUTS_OUTPUTS.value
    description: str = "Components related to data input and output processes."
    icon: str = "shuffle"  # Lucide icon name for inputs/outputs
    color: str = "#F0E68C"  # Khaki


class DataCategorySchema(CategorySchema):
    name: str = Category.DATA.value
    description: str = "Components focused on data manipulation and storage."
    icon: str = "database"  # Lucide icon name for data
    color: str = "#87CEEB"  # SkyBlue


class LanguageModelsCategorySchema(CategorySchema):
    name: str = Category.LANGUAGE_MODELS.value
    description: str = "Components that utilize or integrate language models."
    icon: str = "message-circle"  # Lucide icon name for language models
    color: str = "#FFB6C1"  # LightPink


class OtherCategorySchema(CategorySchema):
    name: str = "Other"
    description: str = "Components that do not fit or are not categorized in the other categories."
    icon: str = "package"  # Lucide icon name for other
    color: str = "#D3D3D3"  # LightGrey


categories = [
    InputsOutputsCategorySchema(),
    DataCategorySchema(),
    LanguageModelsCategorySchema(),
    OtherCategorySchema(),
]
