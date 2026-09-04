from __future__ import annotations

import keyword
import re
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from fastapi import HTTPException, status
from lfx.log.logger import logger
from pydantic.v1 import BaseModel, Field, create_model
from sqlalchemy.orm import aliased
from sqlmodel import asc, desc, select

from langflow.schema.schema import INPUT_FIELD_NAME
from langflow.services.database.models.flow.model import Flow, FlowRead, FlowType
from langflow.services.deps import get_settings_service, session_scope

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from lfx.graph.graph.base import Graph
    from lfx.graph.schema import RunOutputs
    from lfx.graph.vertex.base import Vertex

    from langflow.services.database.models.user.model import User

from langflow.schema.data import Data

INPUT_TYPE_MAP = {
    "ChatInput": {"type_hint": "Optional[str]", "default": '""'},
    "TextInput": {"type_hint": "Optional[str]", "default": '""'},
    "JSONInput": {"type_hint": "Optional[dict]", "default": "{}"},
}
SORT_DISPATCHER = {
    "asc": asc,
    "desc": desc,
}


def _safe_function_argument_names(inputs: list[Vertex]) -> list[str]:
    """Return unique Python identifiers for flow-tool input arguments."""
    names: list[str] = []
    used: set[str] = set()
    for index, input_ in enumerate(inputs, start=1):
        base = re.sub(r"\W", "_", input_.display_name.lower())
        if not base or not base.isidentifier() or keyword.iskeyword(base) or base == "__debug__":
            base = f"input_{index}"

        name = base
        suffix = 2
        while name in used:
            name = f"{base}_{suffix}"
            suffix += 1
        names.append(name)
        used.add(name)
    return names


async def list_flows(*, user_id: str | None = None) -> list[Data]:
    if not user_id:
        msg = "Session is invalid"
        raise ValueError(msg)
    try:
        async with session_scope() as session:
            uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
            stmt = select(Flow).where(Flow.user_id == uuid_user_id).where(Flow.is_component == False)  # noqa: E712
            flows = (await session.exec(stmt)).all()

            return [flow.to_data() for flow in flows]
    except Exception as e:
        msg = f"Error listing flows: {e}"
        raise ValueError(msg) from e


async def _list_flows_in_flow_folder(
    *,
    user_id: str | None,
    flow_id: str | None,
    order_params: dict | None,
    a2a_only: bool,
) -> list[Data]:
    """Query flows sharing ``flow_id``'s folder, optionally only those published as A2A agents."""
    if not user_id:
        msg = "Session is invalid"
        raise ValueError(msg)
    if not flow_id:
        msg = "Flow ID is required"
        raise ValueError(msg)
    try:
        async with session_scope() as session:
            uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
            uuid_flow_id = UUID(flow_id) if isinstance(flow_id, str) else flow_id
            # get all flows belonging to the specified user
            # and inside the same folder as the specified flow
            flow_ = aliased(Flow)  # flow table alias, used to retrieve the folder
            stmt = (
                select(Flow.id, Flow.name, Flow.updated_at)
                .join(flow_, Flow.folder_id == flow_.folder_id)
                .where(flow_.id == uuid_flow_id)
                .where(flow_.user_id == uuid_user_id)
                .where(Flow.user_id == uuid_user_id)
                .where(Flow.id != uuid_flow_id)
            )
            if a2a_only:
                stmt = stmt.where(Flow.a2a_enabled == True)  # noqa: E712
            # sort flows by the specified column and direction
            if order_params is not None:
                sort_col = getattr(Flow, order_params.get("column", "updated_at"), Flow.updated_at)
                sort_dir = SORT_DISPATCHER.get(order_params.get("direction", "desc"), desc)
                stmt = stmt.order_by(sort_dir(sort_col))

            flows = (await session.exec(stmt)).all()
            return [Data(data=dict(flow._mapping)) for flow in flows]  # noqa: SLF001
    except Exception as e:
        msg = f"Error listing {'A2A agents' if a2a_only else 'flows'}: {e}"
        raise ValueError(msg) from e


async def list_flows_by_flow_folder(
    *,
    user_id: str | None = None,
    flow_id: str | None = None,
    order_params: dict | None = {"column": "updated_at", "direction": "desc"},  # noqa: B006
) -> list[Data]:
    """List the user's other flows in the same folder as ``flow_id``."""
    return await _list_flows_in_flow_folder(user_id=user_id, flow_id=flow_id, order_params=order_params, a2a_only=False)


async def list_a2a_agents_by_flow_folder(
    *,
    user_id: str | None = None,
    flow_id: str | None = None,
    order_params: dict | None = {"column": "updated_at", "direction": "desc"},  # noqa: B006
) -> list[Data]:
    """List flows published as A2A agents in the same folder as ``flow_id``.

    Same shape as ``list_flows_by_flow_folder`` but restricted to flows the user has turned on
    as A2A agents (``a2a_enabled``), so the A2A Agent component offers only real agents to call
    internally, not every flow (that would just be Run Flow).
    """
    return await _list_flows_in_flow_folder(user_id=user_id, flow_id=flow_id, order_params=order_params, a2a_only=True)


async def list_flows_by_folder_id(
    *, user_id: str | None = None, folder_id: str | None = None, order_params: dict | None = None
) -> list[Data]:
    if not user_id:
        msg = "Session is invalid"
        raise ValueError(msg)
    if not folder_id:
        msg = "Folder ID is required"
        raise ValueError(msg)

    if order_params is None:
        order_params = {"column": "updated_at", "direction": "desc"}

    try:
        async with session_scope() as session:
            uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
            uuid_folder_id = UUID(folder_id) if isinstance(folder_id, str) else folder_id
            stmt = (
                select(Flow.id, Flow.name, Flow.updated_at)
                .where(Flow.user_id == uuid_user_id)
                .where(Flow.folder_id == uuid_folder_id)
            )
            if order_params is not None:
                sort_col = getattr(Flow, order_params.get("column", "updated_at"), Flow.updated_at)
                sort_dir = SORT_DISPATCHER.get(order_params.get("direction", "desc"), desc)
                stmt = stmt.order_by(sort_dir(sort_col))

            flows = (await session.exec(stmt)).all()
            return [Data(data=dict(flow._mapping)) for flow in flows]  # noqa: SLF001
    except Exception as e:
        msg = f"Error listing flows: {e}"
        raise ValueError(msg) from e


async def get_flow_by_id_or_name(
    *,
    user_id: str | None = None,
    flow_id: str | None = None,
    flow_name: str | None = None,
) -> Data | None:
    if not user_id:
        msg = "Session is invalid"
        raise ValueError(msg)
    if not (flow_id or flow_name):
        msg = "Flow ID or Flow Name is required"
        raise ValueError(msg)

    # set user provided flow id or flow name.
    # if both are provided, flow_id is used.
    attr, val = None, None
    if flow_name:
        attr = "name"
        val = flow_name
    if flow_id:
        attr = "id"
        val = flow_id
    if not (attr and val):
        msg = "Flow id or Name is required"
        raise ValueError(msg)
    try:
        async with session_scope() as session:
            uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id  # type: ignore[assignment]
            uuid_flow_id_or_name = val  # type: ignore[assignment]
            if isinstance(val, str) and attr == "id":
                uuid_flow_id_or_name = UUID(val)  # type: ignore[assignment]
            stmt = select(Flow).where(Flow.user_id == uuid_user_id).where(getattr(Flow, attr) == uuid_flow_id_or_name)
            flow = (await session.exec(stmt)).first()
            return flow.to_data() if flow else None

    except Exception as e:
        msg = f"Error getting flow by id: {e}"
        raise ValueError(msg) from e


async def _build_graph_from_authorized_flow(
    *,
    flow: Flow,
    flow_id: str,
    user_id: str,
    tweaks: dict | None,
) -> Graph:
    """Build a Graph from an already-authorized target flow row."""
    from lfx.graph.graph.base import Graph

    from langflow.processing.process import process_tweaks

    graph_data = flow.data
    if not graph_data:
        msg = f"Flow {flow_id} not found"
        raise ValueError(msg)
    if tweaks:
        # Component-side, not caller-side. The only routes here are the generated
        # flow-as-tool function below and ``CustomComponent.run_flow``, both of
        # which build these tweaks from their own declared inputs. Judging them
        # against the deployment policy would make ``off`` stop an agent from
        # calling a flow as a tool. The protected-field floor still applies.
        graph_data = process_tweaks(graph_data=graph_data, tweaks=tweaks, caller_supplied=False)
    return Graph.from_payload(graph_data, flow_id=flow_id, user_id=user_id)


async def _resolve_authorized_target_flow(
    *,
    user_id: str | UUID,
    flow_id: str | UUID | None = None,
    flow_name: str | None = None,
) -> tuple[User, Flow]:
    """Freshly load and authorize a nested target flow for the calling user."""
    from langflow.services.authorization import FlowAction, ensure_flow_permission
    from langflow.services.authorization.fetch import authorized_or_owner_scoped
    from langflow.services.database.models.user.model import User

    if not user_id:
        msg = "Session is invalid"
        raise ValueError(msg)
    if not flow_id and not flow_name:
        msg = "Flow ID or Flow Name is required"
        raise ValueError(msg)
    if not flow_id and flow_name:
        flow_id = await find_flow(flow_name, str(user_id))
        if not flow_id:
            msg = f"Flow {flow_name} not found"
            raise ValueError(msg)

    uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
    uuid_flow_id = UUID(flow_id) if isinstance(flow_id, str) else flow_id
    if uuid_flow_id is None:
        msg = "Flow ID or Flow Name is required"
        raise ValueError(msg)

    async with session_scope() as session:
        flow = await authorized_or_owner_scoped(
            session,
            Flow,
            id_column=Flow.id,
            resource_id=uuid_flow_id,
            owner_column=Flow.user_id,
            owner_id=uuid_user_id,
        )
        if flow is None:
            msg = f"Flow {flow_id} not found"
            raise ValueError(msg)

        caller = await session.get(User, uuid_user_id)
        if caller is None:
            msg = "Session is invalid"
            raise ValueError(msg)

        try:
            await ensure_flow_permission(
                caller,
                FlowAction.EXECUTE,
                flow_id=flow.id,
                flow_user_id=flow.user_id,
                workspace_id=flow.workspace_id,
                folder_id=flow.folder_id,
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_403_FORBIDDEN:
                msg = f"Flow {flow_id} not found"
                raise ValueError(msg) from exc
            raise

    return caller, flow


@asynccontextmanager
async def scoped_model_provider_policy_for_target_flow(
    *,
    user_id: str | UUID,
    flow_id: str | UUID | None = None,
    flow_name: str | None = None,
) -> AsyncIterator[Flow]:
    """Bind a freshly resolved nested target scope for build and execution.

    The target row is reloaded on every entry, including cache hits, so role
    revocation and project moves take effect immediately. ContextVar nesting
    restores the caller's scope on success, failure, and concurrent tasks.
    """
    from langflow.services.model_provider_policy_scope import scoped_model_provider_policy_for_flow

    caller, flow = await _resolve_authorized_target_flow(
        user_id=user_id,
        flow_id=flow_id,
        flow_name=flow_name,
    )
    with scoped_model_provider_policy_for_flow(
        flow,
        user_id=caller.id,
        is_superuser=bool(caller.is_superuser),
    ):
        yield flow


async def load_flow(
    user_id: str, flow_id: str | None = None, flow_name: str | None = None, tweaks: dict | None = None
) -> Graph:
    """Load a flow graph after authorizing EXECUTE for the caller."""
    async with scoped_model_provider_policy_for_target_flow(
        user_id=user_id,
        flow_id=flow_id,
        flow_name=flow_name,
    ) as flow:
        return await _build_graph_from_authorized_flow(
            flow=flow,
            flow_id=str(flow.id),
            user_id=str(user_id),
            tweaks=tweaks,
        )


async def find_flow(flow_name: str, user_id: str) -> str | None:
    async with session_scope() as session:
        uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
        stmt = select(Flow).where(Flow.name == flow_name).where(Flow.user_id == uuid_user_id)
        flow = (await session.exec(stmt)).first()
        return flow.id if flow else None


async def run_flow(
    inputs: dict | list[dict] | None = None,
    tweaks: dict | None = None,
    flow_id: str | None = None,
    flow_name: str | None = None,
    output_type: str | None = "chat",
    user_id: str | None = None,
    run_id: str | None = None,
    session_id: str | None = None,
    graph: Graph | None = None,
) -> list[RunOutputs]:
    if user_id is None:
        msg = "Session is invalid"
        raise ValueError(msg)

    graph_flow_id = getattr(graph, "flow_id", None) if graph is not None else None
    if flow_id is not None and graph_flow_id is not None and str(flow_id) != str(graph_flow_id):
        msg = "Provided flow ID does not match the graph's target flow"
        raise ValueError(msg)
    target_flow_id = flow_id or graph_flow_id
    target_flow_name = flow_name or (getattr(graph, "flow_name", None) if graph is not None else None)

    async with scoped_model_provider_policy_for_target_flow(
        user_id=user_id,
        flow_id=target_flow_id,
        flow_name=target_flow_name,
    ) as target_flow:
        if graph is None:
            graph = await _build_graph_from_authorized_flow(
                flow=target_flow,
                flow_id=str(target_flow.id),
                user_id=str(user_id),
                tweaks=tweaks,
            )
        if run_id:
            graph.set_run_id(UUID(run_id))
        if session_id:
            graph.session_id = session_id
        graph.user_id = str(user_id)

        if inputs is None:
            inputs = []
        if isinstance(inputs, dict):
            inputs = [inputs]
        inputs_list = []
        inputs_components = []
        types = []
        for input_dict in inputs:
            inputs_list.append({INPUT_FIELD_NAME: cast("str", input_dict.get("input_value"))})
            inputs_components.append(input_dict.get("components", []))
            types.append(input_dict.get("type", "chat"))

        outputs = [
            vertex.id
            for vertex in graph.vertices
            if output_type == "debug"
            or (
                vertex.is_output and (output_type == "any" or output_type in vertex.id.lower())  # type: ignore[operator]
            )
        ]

        fallback_to_env_vars = get_settings_service().settings.fallback_to_env_var

        from lfx.run.hitl import raise_if_nested_hitl_unsupported

        # A nested run cannot pause: a Human Input in here would silently not pause. Fail loud instead.
        raise_if_nested_hitl_unsupported(graph)

        return await graph.arun(
            inputs_list,
            outputs=outputs,
            inputs_components=inputs_components,
            types=types,
            fallback_to_env_vars=fallback_to_env_vars,
        )


def generate_function_for_flow(
    inputs: list[Vertex], flow_id: str, user_id: str | UUID | None
) -> Callable[..., Awaitable[Any]]:
    """Generate a dynamic flow function based on the given inputs and flow ID.

    Args:
        inputs (List[Vertex]): The list of input vertices for the flow.
        flow_id (str): The ID of the flow.
        user_id (str | UUID | None): The user ID associated with the flow.

    Returns:
        Coroutine: The dynamic flow function.

    Raises:
        None

    Example:
        inputs = [vertex1, vertex2]
        flow_id = "my_flow"
        function = generate_function_for_flow(inputs, flow_id)
        result = function(input1, input2)
    """
    # Prepare function arguments with type hints and default values
    safe_arg_names = _safe_function_argument_names(inputs)
    args = [
        (f"{arg_name}: {INPUT_TYPE_MAP[input_.base_name]['type_hint']} = {INPUT_TYPE_MAP[input_.base_name]['default']}")
        for input_, arg_name in zip(inputs, safe_arg_names, strict=True)
    ]

    # Use vertex IDs for tweaks so duplicate display names remain independently addressable.
    input_ids = [str(input_.id) for input_ in inputs]

    # Prepare a Pythonic, valid function argument string
    func_args = ", ".join(args)

    # Map input vertex IDs to their corresponding Pythonic variable names in the function.
    arg_mappings = ", ".join(f"{input_id!r}: {name}" for input_id, name in zip(input_ids, safe_arg_names, strict=True))

    func_body = f"""
from typing import Optional
async def flow_function({func_args}):
    tweaks = {{ {arg_mappings} }}
    from langflow.helpers.flow import run_flow
    from langchain_core.tools import ToolException
    from lfx.base.flow_processing.utils import build_data_from_result_data, format_flow_output_data
    try:
        run_outputs = await run_flow(
            tweaks={{key: {{'input_value': value}} for key, value in tweaks.items()}},
            flow_id={flow_id!r},
            user_id={str(user_id)!r}
        )
        if not run_outputs:
                return []
        run_output = run_outputs[0]

        data = []
        if run_output is not None:
            for output in run_output.outputs:
                if output:
                    data.extend(build_data_from_result_data(output))
        return format_flow_output_data(data)
    except Exception as e:
        raise ToolException(f'Error running flow: {{e}}') from e
"""

    compiled_func = compile(func_body, "<string>", "exec")
    local_scope: dict = {}
    exec(compiled_func, globals(), local_scope)  # noqa: S102
    return local_scope["flow_function"]


def build_function_and_schema(
    flow_data: Data, graph: Graph, user_id: str | UUID | None
) -> tuple[Callable[..., Awaitable[Any]], type[BaseModel]]:
    """Builds a dynamic function and schema for a given flow.

    Args:
        flow_data (Data): The flow record containing information about the flow.
        graph (Graph): The graph representing the flow.
        user_id (str): The user ID associated with the flow.

    Returns:
        Tuple[Callable, BaseModel]: A tuple containing the dynamic function and the schema.
    """
    flow_id = flow_data.id
    inputs = get_flow_inputs(graph)
    dynamic_flow_function = generate_function_for_flow(inputs, flow_id, user_id=user_id)
    schema = build_schema_from_inputs(flow_data.name, inputs)
    return dynamic_flow_function, schema


def get_flow_inputs(graph: Graph) -> list[Vertex]:
    """Retrieves the flow inputs from the given graph.

    Args:
        graph (Graph): The graph object representing the flow.

    Returns:
        List[Data]: A list of input data, where each record contains the ID, name, and description of the input vertex.
    """
    return [vertex for vertex in graph.vertices if vertex.is_input]


def build_schema_from_inputs(name: str, inputs: list[Vertex]) -> type[BaseModel]:
    """Builds a schema from the given inputs.

    Args:
        name (str): The name of the schema.
        inputs (List[tuple[str, str, str]]): A list of tuples representing the inputs.
            Each tuple contains three elements: the input name, the input type, and the input description.

    Returns:
        BaseModel: The schema model.

    """
    fields = {}
    safe_arg_names = _safe_function_argument_names(inputs)
    for input_, field_name in zip(inputs, safe_arg_names, strict=True):
        description = input_.description
        fields[field_name] = (str, Field(default="", description=description))
    return create_model(name, **fields)


def get_arg_names(inputs: list[Vertex]) -> list[dict[str, str]]:
    """Returns a list of dictionaries containing the component name and its corresponding argument name.

    Args:
        inputs (List[Vertex]): A list of Vertex objects representing the inputs.

    Returns:
        List[dict[str, str]]: A list of dictionaries, where each dictionary contains the component name and its
            argument name.
    """
    safe_arg_names = _safe_function_argument_names(inputs)
    return [
        {"component_name": str(input_.id), "arg_name": arg_name}
        for input_, arg_name in zip(inputs, safe_arg_names, strict=True)
    ]


async def get_flow_by_id_or_endpoint_name(
    flow_id_or_name: str,
    user_id: str | UUID | None = None,
    *,
    widen_for_shares: bool = False,
) -> FlowRead:
    """Resolve a flow by UUID or endpoint_name.

    By default this is owner-scoped (``user_id`` must match the flow owner)
    even when an authorization plugin is registered.  Callers that
    immediately follow up with ``ensure_flow_permission(...)`` and therefore
    *want* the widening — so a shared flow becomes reachable — can opt in by
    passing ``widen_for_shares=True``.  Helpers that read ``flow.data`` without
    a subsequent permission check (e.g. agentic MCP tools) must leave the
    default, otherwise widening leaks graph metadata for another user's flow
    before any policy decision runs.

    SECURITY — ``user_id``: passing ``user_id=None`` disables owner scoping and
    resolves the flow by id/endpoint_name ALONE (any user's flow). This is an
    intentional contract for trusted internal callers, but it means every caller
    MUST pass the authenticated user's id. Never wire this as a FastAPI
    ``Depends`` whose ``user_id`` comes from a request-controlled (and possibly
    unset) query param, and never forward a caller-supplied ``user_id`` that was
    not derived from the authenticated identity — either reintroduces a flow
    IDOR.
    """
    from langflow.services.deps import get_authorization_service

    authz = get_authorization_service()
    # Widening also requires the plugin contract to advertise cross-user fetch
    # AND AUTHZ_ENABLED to be on, in addition to the opt-in flag above.
    share_aware = widen_for_shares and await authz.supports_cross_user_fetch() and await authz.is_enabled()

    async with session_scope() as session:
        # SECURITY: previously the UUID branch below called
        # ``session.get(Flow, flow_id)`` with no ownership check, so any
        # authenticated caller could resolve any other user's flow by UUID.
        # The endpoint_name branch scoped by ``user_id`` only when a truthy
        # value was passed, so callers using this as a FastAPI ``Depends``
        # (which resolves ``user_id`` from a query param that no one sets) had
        # the same hole on both branches.  Normalize ``user_id`` once and
        # enforce it on both branches -- returning None on cross-user lookup
        # so the shared 404 below fires and we don't disclose existence of
        # another user's flow.
        uuid_user_id: UUID | None = None
        if user_id is not None:
            # Malformed user_id -- e.g. ``?user_id=foo`` on a legacy Depends
            # route -- previously raised a raw ValueError (500 to the client).
            # Fail closed: convert to 404 so we never disclose a flow to a
            # caller whose identity we can't resolve.
            try:
                uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
            except (ValueError, AttributeError) as exc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Flow identifier {flow_id_or_name} not found",
                ) from exc
        try:
            flow_id = UUID(flow_id_or_name)
            flow = await session.get(Flow, flow_id)
            if flow is not None and uuid_user_id is not None and not share_aware and flow.user_id != uuid_user_id:
                flow = None
        except ValueError:
            endpoint_name = flow_id_or_name
            stmt = select(Flow).where(Flow.endpoint_name == endpoint_name)
            if uuid_user_id is not None and not share_aware:
                stmt = stmt.where(Flow.user_id == uuid_user_id)
            flow = (await session.exec(stmt)).first()
        if flow is None:
            raise HTTPException(status_code=404, detail=f"Flow identifier {flow_id_or_name} not found")
        return FlowRead.model_validate(flow, from_attributes=True)


async def generate_unique_flow_name(flow_name, user_id, session):
    original_name = flow_name
    n = 1
    while True:
        # Check if a flow with the given name exists
        existing_flow = (
            await session.exec(
                select(Flow).where(
                    Flow.name == flow_name,
                    Flow.user_id == user_id,
                )
            )
        ).first()

        # If no flow with the given name exists, return the name
        if not existing_flow:
            return flow_name

        # If a flow with the name already exists, append (n) to the name and increment n
        flow_name = f"{original_name} ({n})"
        n += 1


def _get_flow_input_nodes(flow: Flow) -> list[Vertex]:
    from lfx.graph.graph.base import Graph

    graph = Graph.from_payload(flow.data or {})
    return [vertex for vertex in graph.vertices if vertex.is_input]


def _is_visible_input_field(field_data: Any) -> bool:
    return isinstance(field_data, dict) and field_data.get("show", False) and not field_data.get("advanced", False)


# ``input_value`` carries the flow's chat message. ``handle_call_tool`` pops it before the tweak
# filter runs and forwards it as ``SimplifiedAPIRequest.input_value``, so the runtime accepts it
# whatever the allowlist says. Withholding it from the advertised schema publishes a contract
# narrower than the one actually served, and a caller obeying that schema sends no message at all.
_ALWAYS_EXPOSED_INPUT_FIELDS = frozenset({"input_value"})


def _input_nodes_declare_api_allowlist(input_nodes: list[Vertex]) -> bool:
    """Return whether any input node marks a template field ``api_editable``.

    This mirrors ``lfx.utils.flow_validation.flow_declares_api_editable`` and the reasoning
    recorded there: a flow whose author toggled at least one field has declared an allowlist, so
    the untoggled fields close. A flow with no toggles has declared nothing and keeps its previous
    permissive contract. ``api_editable`` defaults to ``False``, is written only by the Inspector's
    API toggle, and has no backfill, so without this fallback the flag empties the advertised schema
    of every flow nobody hand-prepared -- including every flow the UI creates from a template.

    Scoped to input nodes because those are the only fields MCP can advertise. A toggle elsewhere in
    the flow is an API-snippet concern and must not reshape the MCP contract.
    """
    for node in input_nodes:
        template = node.data.get("node", {}).get("template")
        if not isinstance(template, dict):
            continue
        if any(isinstance(field, dict) and field.get("api_editable") is True for field in template.values()):
            return True
    return False


def _is_exposed_input_field(field_name: str, field_data: Any, *, honor_allowlist: bool) -> bool:
    """Return whether an input node's field belongs in the advertised input contract."""
    if not _is_visible_input_field(field_data):
        return False
    if not honor_allowlist or field_name in _ALWAYS_EXPOSED_INPUT_FIELDS:
        return True
    return field_data.get("api_editable") is True


_JSON_SCHEMA_TYPE_BY_FIELD_TYPE = {
    "str": "string",
    "string": "string",
    "int": "integer",
    "integer": "integer",
    "float": "number",
    "number": "number",
    "slider": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "dict": "object",
    "NestedDict": "object",
    "duration": "object",
    "auth": "object",
    "mcp": "object",
    "data_display": "object",
    "object": "object",
    "array": "array",
    "connect": "string",
    "file": "string",
    "prompt": "string",
    "mustache": "string",
    "code": "string",
    "other": "string",
    "link": "string",
    "tab": "string",
    "query": "string",
    "knowledge_backend": "string",
}

_JSON_SCHEMA_ARRAY_ITEM_TYPE_BY_FIELD_TYPE = {
    "sortableList": "object",
    "actionPicker": "string",
    "table": "object",
    "tools": "object",
    "model": "object",
}


def _json_schema_type_for_field(field_data: dict[str, Any]) -> dict[str, Any]:
    field_type = field_data.get("type", "string")
    array_item_type = _JSON_SCHEMA_ARRAY_ITEM_TYPE_BY_FIELD_TYPE.get(field_type)
    if array_item_type is not None:
        return {"type": "array", "items": {"type": array_item_type}}

    json_schema_type = _JSON_SCHEMA_TYPE_BY_FIELD_TYPE.get(field_type)
    if json_schema_type is None:
        logger.warning(f"Unknown field type: {field_type} defaulting to string")
        json_schema_type = "string"

    if field_data.get("list") is True or field_data.get("is_list") is True:
        return {"type": "array", "items": {"type": json_schema_type}}
    return {"type": json_schema_type}


def get_flow_input_tweaks(flow: Flow, inputs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map advertised MCP inputs to node-scoped flow tweaks."""
    tweaks: dict[str, dict[str, Any]] = {}
    input_nodes = _get_flow_input_nodes(flow)
    honor_allowlist = _input_nodes_declare_api_allowlist(input_nodes)
    for node in input_nodes:
        template = node.data["node"]["template"]
        node_tweaks = {
            field_name: inputs[field_name]
            for field_name, field_data in template.items()
            if field_name in inputs and _is_exposed_input_field(field_name, field_data, honor_allowlist=honor_allowlist)
        }
        if node_tweaks:
            tweaks[node.id] = node_tweaks

    return tweaks


def json_schema_from_flow(flow: Flow, *, require_api_editable: bool = True) -> dict:
    """Generate JSON schema from flow input nodes.

    MCP schemas honor a flow's API exposure allowlist once the flow declares one. Other consumers,
    such as A2A, include every visible, non-advanced field in their input contract.
    """
    properties = {}
    required = []
    input_nodes = _get_flow_input_nodes(flow)
    honor_allowlist = require_api_editable and _input_nodes_declare_api_allowlist(input_nodes)
    for node in input_nodes:
        node_data = node.data["node"]
        template = node_data["template"]

        for field_name, field_data in template.items():
            if _is_exposed_input_field(field_name, field_data, honor_allowlist=honor_allowlist):
                properties[field_name] = {
                    **_json_schema_type_for_field(field_data),
                    "description": field_data.get("info", f"Input for {field_name}"),
                }

                if field_data.get("required", False):
                    required.append(field_name)

    if "session_id" not in properties:
        properties["session_id"] = {
            "type": "string",
            "description": (
                "Optional session identifier used to persist conversation "
                "history across tool calls. Omit to start a new session."
            ),
        }

    return {"type": "object", "properties": properties, "required": required}


# Built-in agents matched by their component ``name`` (stored as ``node.data.type``). The name is the
# stable flow-matching identifier and never changes, so this classifies an agent flow even when the
# node's stored source was saved by an older build and no longer evaluates. Custom agent components
# (an unknown name) still fall through to the eval-based check below.
_AGENT_TYPE_NAMES = frozenset({"Agent"})


def suggest_flow_type(flow_data: dict | None) -> FlowType:
    """Suggest ``agent`` vs ``workflow`` for a flow based on its graph contents.

    Returns ``FlowType.AGENT`` if any node is a known agent component (matched by its stable
    ``node.data.type`` name) or resolves to a subclass of ``LCAgentComponent``, else
    ``FlowType.WORKFLOW``. This is a UI default suggestion only, never the stored source of truth, so
    it never raises: any node it cannot resolve is skipped and the flow falls back to ``WORKFLOW``.
    A custom component's class is recovered from its own stored source
    (``node.data.node.template.code.value``) via ``eval_custom_component_code``, which evaluates the
    class definition without instantiating or running it; the name fast-path handles flows whose
    stored code predates the lfx module split and no longer evaluates.
    """
    from lfx.base.agents.agent import LCAgentComponent
    from lfx.custom.eval import eval_custom_component_code

    nodes = (flow_data or {}).get("nodes") or []
    for node in nodes:
        node_data = node.get("data") or {}
        # Version-stable fast path before the fragile eval: a built-in agent classifies by name even
        # if its stored code can't be evaluated in this build.
        if node_data.get("type") in _AGENT_TYPE_NAMES:
            return FlowType.AGENT
        try:
            code = node_data["node"]["template"]["code"]["value"]
        except (KeyError, TypeError):
            continue
        if not code:
            continue
        try:
            component_class = eval_custom_component_code(code)
        except Exception:  # noqa: BLE001 - a suggestion must never fail the caller
            logger.debug("suggest_flow_type: skipping a node whose code could not be evaluated", exc_info=True)
            continue
        try:
            if issubclass(component_class, LCAgentComponent):
                return FlowType.AGENT
        except TypeError:
            continue
    return FlowType.WORKFLOW
