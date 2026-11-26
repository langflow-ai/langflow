"""A loop flow of While Loop, Agent Step and Execute Tool, run without a harness, against the real message store.

The next turn's Message History reads what a turn stored, so a tool round must not leave an empty AI message there.
"""

from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langflow.memory import aget_messages
from lfx.components.flow_controls.while_loop import WhileLoopComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents import AgentStepComponent, ExecuteToolComponent
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.io import Output


class SilentModel(BaseChatModel):
    """Calls `echo` without saying anything, then answers."""

    @property
    def _llm_type(self):
        return "silent"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        if any(isinstance(m, ToolMessage) for m in messages):
            message = AIMessage(content="done")
        else:
            message = AIMessage(content="", tool_calls=[{"name": "echo", "args": {"text": "hi"}, "id": "call-1"}])
        return ChatResult(generations=[ChatGeneration(message=message)])


@tool
def echo(text: str) -> str:
    """Echo the text."""
    return f"echo {text}"


class SilentModelSource(Component):
    display_name = "Silent Model"
    outputs = [Output(display_name="Model", name="model_output", method="build_model", types=["LanguageModel"])]

    def build_model(self) -> BaseChatModel:
        return SilentModel()


class EchoTool(Component):
    display_name = "Echo Tool"
    outputs = [Output(display_name="Tools", name="tools", method="build_tools", types=["Tool"])]

    def build_tools(self) -> list:
        return [echo]


async def test_a_tool_round_with_no_text_is_not_kept_in_the_chat_history(client, active_user):  # noqa: ARG001
    chat_input = ChatInput(_id="ChatInput-ci001")
    chat_input.set(input_value="hi")
    loop = WhileLoopComponent(_id="WhileLoop-wl001")
    loop.set(input_value=chat_input.message_response)
    step = AgentStepComponent(_id="AgentStep-as001")
    step.set(messages=loop.loop_output, model=SilentModelSource(_id="model").build_model)
    execute = ExecuteToolComponent(_id="ExecuteTool-et001")
    execute.set(messages=step.get_tool_calls, tools=EchoTool(_id="tools").build_tools)
    step.set(tools=EchoTool(_id="tools").build_tools)
    loop.set(loop=execute.execute_tools)
    chat_output = ChatOutput(_id="ChatOutput-co001")
    chat_output.set(input_value=step.get_ai_message)
    flow_id, owner_id, session_id = uuid4(), active_user.id, f"blocks-{uuid4()}"
    graph = Graph(chat_input, chat_output, flow_id=str(flow_id), user_id=str(owner_id))
    graph.session_id = session_id

    async for _ in graph.async_start():
        pass

    stored = await aget_messages(session_id=session_id, flow_id=flow_id, user_id=owner_id)
    assert [(m.sender, m.text) for m in stored if m.sender == "Machine"]
    assert all(m.text for m in stored if m.sender == "Machine")
