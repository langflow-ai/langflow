import operator
from typing import Any, Callable, List, Optional, Union

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
    """
    Represents a custom component in Langflow.

    Attributes:
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

    def __init__(self, **data):
        """
        Initializes a new instance of the CustomComponent class.

        Args:
            **data: Additional keyword arguments to initialize the custom component.
        """
        self.cache = TTLCache(maxsize=1024, ttl=60)
        super().__init__(**data)

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
        return str(self.repr_value)

    def build_config(self):
        """
        Builds the configuration for the custom component.

        Returns:
            dict: The configuration for the custom component.
        """
        return self.field_config

    @property
    def tree(self):
        """
        Gets the code tree of the custom component.

        Returns:
            dict: The code tree of the custom component.
        """
        return self.get_code_tree(self.code or "")

    @property
    def get_function_entrypoint_args(self) -> list:
        """
        Gets the arguments of the function entrypoint for the custom component.

        Returns:
            list: The arguments of the function entrypoint.
        """
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
        """
        Gets the build method for the custom component.

        Returns:
            dict: The build method for the custom component.
        """
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
        """
        Gets the return type of the function entrypoint for the custom component.

        Returns:
            List[Any]: The return type of the function entrypoint.
        """
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

    def build_template_config(self):
        """
        Builds the template configuration for the custom component.

        Returns:
            dict: The template configuration for the custom component.
        """
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
        """
        Returns the credential for the current user with the specified name.

        Raises:
            ValueError: If the user id is not set.

        Returns:
            The credential for the current user with the specified name.
        """

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
        """
        Lists the names of the credentials for the current user.

        Raises:
            ValueError: If the user id is not set.

        Returns:
            List[str]: The names of the credentials for the current user.
        """
        if hasattr(self, "_user_id") and not self._user_id:
            raise ValueError(f"User id is not set for {self.__class__.__name__}")
        credential_service = get_credential_service()
        db_service = get_db_service()
        with session_getter(db_service) as session:
            return credential_service.list_credentials(user_id=self._user_id, session=session)

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

    @property
    def get_function(self):
        """
        Gets the function associated with the custom component.

        Returns:
            Callable: The function associated with the custom component.
        """
        return validate.create_function(self.code, self.function_entrypoint_name)

    async def load_flow(self, flow_id: str, tweaks: Optional[dict] = None) -> Any:
        """
        Loads a flow with the specified ID and applies tweaks if provided.

        Args:
            flow_id (str): The ID of the flow to load.
            tweaks (Optional[dict]): The tweaks to apply to the flow.

        Returns:
            Any: The loaded flow.
        """
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
        """
        Lists the flows associated with the custom component.

        Args:
            get_session (Optional[Callable]): The function to get the session.

        Returns:
            List[Flow]: The list of flows associated with the custom component.
        """
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
        """
        Gets a flow with the specified name or ID and applies tweaks if provided.

        Args:
            flow_name (Optional[str]): The name of the flow to get.
            flow_id (Optional[str]): The ID of the flow to get.
            tweaks (Optional[dict]): The tweaks to apply to the flow.
            get_session (Optional[Callable]): The function to get the session.

        Returns:
            Flow: The flow with the specified name or ID.
        """
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
        """
        Builds the custom component.

        Args:
            *args: The positional arguments.
            **kwargs: The keyword arguments.

        Returns:
            Any: The result of the build process.
        """
        raise NotImplementedError
