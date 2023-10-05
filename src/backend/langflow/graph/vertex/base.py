import ast
import pickle
from langflow.graph.utils import UnbuiltObject
from langflow.graph.vertex.utils import is_basic_type
from langflow.interface.initialize import loading
from langflow.interface.listing import lazy_load_dict
from langflow.utils.constants import DIRECT_TYPES
from loguru import logger
from langflow.utils.util import sync_to_async


import inspect
import types
from typing import Any, Dict, List, Optional
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from langflow.graph.edge.base import Edge


class Vertex:
    def __init__(
        self,
        data: Dict,
        base_type: Optional[str] = None,
        is_task: bool = False,
        params: Optional[Dict] = None,
    ) -> None:
        self.id: str = data["id"]
        self._data = data
        self.edges: List["Edge"] = []
        self.base_type: Optional[str] = base_type
        self._parse_data()
        self._built_object = UnbuiltObject()
        self._built = False
        self.artifacts: Dict[str, Any] = {}
        self.task_id: Optional[str] = None
        self.is_task = is_task
        self.params = params or {}

    def reset_params(self):
        for edge in self.edges:
            if edge.source != self:
                target_param = edge.target_param
                if target_param in ["document", "texts"]:
                    # this means they got data and have already ingested it
                    # so we continue after removing the param
                    self.params.pop(target_param, None)
                    continue

                if target_param in self.params and not is_basic_type(
                    self.params[target_param]
                ):
                    # edge.source.params = {}
                    edge.source._build_params()
                    edge.source._built_object = UnbuiltObject()
                    edge.source._built = False

                    self.params[target_param] = edge.source

    def __getstate__(self):
        state_dict = self.__dict__.copy()
        try:
            # try pickling the built object
            # if it fails, then we need to delete it
            # and build it again
            pickle.dumps(state_dict["_built_object"])
        except Exception:
            self.reset_params()
            del state_dict["_built_object"]
            del state_dict["_built"]
        return state_dict

    def __setstate__(self, state):
        self._data = state["_data"]
        self.params = state["params"]
        self.base_type = state["base_type"]
        self.is_task = state["is_task"]
        self.edges = state["edges"]
        self.id = state["id"]
        self._parse_data()
        if "_built_object" in state:
            self._built_object = state["_built_object"]
            self._built = state["_built"]
        else:
            self._built_object = UnbuiltObject()
            self._built = False
        self.artifacts: Dict[str, Any] = {}
        self.task_id: Optional[str] = None

    def _parse_data(self) -> None:
        self.data = self._data["data"]
        self.output = self.data["node"]["base_classes"]
        template_dicts = {
            key: value
            for key, value in self.data["node"]["template"].items()
            if isinstance(value, dict)
        }

        self.required_inputs = [
            template_dicts[key]["type"]
            for key, value in template_dicts.items()
            if value["required"]
        ]
        self.optional_inputs = [
            template_dicts[key]["type"]
            for key, value in template_dicts.items()
            if not value["required"]
        ]
        # Add the template_dicts[key]["input_types"] to the optional_inputs
        self.optional_inputs.extend(
            [
                input_type
                for value in template_dicts.values()
                for input_type in value.get("input_types", [])
            ]
        )

        template_dict = self.data["node"]["template"]
        self.vertex_type = (
            self.data["type"]
            if "Tool" not in self.output or template_dict["_type"].islower()
            else template_dict["_type"]
        )

        if self.base_type is None:
            for base_type, value in lazy_load_dict.ALL_TYPES_DICT.items():
                if self.vertex_type in value:
                    self.base_type = base_type
                    break

    def get_task(self):
        # using the task_id, get the task from celery
        # and return it
        from celery.result import AsyncResult  # type: ignore

        return AsyncResult(self.task_id)

    def _build_params(self):
        # sourcery skip: merge-list-append, remove-redundant-if
        # Some params are required, some are optional
        # but most importantly, some params are python base classes
        # like str and others are LangChain objects like LLMChain, BasePromptTemplate
        # so we need to be able to distinguish between the two

        # The dicts with "type" == "str" are the ones that are python base classes
        # and most likely have a "value" key

        # So for each key besides "_type" in the template dict, we have a dict
        # with a "type" key. If the type is not "str", then we need to get the
        # edge that connects to that node and get the Node with the required data
        # and use that as the value for the param
        # If the type is "str", then we need to get the value of the "value" key
        # and use that as the value for the param
        template_dict = {
            key: value
            for key, value in self.data["node"]["template"].items()
            if isinstance(value, dict)
        }
        params = self.params.copy() if self.params else {}

        for edge in self.edges:
            if not hasattr(edge, "target_param"):
                continue
            param_key = edge.target_param
            if param_key in template_dict:
                if template_dict[param_key]["list"]:
                    if param_key not in params:
                        params[param_key] = []
                    params[param_key].append(edge.source)
                elif edge.target.id == self.id:
                    params[param_key] = edge.source

        for key, value in template_dict.items():
            if key in params:
                continue
            # Skip _type and any value that has show == False and is not code
            # If we don't want to show code but we want to use it
            if key == "_type" or (not value.get("show") and key != "code"):
                continue
            # If the type is not transformable to a python base class
            # then we need to get the edge that connects to this node
            if value.get("type") == "file":
                # Load the type in value.get('suffixes') using
                # what is inside value.get('content')
                # value.get('value') is the file name
                if file_path := value.get("file_path"):
                    params[key] = file_path
                else:
                    raise ValueError(f"File path not found for {self.vertex_type}")
            elif value.get("type") in DIRECT_TYPES and params.get(key) is None:
                if value.get("type") == "code":
                    try:
                        params[key] = ast.literal_eval(value.get("value"))
                    except Exception as exc:
                        logger.debug(f"Error parsing code: {exc}")
                        params[key] = value.get("value")
                elif value.get("type") in ["dict", "NestedDict"]:
                    # When dict comes from the frontend it comes as a
                    # list of dicts, so we need to convert it to a dict
                    # before passing it to the build method
                    _value = value.get("value")
                    if isinstance(_value, list):
                        params[key] = {
                            k: v
                            for item in value.get("value", [])
                            for k, v in item.items()
                        }
                    elif isinstance(_value, dict):
                        params[key] = _value
                else:
                    params[key] = value.get("value")

            if not value.get("required") and params.get(key) is None:
                if value.get("default"):
                    params[key] = value.get("default")
                else:
                    params.pop(key, None)
        # Add _type to params
        self._raw_params = params
        self.params = params

    def _build(self, user_id=None):
        """
        Initiate the build process.
        """
        logger.debug(f"Building {self.vertex_type}")
        self._build_each_node_in_params_dict(user_id)
        self._get_and_instantiate_class(user_id)
        self._validate_built_object()

        self._built = True

    def _build_each_node_in_params_dict(self, user_id=None):
        """
        Iterates over each node in the params dictionary and builds it.
        """
        for key, value in self.params.copy().items():
            if self._is_node(value):
                if value == self:
                    del self.params[key]
                    continue
                self._build_node_and_update_params(key, value, user_id)
            elif isinstance(value, list) and self._is_list_of_nodes(value):
                self._build_list_of_nodes_and_update_params(key, value, user_id)

    def _is_node(self, value):
        """
        Checks if the provided value is an instance of Vertex.
        """
        return isinstance(value, Vertex)

    def _is_list_of_nodes(self, value):
        """
        Checks if the provided value is a list of Vertex instances.
        """
        return all(self._is_node(node) for node in value)

    def get_result(self, user_id=None, timeout=None) -> Any:
        # Check if the Vertex was built already
        if self._built:
            return self._built_object

        if self.is_task and self.task_id is not None:
            task = self.get_task()
            result = task.get(timeout=timeout)
            if result is not None:  # If result is ready
                self._update_built_object_and_artifacts(result)
                return self._built_object
            else:
                # Handle the case when the result is not ready (retry, throw exception, etc.)
                pass

        # If there's no task_id, build the vertex locally
        self.build(user_id)
        return self._built_object

    def _build_node_and_update_params(self, key, node, user_id=None):
        """
        Builds a given node and updates the params dictionary accordingly.
        """

        result = node.get_result(user_id)
        self._handle_func(key, result)
        if isinstance(result, list):
            self._extend_params_list_with_result(key, result)
        self.params[key] = result

    def _build_list_of_nodes_and_update_params(
        self, key, nodes: List["Vertex"], user_id=None
    ):
        """
        Iterates over a list of nodes, builds each and updates the params dictionary.
        """
        self.params[key] = []
        for node in nodes:
            built = node.get_result(user_id)
            if isinstance(built, list):
                if key not in self.params:
                    self.params[key] = []
                self.params[key].extend(built)
            else:
                self.params[key].append(built)

    def _handle_func(self, key, result):
        """
        Handles 'func' key by checking if the result is a function and setting it as coroutine.
        """
        if key == "func":
            if not isinstance(result, types.FunctionType):
                if hasattr(result, "run"):
                    result = result.run  # type: ignore
                elif hasattr(result, "get_function"):
                    result = result.get_function()  # type: ignore
            elif inspect.iscoroutinefunction(result):
                self.params["coroutine"] = result
            else:
                self.params["coroutine"] = sync_to_async(result)

    def _extend_params_list_with_result(self, key, result):
        """
        Extends a list in the params dictionary with the given result if it exists.
        """
        if isinstance(self.params[key], list):
            self.params[key].extend(result)

    def _get_and_instantiate_class(self, user_id=None):
        """
        Gets the class from a dictionary and instantiates it with the params.
        """
        if self.base_type is None:
            raise ValueError(f"Base type for node {self.vertex_type} not found")
        try:
            result = loading.instantiate_class(
                node_type=self.vertex_type,
                base_type=self.base_type,
                params=self.params,
                user_id=user_id,
            )
            self._update_built_object_and_artifacts(result)
        except Exception as exc:
            logger.exception(exc)
            raise ValueError(
                f"Error building node {self.vertex_type}: {str(exc)}"
            ) from exc

    def _update_built_object_and_artifacts(self, result):
        """
        Updates the built object and its artifacts.
        """
        if isinstance(result, tuple):
            self._built_object, self.artifacts = result
        else:
            self._built_object = result

    def _validate_built_object(self):
        """
        Checks if the built object is None and raises a ValueError if so.
        """
        if isinstance(self._built_object, UnbuiltObject):
            raise ValueError(f"{self.vertex_type}: {self._built_object_repr()}")
        elif self._built_object is None:
            message = f"{self.vertex_type} returned None."
            if self.base_type == "custom_components":
                message += " Make sure your build method returns a component."

            raise ValueError(message)

    def build(self, force: bool = False, user_id=None, *args, **kwargs) -> Any:
        if not self._built or force:
            self._build(user_id, *args, **kwargs)

        return self._built_object

    def add_edge(self, edge: "Edge") -> None:
        if edge not in self.edges:
            self.edges.append(edge)

    def __repr__(self) -> str:
        return f"Vertex(id={self.id}, data={self.data})"

    def __eq__(self, __o: object) -> bool:
        try:
            return self.id == __o.id if isinstance(__o, Vertex) else False
        except AttributeError:
            return False

    def __hash__(self) -> int:
        return id(self)

    def _built_object_repr(self):
        # Add a message with an emoji, stars for sucess,
        return (
            "Built sucessfully ✨"
            if self._built_object is not None
            else "Failed to build 😵‍💫"
        )
