"""WatsonX-specific middleware for `langchain.agents.create_agent`.

WatsonX models (Granite, Llama, Mistral) have platform-specific tool calling behavior:
- With `tool_choice='auto'`: models often *describe* tools in text instead of calling them.
- With `tool_choice='required'`: models cannot provide final answers (causes infinite loops).
- Models only reliably support a single tool call per turn.

This middleware ports the legacy `create_granite_agent` logic to the create_agent
middleware API:
- Dynamic tool_choice: `required` for the first N model calls, then `auto`.
- Truncate to a single tool call per turn.
- Detect placeholder syntax (`<result-from-...>`) and re-invoke with a corrective message.
"""

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from lfx.components.langchain_utilities.ibm_granite_handler import (
    _ahandle_placeholder_in_response,
    _handle_placeholder_in_response,
    _limit_to_single_tool_call,
)
from lfx.log.logger import logger

DEFAULT_FORCED_ITERATIONS = 2


class WatsonXAgentMiddleware(AgentMiddleware):
    """Middleware that mirrors `create_granite_agent` behavior under create_agent."""

    def __init__(
        self,
        *,
        llm: Any,
        tools: list,
        forced_iterations: int = DEFAULT_FORCED_ITERATIONS,
    ) -> None:
        super().__init__()
        if not hasattr(llm, "bind_tools"):
            msg = "WatsonXAgentMiddleware requires a language model with bind_tools support."
            raise ValueError(msg)
        self._llm_required = llm.bind_tools(tools or [], tool_choice="required")
        self._llm_auto = llm.bind_tools(tools or [], tool_choice="auto")
        self._forced_iterations = forced_iterations

    def select_tool_choice(self, num_steps: int) -> str:
        """Return 'required' for the first N steps, 'auto' afterwards."""
        return "required" if num_steps < self._forced_iterations else "auto"

    def wrap_model_call(self, request, handler):  # pragma: no cover - exercised via integration
        """Sync path: build a new request with the right model, run handler, post-process."""
        new_request = self._prepare_request(request)
        response = handler(new_request)
        _log_response(response, num_steps=_count_tool_messages(request))
        return _post_process_response(response, new_request, self._llm_auto)

    async def awrap_model_call(self, request, handler):
        """Async path: same logic as wrap_model_call, but awaits the async handler.

        REQUIRED because LCAgentComponent.run_agent invokes the graph via
        `astream_events` (async). Without this, the base AgentMiddleware raises
        NotImplementedError and the entire WatsonX flow fails.

        Post-processing also runs async — see `_apost_process_response`.
        Calling the sync variant here was a latent deadlock with async-only
        providers (langchain-ibm) when the placeholder branch fires.
        """
        new_request = self._prepare_request(request)
        response = await handler(new_request)
        _log_response(response, num_steps=_count_tool_messages(request))
        return await _apost_process_response(response, new_request, self._llm_auto)

    def _prepare_request(self, request: Any) -> Any:
        """Return a new request with the bound model swapped to required/auto.

        Uses the immutable `request.override(model=...)` API instead of mutating
        the original — direct attribute assignment is deprecated by langchain
        and can break streaming sessions because the framework retains references
        to the original request.
        """
        num_steps = _count_tool_messages(request)
        choice = self.select_tool_choice(num_steps)
        new_model = self._llm_required if choice == "required" else self._llm_auto
        logger.info(
            f"[WatsonX] step={num_steps} tool_choice={choice} "
            f"(forced_iterations={self._forced_iterations})"
        )
        return request.override(model=new_model)


def build_watsonx_middleware(*, llm: Any, tools: list) -> WatsonXAgentMiddleware:
    return WatsonXAgentMiddleware(llm=llm, tools=tools)


def _count_tool_messages(request: Any) -> int:
    state = getattr(request, "state", None)
    if state is None:
        return 0
    messages = state.get("messages") if isinstance(state, dict) else getattr(state, "messages", [])
    return sum(1 for m in messages or [] if isinstance(m, ToolMessage))


def _post_process_response(response: Any, request: Any, llm_auto: Any) -> Any:
    if not isinstance(response, AIMessage):
        return response
    response = _limit_to_single_tool_call(response)
    messages = _extract_request_messages(request)
    return _handle_placeholder_in_response(response, _MessagesContainer(messages), llm_auto)


async def _apost_process_response(response: Any, request: Any, llm_auto: Any) -> Any:
    """Async sibling of `_post_process_response` — awaits placeholder re-invoke."""
    if not isinstance(response, AIMessage):
        return response
    response = _limit_to_single_tool_call(response)
    messages = _extract_request_messages(request)
    return await _ahandle_placeholder_in_response(response, _MessagesContainer(messages), llm_auto)


def _extract_request_messages(request: Any) -> list:
    state = getattr(request, "state", None)
    if state is None:
        return []
    messages = state.get("messages") if isinstance(state, dict) else getattr(state, "messages", [])
    return list(messages or [])


def _log_response(response: Any, *, num_steps: int) -> None:
    """Log what the model emitted at each step — diagnostic for chain failures.

    Set log level to INFO (or DEBUG) and look for `[WatsonX]` lines to see:
      - which tool the model chose at each step
      - whether it returned tool_calls or final text content
      - whether the chain stalled (no new tool call after step 1)
    """
    if not isinstance(response, AIMessage):
        return
    tool_calls = getattr(response, "tool_calls", None) or []
    if tool_calls:
        names = ", ".join(tc.get("name", "?") for tc in tool_calls if isinstance(tc, dict))
        logger.info(f"[WatsonX] step={num_steps} → emitted {len(tool_calls)} tool_call(s): {names}")
    else:
        snippet = str(response.content)[:80].replace("\n", " ")
        logger.info(f"[WatsonX] step={num_steps} → final text (no tools), preview: {snippet!r}")


class _MessagesContainer:
    """Lightweight wrapper exposing `.messages` to satisfy `_handle_placeholder_in_response`."""

    def __init__(self, messages: list) -> None:
        self.messages = list(messages)

    def __iter__(self):
        return iter(self.messages)


__all__ = [
    "DEFAULT_FORCED_ITERATIONS",
    "WatsonXAgentMiddleware",
    "build_watsonx_middleware",
]


# Re-export the legacy SystemMessage import target so callers depending on this module's
# public API do not break (placeholder corrective message uses SystemMessage).
SystemMessage = SystemMessage
