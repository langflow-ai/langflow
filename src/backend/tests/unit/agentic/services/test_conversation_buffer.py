"""Tests for the per-session conversation buffer.

The buffer mirrors the shell-history model: each ``session_id`` gets a
ring buffer of the last N turns, and the buffer itself caps the number
of tracked sessions (oldest evicted) so a long-lived process doesn't
leak memory under heavy concurrent use.

These tests pin the contract used by ``assistant_service`` to inject
prior turns into the next LLM request so the agent has continuity
without the frontend having to carry the whole conversation back.
"""

from __future__ import annotations

import asyncio

import pytest
from langflow.agentic.services.conversation_buffer import (
    MAX_SESSIONS,
    MAX_TURNS_PER_SESSION,
    ConversationBuffer,
    ConversationTurn,
)

USER = "u-test"


class TestPushAndGetRecent:
    def test_push_then_get_recent_should_return_the_pushed_turn(self):
        buf = ConversationBuffer()
        turn = ConversationTurn(user="hi", assistant="hello")

        buf.push(USER, "s1", turn)

        assert buf.get_recent(USER, "s1") == [turn]

    def test_get_recent_should_return_empty_list_when_session_unknown(self):
        buf = ConversationBuffer()
        assert buf.get_recent(USER, "never-pushed") == []

    def test_get_recent_should_return_turns_in_oldest_first_order(self):
        buf = ConversationBuffer()
        t1 = ConversationTurn(user="u1", assistant="a1")
        t2 = ConversationTurn(user="u2", assistant="a2")
        t3 = ConversationTurn(user="u3", assistant="a3")

        buf.push(USER, "s1", t1)
        buf.push(USER, "s1", t2)
        buf.push(USER, "s1", t3)

        assert buf.get_recent(USER, "s1") == [t1, t2, t3]

    def test_get_recent_with_explicit_limit_should_return_only_last_n(self):
        buf = ConversationBuffer()
        for i in range(5):
            buf.push(USER, "s1", ConversationTurn(user=f"u{i}", assistant=f"a{i}"))

        # Last 2 turns, oldest-first.
        recent = buf.get_recent(USER, "s1", limit=2)
        assert [t.user for t in recent] == ["u3", "u4"]

    def test_push_should_cap_at_max_turns_per_session(self):
        # Older turns dropped FIFO once the per-session cap is hit.
        buf = ConversationBuffer()
        for i in range(MAX_TURNS_PER_SESSION + 3):
            buf.push(USER, "s1", ConversationTurn(user=f"u{i}", assistant=f"a{i}"))

        recent = buf.get_recent(USER, "s1")
        assert len(recent) == MAX_TURNS_PER_SESSION
        # The oldest 3 (u0, u1, u2) were dropped — the survivors start at u3.
        assert recent[0].user == "u3"
        assert recent[-1].user == f"u{MAX_TURNS_PER_SESSION + 2}"


class TestSessionIsolation:
    def test_get_recent_should_isolate_sessions(self):
        buf = ConversationBuffer()
        buf.push("alice", "s1", ConversationTurn(user="hi-a", assistant="ack-a"))
        buf.push("alice", "s2", ConversationTurn(user="hi-b", assistant="ack-b"))

        assert [t.user for t in buf.get_recent("alice", "s1")] == ["hi-a"]
        assert [t.user for t in buf.get_recent("alice", "s2")] == ["hi-b"]

    def test_clear_should_drop_only_the_named_session(self):
        buf = ConversationBuffer()
        buf.push("alice", "s1", ConversationTurn(user="hi-a", assistant="ack-a"))
        buf.push("alice", "s2", ConversationTurn(user="hi-b", assistant="ack-b"))

        buf.clear("alice", "s1")

        assert buf.get_recent("alice", "s1") == []
        assert len(buf.get_recent("alice", "s2")) == 1

    def test_clear_should_be_idempotent_on_unknown_session(self):
        buf = ConversationBuffer()
        # No exception — silently no-op.
        buf.clear(USER, "never-pushed")


class TestCrossTenantIsolation:
    """SECURITY contract — buffer MUST partition by ``(user_id, session_id)``.

    A tenant who learns another tenant's ``session_id`` (via observability
    leaks, log exfil, header echoing, etc.) MUST NOT be able to read or
    wipe that tenant's conversation history by reusing the session_id.
    """

    def test_get_recent_should_return_empty_for_a_different_user_with_the_same_session_id(self):
        buf = ConversationBuffer()
        buf.push("alice", "shared-sid", ConversationTurn(user="secret", assistant="ok"))

        # Bob shows up with Alice's session_id — must see nothing.
        assert buf.get_recent("bob", "shared-sid") == []

    def test_push_should_not_co_mingle_into_a_different_user_with_the_same_session_id(self):
        buf = ConversationBuffer()
        buf.push("alice", "shared-sid", ConversationTurn(user="alice-1", assistant="ok"))
        buf.push("bob", "shared-sid", ConversationTurn(user="bob-1", assistant="ok"))

        # Two distinct buffers under the same session_id, partitioned by user.
        assert [t.user for t in buf.get_recent("alice", "shared-sid")] == ["alice-1"]
        assert [t.user for t in buf.get_recent("bob", "shared-sid")] == ["bob-1"]

    def test_clear_should_only_affect_the_calling_users_partition(self):
        buf = ConversationBuffer()
        buf.push("alice", "shared-sid", ConversationTurn(user="alice-1", assistant="ok"))
        buf.push("bob", "shared-sid", ConversationTurn(user="bob-1", assistant="ok"))

        # Bob clears using Alice's session_id — must NOT touch Alice's partition.
        buf.clear("bob", "shared-sid")

        assert [t.user for t in buf.get_recent("alice", "shared-sid")] == ["alice-1"]
        assert buf.get_recent("bob", "shared-sid") == []


class TestLRUEviction:
    def test_push_should_evict_oldest_session_when_max_sessions_exceeded(self):
        # The buffer keeps at most MAX_SESSIONS keyed sessions in memory.
        # Push to MAX_SESSIONS+1 unique sessions and confirm the very first
        # one was evicted.
        buf = ConversationBuffer()
        for i in range(MAX_SESSIONS + 1):
            buf.push(USER, f"s{i}", ConversationTurn(user=f"u{i}", assistant=f"a{i}"))

        assert buf.get_recent(USER, "s0") == [], "Oldest session must be evicted"
        # The most recent session still has its turn.
        assert len(buf.get_recent(USER, f"s{MAX_SESSIONS}")) == 1

    def test_push_should_refresh_session_on_use_so_recently_used_stays(self):
        # Touch s0 after filling up — its LRU position should refresh and a
        # different oldest session should be evicted instead.
        buf = ConversationBuffer()
        for i in range(MAX_SESSIONS):
            buf.push(USER, f"s{i}", ConversationTurn(user=f"u{i}", assistant=f"a{i}"))

        # Refresh s0 by pushing another turn.
        buf.push(USER, "s0", ConversationTurn(user="u0-fresh", assistant="a0-fresh"))

        # Now adding one more new session should evict s1 (the new oldest),
        # not s0 which we just refreshed.
        buf.push(USER, "s-new", ConversationTurn(user="u-new", assistant="a-new"))

        assert buf.get_recent(USER, "s1") == []
        assert len(buf.get_recent(USER, "s0")) == 2  # original + fresh
        assert len(buf.get_recent(USER, "s-new")) == 1


class TestConcurrency:
    def test_concurrent_pushes_to_same_session_should_preserve_all_turns(self):
        # Under asyncio.gather, pushes must serialize cleanly. Without a
        # lock, a deque/dict mutation could race and drop turns.
        buf = ConversationBuffer()

        async def push_one(i: int):
            await buf.push_async(USER, "s1", ConversationTurn(user=f"u{i}", assistant=f"a{i}"))

        async def main():
            await asyncio.gather(*[push_one(i) for i in range(8)])

        asyncio.run(main())

        # All 8 turns landed (order may vary because gather has no fairness
        # guarantees, but the count must be exact).
        recent = buf.get_recent(USER, "s1")
        assert len(recent) == 8


class TestConversationTurnPayload:
    def test_format_for_prompt_should_render_a_compact_user_assistant_block(self):
        # The exact wire format is the contract assistant_service depends on
        # when injecting history into the prompt. Keep it deterministic.
        turn = ConversationTurn(user="how do I add a Memory?", assistant="Use the Memory component.")
        rendered = turn.format_for_prompt()

        assert "how do I add a Memory?" in rendered
        assert "Use the Memory component." in rendered
        # Loose: must contain SOME framing that distinguishes user vs assistant.
        assert "User:" in rendered
        assert "Assistant:" in rendered


@pytest.mark.parametrize(
    "max_turns_assertion",
    [
        # Just a smoke check that the module-level constants are sane
        # before tests interpret them.
        (MAX_TURNS_PER_SESSION >= 5, "MAX_TURNS_PER_SESSION must be at least 5"),
        (MAX_SESSIONS >= 10, "MAX_SESSIONS must be at least 10"),
    ],
)
def test_module_constants_are_within_expected_bounds(max_turns_assertion):
    assertion, message = max_turns_assertion
    assert assertion, message
