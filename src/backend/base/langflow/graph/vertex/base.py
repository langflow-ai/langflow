from __future__ import annotations

import ast
import asyncio
import inspect
import os
import traceback
import types
from collections.abc import AsyncIterator, Callable, Iterator, Mapping
from enum import Enum
from typing import TYPE_CHECKING, Any

import pandas as pd
from loguru import logger

from langflow.exceptions.component import ComponentBuildError
from langflow.graph.schema import INPUT_COMPONENTS, OUTPUT_COMPONENTS, InterfaceComponentTypes, ResultData
from langflow.graph.utils import UnbuiltObject, UnbuiltResult, log_transaction
from langflow.interface import initialize
from langflow.interface.listing import lazy_load_dict
from langflow.schema.artifact import ArtifactType
from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.schema.schema import INPUT_FIELD_NAME, OutputValue, build_output_logs
from langflow.services.deps import get_storage_service
from langflow.utils.constants import DIRECT_TYPES
from langflow.utils.schemas import ChatOutputResponse
from langflow.utils.util import sync_to_async, unescape_string

if TYPE_CHECKING:
    from uuid import UUID

    from langflow.custom import Component
    from langflow.events.event_manager import EventManager
    from langflow.graph.edge.base import CycleEdge, Edge
    from langflow.graph.graph.base import Graph
    from langflow.graph.vertex.schema import NodeData
    from langflow.services.tracing.schema import Log


class VertexStates(str, Enum):
    """Vertex are related to it being active, inactive, or in an error state."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ERROR = "ERROR"


class Vertex:
    def __init__(
        self,
        data: NodeData,
        graph: Graph,
        *,
        base_type: str | None = None,
        is_task: bool = False,
        params: dict | None = None,
    ) -> None:
        # is_external means that the Vertex send or receives data from
        # an external source (e.g the chat)
        self._lock = asyncio.Lock()
        self.will_stream = False
        self.updated_raw_params = False
        self.id: str = data["id"]
        self.base_name = self.id.split("-")[0]
        self.is_state = False
        self.is_input = any(input_component_name in self.id for input_component_name in INPUT_COMPONENTS)
        self.is_output = any(output_component_name in self.id for output_component_name in OUTPUT_COMPONENTS)
        self.has_session_id = None
        self.custom_component = None
        self.has_external_input = False
        self.has_external_output = False
        self.graph = graph
        self.full_data = data.copy()
        self.base_type: str | None = base_type
        self.outputs: list[dict] = []
        self.parse_data()
        self.built_object: Any = UnbuiltObject()
        self.built_result: Any = None
        self.built = False
        self._successors_ids: list[str] | None = None
        self.artifacts: dict[str, Any] = {}
        self.artifacts_raw: dict[str, Any] = {}
        self.artifacts_type: dict[str, str] = {}
        self.steps: list[Callable] = [self._build]
        self.steps_ran: list[Callable] = []
        self.task_id: str | None = None
        self.is_task = is_task
        self.params = params or {}
        self.parent_node_id: str | None = self.full_data.get("parent_node_id")
        self.load_from_db_fields: list[str] = []
        self.parent_is_top_level = False
        self.layer = None
        self.result: ResultData | None = None
        self.results: dict[str, Any] = {}
        self.outputs_logs: dict[str, OutputValue] = {}
        self.logs: dict[str, list[Log]] = {}
        self.has_cycle_edges = False
        try:
            self.is_interface_component = self.vertex_type in InterfaceComponentTypes
        except ValueError:
            self.is_interface_component = False

        self.use_result = False
        self.build_times: list[float] = []
        self.state = VertexStates.ACTIVE
        self.log_transaction_tasks: set[asyncio.Task] = set()

    def set_input_value(self, name: str, value: Any) -> None:
        if self.custom_component is None:
            msg = f"Vertex {self.id} does not have a component instance."
            raise ValueError(msg)
        self.custom_component._set_input_value(name, value)

    def to_data(self):
        return self.full_data

    def add_component_instance(self, component_instance: Component) -> None:
        component_instance.set_vertex(self)
        self.custom_component = component_instance

    def add_result(self, name: str, result: Any) -> None:
        self.results[name] = result

    def update_graph_state(self, key, new_state, *, append: bool) -> None:
        if append:
            self.graph.append_state(key, new_state, caller=self.id)
        else:
            self.graph.update_state(key, new_state, caller=self.id)

    def set_state(self, state: str) -> None:
        self.state = VertexStates[state]
        if self.state == VertexStates.INACTIVE and self.graph.in_degree_map[self.id] <= 1:
            # If the vertex is inactive and has only one in degree
            # it means that it is not a merge point in the graph
            self.graph.inactivated_vertices.add(self.id)
        elif self.state == VertexStates.ACTIVE and self.id in self.graph.inactivated_vertices:
            self.graph.inactivated_vertices.remove(self.id)

    def is_active(self):
        return self.state == VertexStates.ACTIVE

    @property
    def avg_build_time(self):
        return sum(self.build_times) / len(self.build_times) if self.build_times else 0

    def add_build_time(self, time) -> None:
        self.build_times.append(time)

    def set_result(self, result: ResultData) -> None:
        self.result = result

    def get_built_result(self):
        # If the Vertex.type is a power component
        # then we need to return the built object
        # instead of the result dict
        if self.is_interface_component and not isinstance(self.built_object, UnbuiltObject):
            result = self.built_object
            # if it is not a dict or a string and hasattr model_dump then
            # return the model_dump
            if not isinstance(result, dict | str) and hasattr(result, "content"):
                return result.content
            return result
        if isinstance(self.built_object, str):
            self.built_result = self.built_object

        if isinstance(self.built_result, UnbuiltResult):
            return {}
        return self.built_result if isinstance(self.built_result, dict) else {"result": self.built_result}

    def set_artifacts(self) -> None:
        pass

    @property
    def edges(self) -> list[CycleEdge]:
        return self.graph.get_vertex_edges(self.id)

    @property
    def outgoing_edges(self) -> list[CycleEdge]:
        return [edge for edge in self.edges if edge.source_id == self.id]

    @property
    def incoming_edges(self) -> list[CycleEdge]:
        return [edge for edge in self.edges if edge.target_id == self.id]

    @property
    def edges_source_names(self) -> set[str | None]:
        return {edge.source_handle.name for edge in self.edges}

    @property
    def predecessors(self) -> list[Vertex]:
        return self.graph.get_predecessors(self)

    @property
    def successors(self) -> list[Vertex]:
        return self.graph.get_successors(self)

    @property
    def successors_ids(self) -> list[str]:
        return self.graph.successor_map.get(self.id, [])

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_lock"] = None  # Locks are not serializable
        state["built_object"] = None if isinstance(self.built_object, UnbuiltObject) else self.built_object
        state["built_result"] = None if isinstance(self.built_result, UnbuiltResult) else self.built_result
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._lock = asyncio.Lock()  # Reinitialize the lock
        self.built_object = state.get("built_object") or UnbuiltObject()
        self.built_result = state.get("built_result") or UnbuiltResult()

    def set_top_level(self, top_level_vertices: list[str]) -> None:
        self.parent_is_top_level = self.parent_node_id in top_level_vertices

    def parse_data(self) -> None:
        self.data = self.full_data["data"]
        if self.data["node"]["template"]["_type"] == "Component":
            if "outputs" not in self.data["node"]:
                msg = f"Outputs not found for {self.display_name}"
                raise ValueError(msg)
            self.outputs = self.data["node"]["outputs"]
        else:
            self.outputs = self.data["node"].get("outputs", [])
            self.output = self.data["node"]["base_classes"]

        self.display_name: str = self.data["node"].get("display_name", self.id.split("-")[0])
        self.icon: str = self.data["node"].get("icon", self.id.split("-")[0])

        self.description: str = self.data["node"].get("description", "")
        self.frozen: bool = self.data["node"].get("frozen", False)

        self.is_input = self.data["node"].get("is_input") or self.is_input
        self.is_output = self.data["node"].get("is_output") or self.is_output
        template_dicts = {key: value for key, value in self.data["node"]["template"].items() if isinstance(value, dict)}

        self.has_session_id = "session_id" in template_dicts

        self.required_inputs: list[str] = []
        self.optional_inputs: list[str] = []
        for value_dict in template_dicts.values():
            list_to_append = self.required_inputs if value_dict.get("required") else self.optional_inputs

            if "type" in value_dict:
                list_to_append.append(value_dict["type"])
            if "input_types" in value_dict:
                list_to_append.extend(value_dict["input_types"])

        template_dict = self.data["node"]["template"]
        self.vertex_type = (
            self.data["type"]
            if "Tool" not in [type_ for out in self.outputs for type_ in out["types"]]
            or template_dict["_type"].islower()
            else template_dict["_type"]
        )

        if self.base_type is None:
            for base_type, value in lazy_load_dict.all_types_dict.items():
                if self.vertex_type in value:
                    self.base_type = base_type
                    break

    def get_value_from_template_dict(self, key: str):
        template_dict = self.data.get("node", {}).get("template", {})
        if key not in template_dict:
            msg = f"Key {key} not found in template dict"
            raise ValueError(msg)
        return template_dict.get(key, {}).get("value")

    def get_task(self):
        # using the task_id, get the task from celery
        # and return it
        from celery.result import AsyncResult

        return AsyncResult(self.task_id)

    def _set_params_from_normal_edge(self, params: dict, edge: Edge, template_dict: dict):
        param_key = edge.target_param

        # If the param_key is in the template_dict and the edge.target_id is the current node
        # We check this to make sure params with the same name but different target_id
        # don't get overwritten
        if param_key in template_dict and edge.target_id == self.id:
            if template_dict[param_key].get("list"):
                if param_key not in params:
                    params[param_key] = []
                params[param_key].append(self.graph.get_vertex(edge.source_id))
            elif edge.target_id == self.id:
                if isinstance(template_dict[param_key].get("value"), dict):
                    # we don't know the key of the dict but we need to set the value
                    # to the vertex that is the source of the edge
                    param_dict = template_dict[param_key]["value"]
                    if not param_dict or len(param_dict) != 1:
                        params[param_key] = self.graph.get_vertex(edge.source_id)
                    else:
                        params[param_key] = {key: self.graph.get_vertex(edge.source_id) for key in param_dict}

                else:
                    params[param_key] = self.graph.get_vertex(edge.source_id)
        return params

    def build_params(self) -> None:
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
            msg = "Graph not found"
            raise ValueError(msg)

        if self.updated_raw_params:
            self.updated_raw_params = False
            return

        template_dict = {key: value for key, value in self.data["node"]["template"].items() if isinstance(value, dict)}
        params: dict = {}

        for edge in self.edges:
            if not hasattr(edge, "target_param"):
                continue
            params = self._set_params_from_normal_edge(params, edge, template_dict)

        load_from_db_fields = []
        for field_name, field in template_dict.items():
            if field_name in params:
                continue
            # Skip _type and any value that has show == False and is not code
            # If we don't want to show code but we want to use it
            if field_name == "_type" or (not field.get("show") and field_name != "code"):
                continue
            # If the type is not transformable to a python base class
            # then we need to get the edge that connects to this node
            if field.get("type") == "file":
                # Load the type in value.get('fileTypes') using
                # what is inside value.get('content')
                # value.get('value') is the file name
                if file_path := field.get("file_path"):
                    storage_service = get_storage_service()
                    try:
                        flow_id, file_name = os.path.split(file_path)
                        full_path = storage_service.build_full_path(flow_id, file_name)
                    except ValueError as e:
                        if "too many values to unpack" in str(e):
                            full_path = file_path
                        else:
                            raise
                    params[field_name] = full_path
                elif field.get("required"):
                    field_display_name = field.get("display_name")
                    logger.warning(
                        f"File path not found for {field_display_name} in component {self.display_name}. "
                        "Setting to None."
                    )
                    params[field_name] = None
                elif field["list"]:
                    params[field_name] = []
                else:
                    params[field_name] = None

            elif field.get("type") in DIRECT_TYPES and params.get(field_name) is None:
                val = field.get("value")
                if field.get("type") == "code":
                    try:
                        if field_name == "code":
                            params[field_name] = val
                        else:
                            params[field_name] = ast.literal_eval(val) if val else None
                    except Exception:  # noqa: BLE001
                        logger.debug(f"Error evaluating code for {field_name}")
                        params[field_name] = val
                elif field.get("type") in {"dict", "NestedDict"}:
                    # When dict comes from the frontend it comes as a
                    # list of dicts, so we need to convert it to a dict
                    # before passing it to the build method
                    if isinstance(val, list):
                        params[field_name] = {k: v for item in field.get("value", []) for k, v in item.items()}
                    elif isinstance(val, dict):
                        params[field_name] = val
                elif field.get("type") == "int" and val is not None:
                    try:
                        params[field_name] = int(val)
                    except ValueError:
                        params[field_name] = val
                elif field.get("type") == "float" and val is not None:
                    try:
                        params[field_name] = float(val)
                    except ValueError:
                        params[field_name] = val
                        params[field_name] = val
                elif field.get("type") == "str" and val is not None:
                    # val may contain escaped \n, \t, etc.
                    # so we need to unescape it
                    if isinstance(val, list):
                        params[field_name] = [unescape_string(v) for v in val]
                    elif isinstance(val, str):
                        params[field_name] = unescape_string(val)
                    elif isinstance(val, Data):
                        params[field_name] = unescape_string(val.get_text())
                elif field.get("type") == "bool" and val is not None:
                    if isinstance(val, bool):
                        params[field_name] = val
                    elif isinstance(val, str):
                        params[field_name] = bool(val)
                elif field.get("type") == "table" and val is not None:
                    # check if the value is a list of dicts
                    # if it is, create a pandas dataframe from it
                    if isinstance(val, list) and all(isinstance(item, dict) for item in val):
                        params[field_name] = pd.DataFrame(val)
                    else:
                        msg = f"Invalid value type {type(val)} for field {field_name}"
                        raise ValueError(msg)
                elif val is not None and val != "":
                    params[field_name] = val

                if field.get("load_from_db"):
                    load_from_db_fields.append(field_name)

            if not field.get("required") and params.get(field_name) is None:
                if field.get("default"):
                    params[field_name] = field.get("default")
                else:
                    params.pop(field_name, None)
        # Add _type to params
        self.params = params
        self.load_from_db_fields = load_from_db_fields
        self.raw_params = params.copy()

    def update_raw_params(self, new_params: Mapping[str, str | list[str]], *, overwrite: bool = False) -> None:
        """Update the raw parameters of the vertex with the given new parameters.

        Args:
            new_params (Dict[str, Any]): The new parameters to update.
            overwrite (bool, optional): Whether to overwrite the existing parameters.
                Defaults to False.

        Raises:
            ValueError: If any key in new_params is not found in self.raw_params.
        """
        # First check if the input_value in raw_params is not a vertex
        if not new_params:
            return
        if any(isinstance(self.raw_params.get(key), Vertex) for key in new_params):
            return
        if not overwrite:
            for key in new_params.copy():  # type: ignore[attr-defined]
                if key not in self.raw_params:
                    new_params.pop(key)  # type: ignore[attr-defined]
        self.raw_params.update(new_params)
        self.params = self.raw_params.copy()
        self.updated_raw_params = True

    def instantiate_component(self, user_id=None) -> None:
        if not self.custom_component:
            self.custom_component, _ = initialize.loading.instantiate_class(
                user_id=user_id,
                vertex=self,
            )

    async def _build(
        self,
        fallback_to_env_vars,
        user_id=None,
        event_manager: EventManager | None = None,
    ) -> None:
        """Initiate the build process."""
        logger.debug(f"Building {self.display_name}")
        await self._build_each_vertex_in_params_dict()

        if self.base_type is None:
            msg = f"Base type for vertex {self.display_name} not found"
            raise ValueError(msg)

        if not self.custom_component:
            custom_component, custom_params = initialize.loading.instantiate_class(
                user_id=user_id, vertex=self, event_manager=event_manager
            )
        else:
            custom_component = self.custom_component
            self.custom_component.set_event_manager(event_manager)
            custom_params = initialize.loading.get_params(self.params)

        await self._build_results(
            custom_component=custom_component,
            custom_params=custom_params,
            fallback_to_env_vars=fallback_to_env_vars,
            base_type=self.base_type,
        )

        self._validate_built_object()

        self.built = True

    def extract_messages_from_artifacts(self, artifacts: dict[str, Any]) -> list[dict]:
        """Extracts messages from the artifacts.

        Args:
            artifacts (Dict[str, Any]): The artifacts to extract messages from.

        Returns:
            List[str]: The extracted messages.
        """
        try:
            text = artifacts["text"]
            sender = artifacts.get("sender")
            sender_name = artifacts.get("sender_name")
            session_id = artifacts.get("session_id")
            stream_url = artifacts.get("stream_url")
            files = [{"path": file} if isinstance(file, str) else file for file in artifacts.get("files", [])]
            component_id = self.id
            _type = self.artifacts_type

            if isinstance(sender_name, Data | Message):
                sender_name = sender_name.get_text()

            messages = [
                ChatOutputResponse(
                    message=text,
                    sender=sender,
                    sender_name=sender_name,
                    session_id=session_id,
                    stream_url=stream_url,
                    files=files,
                    component_id=component_id,
                    type=_type,
                ).model_dump(exclude_none=True)
            ]
        except KeyError:
            messages = []

        return messages

    def finalize_build(self) -> None:
        result_dict = self.get_built_result()
        # We need to set the artifacts to pass information
        # to the frontend
        self.set_artifacts()
        artifacts = self.artifacts_raw
        messages = self.extract_messages_from_artifacts(artifacts) if isinstance(artifacts, dict) else []
        result_dict = ResultData(
            results=result_dict,
            artifacts=artifacts,
            outputs=self.outputs_logs,
            logs=self.logs,
            messages=messages,
            component_display_name=self.display_name,
            component_id=self.id,
        )
        self.set_result(result_dict)

    async def _build_each_vertex_in_params_dict(self) -> None:
        """Iterates over each vertex in the params dictionary and builds it."""
        for key, value in self.raw_params.items():
            if self._is_vertex(value):
                if value == self:
                    del self.params[key]
                    continue
                await self._build_vertex_and_update_params(
                    key,
                    value,
                )
            elif isinstance(value, list) and self._is_list_of_vertices(value):
                await self._build_list_of_vertices_and_update_params(key, value)
            elif isinstance(value, dict):
                await self._build_dict_and_update_params(
                    key,
                    value,
                )
            elif key not in self.params or self.updated_raw_params:
                self.params[key] = value

    async def _build_dict_and_update_params(
        self,
        key,
        vertices_dict: dict[str, Vertex],
    ) -> None:
        """Iterates over a dictionary of vertices, builds each and updates the params dictionary."""
        for sub_key, value in vertices_dict.items():
            if not self._is_vertex(value):
                self.params[key][sub_key] = value
            else:
                result = await value.get_result(self, target_handle_name=key)
                self.params[key][sub_key] = result

    def _is_vertex(self, value):
        """Checks if the provided value is an instance of Vertex."""
        return isinstance(value, Vertex)

    def _is_list_of_vertices(self, value):
        """Checks if the provided value is a list of Vertex instances."""
        return all(self._is_vertex(vertex) for vertex in value)

    async def get_result(self, requester: Vertex, target_handle_name: str | None = None) -> Any:
        """Retrieves the result of the vertex.

        This is a read-only method so it raises an error if the vertex has not been built yet.

        Returns:
            The result of the vertex.
        """
        async with self._lock:
            return await self._get_result(requester, target_handle_name)

    def _log_transaction_async(
        self, flow_id: str | UUID, source: Vertex, status, target: Vertex | None = None, error=None
    ) -> None:
        task = asyncio.create_task(log_transaction(flow_id, source, status, target, error))
        self.log_transaction_tasks.add(task)
        task.add_done_callback(self.log_transaction_tasks.discard)

    async def _get_result(
        self,
        requester: Vertex,
        target_handle_name: str | None = None,  # noqa: ARG002
    ) -> Any:
        """Retrieves the result of the built component.

        If the component has not been built yet, a ValueError is raised.

        Returns:
            The built result if use_result is True, else the built object.
        """
        flow_id = self.graph.flow_id
        if not self.built:
            if flow_id:
                self._log_transaction_async(str(flow_id), source=self, target=requester, status="error")
            msg = f"Component {self.display_name} has not been built yet"
            raise ValueError(msg)

        result = self.built_result if self.use_result else self.built_object
        if flow_id:
            self._log_transaction_async(str(flow_id), source=self, target=requester, status="success")
        return result

    async def _build_vertex_and_update_params(self, key, vertex: Vertex) -> None:
        """Builds a given vertex and updates the params dictionary accordingly."""
        result = await vertex.get_result(self, target_handle_name=key)
        self._handle_func(key, result)
        if isinstance(result, list):
            self._extend_params_list_with_result(key, result)
        self.params[key] = result

    async def _build_list_of_vertices_and_update_params(
        self,
        key,
        vertices: list[Vertex],
    ) -> None:
        """Iterates over a list of vertices, builds each and updates the params dictionary."""
        self.params[key] = []
        for vertex in vertices:
            result = await vertex.get_result(self, target_handle_name=key)
            # Weird check to see if the params[key] is a list
            # because sometimes it is a Data and breaks the code
            if not isinstance(self.params[key], list):
                self.params[key] = [self.params[key]]

            if isinstance(result, list):
                self.params[key].extend(result)
            else:
                try:
                    if self.params[key] == result:
                        continue

                    self.params[key].append(result)
                except AttributeError as e:
                    logger.exception(e)
                    msg = (
                        f"Params {key} ({self.params[key]}) is not a list and cannot be extended with {result}"
                        f"Error building Component {self.display_name}: \n\n{e}"
                    )
                    raise ValueError(msg) from e

    def _handle_func(self, key, result) -> None:
        """Handles 'func' key by checking if the result is a function and setting it as coroutine."""
        if key == "func":
            if not isinstance(result, types.FunctionType):
                if hasattr(result, "run"):
                    result = result.run
                elif hasattr(result, "get_function"):
                    result = result.get_function()
            elif inspect.iscoroutinefunction(result):
                self.params["coroutine"] = result
            else:
                self.params["coroutine"] = sync_to_async(result)

    def _extend_params_list_with_result(self, key, result) -> None:
        """Extends a list in the params dictionary with the given result if it exists."""
        if isinstance(self.params[key], list):
            self.params[key].extend(result)

    async def _build_results(
        self, custom_component, custom_params, base_type: str, *, fallback_to_env_vars=False
    ) -> None:
        try:
            result = await initialize.loading.get_instance_results(
                custom_component=custom_component,
                custom_params=custom_params,
                vertex=self,
                fallback_to_env_vars=fallback_to_env_vars,
                base_type=base_type,
            )

            self.outputs_logs = build_output_logs(self, result)

            self._update_built_object_and_artifacts(result)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.exception(exc)
            msg = f"Error building Component {self.display_name}: \n\n{exc}"
            raise ComponentBuildError(msg, tb) from exc

    def _update_built_object_and_artifacts(self, result: Any | tuple[Any, dict] | tuple[Component, Any, dict]) -> None:
        """Updates the built object and its artifacts."""
        if isinstance(result, tuple):
            if len(result) == 2:  # noqa: PLR2004
                self.built_object, self.artifacts = result
            elif len(result) == 3:  # noqa: PLR2004
                self.custom_component, self.built_object, self.artifacts = result
                self.logs = self.custom_component._output_logs
                self.artifacts_raw = self.artifacts.get("raw", None)
                self.artifacts_type = {
                    self.outputs[0]["name"]: self.artifacts.get("type", None) or ArtifactType.UNKNOWN.value
                }
                self.artifacts = {self.outputs[0]["name"]: self.artifacts}
        else:
            self.built_object = result

    def _validate_built_object(self) -> None:
        """Checks if the built object is None and raises a ValueError if so."""
        if isinstance(self.built_object, UnbuiltObject):
            msg = f"{self.display_name}: {self.built_object_repr()}"
            raise TypeError(msg)
        if self.built_object is None:
            message = f"{self.display_name} returned None."
            if self.base_type == "custom_components":
                message += " Make sure your build method returns a component."

            logger.warning(message)
        elif isinstance(self.built_object, Iterator | AsyncIterator):
            if self.display_name == "Text Output":
                msg = f"You are trying to stream to a {self.display_name}. Try using a Chat Output instead."
                raise ValueError(msg)

    def _reset(self) -> None:
        self.built = False
        self.built_object = UnbuiltObject()
        self.built_result = UnbuiltResult()
        self.artifacts = {}
        self.steps_ran = []
        self.build_params()

    def _is_chat_input(self) -> bool:
        return False

    def build_inactive(self) -> None:
        # Just set the results to None
        self.built = True
        self.built_object = None
        self.built_result = None

    async def build(
        self,
        user_id=None,
        inputs: dict[str, Any] | None = None,
        files: list[str] | None = None,
        requester: Vertex | None = None,
        event_manager: EventManager | None = None,
        **kwargs,
    ) -> Any:
        async with self._lock:
            if self.state == VertexStates.INACTIVE:
                # If the vertex is inactive, return None
                self.build_inactive()
                return None

            if self.frozen and self.built:
                return await self.get_requester_result(requester)
            if self.built and requester is not None:
                # This means that the vertex has already been built
                # and we are just getting the result for the requester
                return await self.get_requester_result(requester)
            self._reset()
            # inject session_id if it is not None
            if inputs is not None and "session" in inputs and inputs["session"] is not None and self.has_session_id:
                session_id_value = self.get_value_from_template_dict("session_id")
                if session_id_value == "":
                    self.update_raw_params({"session_id": inputs["session"]}, overwrite=True)
            if self._is_chat_input() and (inputs or files):
                chat_input = {}
                if (
                    inputs
                    and isinstance(inputs, dict)
                    and "input_value" in inputs
                    and inputs.get("input_value") is not None
                ):
                    chat_input.update({"input_value": inputs.get(INPUT_FIELD_NAME, "")})
                if files:
                    chat_input.update({"files": files})

                self.update_raw_params(chat_input, overwrite=True)

            # Run steps
            for step in self.steps:
                if step not in self.steps_ran:
                    await step(user_id=user_id, event_manager=event_manager, **kwargs)
                    self.steps_ran.append(step)

            self.finalize_build()

        return await self.get_requester_result(requester)

    async def get_requester_result(self, requester: Vertex | None):
        # If the requester is None, this means that
        # the Vertex is the root of the graph
        if requester is None:
            return self.built_object

        # Get the requester edge
        requester_edge = next((edge for edge in self.edges if edge.target_id == requester.id), None)
        # Return the result of the requester edge
        return (
            None
            if requester_edge is None
            else await requester_edge.get_result_from_source(source=self, target=requester)
        )

    def add_edge(self, edge: CycleEdge) -> None:
        if edge not in self.edges:
            self.edges.append(edge)

    def __repr__(self) -> str:
        return f"Vertex(display_name={self.display_name}, id={self.id}, data={self.data})"

    def __eq__(self, __o: object) -> bool:
        try:
            if not isinstance(__o, Vertex):
                return False
            # We should create a more robust comparison
            # for the Vertex class
            ids_are_equal = self.id == __o.id
            # self.data is a dict and we need to compare them
            # to check if they are equal
            data_are_equal = self.data == __o.data
        except AttributeError:
            return False
        else:
            return ids_are_equal and data_are_equal

    def __hash__(self) -> int:
        return id(self)

    def built_object_repr(self) -> str:
        # Add a message with an emoji, stars for success,
        return "Built successfully ✨" if self.built_object is not None else "Failed to build 😵‍💫"

    def apply_on_outputs(self, func: Callable[[Any], Any]) -> None:
        """Applies a function to the outputs of the vertex."""
        if not self.custom_component or not self.custom_component.outputs:
            return
        # Apply the function to each output
        [func(output) for output in self.custom_component.outputs]
