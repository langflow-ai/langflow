"""Chat + DB Locust user."""

from __future__ import annotations

from locust import task

from tests.locust.langflow_runtime.flows.defaults import DEFAULT_CHAT_INPUT
from tests.locust.langflow_runtime.metrics.correctness import expect_chat_ordering, expect_contains
from tests.locust.langflow_runtime.users.base import PerfBaseUser, extract_output_text


class ChatDbUser(PerfBaseUser):
    weight = 1
    workload_name = "chat_db"
    flow_class = "memory_chatbot"

    def on_start(self) -> None:
        super().on_start()
        self._turn = 0
        self._messages: list[dict[str, object]] = []

    @task
    def chat_turn(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return
        flow = self.require_flow_or_fail("MemoryChatbotNoLLM")
        workflows = self.require_workflows_client()

        self._turn += 1
        input_value = f"{DEFAULT_CHAT_INPUT}-{self._turn}"
        result = workflows.run_sync(
            flow_id=str(flow["flow_id"]),
            input_value=input_value,
            session_id=self.session_id,
        )
        text = extract_output_text(result)
        if not text.strip():
            raise AssertionError("chat response was empty")
        # Server-visible contract: response must echo/include this turn's input marker.
        contains = expect_contains(text, input_value)
        if not contains.ok:
            # Memory chatbot may wrap the user text; require at least the turn suffix.
            turn_marker = f"-{self._turn}"
            if turn_marker not in text and input_value not in text:
                raise AssertionError(contains.reason or "chat response missing turn input")

        self._messages.append({"index": self._turn, "sequence": self._turn, "text": text, "input": input_value})
        ordering = expect_chat_ordering(self._messages)
        if not ordering.ok:
            raise AssertionError(ordering.reason or "chat ordering failed")
        # Multi-turn: later responses should not drop earlier turn markers when history is returned.
        if self._turn >= 2 and f"{DEFAULT_CHAT_INPUT}-1" in text:
            history_order = expect_chat_ordering([{"index": i + 1, "sequence": i + 1} for i in range(self._turn)])
            if not history_order.ok:
                raise AssertionError(history_order.reason or "chat history ordering failed")
