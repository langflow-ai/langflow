"""Plan / build / run / generate orchestration tools.

The "do the bigger thing" tools — propose a plan to the user, build a whole
flow from a spec, execute the canvas flow, generate a brand-new component.
Each is decoupled from ``langflow`` via late imports (``lfx`` ships without
the backend), and the run/generate tools coordinate with the per-request
state in ``_state`` so the canvas the user sees is the canvas that runs.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from lfx.custom import Component
from lfx.graph.flow_builder.builder import build_flow_from_spec
from lfx.io import MessageTextInput, Output
from lfx.log.logger import logger
from lfx.schema import Data

from ._state import (
    _current_flow_id_var,
    _emit,
    _ensure_working_flow,
    _load_registry_user_aware,
    emit_tool_start,
    get_working_flow,
    isolate_flow_run_context,
)


class ProposePlan(Component):
    """Propose a build plan to the user and pause until they approve or dismiss.

    Emitted as a `propose_plan` event with the markdown body; the assistant
    service forwards it to the frontend, which renders a Continue/Dismiss card
    in the chat. The agent MUST stop after this tool call — the user's reply
    arrives as a new user turn (Continue ⇒ "User approved the plan. Proceed.",
    Dismiss ⇒ free-form refinement feedback).
    """

    display_name = "Propose Plan"
    description = (
        "Propose a high-level build plan to the user as markdown. The user sees a "
        "Continue/Dismiss card and the agent must wait for the next user turn before "
        "calling any other tools."
    )
    icon = "ClipboardList"
    name = "ProposePlan"

    inputs = [
        MessageTextInput(
            name="plan",
            display_name="Plan (Markdown)",
            info=(
                "Markdown text describing what the agent will build. Should cover the "
                "components to add, the model/persona, and any non-obvious configuration. "
                "Keep it readable for the user — they will Continue or Dismiss it."
            ),
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="plan_result", display_name="Plan Result", method="propose_plan"),
    ]

    def propose_plan(self) -> Data:
        plan = (self.plan or "").strip()
        if not plan:
            error_msg = (
                "Plan is empty. Provide a non-empty markdown description of what you intend to build, "
                "then call propose_plan again."
            )
            return Data(data={"error": error_msg, "text": error_msg})

        _emit("propose_plan", markdown=self.plan)
        marker = (
            "Plan emitted to the user. STOP — do NOT call any other tools. "
            "The user's Continue/Dismiss reply arrives as the next user turn. "
            "On Continue, proceed with search_components / describe_component / build_flow. "
            "On Dismiss, the user will send refinement feedback — replan with propose_plan."
        )
        return Data(data={"text": marker, "status": "awaiting_user_approval"})


class BuildFlowFromSpec(Component):
    display_name = "Build Flow"
    description = (
        "Build a complete flow from a text spec. Use for building entire flows at once. "
        "For incremental changes, use add_component/connect_components instead."
    )
    icon = "Workflow"
    name = "BuildFlowFromSpec"

    inputs = [
        MessageTextInput(
            name="spec",
            display_name="Flow Spec",
            info=(
                "Text spec defining the flow. Format:\n"
                "  name: My Flow\n"
                "  nodes:\n"
                "    A: ChatInput\n"
                "    B: ChatOutput\n"
                "  edges:\n"
                "    A.message -> B.input_value\n"
                "  config:\n"
                "    A.input_value: hello"
            ),
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="flow_result", display_name="Flow Result", method="build_flow"),
    ]

    def build_flow(self) -> Data:
        emit_tool_start("build_flow")
        existing = get_working_flow()
        if existing and existing.get("data", {}).get("nodes"):
            node_count = len(existing["data"]["nodes"])
            logger.warning("build_flow called on non-empty canvas (%d nodes) -- replacing", node_count)

        # User-aware registry: user-registered Components (Layer-2 validated
        # generation) stay addressable in the spec by their class name.
        result = build_flow_from_spec(self.spec, registry=_load_registry_user_aware())
        if "error" in result:
            error_msg = f"Flow build failed: {result['error']}"
            if "details" in result:
                error_msg += f"\nDetails: {result['details']}"
            # Anti-churn: without this the agent restarts discovery after a
            # failed build and exhausts its recursion budget (loop_flow eval).
            error_msg += (
                "\nCorrect the spec using the error above and call build_flow again NOW — "
                "do NOT re-run search_components or describe_component for components "
                "you already inspected this turn."
            )
            logger.warning("build_flow_from_spec failed: %s", result["error"])
            result["text"] = error_msg
        elif "flow" in result:
            orphan_ids = _find_orphan_nodes(result["flow"])
            # A single-component flow is a valid standalone build (no edges by
            # definition) — only reject when 2+ nodes exist but wiring is missing.
            if orphan_ids and result.get("node_count", len(orphan_ids)) > 1:
                # Safety net for the prompt-level orphan ban: reject so the LLM
                # retries instead of rendering an unconnected component.
                error_msg = (
                    f"Flow build rejected: orphan components with no edges: {orphan_ids}. "
                    "Either wire each component into the flow or remove it from the spec, "
                    "then call build_flow again."
                )
                logger.warning("build_flow_from_spec produced orphans: %s", orphan_ids)
                return Data(data={"error": error_msg, "text": error_msg, "orphans": orphan_ids})
            result["text"] = (
                f"Flow '{result['name']}' built successfully "
                f"({result['node_count']} nodes, {result['edge_count']} edges)."
            )
            # Mutate the working-flow dict in place: a ContextVar `.set()` rebind is
            # invisible to sibling tool contexts (run_flow would see the old flow).
            working = _ensure_working_flow()
            working.clear()
            working.update(result["flow"])
            _emit("set_flow", flow=result["flow"])
        return Data(data=result)


def _find_orphan_nodes(flow: dict) -> list[str]:
    """Return the IDs of nodes that have no edges (incoming or outgoing).

    A 1-node flow is treated as all-orphans by definition: a flow with no edges
    has no execution path. Callers can distinguish 1-node specs by inspecting
    the result's node_count if needed.
    """
    data = flow.get("data") or {}
    nodes = data.get("nodes") or []
    edges = data.get("edges") or []

    connected: set[str] = set()
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src:
            connected.add(src)
        if tgt:
            connected.add(tgt)

    orphans: list[str] = []
    for node in nodes:
        node_id = node.get("id") or node.get("data", {}).get("id")
        if node_id and node_id not in connected:
            orphans.append(node_id)
    return orphans


def _format_run_metrics(metrics: dict) -> str:
    """Render run metrics as one human line the agent can repeat verbatim.

    Always reports wall time; appends token usage only when an LLM was
    actually involved (total > 0), so non-LLM flows don't read "0 tokens".
    """
    if not metrics:
        return ""
    duration = metrics.get("duration_seconds") or 0
    parts = [f"Ran in {duration:g}s"]
    total = metrics.get("total_tokens") or 0
    if total:
        in_tok = metrics.get("input_tokens") or 0
        out_tok = metrics.get("output_tokens") or 0
        parts.append(f"used {total} tokens ({in_tok} in / {out_tok} out)")
    return f"({' · '.join(parts)})"


class RunFlow(Component):
    """Run the user's current canvas flow and return its result.

    Executes the working flow exactly as it is on the canvas (honoring any
    unsaved assistant edits) with the components' currently-configured
    values — no input is invented. Vertex-build events are forwarded so the
    canvas animates like a normal Run, and the result text is returned to
    the agent so it can answer follow-up questions about it.

    Decoupled from ``langflow`` via a late import (same pattern as
    ``_load_registry_user_aware``): ``lfx`` may run without the backend.
    """

    display_name = "Run Flow"
    description = (
        "Execute the user's current flow on the canvas (with its configured values) and "
        "return the result. Use when the user asks to run/test/execute the flow or asks "
        "about what it produces. The canvas animates while it runs; the result comes back "
        "so you can discuss it. Do not invent inputs; run it as configured."
    )
    icon = "Play"
    name = "RunFlow"

    inputs = [
        MessageTextInput(
            name="reason",
            display_name="Reason",
            info="Optional short note on why you are running the flow (does not change the run).",
            required=False,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="run_result", display_name="Run Result", method="run_flow"),
    ]

    async def run_flow(self) -> Data:
        flow = _ensure_working_flow()
        nodes = (flow.get("data") or {}).get("nodes") or []
        if not nodes:
            msg = "There is no flow on the canvas to run. Build or add components first."
            return Data(data={"error": msg, "text": msg})

        try:
            from langflow.agentic.services.flow_run import run_working_flow
        except ImportError:
            msg = "Flow execution is not available in this environment."
            return Data(data={"error": msg, "text": msg})

        try:
            from langflow.agentic.services.user_components_context import current_user_id

            user_id = current_user_id()
        except ImportError:
            user_id = None

        # The run engine requires a valid UUID flow id ("badly formed hexadecimal
        # UUID string" otherwise); fall back to a fresh uuid4 when none persisted.
        flow_id = _current_flow_id_var.get() or str(uuid4())

        # Model-less Agents get the assistant's verified credential, but a model the
        # user explicitly set must never be swapped (overwrite_existing_model=False).
        try:
            from langflow.agentic.services.agent_run_context import (
                current_agent_run_model,
                current_requested_agent_model,
            )
            from langflow.agentic.services.flow_preparation import inject_model_into_flow

            requested = current_requested_agent_model() or {}
            req_provider = requested.get("provider")
            req_model_name = requested.get("model_name")
            run_model = current_agent_run_model() or {}
            run_provider = run_model.get("provider")
            run_model_name = run_model.get("model_name")
            if req_provider and req_model_name:
                # User explicitly named a model — enforce it on every Agent so the
                # canvas never shows the assistant's own runtime model instead.
                inject_model_into_flow(
                    flow,
                    req_provider,
                    req_model_name,
                    requested.get("api_key_var"),
                    overwrite_existing_model=True,
                )
            elif run_provider and run_model_name:
                # No explicit request: only FILL an Agent that has no model with
                # the assistant's verified runtime model (preserve a set one).
                inject_model_into_flow(
                    flow,
                    run_provider,
                    run_model_name,
                    run_model.get("api_key_var"),
                    overwrite_existing_model=False,
                )
        except (ImportError, ValueError) as exc:
            logger.warning("run_flow.verified_model_inject_skipped: %s", exc)

        result = await run_working_flow(flow_data=flow, flow_id=flow_id, user_id=user_id)
        if "error" in result:
            return Data(data={"error": result["error"], "text": result["error"]})
        # Deterministic "flow actually ran" signal the streaming generator uses to
        # force the built flow onto the canvas. Success-only: a failed run never claims it ran.
        _emit("flow_ran", flow_id=flow_id)
        text = result.get("result", "")
        metrics = result.get("metrics") or {}
        summary = _format_run_metrics(metrics)
        # The LLM only reads `text`, so the performance summary must be inline;
        # `metrics` stays structured for programmatic use.
        text_with_metrics = f"{text}\n\n{summary}" if summary else text
        return Data(data={"text": text_with_metrics, "result": text, "metrics": metrics})


class GenerateComponent(Component):
    """Generate, validate and register a NEW custom Langflow component.

    This is what lets ONE agent loop handle "create a component that does X
    and use it in a flow" without an intent router or phase orchestration:
    the agent calls this tool, then ``search_components`` finds the new
    component by class name and ``build_flow``/``add_component`` use it.

    Wraps the full backend pipeline (LLM generation → security scan → code
    + runtime validation with retries → user-scoped registration). Lazily
    imports ``langflow`` (same decoupling as ``RunFlow``): ``lfx`` may run
    without the backend.
    """

    display_name = "Generate Component"
    description = (
        "Create a brand-new custom Langflow component from a natural-language description. "
        "Use this when the user asks for a component/tool that does not exist yet. On success "
        "the component is validated and registered — then call search_components to find it by "
        "its class name and add it to the flow. Returns the generated component's class name."
    )
    icon = "Wand2"
    name = "GenerateComponent"

    inputs = [
        MessageTextInput(
            name="spec",
            display_name="Spec",
            info="Natural-language spec of the component to create (what it takes and what it returns).",
            required=True,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(name="result", display_name="Result", method="generate_component"),
    ]

    async def generate_component(self) -> Data:
        spec = (self.spec or "").strip()
        if not spec:
            msg = "Describe the component to generate (what it takes as input and what it returns)."
            return Data(data={"error": msg, "text": msg})

        try:
            from langflow.agentic.services.assistant_service import execute_flow_with_validation
            from langflow.agentic.services.file_events import reset_file_events
            from langflow.agentic.services.flow_types import LANGFLOW_ASSISTANT_FLOW
        except ImportError:
            msg = "Component generation is not available in this environment."
            return Data(data={"error": msg, "text": msg})

        try:
            from langflow.agentic.services.agent_run_context import (
                current_agent_run_iterations,
                current_agent_run_model,
            )
            from langflow.agentic.services.user_components_context import current_user_id

            user_id = current_user_id()
            model = current_agent_run_model() or {}
            iterations_limit = current_agent_run_iterations()
        except ImportError:
            user_id = None
            model = {}
            iterations_limit = None

        # Ephemeral flow id keeps the sub-flow's tracing from logging
        # "Invalid flow_id ... None" and persisting under a sentinel.
        from lfx.mcp.tool_cache import reset_tool_cache

        flow_id = str(uuid4())

        # Without ITERATIONS_LIMIT the nested assistant keeps the default step
        # budget, defeating /iterations N for component_then_flow requests.
        nested_globals = {"FLOW_ID": flow_id}
        if iterations_limit is not None:
            nested_globals["ITERATIONS_LIMIT"] = str(iterations_limit)
            logger.info("generate_component: nested subflow inherits step budget %s", iterations_limit)

        async def _isolated_generation() -> dict:
            # Fresh per-run state: the nested pipeline must neither steal the parent
            # loop's queued events nor wipe the canvas built this turn.
            isolate_flow_run_context()
            reset_tool_cache()
            reset_file_events()
            return await execute_flow_with_validation(
                flow_filename=LANGFLOW_ASSISTANT_FLOW,
                input_value=spec,
                global_variables=nested_globals,
                user_id=user_id,
                provider=model.get("provider"),
                model_name=model.get("model_name"),
                api_key_var=model.get("api_key_var"),
            )

        # create_task copies the context: ContextVar writes inside it
        # (incl. isolate/reset above) never propagate back to the parent loop.
        result = await asyncio.create_task(_isolated_generation())

        if result.get("validated"):
            class_name = result.get("class_name", "")
            text = (
                f"Component '{class_name}' created, validated and registered. "
                f"Now call search_components to find '{class_name}' and add it to the flow."
            )
            return Data(data={"text": text, "class_name": class_name, "component_code": result.get("component_code")})

        err = result.get("validation_error") or result.get("result") or "Component generation failed."
        # Structured failure signal (not prose the agent can bury): assistant_service
        # drains it into a validation_failed progress event for the user.
        try:
            from langflow.agentic.services.component_events import emit_component_generation_failed

            emit_component_generation_failed(
                error=err,
                class_name=result.get("class_name"),
                component_code=result.get("component_code"),
            )
        except ImportError:
            pass
        return Data(data={"error": err, "text": err})
