"""Adapt LangGraph events to the AgentExecutor event shape.

`langchain.agents.create_agent` returns a `CompiledStateGraph` whose `astream_events(v2)`
emits the outermost `on_chain_start` with `data.input = {"messages": [...]}` and the
outermost `on_chain_end` with `data.output = {"messages": [..., AIMessage]}`. The legacy
`process_agent_events` in `lfx.base.agents.events` was written for the AgentExecutor
shape — `{"input": str, "chat_history": [...]}` and `AgentFinish` respectively.

This adapter wraps the graph's event stream and re-shapes ONLY the outermost graph
events into the executor shape, so `process_agent_events` works unchanged. Inner
events (graph nodes, retrievers), tool events, and chat-model-stream events pass
through untouched.

Outermost-event detection: the run_id of the FIRST `on_chain_start` is captured;
events with that run_id are the outermost graph's events. Inner nested events have
different run_ids and are passed through verbatim.
"""

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.agents import AgentFinish
from langchain_core.messages import AIMessage, HumanMessage


async def adapt_graph_events_to_executor_shape(
    stream: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[dict[str, Any]]:
    """Re-shape outermost graph events; pass everything else through unchanged."""
    outer_run_id: str | None = None
    last_model_output: AIMessage | None = None
    async for event in stream:
        if outer_run_id is None and event.get("event") == "on_chain_start":
            outer_run_id = event.get("run_id")
        if event.get("event") == "on_chat_model_end":
            output = (event.get("data") or {}).get("output")
            if isinstance(output, AIMessage):
                last_model_output = output
        if event.get("run_id") == outer_run_id:
            if event.get("event") == "on_chain_start":
                yield _reshape_chain_start(event)
                continue
            if event.get("event") == "on_chain_end":
                unstreamed = _final_message_without_model_call(event, last_model_output)
                if unstreamed is not None:
                    yield _synthetic_model_end(event, unstreamed)
                yield _reshape_chain_end(event)
                continue
        yield event


def _final_message_without_model_call(
    event: dict[str, Any],
    last_model_output: AIMessage | None,
) -> AIMessage | None:
    """Return the final AIMessage when no model call produced it, else None.

    Middleware can end a run with its own AIMessage — `ModelCallLimitMiddleware` injects
    "Model call limits exceeded: ...". No `on_chat_model_end` fires for it, so without
    this it never reaches `content_blocks`, and any text the model wrote earlier in the
    run becomes the final answer instead.
    """
    output = (event.get("data") or {}).get("output")
    if last_model_output is None or not isinstance(output, dict):
        return None
    final = next((msg for msg in reversed(output.get("messages") or []) if isinstance(msg, AIMessage)), None)
    if final is None or not _message_text(final).strip():
        return None
    if (final.id is not None and final.id == last_model_output.id) or (
        _message_text(final).strip() == _message_text(last_model_output).strip()
    ):
        return None
    return final


def _synthetic_model_end(event: dict[str, Any], message: AIMessage) -> dict[str, Any]:
    return {
        "event": "on_chat_model_end",
        "name": event.get("name", ""),
        "run_id": f"{event.get('run_id', '')}:final-message",
        "data": {"output": message},
    }


def _message_text(message: AIMessage) -> str:
    return message.content if isinstance(message.content, str) else _extract_text(message.content)


def _reshape_chain_start(event: dict[str, Any]) -> dict[str, Any]:
    """Translate `{"messages": [...]}` → `{"input": str, "chat_history": [...]}`.

    The user's fresh turn is the LAST HumanMessage. Everything before it is history.
    If the last message is not a HumanMessage (rare — defensive), keep an empty input.
    """
    data = event.get("data") or {}
    graph_input = data.get("input")
    if not isinstance(graph_input, dict) or "messages" not in graph_input:
        return event

    messages = list(graph_input["messages"])
    if messages and isinstance(messages[-1], HumanMessage):
        last = messages[-1]
        text = last.content if isinstance(last.content, str) else _extract_text(last.content)
        executor_input = {"input": text, "chat_history": messages[:-1]}
    else:
        executor_input = {"input": "", "chat_history": messages}

    return {**event, "data": {**data, "input": executor_input}}


def _reshape_chain_end(event: dict[str, Any]) -> dict[str, Any]:
    """Translate final state `{"messages": [..., AIMessage]}` → `AgentFinish`.

    The final answer is the LAST AIMessage in the state's messages list. If the state
    doesn't contain that shape (rare — defensive), pass the event through unchanged.
    """
    data = event.get("data") or {}
    output = data.get("output")
    if not isinstance(output, dict) or "messages" not in output:
        return event

    messages = output["messages"]
    final_text = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            final_text = msg.content if isinstance(msg.content, str) else _extract_text(msg.content)
            break

    return {**event, "data": {**data, "output": AgentFinish(return_values={"output": final_text}, log="")}}


def _extract_text(content: object) -> str:
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
        return "".join(parts)
    return str(content)
