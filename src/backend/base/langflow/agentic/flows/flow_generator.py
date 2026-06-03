"""FlowGenerator — LLM graph that generates compact flow JSON from natural language.

This flow takes a user prompt (with an injected component catalog) and produces
a compact flow JSON object: {"nodes": [...], "edges": [...]}. The compact format
is then validated and expanded into full ReactFlow format by the
flow_generation_service.

Usage:
    from langflow.agentic.flows.flow_generator import get_graph
    graph = get_graph(provider="OpenAI", model_name="gpt-4o-mini")
"""

from __future__ import annotations

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models import LanguageModelComponent
from lfx.graph import Graph

from langflow.agentic.flows._model_config import build_model_config

# ---------------------------------------------------------------------------
# System prompt template — catalog and flow_context are injected at call time
# via the user message (not via the system prompt template itself), so the
# system prompt stays stable across retries while the user turn changes.
# ---------------------------------------------------------------------------

FLOW_GENERATION_SYSTEM_PROMPT = """\
You are a Langflow Flow Generator. Your only job is to output a valid compact flow JSON object.

## Compact Flow Format
Output EXACTLY this JSON structure — nothing before, nothing after:
{{
  "nodes": [
    {{"id": "node-1", "type": "ChatInput"}},
    {{"id": "node-2", "type": "OpenAIModel", "values": {{"model_name": "gpt-4o"}}}},
    {{"id": "node-3", "type": "ChatOutput"}}
  ],
  "edges": [
    {{"source": "node-1", "source_output": "message", "target": "node-2", "target_input": "input_value"}},
    {{"source": "node-2", "source_output": "text_output", "target": "node-3", "target_input": "input_value"}}
  ]
}}

## Rules
1. Use ONLY component types from the Available Components section in the user message
2. Every node must have a unique "id" string (use "node-1", "node-2", etc.)
3. "type" must EXACTLY match a component name from the catalog — no inventing names
4. Only set "values" for fields the user explicitly mentioned or that differ from \
obvious defaults
5. "source_output" must match an output name listed for that component
6. "target_input" must match an input name listed for that component
7. Always include terminal nodes: ChatInput (or TextInput) for input, ChatOutput \
(or TextOutput) for output — unless the user explicitly says otherwise
8. For RAG pipelines: connect retriever output to LLM context/input, also connect \
the user query directly to the LLM
9. Output ONLY the JSON object — absolutely no explanation, no markdown, no preamble
"""


def get_graph(
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> Graph:
    """Create and return the FlowGenerator graph.

    The graph takes a user message containing the catalog + request and
    produces compact flow JSON. session_id-based message storage is enabled
    so multi-turn editing ("replace X with Y") retains context.

    Args:
        provider: Model provider (e.g., "OpenAI", "Anthropic"). Defaults to OpenAI.
        model_name: Model name (e.g., "gpt-4o-mini"). Defaults to gpt-4o-mini.
        api_key_var: Optional API key variable name.

    Returns:
        Graph: The configured flow generator graph.
    """
    provider = provider or "OpenAI"
    model_name = model_name or "gpt-4o-mini"

    # Chat input — stores messages so multi-turn edit sessions retain context
    chat_input = ChatInput()
    chat_input.set(
        sender="User",
        sender_name="User",
        should_store_message=True,
    )

    # Language model component
    llm = LanguageModelComponent()
    llm.set_input_value("model", build_model_config(provider, model_name))

    llm_config: dict = {
        "input_value": chat_input.message_response,
        "system_message": FLOW_GENERATION_SYSTEM_PROMPT,
        "temperature": 0.3,  # Some creativity, but not too much
    }

    if api_key_var:
        llm_config["api_key"] = api_key_var

    llm.set(**llm_config)

    # Chat output — stores model responses for session continuity
    chat_output = ChatOutput()
    chat_output.set(
        input_value=llm.text_response,
        sender="Machine",
        sender_name="AI",
        should_store_message=True,
        clean_data=True,
        data_template="{text}",
    )

    return Graph(start=chat_input, end=chat_output)
