import ast
import inspect
import types
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict, List, Optional

from loguru import logger

from langflow.graph.schema import (
    INPUT_COMPONENTS,
    OUTPUT_COMPONENTS,
    InterfaceComponentTypes,
    ResultData,
)
from langflow.graph.utils import UnbuiltObject, UnbuiltResult
from langflow.graph.vertex.utils import generate_result
from langflow.interface.initialize import loading
from langflow.interface.listing import lazy_load_dict
from langflow.services.deps import get_storage_service
from langflow.utils.constants import DIRECT_TYPES
from langflow.utils.util import sync_to_async

if TYPE_CHECKING:
    from langflow.graph.edge.base import ContractEdge
    from langflow.graph.graph.base import Graph


class VertexStates(Enum):
    """Vertex are related to it being active, inactive, or in an error state."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class Vertex:
    def __init__(
        self,
        data: Dict,
        graph: "Graph",
        base_type: Optional[str] = None,
        is_task: bool = False,
        params: Optional[Dict] = None,
    ) -> None:
        # is_external means that the Vertex send or receives data from
        # an external source (e.g the chat)

        self.id: str = data["id"]
        self.is_input = any(
            input_component_name in self.id for input_component_name in INPUT_COMPONENTS
        )
        self.is_output = any(
            output_component_name in self.id
            for output_component_name in OUTPUT_COMPONENTS
        )
        self._custom_component = None
        self.has_external_input = False
        self.has_external_output = False
        self.graph = graph
        self._data = data
        self.base_type: Optional[str] = base_type
        self._parse_data()
        self._built_object = UnbuiltObject()
        self._built_result = None
        self._built = False
        self.artifacts: Dict[str, Any] = {}
        self.steps: List[Callable] = [self._build]
        self.steps_ran: List[Callable] = []
        self.task_id: Optional[str] = None
        self.is_task = is_task
        self.params = params or {}
        self.parent_node_id: Optional[str] = self._data.get("parent_node_id")
        self.parent_is_top_level = False
        self.layer = None
        self.should_run = True
        self.result: Optional[ResultData] = None
        try:
            self.is_interface_component = InterfaceComponentTypes(self.vertex_type)
        except ValueError:
            self.is_interface_component = False

        self.use_result = False
        self.build_times: List[float] = []
        self.state = VertexStates.ACTIVE

    def set_state(self, state: str):
        self.state = VertexStates[state]
        if (
            self.state == VertexStates.INACTIVE
            and self.graph.in_degree_map[self.id] < 2
        ):
            # If the vertex is inactive and has only one in degree
            # it means that it is not a merge point in the graph
            self.graph.inactive_vertices.add(self.id)
        elif (
            self.state == VertexStates.ACTIVE
            and self.id in self.graph.inactive_vertices
        ):
            self.graph.inactive_vertices.remove(self.id)

    @property
    def avg_build_time(self):
        return sum(self.build_times) / len(self.build_times) if self.build_times else 0

    def add_build_time(self, time):
        self.build_times.append(time)

    # Build a result dict for each edge
    # like so: {edge.target.id: {edge.target_param: self._built_object}}
    async def get_result_dict(self, force: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Returns a dictionary with the result of the build process.
        """
        edge_results = {}
        for edge in self.edges:
            target = self.graph.get_vertex(edge.target_id)
            if edge.is_fulfilled and isinstance(
                await edge.get_result(
                    source=self,
                    target=target,
                ),
                str,
            ):
                if edge.target_id not in edge_results:
                    edge_results[edge.target_id] = {}
                edge_results[edge.target_id][edge.target_param] = await edge.get_result(
                    source=self, target=target
                )
        return edge_results

    def set_result(self, result: ResultData) -> None:
        self.result = result

    def get_built_result(self):
        # If the Vertex.type is a power component
        # then we need to return the built object
        # instead of the result dict
        if self.is_interface_component and not isinstance(
            self._built_object, UnbuiltObject
        ):
            result = self._built_object
            # if it is not a dict or a string and hasattr model_dump then
            # return the model_dump
            if not isinstance(result, (dict, str)) and hasattr(result, "content"):
                return result.content
            return result

        if isinstance(self._built_result, UnbuiltResult):
            return {}
        return (
            self._built_result
            if isinstance(self._built_result, dict)
            else {"result": self._built_result}
        )

    def set_artifacts(self) -> None:
        pass

    @property
    def edges(self) -> List["ContractEdge"]:
        return self.graph.get_vertex_edges(self.id)

    @property
    def predecessors(self) -> List["Vertex"]:
        return self.graph.get_predecessors(self)

    @property
    def successors(self) -> List["Vertex"]:
        return self.graph.get_successors(self)

    def __getstate__(self):
        return {
            "_data": self._data,
            "params": {},
            "base_type": self.base_type,
            "is_task": self.is_task,
            "id": self.id,
            "_built_object": UnbuiltObject(),
            "_built": False,
            "parent_node_id": self.parent_node_id,
            "parent_is_top_level": self.parent_is_top_level,
        }

    def __setstate__(self, state):
        self._data = state["_data"]
        self.params = state["params"]
        self.base_type = state["base_type"]
        self.is_task = state["is_task"]
        self.id = state["id"]
        self.pinned = state.get("pinned", False)
        self._parse_data()
        if "_built_object" in state:
            self._built_object = state["_built_object"]
            self._built = state["_built"]
        else:
            self._built_object = UnbuiltObject()
            self._built = False
        if "_built_result" in state:
            self._built_result = state["_built_result"]
        else:
            self._built_result = UnbuiltResult()
        self.artifacts: Dict[str, Any] = {}
        self.task_id: Optional[str] = None
        self.parent_node_id = state["parent_node_id"]
        self.parent_is_top_level = state["parent_is_top_level"]
        self.layer = state.get("layer")
        self.steps = state.get("steps", [self._build])

    def set_top_level(self, top_level_vertices: List[str]) -> None:
        self.parent_is_top_level = self.parent_node_id in top_level_vertices

    def _parse_data(self) -> None:
        self.data = self._data["data"]
        self.output = self.data["node"]["base_classes"]
        self.display_name = self.data["node"]["display_name"]
        self.pinned = self.data["node"].get("pinned", False)
        self.selected_output_type = self.data["node"].get("selected_output_type")
        self.is_input = self.data["node"].get("is_input") or self.is_input
        self.is_output = self.data["node"].get("is_output") or self.is_output
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

        if self.graph is None:
            raise ValueError("Graph not found")

        template_dict = {
            key: value
            for key, value in self.data["node"]["template"].items()
            if isinstance(value, dict)
        }
        params = {}

        for edge in self.edges:
            if not hasattr(edge, "target_param"):
                continue
            param_key = edge.target_param

            # If the param_key is in the template_dict and the edge.target_id is the current node
            # We check this to make sure params with the same name but different target_id
            # don't get overwritten
            if param_key in template_dict and edge.target_id == self.id:
                if template_dict[param_key]["list"]:
                    if param_key not in params:
                        params[param_key] = []
                    params[param_key].append(self.graph.get_vertex(edge.source_id))
                elif edge.target_id == self.id:
                    params[param_key] = self.graph.get_vertex(edge.source_id)

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
                # Load the type in value.get('fileTypes') using
                # what is inside value.get('content')
                # value.get('value') is the file name
                if file_path := value.get("file_path"):
                    storage_service = get_storage_service()
                    flow_id, file_name = file_path.split("/")
                    full_path = storage_service.build_full_path(flow_id, file_name)
                    params[key] = full_path
                else:
                    raise ValueError(f"File path not found for {self.display_name}")
            elif value.get("type") in DIRECT_TYPES and params.get(key) is None:
                val = value.get("value")
                if value.get("type") == "code":
                    try:
                        params[key] = ast.literal_eval(val) if val else None
                    except Exception:
                        params[key] = val
                elif value.get("type") in ["dict", "NestedDict"]:
                    # When dict comes from the frontend it comes as a
                    # list of dicts, so we need to convert it to a dict
                    # before passing it to the build method
                    if isinstance(val, list):
                        params[key] = {
                            k: v
                            for item in value.get("value", [])
                            for k, v in item.items()
                        }
                    elif isinstance(val, dict):
                        params[key] = val
                elif value.get("type") == "int" and val is not None:
                    try:
                        params[key] = int(val)
                    except ValueError:
                        params[key] = val
                elif value.get("type") == "float" and val is not None:
                    try:
                        params[key] = float(val)
                    except ValueError:
                        params[key] = val
                elif value.get("type") == "str" and val is not None:
                    # val may contain escaped \n, \t, etc.
                    # so we need to unescape it
                    if isinstance(val, list):
                        params[key] = [v.encode().decode("unicode_escape") for v in val]
                    elif isinstance(val, str):
                        params[key] = val.encode().decode("unicode_escape")
                elif val is not None and val != "":
                    params[key] = val

            if not value.get("required") and params.get(key) is None:
                if value.get("default"):
                    params[key] = value.get("default")
                else:
                    params.pop(key, None)
        # Add _type to params
        self.params = params
        self._raw_params = params.copy()

    def update_raw_params(self, new_params: Dict[str, str]):
        """
        Update the raw parameters of the vertex with the given new parameters.

        Args:
            new_params (Dict[str, Any]): The new parameters to update.

        Raises:
            ValueError: If any key in new_params is not found in self._raw_params.
        """
        for key in new_params:
            if key not in self._raw_params:
                raise ValueError(f"Key {key} not found in raw params")
        self._raw_params.update(new_params)

    async def _build(self, user_id=None):
        """
        Initiate the build process.
        """
        logger.debug(f"Building {self.display_name}")
        await self._build_each_node_in_params_dict(user_id)
        await self._get_and_instantiate_class(user_id)
        self._validate_built_object()

        self._built = True

    def _finalize_build(self):
        result_dict = self.get_built_result()
        # We need to set the artifacts to pass information
        # to the frontend
        self.set_artifacts()
        artifacts = self.artifacts
        result_dict = ResultData(
            results=result_dict,
            artifacts=artifacts,
        )
        self.set_result(result_dict)

    async def _run(
        self,
        user_id: str,
        inputs: Optional[dict] = None,
        session_id: Optional[str] = None,
    ):
        # user_id is just for compatibility with the other build methods
        inputs = inputs or {}
        # inputs = {key: value or "" for key, value in inputs.items()}
        # if hasattr(self._built_object, "input_keys"):
        #     # test if all keys are in inputs
        #     # and if not add them with empty string
        #     # for key in self._built_object.input_keys:
        #     #     if key not in inputs:
        #     #         inputs[key] = ""
        #     if inputs == {} and hasattr(self._built_object, "prompt"):
        #         inputs = self._built_object.prompt.partial_variables
        if isinstance(self._built_object, str):
            self._built_result = self._built_object

        result = await generate_result(
            self._built_object, inputs, self.has_external_output, session_id
        )
        self._built_result = result

    async def _build_each_node_in_params_dict(self, user_id=None):
        """
        Iterates over each node in the params dictionary and builds it.
        """
        for key, value in self._raw_params.items():
            if self._is_node(value):
                if value == self:
                    del self.params[key]
                    continue
                await self._build_node_and_update_params(key, value, user_id)
            elif isinstance(value, list) and self._is_list_of_nodes(value):
                await self._build_list_of_nodes_and_update_params(key, value, user_id)

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

    async def get_result(
        self, requester: Optional["Vertex"] = None, user_id=None, timeout=None
    ) -> Any:
        # PLEASE REVIEW THIS IF STATEMENT
        # Check if the Vertex was built already
        if self._built:
            return self._built_object if not self.use_result else self._built_result

        if self.is_task and self.task_id is not None:
            task = self.get_task()

            result = task.get(timeout=timeout)
            if isinstance(result, Coroutine):
                result = await result
            if result is not None:  # If result is ready
                self._update_built_object_and_artifacts(result)
                return self._built_object
            else:
                # Handle the case when the result is not ready (retry, throw exception, etc.)
                pass

        # If there's no task_id, build the vertex locally
        await self.build(requester=requester, user_id=user_id)
        return self._built_object

    async def _build_node_and_update_params(self, key, node: "Vertex", user_id=None):
        """
        Builds a given node and updates the params dictionary accordingly.
        """

        result = await node.get_result(requester=self, user_id=user_id)
        self._handle_func(key, result)
        if isinstance(result, list):
            self._extend_params_list_with_result(key, result)
        self.params[key] = result

    async def _build_list_of_nodes_and_update_params(
        self, key, nodes: List["Vertex"], user_id=None
    ):
        """
        Iterates over a list of nodes, builds each and updates the params dictionary.
        """
        self.params[key] = []
        for node in nodes:
            built = await node.get_result(requester=self, user_id=user_id)
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

    async def _get_and_instantiate_class(self, user_id=None):
        """
        Gets the class from a dictionary and instantiates it with the params.
        """
        if self.base_type is None:
            raise ValueError(f"Base type for node {self.display_name} not found")
        try:

            result = await loading.instantiate_class(
                node_type=self.vertex_type,
                base_type=self.base_type,
                params=self.params,
                user_id=user_id,
                vertex=self,
            )
            self._update_built_object_and_artifacts(result)
        except Exception as exc:
            logger.exception(exc)

            raise ValueError(
                f"Error building node {self.display_name}: {str(exc)}"
            ) from exc

    def _update_built_object_and_artifacts(self, result):
        """
        Updates the built object and its artifacts.
        """
        if isinstance(result, tuple):
            if len(result) == 2:
                self._built_object, self.artifacts = result
            elif len(result) == 3:
                self._custom_component, self._built_object, self.artifacts = result
        else:
            self._built_object = result

    def _validate_built_object(self):
        """
        Checks if the built object is None and raises a ValueError if so.
        """
        if isinstance(self._built_object, UnbuiltObject):
            raise ValueError(f"{self.display_name}: {self._built_object_repr()}")
        elif self._built_object is None:
            message = f"{self.display_name} returned None."
            if self.base_type == "custom_components":
                message += " Make sure your build method returns a component."

            logger.warning(message)

    def _reset(self):
        self._built = False
        self._built_object = UnbuiltObject()
        self._built_result = UnbuiltResult()
        self.artifacts = {}
        self.steps_ran = []
        self._build_params()

    def build_inactive(self):
        # Just set the results to None
        self._built = True
        self._built_object = None
        self._built_result = None

    async def build(
        self,
        user_id=None,
        requester: Optional["Vertex"] = None,
        **kwargs,
    ) -> Any:
        if self.state == VertexStates.INACTIVE:
            # If the vertex is inactive, return None
            self.build_inactive()
            return

        if self.pinned and self._built:
            return self.get_requester_result(requester)
        self._reset()

        # Run steps
        for step in self.steps:
            if step not in self.steps_ran:
                if inspect.iscoroutinefunction(step):
                    await step(user_id=user_id, **kwargs)
                else:
                    step(user_id=user_id, **kwargs)
                self.steps_ran.append(step)

        self._finalize_build()

        return await self.get_requester_result(requester)

    async def get_requester_result(self, requester: Optional["Vertex"]):
        # If the requester is None, this means that
        # the Vertex is the root of the graph
        if requester is None:
            return self._built_object

        # Get the requester edge
        requester_edge = next(
            (edge for edge in self.edges if edge.target_id == requester.id), None
        )
        # Return the result of the requester edge
        return (
            None
            if requester_edge is None
            else await requester_edge.get_result(source=self, target=requester)
        )

    def add_edge(self, edge: "ContractEdge") -> None:
        if edge not in self.edges:
            self.edges.append(edge)

    def __repr__(self) -> str:
        return (
            f"Vertex(display_name={self.display_name}, id={self.id}, data={self.data})"
        )

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


class StatefulVertex(Vertex):
    pass


class StatelessVertex(Vertex):
    pass
