from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from json_repair import repair_json
from pydantic import BaseModel

from lfx.graph.vertex.base import Vertex
from lfx.graph.vertex.param_handler import ParameterHandler
from lfx.log.logger import logger
from lfx.schema.graph import InputValue, Tweaks
from lfx.schema.schema import INPUT_FIELD_NAME, InputValueRequest
from lfx.services.deps import get_settings_service

if TYPE_CHECKING:
    from lfx.events.event_manager import EventManager
    from lfx.graph.graph.base import Graph
    from lfx.graph.schema import RunOutputs


def validate_and_repair_json(json_str: str | dict) -> dict[str, Any] | str:
    """Validates a JSON string and attempts to repair it if invalid.

    Args:
        json_str (str): The JSON string to validate/repair

    Returns:
        Union[Dict[str, Any], str]: The parsed JSON dict if valid/repairable,
        otherwise returns the original string
    """
    if not isinstance(json_str, str):
        return json_str
    try:
        # If invalid, attempt repair
        repaired = repair_json(json_str)
        return json.loads(repaired)
    except (json.JSONDecodeError, ImportError):
        # Return original if repair fails or module not found
        return json_str


class Result(BaseModel):
    result: Any
    session_id: str


def validate_targeted_inputs(inputs: list[InputValueRequest] | None) -> None:
    """Refuse caller-selected input components when the tweak policy is off."""
    from lfx.utils.flow_validation import TWEAK_POLICY_OFF

    if _resolve_tweak_policy() != TWEAK_POLICY_OFF:
        return

    targeted = sorted({component for request in inputs or [] for component in (request.components or [])})
    if targeted:
        from lfx.exceptions.tweaks import TweakRefusedError

        raise TweakRefusedError(targeted, reason="This deployment does not accept component-targeted inputs.")


async def run_graph_internal(
    graph: Graph,
    flow_id: str,
    *,
    stream: bool = False,
    session_id: str | None = None,
    inputs: list[InputValueRequest] | None = None,
    outputs: list[str] | None = None,
    event_manager: EventManager | None = None,
) -> tuple[list[RunOutputs], str]:
    """Run the graph and generate the result."""
    inputs = inputs or []
    effective_session_id = session_id or flow_id

    # ``off`` refuses component-targeted inputs as well as tweaks. Both aim a
    # value at a named node, so refusing only tweaks would make the setting
    # tell a half-truth. ``input_value`` and ``session_id`` keep working.
    validate_targeted_inputs(inputs)

    components = []
    inputs_list = []
    types = []
    for input_value_request in inputs:
        if input_value_request.input_value is None:
            await logger.awarning("InputValueRequest input_value cannot be None, defaulting to an empty string.")
            input_value_request.input_value = ""
        components.append(input_value_request.components or [])
        inputs_list.append({INPUT_FIELD_NAME: input_value_request.input_value})
        types.append(input_value_request.type)

    try:
        fallback_to_env_vars = get_settings_service().settings.fallback_to_env_var
    except (AttributeError, TypeError):
        fallback_to_env_vars = False

    graph.session_id = effective_session_id
    run_outputs = await graph.arun(
        inputs=inputs_list,
        inputs_components=components,
        types=types,
        outputs=outputs or [],
        stream=stream,
        session_id=effective_session_id or "",
        fallback_to_env_vars=fallback_to_env_vars,
        event_manager=event_manager,
    )
    return run_outputs, effective_session_id


async def run_graph(
    graph: Graph,
    input_value: str,
    input_type: str,
    output_type: str,
    *,
    session_id: str | None = None,
    fallback_to_env_vars: bool = False,
    output_component: str | None = None,
    stream: bool = False,
) -> list[RunOutputs]:
    """Runs the given Langflow Graph with the specified input and returns the outputs.

    Args:
        graph (Graph): The graph to be executed.
        input_value (str): The input value to be passed to the graph.
        input_type (str): The type of the input value.
        output_type (str): The type of the desired output.
        session_id (str | None, optional): The session ID to be used for the flow. Defaults to None.
        fallback_to_env_vars (bool, optional): Whether to fallback to environment variables.
            Defaults to False.
        output_component (Optional[str], optional): The specific output component to retrieve. Defaults to None.
        stream (bool, optional): Whether to stream the results or not. Defaults to False.

    Returns:
        List[RunOutputs]: A list of RunOutputs objects representing the outputs of the graph.

    """
    inputs = [InputValue(components=[], input_value=input_value, type=input_type)]
    if output_component:
        outputs = [output_component]
    else:
        outputs = [
            vertex.id
            for vertex in graph.vertices
            if output_type == "debug"
            or (vertex.is_output and (output_type == "any" or output_type in vertex.id.lower()))
        ]
    components = []
    inputs_list = []
    types = []
    for input_value_request in inputs:
        if input_value_request.input_value is None:
            logger.warning("InputValueRequest input_value cannot be None, defaulting to an empty string.")
            input_value_request.input_value = ""
        components.append(input_value_request.components or [])
        inputs_list.append({INPUT_FIELD_NAME: input_value_request.input_value})
        types.append(input_value_request.type)
    return await graph.arun(
        inputs_list,
        inputs_components=components,
        types=types,
        outputs=outputs or [],
        stream=stream,
        session_id=session_id,
        fallback_to_env_vars=fallback_to_env_vars,
    )


def validate_input(
    graph_data: dict[str, Any], tweaks: Tweaks | dict[str, str | dict[str, Any]]
) -> list[dict[str, Any]]:
    if not isinstance(graph_data, dict) or not isinstance(tweaks, dict):
        msg = "graph_data and tweaks should be dictionaries"
        raise TypeError(msg)

    nodes = graph_data.get("data", {}).get("nodes") or graph_data.get("nodes")

    if not isinstance(nodes, list):
        msg = "graph_data should contain a list of nodes under 'data' key or directly under 'nodes' key"
        raise TypeError(msg)

    return nodes


def apply_tweaks(
    node: dict[str, Any],
    node_tweaks: dict[str, Any],
    *,
    policy: str = "permissive",
    flow_declares_allowlist: bool = False,
    exempt_keys: frozenset[str] | None = None,
) -> list[str]:
    """Apply tweaks to one node's template. Return the names this node refused.

    The caller aggregates refusals across every node and raises once, so a
    single 422 can name every offending key.

    ``exempt_keys`` skips the *policy* layer for keys the runtime injected
    rather than the caller supplying them. ``stream`` is injected by
    ``process_tweaks`` on every request, so without the exemption a strict
    policy would refuse every call. The protected-field floor still applies to
    exempt keys.
    """
    exempt_keys = exempt_keys or frozenset()
    template_data = node.get("data", {}).get("node", {}).get("template")

    if not isinstance(template_data, dict):
        logger.warning(f"Template data for node {node.get('id')} should be a dictionary")
        return []

    # One function decides refusals, this one only applies them. Re-deriving the
    # floor and the policy here is exactly the shape that produced the original
    # bypass: two copies of a security predicate that drifted apart. In the
    # two-pass callers this list is already empty by the time we get here, so the
    # skip below only matters to direct callers of this function.
    refused = _refused_tweak_reasons(
        template_data,
        node.get("data", {}).get("type"),
        node_tweaks,
        policy=policy,
        flow_declares_allowlist=flow_declares_allowlist,
        exempt_keys=exempt_keys,
    )

    for tweak_name, tweak_value in node_tweaks.items():
        field = template_data.get(tweak_name)
        if not isinstance(field, dict):
            continue
        if tweak_name in refused:
            continue
        field_type = field.get("type", "")
        if field_type == "NestedDict":
            value = validate_and_repair_json(tweak_value)
            template_data[tweak_name]["value"] = value
        elif field_type == "mcp":
            # MCP fields expect dict values to be set directly
            template_data[tweak_name]["value"] = tweak_value
        elif field_type == "dict" and isinstance(tweak_value, dict):
            # Dict fields: set the dict directly as the value.
            # If the tweak is wrapped in {"value": <actual>}, unwrap it
            # to support the template-format style (e.g. from UI exports).
            # Caveat: a legitimate single-key dict {"value": x} will be unwrapped.
            if len(tweak_value) == 1 and "value" in tweak_value:
                template_data[tweak_name]["value"] = tweak_value["value"]
            else:
                template_data[tweak_name]["value"] = tweak_value
        elif isinstance(tweak_value, dict):
            for k, v in tweak_value.items():
                k_ = "file_path" if field_type == "file" else k
                template_data[tweak_name][k_] = v
            # If the user didn't explicitly set load_from_db in the dict,
            # we default to False for the override.
            if "load_from_db" not in tweak_value and "load_from_db" in template_data[tweak_name]:
                template_data[tweak_name]["load_from_db"] = False
        else:
            key = "file_path" if field_type == "file" else "value"
            template_data[tweak_name][key] = tweak_value
            if "load_from_db" in template_data[tweak_name]:
                template_data[tweak_name]["load_from_db"] = False

    return list(refused)


def _refused_tweak_reasons(
    template_data: dict[str, Any],
    component_type: str | None,
    node_tweaks: dict[str, Any],
    *,
    policy: str,
    flow_declares_allowlist: bool,
    exempt_keys: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Return each refused field with its caller-facing reason. Mutates nothing.

    Refusal has to be decided for the whole request before anything is applied.
    Applying as we go and raising at the end leaves the accepted half written,
    and the graph the run paths hand us is cached and reused, so that half
    survives into later runs that send no tweaks at all.
    """
    refused: dict[str, str] = {}
    for tweak_name in node_tweaks:
        field = template_data.get(tweak_name)
        if not isinstance(field, dict):
            continue
        reason = _tweak_refusal_reason(
            component_type,
            tweak_name,
            field.get("type", ""),
            policy,
            flow_declares_allowlist=flow_declares_allowlist,
            field_is_api_editable=field.get("api_editable") is True,
            policy_exempt=tweak_name in exempt_keys,
        )
        if reason is not None:
            if reason == _PROTECTED_TWEAK_REASON:
                logger.warning(f"Security: refusing to override protected field {tweak_name!r} via tweaks.")
            else:
                logger.warning(f"Policy {policy!r}: refusing to override field {tweak_name!r} via tweaks.")
            refused[tweak_name] = reason
    return refused


def _resolve_tweak_policy() -> str:
    """Return the deployment tweak policy, defaulting to permissive.

    Settings are unavailable in some library contexts, so a missing settings
    service falls back to the default rather than failing the run.
    """
    from lfx.utils.flow_validation import TWEAK_POLICIES, TWEAK_POLICY_PERMISSIVE

    try:
        policy = get_settings_service().settings.tweaks_policy
    except (AttributeError, TypeError):
        return TWEAK_POLICY_PERMISSIVE
    if policy not in TWEAK_POLICIES:
        logger.warning(f"Unknown tweaks policy {policy!r}; falling back to {TWEAK_POLICY_PERMISSIVE!r}.")
        return TWEAK_POLICY_PERMISSIVE
    return policy


def _effective_policy(*, caller_supplied: bool) -> str:
    """Return the policy to enforce for this application of tweaks.

    The deployment policy answers "what may a caller override". Tweaks the
    runtime generated for itself are not a caller overriding anything, so they
    are judged as ``permissive``: the protected-field floor still refuses, and
    the policy layer stays out of it. This is the same reasoning that exempts
    the injected ``stream`` key.
    """
    from lfx.utils.flow_validation import TWEAK_POLICY_PERMISSIVE

    if not caller_supplied:
        return TWEAK_POLICY_PERMISSIVE
    return _resolve_tweak_policy()


_PROTECTED_TWEAK_REASON = "The field is protected and keeps the value set by the flow author."
_DECLARED_TWEAK_REASON = (
    "This flow declares which fields the API may set. Only fields marked editable via API accept a tweak."
)
_OFF_TWEAK_REASON = "This deployment does not accept tweaks."
_REFUSAL_REASON_ORDER = (_PROTECTED_TWEAK_REASON, _DECLARED_TWEAK_REASON, _OFF_TWEAK_REASON)


def _tweak_refusal_reason(
    component_type: str | None,
    field_name: str,
    field_type: str,
    policy: str,
    *,
    flow_declares_allowlist: bool,
    field_is_api_editable: bool,
    policy_exempt: bool,
) -> str | None:
    """Return the single caller-facing reason for refusing a field, if any.

    Under ``off``, the policy alone refuses every caller-supplied field. Keep
    that response uniform so probing one field at a time cannot reveal which
    fields are also protected by the deployment floor. In the other modes the
    floor takes precedence, which is the distinction LE-2387 needs under
    ``declared``.
    """
    from lfx.utils.flow_validation import (
        TWEAK_POLICY_OFF,
        is_protected_tweak_field,
        is_tweak_refused_by_policy,
    )

    refused_by_policy = not policy_exempt and is_tweak_refused_by_policy(
        policy,
        flow_declares_allowlist=flow_declares_allowlist,
        field_is_api_editable=field_is_api_editable,
    )
    if refused_by_policy and policy == TWEAK_POLICY_OFF:
        return _OFF_TWEAK_REASON
    if is_protected_tweak_field(component_type, field_name, field_type):
        return _PROTECTED_TWEAK_REASON
    if refused_by_policy:
        return _DECLARED_TWEAK_REASON
    return None


def _combined_refusal_reason(refused: list[tuple[str, str]]) -> str:
    """Combine the generic reasons present in a request in stable priority order."""
    present_reasons = {reason for _, reason in refused}
    return " ".join(reason for reason in _REFUSAL_REASON_ORDER if reason in present_reasons)


def apply_tweaks_on_vertex(
    vertex: Vertex,
    node_tweaks: dict[str, Any],
    *,
    policy: str = "permissive",
    flow_declares_allowlist: bool = False,
) -> list[str]:
    """Apply tweaks to a built vertex. Return the names this vertex refused.

    The graph-level path runs after ``Graph`` construction, so it enforces the
    same protected-field floor and deployment policy as the pre-construction
    ``apply_tweaks``. Before this, the floor was applied inconsistently here and
    the policy not at all, so the streaming and background run modes accepted
    tweaks the sync mode refused.

    The override is written through ``update_raw_params`` as well as
    ``vertex.params``. Setting ``params`` alone does not reach the built
    component at runtime, which is the bug the two former private copies of this
    function existed to work around.
    """
    template_data = vertex.data.get("node", {}).get("template", {})
    if not isinstance(template_data, dict):
        # No usable template means nothing can be validated, so nothing is
        # applied. Refusing here instead would turn a malformed node into a
        # caller-facing error the caller cannot act on.
        return []

    # Same single-predicate rule as ``apply_tweaks``: this function applies, it
    # does not re-decide. Two copies of the floor are what let the graph path
    # accept tweaks the sync path refused in the first place.
    refused = _refused_tweak_reasons(
        template_data,
        vertex.data.get("type"),
        node_tweaks,
        policy=policy,
        flow_declares_allowlist=flow_declares_allowlist,
    )

    accepted: dict[str, Any] = {}
    for tweak_name, tweak_value in node_tweaks.items():
        field = template_data.get(tweak_name)
        # A key the template does not declare is skipped, not refused. This
        # matches ``apply_tweaks`` on the pre-construction path: an unknown key
        # has never been an error, and treating it as one here would 422 every
        # caller who sends a tweak for a component the flow no longer has.
        if not isinstance(field, dict):
            continue
        if tweak_name in refused:
            continue

        accepted[tweak_name] = tweak_value

        if tweak_name and tweak_value and tweak_name in vertex.params:
            vertex.params[tweak_name] = tweak_value

            # Determine if we should load from DB
            tweak_load_from_db = False
            if isinstance(tweak_value, dict):
                tweak_load_from_db = tweak_value.get("load_from_db", False)

            if tweak_load_from_db:
                if tweak_name not in vertex.load_from_db_fields:
                    vertex.load_from_db_fields.append(tweak_name)
            elif tweak_name in vertex.load_from_db_fields:
                vertex.load_from_db_fields.remove(tweak_name)

    if accepted:
        vertex.update_raw_params(accepted, overwrite=True)

    return list(refused)


def process_tweaks(
    graph_data: dict[str, Any],
    tweaks: Tweaks | dict[str, dict[str, Any]],
    *,
    stream: bool = False,
    caller_supplied: bool = True,
) -> dict[str, Any]:
    """This function is used to tweak the graph data using the node id and the tweaks dict.

    :param graph_data: The dictionary containing the graph data. It must contain a 'data' key with
                       'nodes' as its child or directly contain 'nodes' key. Each node should have an 'id' and 'data'.
    :param tweaks: The dictionary containing the tweaks. The keys can be the node id or the name of the tweak.
                   The values can be a dictionary containing the tweaks for the node or the value of the tweak.
    :param stream: A boolean flag indicating whether streaming should be deactivated across all components or not.
                   Default is False.
    :param caller_supplied: Whether these tweaks came from a run request. Pass False when the runtime
                   generated them itself, e.g. resolved variable values. Runtime-generated tweaks skip
                   the deployment policy for the same reason ``stream`` does: the policy governs what a
                   caller may override, and refusing a value the runtime produced would disable internal
                   machinery rather than restrict an API. The protected-field floor still applies.
    :return: The modified graph_data dictionary.
    :raises ValueError: If the input is not in the expected format.
    """
    from lfx.exceptions.tweaks import TweakRefusedError
    from lfx.utils.flow_validation import flow_declares_api_editable

    # Copied, not aliased: ``stream`` is injected below, and writing that into
    # the caller's own dict makes the key look caller-supplied on a second run
    # with the same dict. The exemption would not apply and a strict policy
    # would refuse ``stream``, a key the caller never sent.
    tweaks_dict = cast("dict[str, Any]", tweaks.model_dump()) if not isinstance(tweaks, dict) else dict(tweaks)
    # ``stream`` is injected here rather than supplied by the caller, so the
    # policy layer must not refuse it. Without this the strict policies would
    # reject every request that omits ``stream``.
    exempt_keys: frozenset[str] = frozenset()
    if "stream" not in tweaks_dict:
        tweaks_dict |= {"stream": stream}
        exempt_keys = frozenset({"stream"})
    nodes = validate_input(graph_data, cast("dict[str, str | dict[str, Any]]", tweaks_dict))
    nodes_map = {node.get("id"): node for node in nodes}
    nodes_display_name_map = {node.get("data", {}).get("node", {}).get("display_name"): node for node in nodes}

    policy = _effective_policy(caller_supplied=caller_supplied)
    flow_declares_allowlist = flow_declares_api_editable(nodes)
    refused: list[tuple[str, str]] = []

    all_nodes_tweaks = {}
    pending: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for key, value in tweaks_dict.items():
        if isinstance(value, dict):
            if (node := nodes_map.get(key)) or (node := nodes_display_name_map.get(key)):
                pending.append((node, value))
        else:
            all_nodes_tweaks[key] = value
    if all_nodes_tweaks:
        pending.extend((node, all_nodes_tweaks) for node in nodes)

    # Decide first, mutate second. A refusal must leave the payload untouched.
    for node, node_tweaks in pending:
        template_data = node.get("data", {}).get("node", {}).get("template")
        if not isinstance(template_data, dict):
            continue
        refused.extend(
            _refused_tweak_reasons(
                template_data,
                node.get("data", {}).get("type"),
                node_tweaks,
                policy=policy,
                flow_declares_allowlist=flow_declares_allowlist,
                exempt_keys=exempt_keys,
            ).items()
        )

    if refused:
        refused_fields = sorted({field_name for field_name, _ in refused})
        raise TweakRefusedError(refused_fields, reason=_combined_refusal_reason(refused))

    for node, node_tweaks in pending:
        apply_tweaks(
            node,
            node_tweaks,
            policy=policy,
            flow_declares_allowlist=flow_declares_allowlist,
            exempt_keys=exempt_keys,
        )

    return graph_data


def process_tweaks_on_graph(graph: Graph, tweaks: dict[str, dict[str, Any]], *, caller_supplied: bool = True):
    """Apply tweaks to a built graph, enforcing the floor and the policy.

    This is the post-construction counterpart to ``process_tweaks``. The
    streaming and background run modes build the graph first, so they land here
    rather than there. Both paths must refuse the same tweaks, or the deployment
    policy would only govern the sync mode.

    ``caller_supplied=False`` marks tweaks the runtime built rather than a caller
    sending them. The Run Flow component passes its own declared inputs through
    here to reach a sub-flow, so judging those against the deployment policy
    would make ``off`` disable flow-as-tool orchestration instead of closing an
    API surface. The floor still applies.
    """
    from lfx.exceptions.tweaks import TweakRefusedError
    from lfx.utils.flow_validation import flow_declares_api_editable

    policy = _effective_policy(caller_supplied=caller_supplied)
    # ``flow_declares_api_editable`` reads node dicts shaped ``{"data": {...}}``.
    # ``vertex.data`` is already that inner mapping, so wrap it back up.
    flow_declares_allowlist = flow_declares_api_editable(
        [{"data": v.data} for v in graph.vertices if isinstance(v, Vertex) and isinstance(v.data, dict)]
    )
    refused: list[tuple[str, str]] = []

    pending: list[tuple[Vertex, dict[str, Any]]] = []
    for vertex in graph.vertices:
        if isinstance(vertex, Vertex) and isinstance(vertex.id, str):
            if node_tweaks := tweaks.get(vertex.id):
                pending.append((vertex, node_tweaks))
        else:
            logger.warning("Each node should be a Vertex with an 'id' attribute of type str")

    # Decide first, mutate second. The graph reaching this function is cached and
    # reused by the Run Flow component, so a half-applied payload would survive
    # into later runs of the same sub-flow.
    for vertex, node_tweaks in pending:
        template_data = vertex.data.get("node", {}).get("template", {})
        if not isinstance(template_data, dict):
            continue
        refused.extend(
            _refused_tweak_reasons(
                template_data,
                vertex.data.get("type"),
                node_tweaks,
                policy=policy,
                flow_declares_allowlist=flow_declares_allowlist,
            ).items()
        )

    if refused:
        refused_fields = sorted({field_name for field_name, _ in refused})
        raise TweakRefusedError(refused_fields, reason=_combined_refusal_reason(refused))

    # FileInput validation can still reject an otherwise policy-allowed tweak. Validate every
    # target before applying any of them so a later invalid vertex cannot leave an earlier cached
    # vertex mutated. Keep the original values for application: unrestricted local paths are a
    # compatibility contract, and this pass exists only to validate them atomically.
    for vertex, node_tweaks in pending:
        template_data = vertex.data.get("node", {}).get("template", {})
        if not isinstance(template_data, dict):
            continue
        declared_tweaks = {
            tweak_name: tweak_value
            for tweak_name, tweak_value in node_tweaks.items()
            if isinstance(template_data.get(tweak_name), dict)
        }
        if declared_tweaks:
            ParameterHandler(vertex, storage_service=None).process_runtime_params(declared_tweaks)

    for vertex, node_tweaks in pending:
        apply_tweaks_on_vertex(
            vertex,
            node_tweaks,
            policy=policy,
            flow_declares_allowlist=flow_declares_allowlist,
        )

    return graph
