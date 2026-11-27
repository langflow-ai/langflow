"""Auto chat history: token budget, fold batch and fold, on an in-memory store."""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from lfx.base.memory import session_memory as sm
from lfx.base.memory.context_budget import estimate_tokens, tool_result_cap
from lfx.memory.session_state import SessionMemoryState
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER

SCOPE = {"flow_id": "f", "user_id": "u", "session_id": "s", "context_id": ""}


class Store:
    """One session in memory, with the call signatures of `lfx.memory`."""

    def __init__(self) -> None:
        self.messages: list[Message] = []
        self.state = SessionMemoryState()
        self.saves = 0

    def add(self, text: str, sender: str = MESSAGE_SENDER_USER) -> Message:
        message = Message(text=text, sender=sender, sender_name=sender, session_id="s", id=str(uuid.uuid4()))
        self.messages.append(message)
        return message

    def _index(self, message_id) -> int | None:
        return next((i for i, m in enumerate(self.messages) if str(m.id) == str(message_id)), None)

    async def aget_session_memory_state(self, **_scope):
        return self.state

    async def aget_messages_between(
        self, *, after_message_id, before_message_id, limit, newest_first=False, **_kwargs
    ) -> list[Message]:
        after = None if after_message_id is None else self._index(after_message_id)
        rows = self.messages[(0 if after is None else after + 1) : self._index(before_message_id)]
        return rows[-limit:] if newest_first else rows[:limit]

    async def asave_session_memory_state(
        self, *, summary, cursor_message_id, folded_delta, expected_version, expected_state_id, **_kwargs
    ):
        if self.state.version != expected_version or self.state.id != expected_state_id:
            return None
        self.saves += 1
        self.state = SessionMemoryState(
            id=self.state.id or uuid.uuid4(),
            summary=summary,
            cursor_message_id=cursor_message_id,
            folded_count=self.state.folded_count + folded_delta,
            version=expected_version + 1,
        )
        return self.state


@pytest.fixture(autouse=True)
def _no_cooldowns():
    sm.reset_fold_cooldowns()
    yield
    sm.reset_fold_cooldowns()


def _session(store: Store, turns: int, size: int) -> Message:
    """Add `turns` user/assistant pairs of `size` tokens each, then the current input."""
    for i in range(turns):
        store.add(f"u{i} " + "x" * (size * 4 - 4))
        store.add(f"a{i} " + "y" * (size * 4 - 4), MESSAGE_SENDER_AI)
    return store.add("current question")


async def _load(store: Store, current: Message, budget: sm.Budget) -> sm.AutoHistory:
    return await sm.load_auto_history(scope=SCOPE, current_input_id=current.id, budget=budget, store=store)


def test_budget_follows_the_window_with_an_absolute_cap():
    assert sm.budget_for_window(128_000) == sm.Budget(high=12_000, low=6_000, message_cap=4_000)
    assert sm.budget_for_window(32_000) == sm.Budget(high=6_400, low=3_200, message_cap=2_133)
    assert sm.budget_for_window(None) == sm.Budget(high=8_000, low=4_000, message_cap=2_666)


def test_small_window_keeps_the_send_bound_and_the_tool_cap_well_inside_the_window():
    window = 8_192
    budget = sm.budget_for_window(window)
    assert budget.high + budget.message_cap <= window // 3
    assert tool_result_cap(window) == 2_048
    assert tool_result_cap(128_000) == 10_000
    assert tool_result_cap(None) == 10_000


async def test_history_under_the_high_mark_sends_every_message_and_folds_nothing():
    store = Store()
    current = _session(store, turns=3, size=100)
    loaded = await _load(store, current, sm.Budget(high=1_000, low=500, message_cap=200))
    assert [m.id for m in loaded.history] == [m.id for m in store.messages[:-1]]
    assert loaded.fold_batch == []


async def test_history_above_the_high_mark_keeps_the_newest_and_folds_the_oldest_to_the_low_mark():
    store = Store()
    current = _session(store, turns=6, size=100)  # 1,200 tokens unfolded
    budget = sm.Budget(high=1_000, low=500, message_cap=200)
    loaded = await _load(store, current, budget)

    assert loaded.history_tokens <= budget.high + budget.message_cap
    assert sum(sm.message_tokens(m, budget) for m in loaded.fold_batch) <= budget.high
    assert loaded.history[-1].id == store.messages[-2].id  # the newest stored message
    assert loaded.fold_batch[0].id == store.messages[0].id  # the oldest one
    remaining = sum(sm.message_tokens(m, budget) for m in store.messages[len(loaded.fold_batch) : -1])
    assert remaining <= budget.low


async def test_a_large_message_is_cut_in_the_model_input_and_unchanged_in_the_store():
    store = Store()
    big = store.add("HEAD " + "z" * 100_000 + " TAIL")
    current = store.add("what was in it?")
    budget = sm.Budget(high=12_000, low=6_000, message_cap=1_000)
    loaded = await _load(store, current, budget)

    sent = loaded.history[0]
    assert estimate_tokens(sent.text) <= 1_030
    assert sent.text.startswith("HEAD")
    assert sent.text.endswith("TAIL")
    assert len(big.text) > 100_000


async def test_fold_saves_the_summary_and_the_next_turn_reads_only_after_the_cursor():
    store = Store()
    current = _session(store, turns=6, size=100)
    budget = sm.Budget(high=1_000, low=500, message_cap=200)
    loaded = await _load(store, current, budget)

    async def summarize(_state, batch):
        return f"folded {len(batch)} messages"

    saved = await sm.fold(
        scope=SCOPE, state=loaded.state, batch=loaded.fold_batch, summarize=summarize, summary_model="m", store=store
    )

    assert saved.cursor_message_id == loaded.fold_batch[-1].id
    again = await _load(store, current, budget)
    assert sm.is_notes_text(again.history[0].text)
    assert "folded" in again.history[0].text
    assert again.history[1].id == store.messages[len(loaded.fold_batch)].id
    assert again.fold_batch == []
    assert again.history_tokens <= budget.high + budget.message_cap


async def test_failed_fold_keeps_the_state_and_pauses_folding_after_two_failures_in_a_row():
    store = Store()
    current = _session(store, turns=6, size=100)
    budget = sm.Budget(high=1_000, low=500, message_cap=200)

    async def broken(_state, _batch):
        msg = "provider down"
        raise RuntimeError(msg)

    for attempt in range(2):
        loaded = await _load(store, current, budget)
        assert loaded.fold_batch, f"attempt {attempt}: one failure only retries on the next turn"
        saved = await sm.fold(
            scope=SCOPE, state=loaded.state, batch=loaded.fold_batch, summarize=broken, summary_model="m", store=store
        )
        assert saved is None
    assert store.state == SessionMemoryState()
    again = await _load(store, current, budget)
    assert again.fold_batch == []  # paused
    assert again.history_tokens <= budget.high + budget.message_cap  # bounded while folding is paused


async def test_history_keeps_the_messages_of_a_fold_that_runs_beside_this_turn():
    store = Store()
    first = store.add("project is PRJ-123")
    store.add("noted", MESSAGE_SENDER_AI)
    current = _session(store, turns=5, size=100)  # 1,000 tokens, plus the first two: just above the high mark
    budget = sm.Budget(high=1_000, low=500, message_cap=200)
    loaded = await _load(store, current, budget)
    assert loaded.fold_batch[0].id == first.id
    assert loaded.history[0].id == first.id  # not yet in the notes, so it must still be in the history


async def test_lost_race_keeps_the_state_of_the_other_writer_and_is_not_a_failure():
    store = Store()
    current = _session(store, turns=10, size=100)
    loaded = await _load(store, current, sm.Budget(high=1_000, low=500, message_cap=200))
    store.state = replace(store.state, id=uuid.uuid4(), version=1, summary="other run")

    async def summarize(_state, _batch):
        return "mine"

    outcome = await sm.fold(
        scope=SCOPE, state=loaded.state, batch=loaded.fold_batch, summarize=summarize, summary_model="m", store=store
    )
    assert outcome == loaded.state  # not None: the Agent shows the fold as done, not failed
    assert store.state.summary == "other run"


async def test_backlog_folds_from_the_oldest_unfolded_message():
    store = Store()
    current = _session(store, turns=sm.MAX_UNFOLDED_ROWS, size=5)  # 400 short rows, under the high mark
    loaded = await _load(store, current, sm.Budget(high=12_000, low=6_000))
    assert loaded.fold_batch
    assert loaded.fold_batch[0].id == store.messages[0].id


async def test_store_without_session_memory_returns_none():
    store = Store()

    async def unsupported(**_scope):
        return None

    store.aget_session_memory_state = unsupported
    assert await _load(store, store.add("hi"), sm.Budget(high=1_000, low=500, message_cap=200)) is None


def test_notes_render_the_summary_as_background_notes():
    text = sm.render_notes(SessionMemoryState(summary="Key facts:\n- project: PRJ-123"))
    assert sm.is_notes_text(text)
    assert "- project: PRJ-123" in text
    assert sm.render_notes(SessionMemoryState()) == ""


@pytest.mark.parametrize(("reply", "expected"), [("  Key facts:\n- a  ", "Key facts:\n- a"), ("   ", None)])
def test_parse_fold_reply_keeps_text_and_rejects_an_empty_reply(reply, expected):
    assert sm.parse_fold_reply(reply) == expected


async def test_history_bound_counts_the_cap_marker_of_cut_messages():
    store = Store()
    for _ in range(6):
        store.add("x" * 10_000)  # each one is cut to the message cap
    current = store.add("q")
    budget = sm.Budget(high=1_000, low=500, message_cap=200)
    loaded = await _load(store, current, budget)
    sent = sum(estimate_tokens(m.text) for m in loaded.history)
    assert sent <= budget.high + budget.message_cap


class ChatOllama:
    """Stand-in for langchain_ollama.ChatOllama, which lfx does not install: no profile, an optional num_ctx."""

    profile = None

    def __init__(self, num_ctx: int | None = None) -> None:
        self.num_ctx = num_ctx


def test_ollama_window_is_its_context_length_not_unknown():
    assert sm.model_window(ChatOllama()) == sm.OLLAMA_DEFAULT_NUM_CTX
    assert sm.model_window(ChatOllama(num_ctx=16_384)) == 16_384
    budget = sm.budget_for_window(sm.model_window(ChatOllama()))
    assert budget.high + budget.message_cap < sm.OLLAMA_DEFAULT_NUM_CTX // 2


async def test_fold_prompt_gets_messages_cut_to_the_budget_message_cap():
    store = Store()
    for _ in range(3):
        store.add("x" * 8_000)  # 2,000 tokens each
    current = store.add("q")
    budget = sm.budget_for_window(sm.OLLAMA_DEFAULT_NUM_CTX)  # message cap of 273 tokens
    loaded = await _load(store, current, budget)
    received: list[str] = []

    async def summarize(_state, batch):
        received.extend(m.text for m in batch)
        return "summary"

    saved = await sm.fold(
        scope=SCOPE,
        state=loaded.state,
        batch=loaded.fold_batch,
        summarize=summarize,
        summary_model="m",
        budget=budget,
        store=store,
    )
    assert saved is not None
    assert received
    assert all(estimate_tokens(text) <= budget.message_cap + 30 for text in received)
    assert len(store.messages[0].text) == 8_000  # the stored message does not change
