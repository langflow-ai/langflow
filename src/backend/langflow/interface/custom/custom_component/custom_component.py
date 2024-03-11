import operator
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    List,
    Optional,
    Sequence,
    Union,
)
from uuid import UUID

import yaml
from cachetools import TTLCache, cachedmethod
from langchain_core.documents import Document
from pydantic import BaseModel
from sqlmodel import select

from langflow.interface.custom.code_parser.utils import (
    extract_inner_type_from_generic_alias,
    extract_union_types_from_generic_alias,
)
from langflow.interface.custom.custom_component.component import Component
from langflow.schema import Record
from langflow.schema.dotdict import dotdict
from langflow.services.database.models.flow import Flow
from langflow.services.database.utils import session_getter
from langflow.services.deps import (
    get_credential_service,
    get_db_service,
    get_storage_service,
)
from langflow.services.storage.service import StorageService
from langflow.utils import validate

if TYPE_CHECKING:
    from langflow.graph.graph.base import Graph
    from langflow.graph.vertex.base import Vertex


class CustomComponent(Component):
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
    selected_output_type: Optional[str] = None
    """The selected output type of the component. Defaults to None."""
    vertex: Optional["Vertex"] = None
    """The edge target parameter of the component. Defaults to None."""
    code_class_base_inheritance: ClassVar[str] = "CustomComponent"
    function_entrypoint_name: ClassVar[str] = "build"
    function: Optional[Callable] = None
    repr_value: Optional[Any] = ""
    user_id: Optional[Union[UUID, str]] = None
    status: Optional[Any] = None
    """The status of the component. This is displayed on the frontend. Defaults to None."""
    _flows_records: Optional[List[Record]] = None

    def update_state(self, name: str, value: Any):
        if not self.vertex:
            raise ValueError("Vertex is not set")
        try:
            self.vertex.graph.update_state(name=name, record=value, caller=self.vertex.id)
        except Exception as e:
            raise ValueError(f"Error updating state: {e}")

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
        self.cache = TTLCache(maxsize=1024, ttl=60)
        super().__init__(**data)

    @staticmethod
    def resolve_path(path: str) -> str:
        """Resolves the path to an absolute path."""
        path_object = Path(path)
        if path_object.parts[0] == "~":
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
        if self.repr_value == "":
            self.repr_value = self.status
        if isinstance(self.repr_value, dict):
            return yaml.dump(self.repr_value)
        if isinstance(self.repr_value, str):
            return self.repr_value
        return self.repr_value

    def build_config(self):
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
        return self.get_code_tree(self.code or "")

    def to_records(self, data: Any, keys: Optional[List[str]] = None, silent_errors: bool = False) -> List[Record]:
        """
        Converts input data into a list of Record objects.

        Args:
            data (Any): The input data to be converted. It can be a single item or a sequence of items.
            If the input data is a Langchain Document, text_key and data_key are ignored.

            keys (List[str], optional): The keys to access the text and data values in each item.
                It should be a list of strings where the first element is the text key and the second element is the data key.
                Defaults to None, in which case the default keys "text" and "data" are used.

        Returns:
            List[Record]: A list of Record objects.

        Raises:
            ValueError: If the input data is not of a valid type or if the specified keys are not found in the data.

        """
        if not keys:
            keys = []
        records = []
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

            records.append(Record(data=data_dict))

        return records

    def create_references_from_records(self, records: List[Record], include_data: bool = False) -> str:
        """
        Create references from a list of records.

        Args:
            records (List[dict]): A list of records, where each record is a dictionary.
            include_data (bool, optional): Whether to include data in the references. Defaults to False.

        Returns:
            str: A string containing the references in markdown format.
        """
        if not records:
            return ""
        markdown_string = "---\n"
        for record in records:
            markdown_string += f"- Text: {record.text}"
            if include_data:
                markdown_string += f" Data: {record.data}"
            markdown_string += "\n"
        return markdown_string

    @property
    def get_function_entrypoint_args(self) -> list:
        build_method = self.get_build_method()
        if not build_method:
            return []

        args = build_method["args"]
        for arg in args:
            if not arg.get("type") and arg.get("name") != "self":
                # Set the type to Data
                arg["type"] = "Data"
        return args

    @cachedmethod(operator.attrgetter("cache"))
    def get_build_method(self):
        if not self.code:
            return {}

        component_classes = [cls for cls in self.tree["classes"] if self.code_class_base_inheritance in cls["bases"]]
        if not component_classes:
            return {}

        # Assume the first Component class is the one we're interested in
        component_class = component_classes[0]
        build_methods = [
            method for method in component_class["methods"] if method["name"] == self.function_entrypoint_name
        ]

        return build_methods[0] if build_methods else {}

    @property
    def get_function_entrypoint_return_type(self) -> List[Any]:
        build_method = self.get_build_method()
        if not build_method or not build_method.get("has_return"):
            return []
        return_type = build_method["return_type"]

        # If list or List is in the return type, then we remove it and return the inner type
        if hasattr(return_type, "__origin__") and return_type.__origin__ in [
            list,
            List,
        ]:
            return_type = extract_inner_type_from_generic_alias(return_type)

        # If the return type is not a Union, then we just return it as a list
        if not hasattr(return_type, "__origin__") or return_type.__origin__ != Union:
            return return_type if isinstance(return_type, list) else [return_type]
        # If the return type is a Union, then we need to parse itx
        return_type = extract_union_types_from_generic_alias(return_type)
        return return_type

    @property
    def get_main_class_name(self):
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
        return self.build_template_config()

    @property
    def keys(self):
        def get_credential(name: str):
            if hasattr(self, "_user_id") and not self._user_id:
                raise ValueError(f"User id is not set for {self.__class__.__name__}")
            credential_service = get_credential_service()  # Get service instance
            # Retrieve and decrypt the credential by name for the current user
            db_service = get_db_service()
            with session_getter(db_service) as session:
                return credential_service.get_credential(user_id=self._user_id or "", name=name, session=session)

        return get_credential

    def list_key_names(self):
        if hasattr(self, "_user_id") and not self._user_id:
            raise ValueError(f"User id is not set for {self.__class__.__name__}")
        credential_service = get_credential_service()
        db_service = get_db_service()
        with session_getter(db_service) as session:
            return credential_service.list_credentials(user_id=self._user_id, session=session)

    def index(self, value: int = 0):
        """Returns a function that returns the value at the given index in the iterable."""

        def get_index(iterable: List[Any]):
            return iterable[value] if iterable else iterable

        return get_index

    def get_function(self):
        return validate.create_function(self.code, self.function_entrypoint_name)

    async def load_flow(self, flow_id: str, tweaks: Optional[dict] = None) -> "Graph":
        from langflow.graph.graph.base import Graph
        from langflow.processing.process import process_tweaks

        db_service = get_db_service()
        with session_getter(db_service) as session:
            graph_data = flow.data if (flow := session.get(Flow, flow_id)) else None
        if not graph_data:
            raise ValueError(f"Flow {flow_id} not found")
        if tweaks:
            graph_data = process_tweaks(graph_data=graph_data, tweaks=tweaks)
        graph = Graph.from_payload(graph_data, flow_id=flow_id)
        return graph

    async def run_flow(
        self,
        input_value: Union[str, list[str]],
        flow_id: Optional[str] = None,
        flow_name: Optional[str] = None,
        tweaks: Optional[dict] = None,
    ) -> Any:
        if not flow_id and not flow_name:
            raise ValueError("Flow ID or Flow Name is required")
        if not self._flows_records:
            self.list_flows()
        if not flow_id and self._flows_records:
            flow_ids = [flow.data["id"] for flow in self._flows_records if flow.data["name"] == flow_name]
            if not flow_ids:
                raise ValueError(f"Flow {flow_name} not found")
            elif len(flow_ids) > 1:
                raise ValueError(f"Multiple flows found with the name {flow_name}")
            flow_id = flow_ids[0]

        if not flow_id:
            raise ValueError(f"Flow {flow_name} not found")
        if isinstance(input_value, str):
            input_value = [input_value]
        graph = await self.load_flow(flow_id, tweaks)
        input_value_dict = [{"input_value": input_val} for input_val in input_value]
        return await graph.run(input_value_dict, stream=False)

    def list_flows(self, *, get_session: Optional[Callable] = None) -> List[Record]:
        if not self._user_id:
            raise ValueError("Session is invalid")
        try:
            get_session = get_session or session_getter
            db_service = get_db_service()
            with get_session(db_service) as session:
                flows = session.exec(
                    select(Flow).where(Flow.user_id == self._user_id).where(Flow.is_component == False)  # noqa
                ).all()

            flows_records = [flow.to_record() for flow in flows]
            self._flows_records = flows_records
            return flows_records
        except Exception as e:
            raise ValueError(f"Error listing flows: {e}")

    def build(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError
