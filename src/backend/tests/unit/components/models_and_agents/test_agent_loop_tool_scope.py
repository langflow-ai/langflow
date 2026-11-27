"""A bound loop flow runs the Agent's tools under the Agent's flow, as the packaged Agent does.

Message History as a tool reads the chat of the flow its tool runs under, so it is the check: run inside the loop
flow's scope, it would read nothing. Real message store, real graphs, a scripted model.
"""

from uuid import UUID, uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langflow.memory import astore_message
from langflow.schema.message import Message
from lfx.components.flow_controls.while_loop import WhileLoopComponent
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents import AgentContextComponent, AgentStepComponent, ExecuteToolComponent
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.components.models_and_agents.memory import MemoryComponent
from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.io import Output
from lfx.projects.bindings import FlowBinding, flow_revision
from pydantic import Field

from tests.unit.api.v1.test_project_config_write_through import create_flow

REMEMBERED = "The code word is banana."


class ReadsHistory(BaseChatModel):
    """Asks Message History for the chat once, then answers. Keeps what the tool returned."""

    tool_results: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "reads-history"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        results = [m for m in messages if isinstance(m, ToolMessage)]
        if results:
            self.tool_results.append(str(results[-1].content))
            message = AIMessage(content="done")
        else:
            call = {"name": "retrieve_messages_as_text", "args": {"order": "Ascending"}, "id": "call-1"}
            message = AIMessage(content="", tool_calls=[call])
        return ChatResult(generations=[ChatGeneration(message=message)])


class SharedModel(Component):
    display_name = "Shared Model"
    outputs = [Output(display_name="Model", name="model_output", method="build_model", types=["LanguageModel"])]

    def build_model(self):
        return self.ctx["model"]


def loop_flow_data() -> dict:
    context = AgentContextComponent(_id="AgentContext-ac001")
    loop = WhileLoopComponent(_id="WhileLoop-wl001")
    loop.set(input_value=context.build_messages)
    step = AgentStepComponent(_id="AgentStep-as001")
    step.set(messages=loop.loop_output)
    execute = ExecuteToolComponent(_id="ExecuteTool-et001")
    execute.set(messages=step.get_tool_calls)
    loop.set(loop=execute.execute_tools)
    chat_output = ChatOutput(_id="ChatOutput-co001")
    chat_output.set(input_value=loop.last_message_output)
    return Graph(context, chat_output).dump()["data"]


def agent_graph(model, *, flow_id: str | None = None, user_id: str | None = None, loop_binding=None) -> Graph:
    chat_input = ChatInput(_id="ChatInput-outer")
    chat_input.set(input_value="What did I say?")
    memory = MemoryComponent(_id="Memory-tool")
    memory._append_tool_to_outputs_map()  # tool mode, as the canvas toggle sets it
    agent = AgentComponent(_id="Agent-ag001")
    agent.set(
        model=SharedModel(_id="model").build_model,
        tools=memory.to_toolkit,
        input_value=chat_input.message_response,
        add_current_date_tool=False,
        **({"loop_binding": loop_binding.model_dump_json()} if loop_binding else {}),
    )
    chat_output = ChatOutput(_id="ChatOutput-outer")
    chat_output.set(input_value=agent.message_response)
    return Graph(chat_input, chat_output, flow_id=flow_id, user_id=user_id, context={"model": model})


async def stored_agent_flow(active_user, loop_binding) -> str:
    """Save the Agent flow, with Message History in tool mode, so its tool calls are authorized."""
    data = agent_graph(None, loop_binding=loop_binding).dump()["data"]
    next(n for n in data["nodes"] if n["id"] == "Memory-tool")["data"]["node"]["tool_mode"] = True
    return await create_flow(active_user, folder_id=None, data=data, name=f"Agent with history tool {uuid4()}")


async def test_message_history_as_a_tool_reads_the_agents_chat_in_the_bound_loop(client, active_user):  # noqa: ARG001
    loop = loop_flow_data()
    loop_id = await create_flow(active_user, folder_id=None, data=loop, name="Loop")
    binding = FlowBinding(
        flow_id=loop_id, node_id="WhileLoop-wl001", output_name="last_message", revision=flow_revision(loop)
    )
    results = {}
    for name, bound in (("packaged", None), ("loop", binding)):
        flow_id = await stored_agent_flow(active_user, bound)
        session_id = f"{name}-{uuid4()}"
        await astore_message(
            Message(text=REMEMBERED, sender="User", sender_name="User", session_id=session_id),
            flow_id=UUID(flow_id),
            user_id=active_user.id,
        )
        model = ReadsHistory()
        graph = agent_graph(model, flow_id=flow_id, user_id=str(active_user.id), loop_binding=bound)
        graph.session_id = session_id
        async for _ in graph.async_start():
            pass
        results[name] = model.tool_results

    assert any(REMEMBERED in result for result in results["packaged"])
    assert any(REMEMBERED in result for result in results["loop"])
