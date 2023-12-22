import operator
from typing import Any, Callable, ClassVar, List, Optional, Union
from uuid import UUID

import yaml
from cachetools import TTLCache, cachedmethod
from fastapi import HTTPException

from langflow.interface.custom.code_parser.utils import (
    extract_inner_type_from_generic_alias,
    extract_union_types_from_generic_alias,
)
from langflow.services.database.models.flow import Flow
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_credential_service, get_db_service
from langflow.utils import validate

from .component import Component


class CustomComponent(Component):
    display_name: Optional[str] = None
    description: Optional[str] = None
    code: Optional[str] = None
    field_config: dict = {}
    code_class_base_inheritance: ClassVar[str] = "CustomComponent"
    function_entrypoint_name: ClassVar[str] = "build"
    function: Optional[Callable] = None
    repr_value: Optional[Any] = ""
    user_id: Optional[Union[UUID, str]] = None
    status: Optional[Any] = None
    _tree: Optional[dict] = None

    def __init__(self, **data):
        self.cache = TTLCache(maxsize=1024, ttl=60)
        super().__init__(**data)

    def custom_repr(self):
        if self.repr_value == "":
            self.repr_value = self.status
        if isinstance(self.repr_value, dict):
            return yaml.dump(self.repr_value)
        if isinstance(self.repr_value, str):
            return self.repr_value
        return str(self.repr_value)

    def build_config(self):
        return self.field_config

    @property
    def tree(self):
        return self.get_code_tree(self.code or "")

    @property
    def get_function_entrypoint_args(self) -> list:
        build_method = self.get_build_method()
        if not build_method:
            return []

        args = build_method["args"]
        for arg in args:
            if arg.get("type") == "prompt":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Type hint Error",
                        "traceback": (
                            "Prompt type is not supported in the build method." " Try using PromptTemplate instead."
                        ),
                    },
                )
            elif not arg.get("type") and arg.get("name") != "self":
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
        if hasattr(return_type, "__origin__") and return_type.__origin__ in [list, List]:
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

    def build_template_config(self):
        if not self.code:
            return {}

        attributes = [
            main_class["attributes"]
            for main_class in self.tree.get("classes", [])
            if main_class["name"] == self.get_main_class_name
        ]
        # Get just the first item
        attributes = next(iter(attributes), [])

        return super().build_template_config(attributes)

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

    @property
    def get_function(self):
        return validate.create_function(self.code, self.function_entrypoint_name)

    async def load_flow(self, flow_id: str, tweaks: Optional[dict] = None) -> Any:
        from langflow.processing.process import build_sorted_vertices, process_tweaks

        db_service = get_db_service()
        with session_getter(db_service) as session:
            graph_data = flow.data if (flow := session.get(Flow, flow_id)) else None
        if not graph_data:
            raise ValueError(f"Flow {flow_id} not found")
        if tweaks:
            graph_data = process_tweaks(graph_data=graph_data, tweaks=tweaks)
        return await build_sorted_vertices(graph_data, self.user_id)

    def list_flows(self, *, get_session: Optional[Callable] = None) -> List[Flow]:
        if not self._user_id:
            raise ValueError("Session is invalid")
        try:
            get_session = get_session or session_getter
            db_service = get_db_service()
            with get_session(db_service) as session:
                flows = session.query(Flow).filter(Flow.user_id == self.user_id).all()
            return flows
        except Exception as e:
            raise ValueError("Session is invalid") from e

    async def get_flow(
        self,
        *,
        flow_name: Optional[str] = None,
        flow_id: Optional[str] = None,
        tweaks: Optional[dict] = None,
        get_session: Optional[Callable] = None,
    ) -> Flow:
        get_session = get_session or session_getter
        db_service = get_db_service()
        with get_session(db_service) as session:
            if flow_id:
                flow = session.query(Flow).get(flow_id)
            elif flow_name:
                flow = (session.query(Flow).filter(Flow.name == flow_name).filter(Flow.user_id == self.user_id)).first()
            else:
                raise ValueError("Either flow_name or flow_id must be provided")

        if not flow:
            raise ValueError(f"Flow {flow_name or flow_id} not found")
        return await self.load_flow(flow.id, tweaks)

    def build(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError
