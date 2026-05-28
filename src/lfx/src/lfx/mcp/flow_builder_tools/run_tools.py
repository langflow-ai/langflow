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
        existing = get_working_flow()
        if existing and existing.get("data", {}).get("nodes"):
            node_count = len(existing["data"]["nodes"])
            logger.warning("build_flow called on non-empty canvas (%d nodes) -- replacing", node_count)

        # Pass the user-aware registry so user-registered Components
        # (created via Layer-2 validated generation) are addressable in
        # the spec by their class name.
        result = build_flow_from_spec(self.spec, registry=_load_registry_user_aware())
        if "error" in result:
            error_msg = f"Flow build failed: {result['error']}"
            if "details" in result:
                error_msg += f"\nDetails: {result['details']}"
            logger.warning("build_flow_from_spec failed: %s", result["error"])
            result["text"] = error_msg
        elif "flow" in result:
            orphan_ids = _find_orphan_nodes(result["flow"])
            # A single-component flow has no edges by definition — it is a
            # valid standalone flow (e.g. the agent built one component to
            # run/inspect), NOT an orphan mistake. Only reject when 2+
            # nodes exist but wiring is missing.
            if orphan_ids and result.get("node_count", len(orphan_ids)) > 1:
                # Reject orphan-bearing flows so the LLM retries instead of
                # rendering an unconnected component on the user's canvas.
                # The agent prompt explicitly forbids orphans; this is the
                # safety net for when it slips through anyway.
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
            # Mutate the EXISTING working-flow dict in place instead of
            # rebinding the ContextVar. A `.set()` rebind is invisible
            # across tool-execution contexts, so a later `run_flow` tool
            # call (different context) would still see the old empty flow
            # ("There is no flow on the canvas to run"). In-place mutation
            # of the shared object is visible everywhere — same proven
            # pattern as `configure_component` (`fb_configure(flow, ...)`).
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

        # The run engine (ChatOutput/session) requires a valid UUID flow id;
        # a non-UUID placeholder makes the run fail with "badly formed
        # hexadecimal UUID string". Fall back to a fresh uuid4 when the
        # canvas has no persisted id yet.
        flow_id = _current_flow_id_var.get() or str(uuid4())

        # The assistant runs with a verified provider/model/api_key. An Agent
        # that has NO model (LLM forgot to set one) would fail the run with
        # "No model selected"/"Authentication failed", so fill those in with
        # the assistant's working credential. But an Agent the user/agent
        # EXPLICITLY gave a model (e.g. "use gpt-5.4") must KEEP that model on
        # the canvas — never silently swapped for the assistant's own model.
        # ``overwrite_existing_model=False`` preserves a set model and only
        # tops up the credential when the provider matches (see
        # inject_model_into_flow). Deterministic and LLM-agnostic.
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
                # The user EXPLICITLY named a model — enforce it on every Agent
                # (overwrite), so the canvas reflects exactly what they asked for
                # and never the assistant's own runtime model. This is the fix for
                # "says gpt-5.4 but the canvas shows gpt-5.5".
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
        # Deterministic, LLM/language-agnostic signal that the flow ACTUALLY
        # ran this turn. The streaming generator uses it to apply a built
        # flow to the canvas (running a flow the user can't see is
        # contradictory) instead of guessing intent from the prompt wording.
        # Emitted only on success — a failed run must never claim it ran.
        _emit("flow_ran", flow_id=flow_id)
        text = result.get("result", "")
        metrics = result.get("metrics") or {}
        summary = _format_run_metrics(metrics)
        # The LLM only reads `text`, so the performance summary must be inline
        # for the agent to be able to report time/tokens; `metrics` is kept
        # structured for any programmatic use.
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
            from langflow.agentic.services.agent_run_context import current_agent_run_model
            from langflow.agentic.services.user_components_context import current_user_id

            user_id = current_user_id()
            model = current_agent_run_model() or {}
        except ImportError:
            user_id = None
            model = {}

        # Give the internal generation sub-flow a valid (ephemeral) flow id
        # so its tracing doesn't log "Invalid flow_id ... None" and persist
        # under a sentinel on every component generation.
        from lfx.mcp.tool_cache import reset_tool_cache

        flow_id = str(uuid4())

        async def _isolated_generation() -> dict:
            # This nested pipeline drains flow events and resets the
            # working flow internally. Run it with fresh per-run state so
            # it can neither steal the parent agent loop's queued events
            # nor wipe the canvas the agent already built this turn.
            isolate_flow_run_context()
            reset_tool_cache()
            reset_file_events()
            return await execute_flow_with_validation(
                flow_filename=LANGFLOW_ASSISTANT_FLOW,
                input_value=spec,
                global_variables={"FLOW_ID": flow_id},
                user_id=user_id,
                provider=model.get("provider"),
                model_name=model.get("model_name"),
                api_key_var=model.get("api_key_var"),
            )

        # asyncio.create_task runs the coroutine in a COPY of the current
        # context; ContextVar writes inside it (incl. the isolate/reset
        # calls above) do not propagate back to the parent agent loop.
        result = await asyncio.create_task(_isolated_generation())

        if result.get("validated"):
            class_name = result.get("class_name", "")
            text = (
                f"Component '{class_name}' created, validated and registered. "
                f"Now call search_components to find '{class_name}' and add it to the flow."
            )
            return Data(data={"text": text, "class_name": class_name, "component_code": result.get("component_code")})

        err = result.get("validation_error") or result.get("result") or "Component generation failed."
        # Surface the failure as a structured signal, not just an error string
        # the agent can bury in prose or paper over by substituting a generic
        # component. assistant_service drains this and emits a `validation_failed`
        # progress event so the user is told honestly the component wasn't built.
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
