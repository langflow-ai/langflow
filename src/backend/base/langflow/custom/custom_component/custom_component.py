from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, ClassVar, List, Optional, Sequence, Union
from uuid import UUID

import yaml
from cachetools import TTLCache
from langchain_core.documents import Document
from pydantic import BaseModel

from langflow.custom.custom_component.base_component import BaseComponent
from langflow.helpers.flow import list_flows, load_flow, run_flow
from langflow.schema import Data
from langflow.schema.artifact import get_artifact_type
from langflow.schema.dotdict import dotdict
from langflow.schema.log import LoggableType
from langflow.schema.schema import OutputValue
from langflow.services.deps import get_storage_service, get_tracing_service, get_variable_service, session_scope
from langflow.services.storage.service import StorageService
from langflow.services.tracing.schema import Log
from langflow.template.utils import update_frontend_node_with_template_values
from langflow.type_extraction.type_extraction import (
    extract_inner_type_from_generic_alias,
    extract_union_types_from_generic_alias,
)
from langflow.utils import validate

if TYPE_CHECKING:
    from langflow.graph.graph.base import Graph
    from langflow.graph.vertex.base import Vertex
    from langflow.services.storage.service import StorageService
    from langflow.services.tracing.service import TracingService


class CustomComponent(BaseComponent):
    """
    Represents a custom component in Langflow.

    Attributes:
        name (Optional[str]): This attribute helps the frontend apply styles to known components.
        display_name (Optional[str]): The display name of the custom component.
        description (Optional[str]): The description of the custom component.
        code (Optional[str]): The code of the custom component.
        field_config (dict): The field configuration of the custom component.
        code_class_base_inheritance (ClassVar[str]): The base class name for the custom component.
        function_entrypoint_name (ClassVar[str]): The name of the function entrypoint for the custom component.
        function (Optional[Callable]): The function associated with the custom component.
        repr_value (Optional[Any]): The representation value of the custom component.
        user_id (Optional[Union[UUID, str]]): The user ID associated with the custom component.
        status (Optional[Any]): The status of the custom component.
        _tree (Optional[dict]): The code tree of the custom component.
    """

    name: Optional[str] = None
    """The name of the component used to styles. Defaults to None."""
    display_name: Optional[str] = None
    """The display name of the component. Defaults to None."""
    description: Optional[str] = None
    """The description of the component. Defaults to None."""
    icon: Optional[str] = None
    """The icon of the component. It should be an emoji. Defaults to None."""
    is_input: Optional[bool] = None
    """The input state of the component. Defaults to None.
    If True, the component must have a field named 'input_value'."""
    is_output: Optional[bool] = None
    """The output state of the component. Defaults to None.
    If True, the component must have a field named 'input_value'."""
    code: Optional[str] = None
    """The code of the component. Defaults to None."""
    field_config: dict = {}
    """The field configuration of the component. Defaults to an empty dictionary."""
    field_order: Optional[List[str]] = None
    """The field order of the component. Defaults to an empty list."""
    frozen: Optional[bool] = False
    """The default frozen state of the component. Defaults to False."""
    build_parameters: Optional[dict] = None
    """The build parameters of the component. Defaults to None."""
    vertex: Optional["Vertex"] = None
    """The edge target parameter of the component. Defaults to None."""
    code_class_base_inheritance: ClassVar[str] = "CustomComponent"
    function_entrypoint_name: ClassVar[str] = "build"
    function: Optional[Callable] = None
    repr_value: Optional[Any] = ""
    user_id: Optional[Union[UUID, str]] = None
    status: Optional[Any] = None
    """The status of the component. This is displayed on the frontend. Defaults to None."""
    _flows_data: Optional[List[Data]] = None
    _outputs: List[OutputValue] = []
    _logs: List[Log] = []
    _output_logs: dict[str, Log] = {}
    tracing_service: Optional["TracingService"] = None

    def set_attributes(self, parameters: dict):
        pass

    def set_parameters(self, parameters: dict):
        self._parameters = parameters
        self.set_attributes(self._parameters)

    @classmethod
    def initialize(cls, **kwargs):
        user_id = kwargs.pop("user_id", None)
        vertex = kwargs.pop("vertex", None)
        tracing_service = kwargs.pop("tracing_service", get_tracing_service())
        params_copy = kwargs.copy()
        return cls(user_id=user_id, _parameters=params_copy, vertex=vertex, tracing_service=tracing_service)

    @property
    def trace_name(self):
        return f"{self.display_name} ({self.vertex.id})"

    def update_state(self, name: str, value: Any):
        if not self.vertex:
            raise ValueError("Vertex is not set")
        try:
            self.vertex.graph.update_state(name=name, record=value, caller=self.vertex.id)
        except Exception as e:
            raise ValueError(f"Error updating state: {e}")

    def stop(self, output_name: str | None = None):
        if not output_name and self.vertex and len(self.vertex.outputs) == 1:
            output_name = self.vertex.outputs[0]["name"]
        elif not output_name:
            raise ValueError("You must specify an output name to call stop")
        if not self.vertex:
            raise ValueError("Vertex is not set")
        try:
            self.graph.mark_branch(vertex_id=self.vertex.id, output_name=output_name, state="INACTIVE")
        except Exception as e:
            raise ValueError(f"Error stopping {self.display_name}: {e}")

    def append_state(self, name: str, value: Any):
        if not self.vertex:
            raise ValueError("Vertex is not set")
        try:
            self.vertex.graph.append_state(name=name, record=value, caller=self.vertex.id)
        except Exception as e:
            raise ValueError(f"Error appending state: {e}")

    def get_state(self, name: str):
        if not self.vertex:
            raise ValueError("Vertex is not set")
        try:
            return self.vertex.graph.get_state(name=name)
        except Exception as e:
            raise ValueError(f"Error getting state: {e}")

    _tree: Optional[dict] = None

    def __init__(self, **data):
        """
        Initializes a new instance of the CustomComponent class.

        Args:
            **data: Additional keyword arguments to initialize the custom component.
        """
        self.cache = TTLCache(maxsize=1024, ttl=60)
        self._logs = []
        super().__init__(**data)

    @staticmethod
    def resolve_path(path: str) -> str:
        """Resolves the path to an absolute path."""
        if not path:
            return path
        path_object = Path(path)

        if path_object.parts and path_object.parts[0] == "~":
            path_object = path_object.expanduser()
        elif path_object.is_relative_to("."):
            path_object = path_object.resolve()
        return str(path_object)

    def get_full_path(self, path: str) -> str:
        storage_svc: "StorageService" = get_storage_service()

        flow_id, file_name = path.split("/", 1)
        return storage_svc.build_full_path(flow_id, file_name)

    @property
    def graph(self):
        return self.vertex.graph

    def _get_field_order(self):
        return self.field_order or list(self.field_config.keys())

    def custom_repr(self):
        """
        Returns the custom representation of the custom component.

        Returns:
            str: The custom representation of the custom component.
        """
        if self.repr_value == "":
            self.repr_value = self.status
        if isinstance(self.repr_value, dict):
            return yaml.dump(self.repr_value)
        if isinstance(self.repr_value, str):
            return self.repr_value
        if isinstance(self.repr_value, BaseModel) and not isinstance(self.repr_value, Data):
            return str(self.repr_value)
        return self.repr_value

    def build_config(self):
        """
        Builds the configuration for the custom component.

        Returns:
            dict: The configuration for the custom component.
        """
        return self.field_config

    def update_build_config(
        self,
        build_config: dotdict,
        field_value: Any,
        field_name: Optional[str] = None,
    ):
        build_config[field_name] = field_value
        return build_config

    @property
    def tree(self):
        """
        Gets the code tree of the custom component.

        Returns:
            dict: The code tree of the custom component.
        """
        return self.get_code_tree(self.code or "")

    def to_data(self, data: Any, keys: Optional[List[str]] = None, silent_errors: bool = False) -> List[Data]:
        """
        Converts input data into a list of Data objects.

        Args:
            data (Any): The input data to be converted. It can be a single item or a sequence of items.
            If the input data is a Langchain Document, text_key and data_key are ignored.

            keys (List[str], optional): The keys to access the text and data values in each item.
                It should be a list of strings where the first element is the text key and the second element is the data key.
                Defaults to None, in which case the default keys "text" and "data" are used.

        Returns:
            List[Data]: A list of Data objects.

        Raises:
            ValueError: If the input data is not of a valid type or if the specified keys are not found in the data.

        """
        if not keys:
            keys = []
        data_objects = []
        if not isinstance(data, Sequence):
            data = [data]
        for item in data:
            data_dict = {}
            if isinstance(item, Document):
                data_dict = item.metadata
                data_dict["text"] = item.page_content
            elif isinstance(item, BaseModel):
                model_dump = item.model_dump()
                for key in keys:
                    if silent_errors:
                        data_dict[key] = model_dump.get(key, "")
                    else:
                        try:
                            data_dict[key] = model_dump[key]
                        except KeyError:
                            raise ValueError(f"Key {key} not found in {item}")

            elif isinstance(item, str):
                data_dict = {"text": item}
            elif isinstance(item, dict):
                data_dict = item.copy()
            else:
                raise ValueError(f"Invalid data type: {type(item)}")

            data_objects.append(Data(data=data_dict))

        return data_objects

    def create_references_from_data(self, data: List[Data], include_data: bool = False) -> str:
        """
        Create references from a list of data.

        Args:
            data (List[dict]): A list of data, where each record is a dictionary.
            include_data (bool, optional): Whether to include data in the references. Defaults to False.

        Returns:
            str: A string containing the references in markdown format.
        """
        if not data:
            return ""
        markdown_string = "---\n"
        for value in data:
            markdown_string += f"- Text: {value.get_text()}"
            if include_data:
                markdown_string += f" Data: {value.data}"
            markdown_string += "\n"
        return markdown_string

    @property
    def get_function_entrypoint_args(self) -> list:
        """
        Gets the arguments of the function entrypoint for the custom component.

        Returns:
            list: The arguments of the function entrypoint.
        """
        build_method = self.get_method(self.function_entrypoint_name)
        if not build_method:
            return []

        args = build_method["args"]
        for arg in args:
            if not arg.get("type") and arg.get("name") != "self":
                # Set the type to Data
                arg["type"] = "Data"
        return args

    def get_method(self, method_name: str):
        """
        Gets the build method for the custom component.

        Returns:
            dict: The build method for the custom component.
        """
        if not self.code:
            return {}

        component_classes = [
            cls for cls in self.tree["classes"] if "Component" in cls["bases"] or "CustomComponent" in cls["bases"]
        ]
        if not component_classes:
            return {}

        # Assume the first Component class is the one we're interested in
        component_class = component_classes[0]
        build_methods = [method for method in component_class["methods"] if method["name"] == (method_name)]

        return build_methods[0] if build_methods else {}

    @property
    def get_function_entrypoint_return_type(self) -> List[Any]:
        """
        Gets the return type of the function entrypoint for the custom component.

        Returns:
            List[Any]: The return type of the function entrypoint.
        """
        return self.get_method_return_type(self.function_entrypoint_name)

    def get_method_return_type(self, method_name: str):
        build_method = self.get_method(method_name)
        if not build_method or not build_method.get("has_return"):
            return []
        return_type = build_method["return_type"]

        if hasattr(return_type, "__origin__") and return_type.__origin__ in [
            list,
            List,
        ]:
            return_type = extract_inner_type_from_generic_alias(return_type)

        # If the return type is not a Union, then we just return it as a list
        inner_type = return_type[0] if isinstance(return_type, list) else return_type
        if not hasattr(inner_type, "__origin__") or inner_type.__origin__ != Union:
            return return_type if isinstance(return_type, list) else [return_type]
        # If the return type is a Union, then we need to parse it
        return_type = extract_union_types_from_generic_alias(return_type)
        return return_type

    @property
    def get_main_class_name(self):
        """
        Gets the main class name of the custom component.

        Returns:
            str: The main class name of the custom component.
        """
        if not self.code:
            return ""

        base_name = self.code_class_base_inheritance
        method_name = self.function_entrypoint_name

        classes = []
        for item in self.tree.get("classes", []):
            if base_name in item["bases"]:
                method_names = [method["name"] for method in item["methods"]]
                if method_name in method_names:
                    classes.append(item["name"])

        # Get just the first item
        return next(iter(classes), "")

    @property
    def template_config(self):
        """
        Gets the template configuration for the custom component.

        Returns:
            dict: The template configuration for the custom component.
        """
        return self.build_template_config()

    @property
    def variables(self):
        """
        Returns the variable for the current user with the specified name.

        Raises:
            ValueError: If the user id is not set.

        Returns:
            The variable for the current user with the specified name.
        """

        def get_variable(name: str, field: str):
            if hasattr(self, "_user_id") and not self._user_id:
                raise ValueError(f"User id is not set for {self.__class__.__name__}")
            variable_service = get_variable_service()  # Get service instance
            # Retrieve and decrypt the variable by name for the current user
            with session_scope() as session:
                user_id = self._user_id or ""
                return variable_service.get_variable(user_id=user_id, name=name, field=field, session=session)

        return get_variable

    def list_key_names(self):
        """
        Lists the names of the variables for the current user.

        Raises:
            ValueError: If the user id is not set.

        Returns:
            List[str]: The names of the variables for the current user.
        """
        if hasattr(self, "_user_id") and not self._user_id:
            raise ValueError(f"User id is not set for {self.__class__.__name__}")
        variable_service = get_variable_service()

        with session_scope() as session:
            return variable_service.list_variables(user_id=self._user_id, session=session)

    def index(self, value: int = 0):
        """
        Returns a function that returns the value at the given index in the iterable.

        Args:
            value (int): The index value.

        Returns:
            Callable: A function that returns the value at the given index.
        """

        def get_index(iterable: List[Any]):
            return iterable[value] if iterable else iterable

        return get_index

    def get_function(self):
        """
        Gets the function associated with the custom component.

        Returns:
            Callable: The function associated with the custom component.
        """
        return validate.create_function(self.code, self.function_entrypoint_name)

    async def load_flow(self, flow_id: str, tweaks: Optional[dict] = None) -> "Graph":
        if not self._user_id:
            raise ValueError("Session is invalid")
        return await load_flow(user_id=self._user_id, flow_id=flow_id, tweaks=tweaks)

    async def run_flow(
        self,
        inputs: Optional[Union[dict, List[dict]]] = None,
        flow_id: Optional[str] = None,
        flow_name: Optional[str] = None,
        output_type: Optional[str] = None,
        tweaks: Optional[dict] = None,
    ) -> Any:
        return await run_flow(
            inputs=inputs,
            output_type=output_type,
            flow_id=flow_id,
            flow_name=flow_name,
            tweaks=tweaks,
            user_id=self._user_id,
        )

    def list_flows(self) -> List[Data]:
        if not self._user_id:
            raise ValueError("Session is invalid")
        try:
            return list_flows(user_id=self._user_id)
        except Exception as e:
            raise ValueError(f"Error listing flows: {e}")

    def build(self, *args: Any, **kwargs: Any) -> Any:
        """
        Builds the custom component.

        Args:
            *args: The positional arguments.
            **kwargs: The keyword arguments.

        Returns:
            Any: The result of the build process.
        """
        raise NotImplementedError

    def log(self, message: LoggableType | list[LoggableType], name: Optional[str] = None):
        """
        Logs a message.

        Args:
            message (LoggableType | list[LoggableType]): The message to log.
        """
        if name is None:
            name = f"Log {len(self._logs) + 1}"
        log = Log(message=message, type=get_artifact_type(message), name=name)
        self._logs.append(log)
        if self.tracing_service and self.vertex:
            self.tracing_service.add_log(trace_name=self.trace_name, log=log)

    def post_code_processing(self, new_frontend_node: dict, current_frontend_node: dict):
        """
        This function is called after the code validation is done.
        """
        frontend_node = update_frontend_node_with_template_values(
            frontend_node=new_frontend_node, raw_frontend_node=current_frontend_node
        )
        return frontend_node
