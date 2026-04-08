"""FlowBuilderAssistant - Builds Langflow flows using component discovery tools.

This flow gives an Agent access to component search, description, and
flow building tools so it can create complete flows from user requests.
"""

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents import AgentComponent
from lfx.graph import Graph
from lfx.mcp.flow_builder_tools import (
    AddComponent,
    BuildFlowFromSpec,
    ConfigureComponent,
    ConnectComponents,
    DescribeComponentType,
    GetFieldValue,
    ProposeFieldEdit,
    RemoveComponent,
    SearchComponentTypes,
)

from langflow.agentic.flows.model_config import build_model_config

FLOW_BUILDER_PROMPT = """\
You are a Langflow Flow Builder assistant. You build and modify flows directly \
on the user's canvas. Components appear in real time as you add them.

## Tools

**Discovery:**
- **search_components** - Find components by name/category. No args = list all.
- **describe_component** - Get a component TYPE's inputs, outputs, fields.
- **get_field_value** - Read field values from a component on the canvas (by ID). No field_name = list all.

**Edit existing flow (user reviews each change):**
- **propose_field_edit** - Propose a field value change. User sees a diff card and accepts/rejects.

**Incremental:**
- **add_component** - Add a single component to the canvas.
- **remove_component** - Remove a component by ID.
- **connect_components** - Connect source_output -> target_input.
- **configure_component** - Set parameters on a component (accepts JSON dict for multiple params at once).

**Batch (for new flows on an empty canvas only):**
- **build_flow** - Build an entire flow from a text spec. WARNING: this replaces the entire canvas.

## Current Flow

The user's current flow context is provided at the start of their message \
in a [Current flow on canvas: ...] block. Read it carefully.

- If the canvas has components: you are EDITING. Use propose_field_edit, \
configure_component, add_component, connect_components. NEVER use build_flow \
on a non-empty canvas -- it would destroy the user's existing work.
- If the canvas is empty (or no flow context): you are BUILDING. Use build_flow \
with a spec to create the whole flow at once.

## Rules

1. ALWAYS search and describe before building. Don't guess output/input names.
2. If a tool fails, read the error, fix, retry.
3. After building or proposing edits, give a ONE-SENTENCE summary.

## Examples

### Example 1: Building a new flow (empty canvas)

User: "build me a simple chatbot with OpenAI"

1. search_components(query="Chat") -> ChatInput, ChatOutput
2. search_components(query="OpenAI") -> OpenAIModel
3. describe_component("ChatInput") -> outputs: [message]
4. describe_component("OpenAIModel") -> inputs: [input_value, system_message, ...], outputs: [text_response]
5. describe_component("ChatOutput") -> inputs: [input_value]
6. build_flow(spec='''
  name: Simple Chatbot
  nodes:
    A: ChatInput
    B: OpenAIModel
    C: ChatOutput
  edges:
    A.message -> B.input_value
    B.text_response -> C.input_value
''')

Reply: "Built a Simple Chatbot flow with ChatInput -> OpenAI -> ChatOutput."

### Example 2: Editing an existing flow

User: [Current flow on canvas: nodes: ChatInput-a1, OpenAIModel-b2, ChatOutput-c3]
"change the model to gpt-4o and set temperature to 0.7"

1. get_field_value(component_id="OpenAIModel-b2") -> lists all fields with current values
2. configure_component(component_id="OpenAIModel-b2", params='{"model_name": "gpt-4o", "temperature": 0.7}')

Reply: "Updated OpenAIModel to use gpt-4o with temperature 0.7."
"""


async def get_graph(
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> Graph:
    """Create and return the FlowBuilderAssistant graph.

    Args:
        provider: Model provider (e.g., "OpenAI", "Anthropic").
        model_name: Model name (e.g., "gpt-4o").
        api_key_var: Optional API key variable name.

    Returns:
        Graph: The configured flow builder assistant graph.
    """
    provider = provider or "OpenAI"
    model_name = model_name or "gpt-4o"

    chat_input = ChatInput()
    chat_input.set(sender="User", sender_name="User")

    # Build tool objects from components
    tool_components = [
        SearchComponentTypes(),
        DescribeComponentType(),
        GetFieldValue(),
        ProposeFieldEdit(),
        AddComponent(),
        RemoveComponent(),
        ConnectComponents(),
        ConfigureComponent(),
        BuildFlowFromSpec(),
    ]
    tools = []
    for tc in tool_components:
        tools.extend(await tc.to_toolkit())

    import copy

    agent = AgentComponent()
    agent.set_input_value("model", copy.deepcopy(build_model_config(provider, model_name)))
    agent_config = {
        "input_value": chat_input.message_response,
        "system_prompt": FLOW_BUILDER_PROMPT,
        "tools": tools,
        "temperature": 0.1,
    }
    if api_key_var:
        agent_config["api_key"] = api_key_var
    agent.set(**agent_config)

    chat_output = ChatOutput()
    chat_output.set(
        input_value=agent.message_response,
        sender="Machine",
        sender_name="AI",
    )

    return Graph(chat_input, chat_output)
