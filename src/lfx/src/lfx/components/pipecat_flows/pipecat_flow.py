"""PipecatFlowComponent — multi-node conversational state machine.

Wraps ``pipecat_flows.FlowManager`` (pipecat-ai-flows 1.x). The component is
placed downstream of ``VoicePipelineComponent``: it consumes the
``PipelineTask`` + ``llm`` + ``context_aggregator_pair`` and **re-emits the
same task** as its terminal output, while creating + initializing a
``FlowManager`` as a side-effect.

The user supplies the *initial node* as JSON in ``flow_config``. That JSON
must be a ``NodeConfig`` dict:

    {
      "name": "greet",
      "role_messages": [{"role": "system", "content": "You are a polite agent."}],
      "task_messages": [{"role": "system", "content": "Greet the user and ask how you can help."}],
      "functions": []
    }

Tools wired via the ``tools`` input become globally available across nodes
(registered on the LLM via ``register_function``). Per-node tool gating still
works by listing function schemas inside each ``NodeConfig.functions``.

For multi-node graphs, the user authors transition functions inside the JSON
whose handlers (defined in companion ``VoiceToolComponent`` instances) call
``flow_manager.set_node_from_config(next_node_config)`` to transition.
"""

import json
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.field_typing.voice_types import PipecatFlowManager, PipecatPipelineTask
from lfx.io import CodeInput, DropdownInput, HandleInput, Output


class PipecatFlowComponent(Component):
    display_name = "Pipecat Flow"
    description = "Multi-node conversational state machine (pipecat-ai-flows FlowManager)."
    icon = "GitFork"
    name = "PipecatFlow"
    category = "pipecat"

    inputs = [
        HandleInput(
            name="task",
            display_name="Pipeline Task",
            input_types=["PipecatPipelineTask"],
            required=True,
            info="The PipelineTask produced by VoicePipelineComponent.",
        ),
        HandleInput(
            name="llm",
            display_name="LLM / S2S Service",
            input_types=["PipecatLLMService", "PipecatS2SService"],
            required=True,
            info="The LLM the FlowManager drives. Must be the same instance wired into the pipeline.",
        ),
        HandleInput(
            name="context_aggregator_pair",
            display_name="Context Aggregator Pair",
            input_types=["PipecatContextAggregatorPair"],
            required=True,
        ),
        HandleInput(
            name="transport",
            display_name="Transport",
            input_types=["PipecatTransport"],
            required=False,
            info="Optional. Required for FlowManager Actions that produce TTS announcements.",
        ),
        HandleInput(
            name="tools",
            display_name="Global Tools",
            input_types=["PipecatTool"],
            is_list=True,
            required=False,
            info=(
                "Tools registered on the LLM for the lifetime of the session. "
                "Per-node tool gating is configured inside `flow_config.functions`."
            ),
        ),
        CodeInput(
            name="flow_config",
            display_name="Initial Node (JSON)",
            value=(
                "{\n"
                '  "name": "start",\n'
                '  "role_messages": [\n'
                '    {"role": "system", "content": "You are a helpful voice assistant."}\n'
                "  ],\n"
                '  "task_messages": [\n'
                '    {"role": "system", "content": "Greet the user and ask how you can help."}\n'
                "  ],\n"
                '  "functions": []\n'
                "}\n"
            ),
            info="A NodeConfig JSON used as the initial node. Multi-node graphs transition at runtime via tool handlers.",  # noqa: E501
        ),
        DropdownInput(
            name="context_strategy",
            display_name="Context Strategy",
            options=["append", "reset", "reset_with_summary"],
            value="append",
            advanced=True,
            info="How the conversation context is carried across node transitions.",
        ),
    ]

    outputs = [
        Output(
            display_name="Flow Manager",
            name="flow_manager",
            method="build_flow_manager",
            types=["PipecatFlowManager"],
        ),
        Output(
            display_name="Pipeline Task",
            name="pipeline_task",
            method="get_task",
            types=["PipecatPipelineTask"],
        ),
    ]

    _flow_manager: PipecatFlowManager | None = None

    def _register_global_tools(self) -> None:
        """Register every wired PipecatTool on the LLM (idempotent)."""
        llm = self.llm
        tools = list(self.tools or [])
        if not llm or not tools:
            return
        register = getattr(llm, "register_function", None)
        if register is None:
            return
        existing = getattr(llm, "_function_handlers", None) or getattr(llm, "_functions", None)
        existing_names = set(existing.keys()) if isinstance(existing, dict) else set()
        for schema, handler in tools:
            if schema.name in existing_names:
                continue
            register(schema.name, handler)
            existing_names.add(schema.name)

    def _parse_initial_node(self) -> dict[str, Any]:
        raw = (self.flow_config or "").strip()
        if not raw:
            msg = "PipecatFlow flow_config is empty — supply a NodeConfig JSON."
            raise ValueError(msg)
        try:
            config = json.loads(raw)
        except json.JSONDecodeError as exc:
            msg = f"PipecatFlow flow_config is not valid JSON: {exc}"
            raise ValueError(msg) from exc
        if not isinstance(config, dict):
            msg = "PipecatFlow flow_config must be a JSON object (NodeConfig)."
            raise TypeError(msg)
        if "task_messages" not in config:
            msg = "NodeConfig is missing required key 'task_messages'."
            raise ValueError(msg)
        return config

    def _build_context_strategy(self) -> Any | None:
        if not self.context_strategy or self.context_strategy == "append":
            return None  # FlowManager default
        from pipecat_flows.types import ContextStrategy, ContextStrategyConfig

        mapping = {
            "append": ContextStrategy.APPEND,
            "reset": ContextStrategy.RESET,
            "reset_with_summary": ContextStrategy.RESET_WITH_SUMMARY,
        }
        return ContextStrategyConfig(strategy=mapping[self.context_strategy])

    async def build_flow_manager(self) -> PipecatFlowManager:
        """Construct and initialize the FlowManager. Returns the live manager."""
        if self._flow_manager is not None:
            return self._flow_manager

        from pipecat_flows import FlowManager

        # 1. Register any global tools on the LLM before FlowManager looks at it.
        self._register_global_tools()

        # 2. Parse initial node JSON.
        initial_node = self._parse_initial_node()

        # 3. Build manager (transport is optional).
        manager = FlowManager(
            task=self.task,
            llm=self.llm,
            context_aggregator=self.context_aggregator_pair,
            context_strategy=self._build_context_strategy(),
            transport=self.transport,
        )

        # 4. Initialize at the named entry node.
        await manager.initialize(initial_node=initial_node)
        self._flow_manager = manager
        return manager

    def get_task(self) -> PipecatPipelineTask:
        """Re-emit the upstream PipelineTask so downstream consumers see it.

        The API runner consumes this output. The FlowManager runs alongside the
        task as a side-effect of ``build_flow_manager`` having been called by
        the graph engine (downstream of `flow_manager` output resolution).
        """
        return self.task
