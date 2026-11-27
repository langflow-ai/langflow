"""Auto mode variants for the eval. They run the real `lfx.base.memory.session_memory` code on the eval store.

- `auto`: the budget from the model window (gpt-4o-mini: 128,000 tokens, so a high mark of 12,000).
- `auto_stress`: a high mark of 2,000 tokens, to force many folds in one session (PRD requirement 1).
- `auto_stress_summary`: the same budget, but the fold writes the free-text summary of PR #16515 and no
  facts. It is the A/B test of facts apart from the summary against a free-text summary.
"""

from __future__ import annotations

import memstore
import pr16515_compressor as pr
from lfx.base.memory import session_memory as sm
from lfx.components.models_and_agents.agent_helpers.tool_result_cap_middleware import ToolResultCapMiddleware
from run_eval import MODEL, FoldRun, Policy, Prepared

STRESS = sm.Budget(high=2_000, low=1_000)


class Auto(Policy):
    """The Auto chat history mode with a fixed or window-based budget."""

    def __init__(self, llm, name: str, budget: sm.Budget | None = None, *, free_text: bool = False) -> None:
        self.llm = llm
        self.name = name
        self.budget = budget or sm.budget_for_window(sm.model_window(llm))
        self.free_text = free_text

    async def prepare(self, store, user_message) -> Prepared:
        scope = {"flow_id": "f", "user_id": "u", "session_id": store.session_id, "context_id": ""}
        loaded = await sm.load_auto_history(
            scope=scope, current_input_id=user_message.id, budget=self.budget, store=memstore
        )
        fold = None
        if loaded.fold_batch:
            fold = FoldRun()

            async def summarize(state, messages):
                prompt = (
                    pr.format_fold_prompt(state.summary, messages)
                    if self.free_text
                    else sm.format_fold_prompt(state, messages)
                )
                response = await self.llm.ainvoke(prompt, config={"callbacks": [fold.usage]})
                return sm.parse_fold_reply(str(response.content))

            fold.coro = sm.fold(
                scope=scope,
                state=loaded.state,
                batch=loaded.fold_batch,
                summarize=summarize,
                summary_model=MODEL,
                store=memstore,
            )
        return Prepared(loaded.history, fold)

    def middleware(self, llm) -> list:  # noqa: ARG002
        return [ToolResultCapMiddleware()]

    def describe_state(self, store) -> dict:
        state = store.state
        return {"facts": [list(p) for p in state.facts], "summary": state.summary, "folded_count": state.folded_count}


def factories(llm) -> dict:
    return {
        "auto": lambda: Auto(llm, "auto"),
        "auto_stress": lambda: Auto(llm, "auto_stress", STRESS),
        "auto_stress_summary": lambda: Auto(llm, "auto_stress_summary", STRESS, free_text=True),
    }
