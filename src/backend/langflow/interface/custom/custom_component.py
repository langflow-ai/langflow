from typing import Any, Callable, List, Optional, Union
from uuid import UUID
from fastapi import HTTPException
from langflow.interface.custom.constants import CUSTOM_COMPONENT_SUPPORTED_TYPES
from langflow.interface.custom.component import Component
from langflow.interface.custom.directory_reader import DirectoryReader
from langflow.services.getters import get_db_service
from langflow.interface.custom.utils import extract_inner_type

from langflow.utils import validate

from langflow.services.database.utils import session_getter
from langflow.services.database.models.flow import Flow
from pydantic import Extra
import yaml


class CustomComponent(Component, extra=Extra.allow):
    code: Optional[str]
    field_config: dict = {}
    code_class_base_inheritance = "CustomComponent"
    function_entrypoint_name = "build"
    function: Optional[Callable] = None
    return_type_valid_list = list(CUSTOM_COMPONENT_SUPPORTED_TYPES.keys())
    repr_value: Optional[Any] = ""
    user_id: Optional[Union[UUID, str]] = None

    def __init__(self, **data):
        super().__init__(**data)

    def custom_repr(self):
        if isinstance(self.repr_value, dict):
            return yaml.dump(self.repr_value)
        if isinstance(self.repr_value, str):
            return self.repr_value
        return str(self.repr_value)

    def build_config(self):
        return self.field_config

    def _class_template_validation(self, code: str):
        TYPE_HINT_LIST = ["Optional", "Prompt", "PromptTemplate", "LLMChain"]

        if not code:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": self.ERROR_CODE_NULL,
                    "traceback": "",
                },
            )

        reader = DirectoryReader("", False)

        for type_hint in TYPE_HINT_LIST:
            if reader._is_type_hint_used_in_args(
                type_hint, code
            ) and not reader._is_type_hint_imported(type_hint, code):
                error_detail = {
                    "error": "Type hint Error",
                    "traceback": f"Type hint '{type_hint}' is used but not imported in the code.",
                }
                raise HTTPException(status_code=400, detail=error_detail)

    def is_check_valid(self) -> bool:
        return self._class_template_validation(self.code) if self.code else False

    def get_code_tree(self, code: str):
        return super().get_code_tree(code)

    @property
    def get_function_entrypoint_args(self) -> str:
        if not self.code:
            return ""
        tree = self.get_code_tree(self.code)

        component_classes = [
            cls
            for cls in tree["classes"]
            if self.code_class_base_inheritance in cls["bases"]
        ]
        if not component_classes:
            return ""

        # Assume the first Component class is the one we're interested in
        component_class = component_classes[0]
        build_methods = [
            method
            for method in component_class["methods"]
            if method["name"] == self.function_entrypoint_name
        ]

        if not build_methods:
            return ""

        build_method = build_methods[0]

        args = build_method["args"]
        for arg in args:
            if arg.get("type") == "prompt":
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Type hint Error",
                        "traceback": (
                            "Prompt type is not supported in the build method."
                            " Try using PromptTemplate instead."
                        ),
                    },
                )
        return args

    @property
    def get_function_entrypoint_return_type(self) -> List[str]:
        if not self.code:
            return []
        tree = self.get_code_tree(self.code)

        component_classes = [
            cls
            for cls in tree["classes"]
            if self.code_class_base_inheritance in cls["bases"]
        ]
        if not component_classes:
            return []

        # Assume the first Component class is the one we're interested in
        component_class = component_classes[0]
        build_methods = [
            method
            for method in component_class["methods"]
            if method["name"] == self.function_entrypoint_name
        ]

        if not build_methods:
            return []

        build_method = build_methods[0]
        return_type = build_method["return_type"]
        if not return_type:
            return []
        # If list or List is in the return type, then we remove it and return the inner type
        if return_type.startswith("list") or return_type.startswith("List"):
            return_type = extract_inner_type(return_type)

        # If the return type is not a Union, then we just return it as a list
        if "Union" not in return_type:
            return [return_type] if return_type in self.return_type_valid_list else []

        # If the return type is a Union, then we need to parse it
        return_type = return_type.replace("Union", "").replace("[", "").replace("]", "")
        return_type = return_type.split(",")
        return_type = [item.strip() for item in return_type]
        return [item for item in return_type if item in self.return_type_valid_list]

    @property
    def get_main_class_name(self):
        tree = self.get_code_tree(self.code)

        base_name = self.code_class_base_inheritance
        method_name = self.function_entrypoint_name

        classes = []
        for item in tree.get("classes"):
            if base_name in item["bases"]:
                method_names = [method["name"] for method in item["methods"]]
                if method_name in method_names:
                    classes.append(item["name"])

        # Get just the first item
        return next(iter(classes), "")

    @property
    def build_template_config(self):
        tree = self.get_code_tree(self.code)

        attributes = [
            main_class["attributes"]
            for main_class in tree.get("classes")
            if main_class["name"] == self.get_main_class_name
        ]
        # Get just the first item
        attributes = next(iter(attributes), [])

        return super().build_template_config(attributes)

    @property
    def get_function(self):
        return validate.create_function(self.code, self.function_entrypoint_name)

    def load_flow(self, flow_id: str, tweaks: Optional[dict] = None) -> Any:
        from langflow.processing.process import build_sorted_vertices
        from langflow.processing.process import process_tweaks

        db_service = get_db_service()
        with session_getter(db_service) as session:
            graph_data = flow.data if (flow := session.get(Flow, flow_id)) else None
        if not graph_data:
            raise ValueError(f"Flow {flow_id} not found")
        if tweaks:
            graph_data = process_tweaks(graph_data=graph_data, tweaks=tweaks)
        return build_sorted_vertices(graph_data)

    def list_flows(self, *, get_session: Optional[Callable] = None) -> List[Flow]:
        if not self.user_id:
            raise ValueError("Session is invalid")
        try:
            get_session = get_session or session_getter
            db_service = get_db_service()
            with get_session(db_service) as session:
                flows = session.query(Flow).filter(Flow.user_id == self.user_id).all()
            return flows
        except Exception as e:
            raise ValueError("Session is invalid") from e

    def get_flow(
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
                flow = (
                    session.query(Flow)
                    .filter(Flow.name == flow_name)
                    .filter(Flow.user_id == self.user_id)
                ).first()
            else:
                raise ValueError("Either flow_name or flow_id must be provided")

        if not flow:
            raise ValueError(f"Flow {flow_name or flow_id} not found")
        return self.load_flow(flow.id, tweaks)

    def build(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError
