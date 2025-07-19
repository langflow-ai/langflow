from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import yaml
from cachetools import TTLCache
from langchain_core.documents import Document
from pydantic import BaseModel

from langflow.custom.custom_component.base_component import BaseComponent
from langflow.helpers.flow import list_flows, load_flow, run_flow
from langflow.schema.data import Data
from langflow.services.deps import get_storage_service, get_variable_service, session_scope
from langflow.services.storage.service import StorageService
from langflow.template.utils import update_frontend_node_with_template_values
from langflow.type_extraction.type_extraction import post_process_type
from langflow.utils import validate
from langflow.utils.async_helpers import run_until_complete

if TYPE_CHECKING:
    from langchain.callbacks.base import BaseCallbackHandler
    from lfx.graph.graph.base import Graph
    from lfx.graph.vertex.base import Vertex

    from langflow.schema.dotdict import dotdict
    from langflow.schema.schema import OutputValue
    from langflow.services.storage.service import StorageService
    from langflow.services.tracing.schema import Log
    from langflow.services.tracing.service import TracingService


class CustomComponent(BaseComponent):
    """Represents a custom component in Langflow.

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

    # True constants that should be shared (using ClassVar)
    _code_class_base_inheritance: ClassVar[str] = "CustomComponent"
    function_entrypoint_name: ClassVar[str] = "build"
    name: str | None = None
    """The name of the component used to styles. Defaults to None."""
    display_name: str | None = None
    """The display name of the component. Defaults to None."""
    description: str | None = None
    """The description of the component. Defaults to None."""
    icon: str | None = None
    """The icon of the component. It should be an emoji. Defaults to None."""
    priority: int | None = None
    """The priority of the component in the category. Lower priority means it will be displayed first. Defaults to None.
    """

    def __init__(self, **data) -> None:
        """Initializes a new instance of the CustomComponent class.

        Args:
            **data: Additional keyword arguments to initialize the custom component.
        """
        # Initialize instance-specific attributes first
        self.is_input: bool | None = None
        self.is_output: bool | None = None
        self.add_tool_output: bool = False
        self.field_config: dict = {}
        self.field_order: list[str] | None = None
        self.frozen: bool = False
        self.build_parameters: dict | None = None
        self._vertex: Vertex | None = None
        self.function: Callable | None = None
        self.repr_value: Any = ""
        self.status: Any | None = None

        # Initialize collections with empty defaults
        self._flows_data: list[Data] | None = None
        self._outputs: list[OutputValue] = []
        self._logs: list[Log] = []
        self._output_logs: dict[str, list[Log] | Log] = {}
        self._tracing_service: TracingService | None = None
        self._tree: dict | None = None

        # Initialize additional instance state
        self.cache: TTLCache = TTLCache(maxsize=1024, ttl=60)
        self._results: dict = {}
        self._artifacts: dict = {}

        # Call parent's init after setting up our attributes
        super().__init__(**data)

    def set_attributes(self, parameters: dict) -> None:
        pass

    def set_parameters(self, parameters: dict) -> None:
        self._parameters = parameters
        self.set_attributes(self._parameters)

    @property
    def trace_name(self) -> str:
        if hasattr(self, "_id") and self._id is None:
            msg = "Component id is not set"
            raise ValueError(msg)
        if hasattr(self, "_id"):
            return f"{self.display_name} ({self._id})"
        return f"{self.display_name}"

    def stop(self, output_name: str | None = None) -> None:
        if not output_name and self._vertex and len(self._vertex.outputs) == 1:
            output_name = self._vertex.outputs[0]["name"]
        elif not output_name:
            msg = "You must specify an output name to call stop"
            raise ValueError(msg)
        if not self._vertex:
            msg = "Vertex is not set"
            raise ValueError(msg)
        try:
            self.graph.mark_branch(vertex_id=self._vertex.id, output_name=output_name, state="INACTIVE")
        except Exception as e:
            msg = f"Error stopping {self.display_name}: {e}"
            raise ValueError(msg) from e

    def start(self, output_name: str | None = None) -> None:
        if not output_name and self._vertex and len(self._vertex.outputs) == 1:
            output_name = self._vertex.outputs[0]["name"]
        elif not output_name:
            msg = "You must specify an output name to call start"
            raise ValueError(msg)
        if not self._vertex:
            msg = "Vertex is not set"
            raise ValueError(msg)
        try:
            self.graph.mark_branch(vertex_id=self._vertex.id, output_name=output_name, state="ACTIVE")
        except Exception as e:
            msg = f"Error starting {self.display_name}: {e}"
            raise ValueError(msg) from e

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
        storage_svc: StorageService = get_storage_service()

        flow_id, file_name = path.split("/", 1)
        return storage_svc.build_full_path(flow_id, file_name)

    @property
    def graph(self):
        return self._vertex.graph

    @property
    def user_id(self):
        if hasattr(self, "_user_id") and self._user_id:
            return self._user_id
        return self.graph.user_id

    @property
    def flow_id(self):
        return self.graph.flow_id

    @property
    def flow_name(self):
        return self.graph.flow_name

    def _get_field_order(self):
        return self.field_order or list(self.field_config.keys())

    def custom_repr(self):
        """Returns the custom representation of the custom component.

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
        """Builds the configuration for the custom component.

        Returns:
            dict: The configuration for the custom component.
        """
        return self.field_config

    def update_build_config(
        self,
        build_config: dotdict,
        field_value: Any,
        field_name: str | None = None,
    ):
        """Updates the build configuration for the custom component.

        Do not call directly as implementation can be a coroutine.
        """
        build_config[field_name]["value"] = field_value
        return build_config

    @property
    def tree(self):
        """Gets the code tree of the custom component.

        Returns:
            dict: The code tree of the custom component.
        """
        return self.get_code_tree(self._code or "")

    def to_data(self, data: Any, *, keys: list[str] | None = None, silent_errors: bool = False) -> list[Data]:
        """Converts input data into a list of Data objects.

        Args:
            data (Any): The input data to be converted. It can be a single item or a sequence of items.
                If the input data is a Langchain Document, text_key and data_key are ignored.

            keys (List[str], optional): The keys to access the text and data values in each item.
                It should be a list of strings where the first element is the text key and the second element
                is the data key.
                Defaults to None, in which case the default keys "text" and "data" are used.
            silent_errors (bool, optional): Whether to suppress errors when the specified keys are not found
                in the data.

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
                        except KeyError as e:
                            msg = f"Key {key} not found in {item}"
                            raise ValueError(msg) from e

            elif isinstance(item, str):
                data_dict = {"text": item}
            elif isinstance(item, dict):
                data_dict = item.copy()
            else:
                msg = f"Invalid data type: {type(item)}"
                raise TypeError(msg)

            data_objects.append(Data(data=data_dict))

        return data_objects

    def get_method_return_type(self, method_name: str):
        build_method = self.get_method(method_name)
        if not build_method or not build_method.get("has_return"):
            return []
        return_type = build_method["return_type"]

        return self._extract_return_type(return_type)

    def create_references_from_data(self, data: list[Data], *, include_data: bool = False) -> str:
        """Create references from a list of data.

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
        """Gets the arguments of the function entrypoint for the custom component.

        Returns:
            list: The arguments of the function entrypoint.
        """
        build_method = self.get_method(self._function_entrypoint_name)
        if not build_method:
            return []

        args = build_method["args"]
        for arg in args:
            if not arg.get("type") and arg.get("name") != "self":
                # Set the type to Data
                arg["type"] = "Data"
        return args

    def get_method(self, method_name: str):
        """Gets the build method for the custom component.

        Returns:
            dict: The build method for the custom component.
        """
        if not self._code:
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
    def _get_function_entrypoint_return_type(self) -> list[Any]:
        """Gets the return type of the function entrypoint for the custom component.

        Returns:
            List[Any]: The return type of the function entrypoint.
        """
        return self.get_method_return_type(self._function_entrypoint_name)

    def _extract_return_type(self, return_type: Any) -> list[Any]:
        return post_process_type(return_type)

    @property
    def get_main_class_name(self):
        """Gets the main class name of the custom component.

        Returns:
            str: The main class name of the custom component.
        """
        if not self._code:
            return ""

        base_name = self._code_class_base_inheritance
        method_name = self._function_entrypoint_name

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
        """Gets the template configuration for the custom component.

        Returns:
            dict: The template configuration for the custom component.
        """
        if not self._template_config:
            self._template_config = self.build_template_config()
        return self._template_config

    def variables(self, name: str, field: str):
        """DEPRECATED - This is kept for backward compatibility. Use get_variables instead."""
        return run_until_complete(self.get_variables(name, field))

    async def get_variables(self, name: str, field: str):
        """DEPRECATED - This is kept for backward compatibility. Use get_variable instead."""
        async with session_scope() as session:
            return await self.get_variable(name, field, session)

    async def get_variable(self, name: str, field: str, session):
        """Returns the variable for the current user with the specified name.

        Raises:
            ValueError: If the user id is not set.

        Returns:
            The variable for the current user with the specified name.
        """
        if hasattr(self, "_user_id") and not self.user_id:
            msg = f"User id is not set for {self.__class__.__name__}"
            raise ValueError(msg)
        variable_service = get_variable_service()  # Get service instance
        # Retrieve and decrypt the variable by name for the current user
        if isinstance(self.user_id, str):
            user_id = uuid.UUID(self.user_id)
        elif isinstance(self.user_id, uuid.UUID):
            user_id = self.user_id
        else:
            msg = f"Invalid user id: {self.user_id}"
            raise TypeError(msg)
        return await variable_service.get_variable(user_id=user_id, name=name, field=field, session=session)

    async def list_key_names(self):
        """Lists the names of the variables for the current user.

        Raises:
            ValueError: If the user id is not set.

        Returns:
            List[str]: The names of the variables for the current user.
        """
        if hasattr(self, "_user_id") and not self.user_id:
            msg = f"User id is not set for {self.__class__.__name__}"
            raise ValueError(msg)
        variable_service = get_variable_service()

        async with session_scope() as session:
            return await variable_service.list_variables(user_id=self.user_id, session=session)

    def index(self, value: int = 0):
        """Returns a function that returns the value at the given index in the iterable.

        Args:
            value (int): The index value.

        Returns:
            Callable: A function that returns the value at the given index.
        """

        def get_index(iterable: list[Any]):
            return iterable[value] if iterable else iterable

        return get_index

    def get_function(self):
        """Gets the function associated with the custom component.

        Returns:
            Callable: The function associated with the custom component.
        """
        return validate.create_function(self._code, self._function_entrypoint_name)

    async def load_flow(self, flow_id: str, tweaks: dict | None = None) -> Graph:
        if not self.user_id:
            msg = "Session is invalid"
            raise ValueError(msg)
        return await load_flow(user_id=str(self.user_id), flow_id=flow_id, tweaks=tweaks)

    async def run_flow(
        self,
        inputs: dict | list[dict] | None = None,
        flow_id: str | None = None,
        flow_name: str | None = None,
        output_type: str | None = "chat",
        tweaks: dict | None = None,
    ) -> Any:
        return await run_flow(
            inputs=inputs,
            output_type=output_type,
            flow_id=flow_id,
            flow_name=flow_name,
            tweaks=tweaks,
            user_id=str(self.user_id),
            run_id=self.graph.run_id,
        )

    def list_flows(self) -> list[Data]:
        """DEPRECATED - This is kept for backward compatibility. Using alist_flows instead is recommended."""
        return run_until_complete(self.alist_flows())

    async def alist_flows(self) -> list[Data]:
        if not self.user_id:
            msg = "Session is invalid"
            raise ValueError(msg)
        try:
            return await list_flows(user_id=str(self.user_id))
        except Exception as e:
            msg = f"Error listing flows: {e}"
            raise ValueError(msg) from e

    def build(self, *args: Any, **kwargs: Any) -> Any:
        """Builds the custom component.

        Args:
            *args: The positional arguments.
            **kwargs: The keyword arguments.

        Returns:
            Any: The result of the build process.
        """
        raise NotImplementedError

    def post_code_processing(self, new_frontend_node: dict, current_frontend_node: dict):
        """DEPRECATED - Kept for backward compatibility. Use update_frontend_node instead."""
        run_until_complete(self.update_frontend_node(new_frontend_node, current_frontend_node))

    async def update_frontend_node(self, new_frontend_node: dict, current_frontend_node: dict):
        """Updates the given new frontend node with values from the current frontend node.

        This function is called after the code validation is done.
        """
        return update_frontend_node_with_template_values(
            frontend_node=new_frontend_node, raw_frontend_node=current_frontend_node
        )

    def get_langchain_callbacks(self) -> list[BaseCallbackHandler]:
        if self._tracing_service:
            return self._tracing_service.get_langchain_callbacks()
        return []
