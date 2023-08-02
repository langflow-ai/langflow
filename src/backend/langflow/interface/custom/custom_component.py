from typing import Any, Callable, List, Optional
from fastapi import HTTPException
from langflow.interface.custom.constants import CUSTOM_COMPONENT_SUPPORTED_TYPES
from langflow.interface.custom.component import Component
from langflow.interface.custom.directory_reader import DirectoryReader

from langflow.utils import validate

from langflow.database.base import session_getter
from langflow.database.models.flow import Flow
from pydantic import Extra


class CustomComponent(Component, extra=Extra.allow):
    code: Optional[str]
    field_config: dict = {}
    code_class_base_inheritance = "CustomComponent"
    function_entrypoint_name = "build"
    function: Optional[Callable] = None
    return_type_valid_list = list(CUSTOM_COMPONENT_SUPPORTED_TYPES.keys())
    repr_value: Optional[str] = ""

    def __init__(self, **data):
        super().__init__(**data)

    def custom_repr(self):
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
            if reader.is_type_hint_used_but_not_imported(type_hint, code):
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

        return build_method["args"]

    @property
    def get_function_entrypoint_return_type(self) -> str:
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

        return build_method["return_type"]

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
        from langflow.processing.process import build_sorted_vertices_with_caching
        from langflow.processing.process import process_tweaks

        with session_getter() as session:
            graph_data = flow.data if (flow := session.get(Flow, flow_id)) else None
        if not graph_data:
            raise ValueError(f"Flow {flow_id} not found")
        if tweaks:
            graph_data = process_tweaks(graph_data=graph_data, tweaks=tweaks)
        return build_sorted_vertices_with_caching(graph_data)

    def list_flows(self, *, get_session: Optional[Callable] = None) -> List[Flow]:
        get_session = get_session or session_getter
        with get_session() as session:
            flows = session.query(Flow).all()
        return flows

    def get_flow(
        self,
        *,
        flow_name: Optional[str] = None,
        flow_id: Optional[str] = None,
        tweaks: Optional[dict] = None,
        get_session: Optional[Callable] = None,
    ) -> Flow:
        get_session = get_session or session_getter

        with get_session() as session:
            if flow_id:
                flow = session.query(Flow).get(flow_id)
            elif flow_name:
                flow = session.query(Flow).filter(Flow.name == flow_name).first()
            else:
                raise ValueError("Either flow_name or flow_id must be provided")

        if not flow:
            raise ValueError(f"Flow {flow_name or flow_id} not found")
        return self.load_flow(flow.id, tweaks)

    def build(self):
        raise NotImplementedError
