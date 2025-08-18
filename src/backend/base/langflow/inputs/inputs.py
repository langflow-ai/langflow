import warnings
from collections.abc import AsyncIterator, Iterator
from typing import Any, TypeAlias, get_args

from pandas import DataFrame
from pydantic import Field, field_validator, model_validator

from langflow.inputs.validators import CoalesceBool
from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.services.database.models.message.model import MessageBase
from langflow.template.field.base import Input

from .input_mixin import (
    AuthMixin,
    BaseInputMixin,
    ConnectionMixin,
    DatabaseLoadMixin,
    DropDownMixin,
    FieldTypes,
    FileMixin,
    InputTraceMixin,
    LinkMixin,
    ListableInputMixin,
    MetadataTraceMixin,
    MultilineMixin,
    QueryMixin,
    RangeMixin,
    SerializableFieldTypes,
    SliderMixin,
    SortableListMixin,
    TableMixin,
    TabMixin,
    ToolModeMixin,
)


class TableInput(BaseInputMixin, MetadataTraceMixin, TableMixin, ListableInputMixin, ToolModeMixin):
    field_type: SerializableFieldTypes = FieldTypes.TABLE
    is_list: bool = True

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, _info):
        # Convert single dict or Data instance into a list.
        if isinstance(v, dict | Data):
            v = [v]
        # Automatically convert DataFrame into a list of dictionaries.
        if isinstance(v, DataFrame):
            v = v.to_dict(orient="records")
        # Verify the value is now a list.
        if not isinstance(v, list):
            msg = (
                "The table input must be a list of rows. You provided a "
                f"{type(v).__name__}, which cannot be converted to table format. "
                "Please provide your data as either:\n"
                "- A list of dictionaries (each dict is a row)\n"
                "- A pandas DataFrame\n"
                "- A single dictionary (will become a one-row table)\n"
                "- A Data object (Langflow's internal data structure)\n"
            )
            raise ValueError(msg)  # noqa: TRY004
        # Ensure each item in the list is either a dict or a Data instance.
        for i, item in enumerate(v):
            if not isinstance(item, dict | Data):
                msg = (
                    f"Row {i + 1} in your table has an invalid format. Each row must be either:\n"
                    "- A dictionary containing column name/value pairs\n"
                    "- A Data object (Langflow's internal data structure for passing data between components)\n"
                    f"Instead, got a {type(item).__name__}. Please check the format of your input data."
                )
                raise ValueError(msg)  # noqa: TRY004
        return v


class HandleInput(BaseInputMixin, ListableInputMixin, MetadataTraceMixin):
    """Represents an Input that has a Handle to a specific type (e.g. BaseLanguageModel, BaseRetriever, etc.).

    This class inherits from the `BaseInputMixin` and `ListableInputMixin` classes.

    Attributes:
        input_types (list[str]): A list of input types.
        field_type (SerializableFieldTypes): The field type of the input.
    """

    input_types: list[str] = Field(default_factory=list)
    field_type: SerializableFieldTypes = FieldTypes.OTHER


class ToolsInput(BaseInputMixin, ListableInputMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents an Input that contains a list of tools to activate, deactivate, or edit.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input.
        value (list[dict]): The value of the input.

    """

    field_type: SerializableFieldTypes = FieldTypes.TOOLS
    value: list[dict] = Field(default_factory=list)
    is_list: bool = True
    real_time_refresh: bool = True


class DataInput(HandleInput, InputTraceMixin, ListableInputMixin, ToolModeMixin):
    """Represents an Input that has a Handle that receives a Data object.

    Attributes:
        input_types (list[str]): A list of input types supported by this data input.
    """

    input_types: list[str] = ["Data"]


class DataFrameInput(HandleInput, InputTraceMixin, ListableInputMixin, ToolModeMixin):
    input_types: list[str] = ["DataFrame"]


class PromptInput(BaseInputMixin, ListableInputMixin, InputTraceMixin, ToolModeMixin):
    field_type: SerializableFieldTypes = FieldTypes.PROMPT


class CodeInput(BaseInputMixin, ListableInputMixin, InputTraceMixin, ToolModeMixin):
    field_type: SerializableFieldTypes = FieldTypes.CODE


# Applying mixins to a specific input type
class StrInput(
    BaseInputMixin,
    ListableInputMixin,
    DatabaseLoadMixin,
    MetadataTraceMixin,
    ToolModeMixin,
):
    field_type: SerializableFieldTypes = FieldTypes.TEXT
    load_from_db: CoalesceBool = False
    """Defines if the field will allow the user to open a text editor. Default is False."""

    @staticmethod
    def _validate_value(v: Any, info):
        """Validates the given value and returns the processed value.

        Args:
            v (Any): The value to be validated.
            info: Additional information about the input.

        Returns:
            The processed value.

        Raises:
            ValueError: If the value is not of a valid type or if the input is missing a required key.
        """
        if not isinstance(v, str) and v is not None:
            # Keep the warning for now, but we should change it to an error
            if info.data.get("input_types") and v.__class__.__name__ not in info.data.get("input_types"):
                warnings.warn(
                    f"Invalid value type {type(v)} for input {info.data.get('name')}. "
                    f"Expected types: {info.data.get('input_types')}",
                    stacklevel=4,
                )
            else:
                warnings.warn(
                    f"Invalid value type {type(v)} for input {info.data.get('name')}.",
                    stacklevel=4,
                )
        return v

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, info):
        """Validates the given value and returns the processed value.

        Args:
            v (Any): The value to be validated.
            info: Additional information about the input.

        Returns:
            The processed value.

        Raises:
            ValueError: If the value is not of a valid type or if the input is missing a required key.
        """
        is_list = info.data["is_list"]
        return [cls._validate_value(vv, info) for vv in v] if is_list else cls._validate_value(v, info)


class MessageInput(StrInput, InputTraceMixin):
    input_types: list[str] = ["Message"]

    @staticmethod
    def _validate_value(v: Any, _info):
        # If v is a instance of Message, then its fine
        if isinstance(v, dict):
            return Message(**v)
        if isinstance(v, Message):
            return v
        if isinstance(v, str | AsyncIterator | Iterator):
            return Message(text=v)
        if isinstance(v, MessageBase):
            return Message(**v.model_dump())
        msg = f"Invalid value type {type(v)}"
        raise ValueError(msg)


class MessageTextInput(StrInput, MetadataTraceMixin, InputTraceMixin, ToolModeMixin):
    """Represents a text input component for the Langflow system.

    This component is used to handle text inputs in the Langflow system.
    It provides methods for validating and processing text values.

    Attributes:
        input_types (list[str]): A list of input types that this component supports.
            In this case, it supports the "Message" input type.
    """

    input_types: list[str] = ["Message"]

    @staticmethod
    def _validate_value(v: Any, info):
        """Validates the given value and returns the processed value.

        Args:
            v (Any): The value to be validated.
            info: Additional information about the input.

        Returns:
            The processed value.

        Raises:
            ValueError: If the value is not of a valid type or if the input is missing a required key.
        """
        value: str | AsyncIterator | Iterator | None = None
        if isinstance(v, dict):
            v = Message(**v)
        if isinstance(v, str):
            value = v
        elif isinstance(v, Message):
            value = v.text
        elif isinstance(v, Data):
            if v.text_key in v.data:
                value = v.data[v.text_key]
            else:
                keys = ", ".join(v.data.keys())
                input_name = info.data["name"]
                msg = (
                    f"The input to '{input_name}' must contain the key '{v.text_key}'."
                    f"You can set `text_key` to one of the following keys: {keys} "
                    "or set the value using another Component."
                )
                raise ValueError(msg)
        elif isinstance(v, AsyncIterator | Iterator):
            value = v
        else:
            msg = f"Invalid value type {type(v)}"
            raise ValueError(msg)  # noqa: TRY004
        return value


class MultilineInput(MessageTextInput, MultilineMixin, InputTraceMixin, ToolModeMixin):
    """Represents a multiline input field.

    Attributes:
        field_type (SerializableFieldTypes): The type of the field. Defaults to FieldTypes.TEXT.
        multiline (CoalesceBool): Indicates whether the input field should support multiple lines. Defaults to True.
    """

    field_type: SerializableFieldTypes = FieldTypes.TEXT
    multiline: CoalesceBool = True
    copy_field: CoalesceBool = False


class MultilineSecretInput(MessageTextInput, MultilineMixin, InputTraceMixin):
    """Represents a multiline input field.

    Attributes:
        field_type (SerializableFieldTypes): The type of the field. Defaults to FieldTypes.TEXT.
        multiline (CoalesceBool): Indicates whether the input field should support multiple lines. Defaults to True.
    """

    field_type: SerializableFieldTypes = FieldTypes.PASSWORD
    multiline: CoalesceBool = True
    password: CoalesceBool = Field(default=True)


class SecretStrInput(BaseInputMixin, DatabaseLoadMixin):
    """Represents a field with password field type.

    This class inherits from `BaseInputMixin` and `DatabaseLoadMixin`.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to `FieldTypes.PASSWORD`.
        password (CoalesceBool): A boolean indicating whether the input is a password. Defaults to `True`.
        input_types (list[str]): A list of input types associated with this input. Defaults to an empty list.
    """

    field_type: SerializableFieldTypes = FieldTypes.PASSWORD
    password: CoalesceBool = Field(default=True)
    input_types: list[str] = []
    load_from_db: CoalesceBool = True

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, info):
        """Validates the given value and returns the processed value.

        Args:
            v (Any): The value to be validated.
            info: Additional information about the input.

        Returns:
            The processed value.

        Raises:
            ValueError: If the value is not of a valid type or if the input is missing a required key.
        """
        value: str | AsyncIterator | Iterator | None = None
        if isinstance(v, str):
            value = v
        elif isinstance(v, Message):
            value = v.text
        elif isinstance(v, Data):
            if v.text_key in v.data:
                value = v.data[v.text_key]
            else:
                keys = ", ".join(v.data.keys())
                input_name = info.data["name"]
                msg = (
                    f"The input to '{input_name}' must contain the key '{v.text_key}'."
                    f"You can set `text_key` to one of the following keys: {keys} "
                    "or set the value using another Component."
                )
                raise ValueError(msg)
        elif isinstance(v, AsyncIterator | Iterator):
            value = v
        elif v is None:
            value = None
        else:
            msg = f"Invalid value type `{type(v)}` for input `{info.data['name']}`"
            raise ValueError(msg)
        return value


class IntInput(BaseInputMixin, ListableInputMixin, RangeMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents an integer field.

    This class represents an integer input and provides functionality for handling integer values.
    It inherits from the `BaseInputMixin`, `ListableInputMixin`, and `RangeMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.INTEGER.
    """

    field_type: SerializableFieldTypes = FieldTypes.INTEGER

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, info):
        """Validates the given value and returns the processed value.

        Args:
            v (Any): The value to be validated.
            info: Additional information about the input.

        Returns:
            The processed value.

        Raises:
            ValueError: If the value is not of a valid type or if the input is missing a required key.
        """
        if v and not isinstance(v, int | float):
            msg = f"Invalid value type {type(v)} for input {info.data.get('name')}."
            raise ValueError(msg)
        if isinstance(v, float):
            v = int(v)
        return v


class FloatInput(BaseInputMixin, ListableInputMixin, RangeMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents a float field.

    This class represents a float input and provides functionality for handling float values.
    It inherits from the `BaseInputMixin`, `ListableInputMixin`, and `RangeMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.FLOAT.
    """

    field_type: SerializableFieldTypes = FieldTypes.FLOAT

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, info):
        """Validates the given value and returns the processed value.

        Args:
            v (Any): The value to be validated.
            info: Additional information about the input.

        Returns:
            The processed value.

        Raises:
            ValueError: If the value is not of a valid type or if the input is missing a required key.
        """
        if v and not isinstance(v, int | float):
            msg = f"Invalid value type {type(v)} for input {info.data.get('name')}."
            raise ValueError(msg)
        if isinstance(v, int):
            v = float(v)
        return v


class BoolInput(BaseInputMixin, ListableInputMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents a boolean field.

    This class represents a boolean input and provides functionality for handling boolean values.
    It inherits from the `BaseInputMixin` and `ListableInputMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.BOOLEAN.
        value (CoalesceBool): The value of the boolean input.
    """

    field_type: SerializableFieldTypes = FieldTypes.BOOLEAN
    value: CoalesceBool = False


class NestedDictInput(
    BaseInputMixin,
    ListableInputMixin,
    MetadataTraceMixin,
    InputTraceMixin,
    ToolModeMixin,
):
    """Represents a nested dictionary field.

    This class represents a nested dictionary input and provides functionality for handling dictionary values.
    It inherits from the `BaseInputMixin` and `ListableInputMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.NESTED_DICT.
        value (Optional[dict]): The value of the input. Defaults to an empty dictionary.
    """

    field_type: SerializableFieldTypes = FieldTypes.NESTED_DICT
    value: dict | None = {}


class DictInput(BaseInputMixin, ListableInputMixin, InputTraceMixin, ToolModeMixin):
    """Represents a dictionary field.

    This class represents a dictionary input and provides functionality for handling dictionary values.
    It inherits from the `BaseInputMixin` and `ListableInputMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.DICT.
        value (Optional[dict]): The value of the dictionary input. Defaults to an empty dictionary.
    """

    field_type: SerializableFieldTypes = FieldTypes.DICT
    # value: dict | None = {"key": "value"}
    # Note do not set value to an empty dict, it will break the component in dynamic update build config
    # value: dict | None = {}
    value: dict = Field(default_factory=dict)


class DropdownInput(BaseInputMixin, DropDownMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents a dropdown input field.

    This class represents a dropdown input field and provides functionality for handling dropdown values.
    It inherits from the `BaseInputMixin` and `DropDownMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.TEXT.
        options (Optional[Union[list[str], Callable]]): List of options for the field.
            Default is None.
        options_metadata (Optional[list[dict[str, str]]): List of dictionaries with metadata for each option.
            Default is None.
        combobox (CoalesceBool): Variable that defines if the user can insert custom values in the dropdown.
        toggle (CoalesceBool): Variable that defines if a toggle button is shown.
        toggle_value (CoalesceBool | None): Variable that defines the value of the toggle button. Defaults to None.
    """

    field_type: SerializableFieldTypes = FieldTypes.TEXT
    options: list[str] = Field(default_factory=list)
    options_metadata: list[dict[str, Any]] = Field(default_factory=list)
    combobox: CoalesceBool = False
    dialog_inputs: dict[str, Any] = Field(default_factory=dict)
    toggle: bool = False
    toggle_disable: bool | None = None
    toggle_value: bool | None = None


class ConnectionInput(BaseInputMixin, ConnectionMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents a connection input field.

    This class represents a connection input field and provides functionality for handling connection values.
    It inherits from the `BaseInputMixin` and `ConnectionMixin` classes.

    """

    field_type: SerializableFieldTypes = FieldTypes.CONNECTION


class AuthInput(BaseInputMixin, AuthMixin, MetadataTraceMixin):
    """Represents an authentication input field.

    This class represents an authentication input field and provides functionality for handling authentication values.
    It inherits from the `BaseInputMixin` and `AuthMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.AUTH.
    """

    field_type: SerializableFieldTypes = FieldTypes.AUTH
    show: bool = False


class QueryInput(MessageTextInput, QueryMixin):
    """Represents a query input field.

    This class represents an query input field and provides functionality for handling search values.
    It inherits from the `BaseInputMixin` and `QueryMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.SEARCH.
        separator (str | None): The separator for the query input. Defaults to None.
        value (str): The value for the query input. Defaults to an empty string.
    """

    field_type: SerializableFieldTypes = FieldTypes.QUERY
    separator: str | None = Field(default=None)


class SortableListInput(BaseInputMixin, SortableListMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents a list selection input field.

    This class represents a list selection input field and provides functionality for handling list selection values.
    It inherits from the `BaseInputMixin` and `ListableInputMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.SORTABLE_LIST.
    """

    field_type: SerializableFieldTypes = FieldTypes.SORTABLE_LIST


class TabInput(BaseInputMixin, TabMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents a tab input field.

    This class represents a tab input field that allows a maximum of 3 values, each with a maximum of 20 characters.
    It inherits from the `BaseInputMixin` and `TabMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.TAB.
        options (list[str]): List of tab options. Maximum of 3 values allowed, each with a maximum of 20 characters.
        active_tab (int): Index of the currently active tab. Defaults to 0.
    """

    field_type: SerializableFieldTypes = FieldTypes.TAB
    options: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    @classmethod
    def validate_value(cls, values):
        """Validates the value to ensure it's one of the tab values."""
        options = values.options  # Agora temos certeza de que options está disponível
        value = values.value

        if not isinstance(value, str):
            msg = f"TabInput value must be a string. Got {type(value).__name__}."
            raise TypeError(msg)

        if value not in options and value != "":
            msg = f"TabInput value must be one of the following: {options}. Got: '{value}'"
            raise ValueError(msg)

        return values


class MultiselectInput(BaseInputMixin, ListableInputMixin, DropDownMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents a multiselect input field.

    This class represents a multiselect input field and provides functionality for handling multiselect values.
    It inherits from the `BaseInputMixin`, `ListableInputMixin` and `DropDownMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.TEXT.
        options (Optional[Union[list[str], Callable]]): List of options for the field. Only used when is_list=True.
            Default is None.
    """

    field_type: SerializableFieldTypes = FieldTypes.TEXT
    options: list[str] = Field(default_factory=list)
    is_list: bool = Field(default=True, serialization_alias="list")
    combobox: CoalesceBool = False

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, _info):
        # Check if value is a list of dicts
        if not isinstance(v, list):
            msg = f"MultiselectInput value must be a list. Value: '{v}'"
            raise ValueError(msg)  # noqa: TRY004
        for item in v:
            if not isinstance(item, str):
                msg = f"MultiselectInput value must be a list of strings. Item: '{item}' is not a string"
                raise ValueError(msg)  # noqa: TRY004
        return v


class FileInput(BaseInputMixin, ListableInputMixin, FileMixin, MetadataTraceMixin):
    """Represents a file field.

    This class represents a file input and provides functionality for handling file values.
    It inherits from the `BaseInputMixin`, `ListableInputMixin`, and `FileMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.FILE.
    """

    field_type: SerializableFieldTypes = FieldTypes.FILE


class McpInput(BaseInputMixin, MetadataTraceMixin):
    """Represents a mcp input field.

    This class represents a mcp input and provides functionality for handling mcp values.
    It inherits from the `BaseInputMixin` and `MetadataTraceMixin` classes.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input. Defaults to FieldTypes.MCP.
    """

    field_type: SerializableFieldTypes = FieldTypes.MCP
    value: dict[str, Any] = Field(default_factory=dict)


class LinkInput(BaseInputMixin, LinkMixin):
    field_type: SerializableFieldTypes = FieldTypes.LINK


class SliderInput(BaseInputMixin, RangeMixin, SliderMixin, ToolModeMixin):
    field_type: SerializableFieldTypes = FieldTypes.SLIDER


class ModelInput(BaseInputMixin, SortableListMixin, MetadataTraceMixin, ToolModeMixin):
    """Represents a model input dropdown field with Provider:ModelName format.

    This class provides a unified dropdown interface for selecting language models or embedding models
    with options formatted as "Provider:ModelName" (e.g., "OpenAI:gpt-4o").
    API keys should be passed to the build_model() method from the component.

    Attributes:
        field_type (SerializableFieldTypes): The field type of the input.
        model_type (str): The type of model - either "language" or "embedding".
        options (list[str]): List of available model options in "Provider:ModelName" format.
        value (str): Selected model option in "Provider:ModelName" format.
        temperature (float): Temperature setting for language models.
        max_tokens (int): Maximum tokens for language models.
    """

    field_type: SerializableFieldTypes = FieldTypes.SORTABLE_LIST
    model_type: str = "language"
    options: list[dict[str, Any]] = Field(default_factory=list)
    placeholder: str = "Select a Model"
    value: Any = Field(default_factory=list)
    temperature: float = 0.1
    max_tokens: int = 256
    limit: int = 1  # Only allow single selection
    providers: list[str] = Field(default=["OpenAI", "Anthropic"])
    # TODO: Option to add fields related to API key.
    api_key: str = Field(
        default="",
        description="API key for the selected provider.",
        repr=False,
        json_schema_extra={"input_type": "password"},
    )

    def __init__(self, **kwargs):
        """Initialize ModelInput with default options based on model_type."""
        super().__init__(**kwargs)
        if not self.options:
            self.options = self._get_options_for_model_type(self.model_type)
        if not self.value and self.options:
            self.value = [self.options[0]]  # SortableListInput expects a list

    def _get_language_model_options(self) -> list[dict[str, str]]:
        """Get language model options with Provider:ModelName format and icons."""
        # Use only the providers specified in self.providers
        # TODO: use api to gets models, ability to select providers.
        # OpenAI language models
        from langflow.base.models.unified_models import get_unified_models_detailed

        provider_models = get_unified_models_detailed(
            # provider=self.providers,
            model_type="llm",
            include_unsupported=False,
        )

        # Flatten the provider->models mapping to a single list of model dicts
        options: list[dict[str, str]] = []
        for entry in provider_models:
            provider_name = entry["provider"]
            options.extend(
                {
                    "name": f"{model['model_name']}",
                    "icon": model.get("icon", provider_name.replace(" ", "")),
                    "category": provider_name,
                    "metadata": model.get("metadata", {}),
                    "provider": provider_name,
                }
                for model in entry["models"]
            )

        return options

    def _get_embedding_model_options(self) -> list[dict[str, str]]:
        """Get embedding model options with Provider:ModelName format and icons."""
        # Use only the providers specified in self.providers
        from langflow.base.models.unified_models import get_unified_models_detailed

        provider_models = get_unified_models_detailed(
            # provider=self.providers,
            model_type="embeddings",
            include_unsupported=False,
        )
        options: list[dict[str, str]] = []
        for entry in provider_models:
            provider_name = entry["provider"]
            options.extend(
                {
                    "name": f"{model['model_name']}",
                    "icon": model.get("icon", provider_name),
                    "category": provider_name,
                    "metadata": model.get("metadata", {}),
                    "provider": provider_name,
                }
                for model in entry["models"]
            )
        return options

    def _get_options_for_model_type(self, model_type: str) -> list[dict[str, str]]:
        """Get options based on model type."""
        if model_type == "language":
            return self._get_language_model_options()
        if model_type == "embedding":
            return self._get_embedding_model_options()
        return self._get_language_model_options()  # Default to language models


    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any, _info):
        """Validates the model input value."""
        # Handle different input formats for SortableListInput
        if isinstance(v, list):
            return v  # Already a list, good for SortableListInput
        if isinstance(v, str):
            # Handle backward compatibility - convert string to list format
            if v and ":" in v:
                return [{"name": v, "icon": ""}]  # Convert string to list format
            return []
        if v is None:
            return []
        # Try to convert other types to list
        return [{"name": str(v), "icon": ""}]

    def build_model(self, api_key: str = "", **kwargs) -> Any | None:
        """Build and return the configured model instance based on selection.

        Args:
            api_key: API key (should be passed from component)
            **kwargs: Additional parameters to pass to the model

        Returns:
            Language model instance for language models, Embedding model instance for embedding models.
        """
        # Extract the selected model from the list (SortableListInput returns a list)
        if not self.value or not isinstance(self.value, list) or not self.value:
            return None

        selected_item = self.value[0]

        model_name = selected_item.get("name", "")
        provider = selected_item.get("provider", "")
        provider = provider.strip()
        model_name = model_name.strip()

        if not provider or not model_name:
            return None

        if not api_key:
            return None

        if self.model_type == "language":
            return self._build_language_model(provider, model_name, api_key, **kwargs)
        if self.model_type == "embedding":
            return self._build_embedding_model(provider, model_name, api_key, **kwargs)
        return None

    def _build_language_model(self, provider: str, model_name: str, api_key: str, **kwargs) -> Any | None:
        """Build a language model instance."""
        try:
            if not api_key:
                return None

            # Use provided kwargs or instance attributes for model parameters
            temperature = kwargs.get("temperature", self.temperature)
            max_tokens = kwargs.get("max_tokens", self.max_tokens)

            if provider == "OpenAI":
                from langchain_openai import ChatOpenAI

                return ChatOpenAI(
                    openai_api_key=api_key,
                    model_name=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            if provider == "Anthropic":
                from langchain_anthropic import ChatAnthropic

                return ChatAnthropic(
                    anthropic_api_key=api_key,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            if provider == "Google Generative AI":
                from langchain_google_genai import ChatGoogleGenerativeAI

                return ChatGoogleGenerativeAI(
                    google_api_key=api_key,
                    model=model_name,
                    temperature=temperature,
                )
        except ImportError:
            # If the required package is not installed, return None
            pass
        return None

    def _build_embedding_model(self, provider: str, model_name: str, api_key: str, **_kwargs) -> Any | None:
        """Build an embedding model instance."""
        try:
            if not api_key:
                return None

            if provider == "OpenAI":
                from langchain_openai import OpenAIEmbeddings

                return OpenAIEmbeddings(
                    openai_api_key=api_key,
                    model=model_name,
                )
        except ImportError:
            # If the required package is not installed, return None
            pass
        return None


DEFAULT_PROMPT_INTUT_TYPES = ["Message"]


class DefaultPromptField(Input):
    name: str
    display_name: str | None = None
    field_type: str = "str"
    advanced: bool = False
    multiline: bool = True
    input_types: list[str] = DEFAULT_PROMPT_INTUT_TYPES
    value: Any = ""  # Set the value to empty string


InputTypes: TypeAlias = (
    Input
    | AuthInput
    | QueryInput
    | DefaultPromptField
    | BoolInput
    | DataInput
    | DictInput
    | DropdownInput
    | MultiselectInput
    | SortableListInput
    | ConnectionInput
    | FileInput
    | FloatInput
    | HandleInput
    | IntInput
    | McpInput
    | ModelInput
    | MultilineInput
    | MultilineSecretInput
    | NestedDictInput
    | ToolsInput
    | PromptInput
    | CodeInput
    | SecretStrInput
    | StrInput
    | MessageTextInput
    | MessageInput
    | TableInput
    | LinkInput
    | SliderInput
    | DataFrameInput
    | TabInput
)

InputTypesMap: dict[str, type[InputTypes]] = {t.__name__: t for t in get_args(InputTypes)}


def instantiate_input(input_type: str, data: dict) -> InputTypes:
    input_type_class = InputTypesMap.get(input_type)
    if "type" in data:
        # Replate with field_type
        data["field_type"] = data.pop("type")
    if input_type_class:
        return input_type_class(**data)
    msg = f"Invalid input type: {input_type}"
    raise ValueError(msg)
