"""How Agent Step and Execute Tool make their call: through which runtime, and who shows it in the chat.

The history between the blocks is a DataFrame of message rows (`lfx.base.agents.loop_rows`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from langchain_core.runnables import RunnableLambda

from lfx.base.agents.events import (
    ExceptionWithMessageError,
    initial_agent_message,
    process_agent_events,
    retract_partial_message,
)
from lfx.base.agents.loop_rows import HARNESS_LOOP_KEY, is_answer
from lfx.components.models_and_agents.agent_helpers.graph_event_adapter import adapt_graph_events_to_executor_shape
from lfx.memory import delete_message
from lfx.schema.message import Message

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langchain_core.messages import BaseMessage

    from lfx.base.agents.loop_runtime import HarnessLoopRuntime
    from lfx.custom.custom_component.component import Component
    from lfx.schema.log import OnTokenFunctionType, SendMessageFunctionType


def block_tools(value: Any) -> list:
    """A block's Tools input as a list."""
    return value if isinstance(value, list) else [value] if value else []


async def block_call(
    component: Component,
    build: Callable[[], HarnessLoopRuntime],
    history: list[BaseMessage],
    call: Callable[[HarnessLoopRuntime, list[BaseMessage]], Awaitable[list[BaseMessage]]],
) -> tuple[list[BaseMessage], Message]:
    """Make the block's call and return what it returned, with the block's Message.

    A harness runtime in the graph context belongs to whoever built it, which also owns the chat display, so the
    call is made directly and the Message only carries the last message's text. Otherwise the block builds its
    own runtime with `build` and shows the call in the chat the way the Agent does. It builds it inside the run it
    shows, because a runtime makes its calls in the context it was built in.
    """
    runtime = component.ctx.get(HARNESS_LOOP_KEY)
    if runtime is not None:
        returned = await call(runtime, history)
        return returned, Message(text=returned[-1].text if returned else "")
    return await _run_with_chat_events(component, history, lambda messages: call(build(), messages))


async def _run_with_chat_events(
    component: Component,
    history: list[BaseMessage],
    call: Callable[[list[BaseMessage]], Awaitable[list[BaseMessage]]],
) -> tuple[list[BaseMessage], Message]:
    """Run `call(history)` under a LangChain event stream and show it in the chat like the Agent does.

    `process_agent_events` turns the stream into one chat Message (text, tool calls, harness events), sends the
    tokens and publishes the message. A message with no text that is not the answer, such as a tool round, is shown
    while the call runs but not kept, because the next turn's history would read it as an empty AI message.
    """
    returned: list[BaseMessage] = []

    async def run(state: dict[str, list[BaseMessage]]) -> dict[str, list[BaseMessage]]:
        returned.extend(await call(state["messages"]))
        return {"messages": returned}

    stream = adapt_graph_events_to_executor_shape(
        RunnableLambda(run).astream_events(
            {"messages": history},
            config={"callbacks": component.get_langchain_callbacks()},
            version="v2",
        )
    )
    on_token = cast("OnTokenFunctionType", component._event_manager.on_token) if component._event_manager else None  # noqa: SLF001
    try:
        message = await process_agent_events(
            stream, initial_agent_message(component), cast("SendMessageFunctionType", component.send_message), on_token
        )
    except ExceptionWithMessageError as e:
        await retract_partial_message(component, e.agent_message)
        raise (e.__cause__ or e) from None  # the error the call itself raised
    if not message.text and not (returned and is_answer(returned[-1])) and (msg_id := message.get_id()):
        await delete_message(id_=msg_id)
    return returned, message
