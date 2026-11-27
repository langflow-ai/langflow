"""Auto chat history: token budget, fold batch and fold, on an in-memory store."""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from lfx.base.memory import session_memory as sm
from lfx.base.memory.context_budget import estimate_tokens
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
        self, *, summary, facts, cursor_message_id, folded_delta, expected_version, expected_state_id, **_kwargs
    ):
        if self.state.version != expected_version or self.state.id != expected_state_id:
            return None
        self.saves += 1
        self.state = SessionMemoryState(
            id=self.state.id or uuid.uuid4(),
            summary=summary,
            facts=tuple(facts),
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
    assert sm.budget_for_window(128_000) == sm.Budget(high=12_000, low=6_000)
    assert sm.budget_for_window(32_000) == sm.Budget(high=6_400, low=3_200)
    assert sm.budget_for_window(None) == sm.Budget(high=8_000, low=4_000)


async def test_history_under_the_high_mark_sends_every_message_and_folds_nothing():
    store = Store()
    current = _session(store, turns=3, size=100)
    loaded = await _load(store, current, sm.Budget(high=1_000, low=500))
    assert [m.id for m in loaded.history] == [m.id for m in store.messages[:-1]]
    assert loaded.fold_batch == []


async def test_history_above_the_high_mark_keeps_the_newest_and_folds_the_oldest_to_the_low_mark():
    store = Store()
    current = _session(store, turns=6, size=100)  # 1,200 tokens unfolded
    budget = sm.Budget(high=1_000, low=500)
    loaded = await _load(store, current, budget)

    assert loaded.history_tokens <= budget.high
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
    budget = sm.Budget(high=1_000, low=500)
    loaded = await _load(store, current, budget)

    async def summarize(_state, batch):
        return sm.FoldResult(summary=f"folded {len(batch)} messages")

    saved = await sm.fold(
        scope=SCOPE, state=loaded.state, batch=loaded.fold_batch, summarize=summarize, summary_model="m", store=store
    )

    assert saved.cursor_message_id == loaded.fold_batch[-1].id
    again = await _load(store, current, budget)
    assert sm.is_notes_text(again.history[0].text)
    assert "folded" in again.history[0].text
    assert again.history[1].id == store.messages[len(loaded.fold_batch)].id
    assert again.fold_batch == []
    assert again.history_tokens <= budget.high


async def test_failed_fold_keeps_the_state_and_pauses_folding_for_the_session():
    store = Store()
    current = _session(store, turns=10, size=100)
    budget = sm.Budget(high=1_000, low=500)
    loaded = await _load(store, current, budget)

    async def broken(_state, _batch):
        msg = "provider down"
        raise RuntimeError(msg)

    assert (
        await sm.fold(
            scope=SCOPE, state=loaded.state, batch=loaded.fold_batch, summarize=broken, summary_model="m", store=store
        )
        is None
    )
    assert store.state == SessionMemoryState()
    again = await _load(store, current, budget)
    assert again.fold_batch == []  # paused
    assert again.history_tokens <= budget.high  # still bounded while folding is paused


async def test_lost_race_keeps_the_state_of_the_other_writer():
    store = Store()
    current = _session(store, turns=10, size=100)
    loaded = await _load(store, current, sm.Budget(high=1_000, low=500))
    store.state = replace(store.state, id=uuid.uuid4(), version=1, summary="other run")

    async def summarize(_state, _batch):
        return sm.FoldResult(summary="mine")

    assert (
        await sm.fold(
            scope=SCOPE,
            state=loaded.state,
            batch=loaded.fold_batch,
            summarize=summarize,
            summary_model="m",
            store=store,
        )
        is None
    )
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
    assert await _load(store, store.add("hi"), sm.Budget(high=1_000, low=500)) is None


def test_notes_render_facts_and_summary_as_background_notes():
    text = sm.render_notes(SessionMemoryState(facts=(("project", "PRJ-123"),), summary="We debugged pods."))
    assert sm.is_notes_text(text)
    assert "- project: PRJ-123" in text
    assert "We debugged pods." in text
    assert sm.render_notes(SessionMemoryState()) == ""
