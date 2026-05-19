"""Tests for the per-request tool-result cache.

The cache mirrors the pattern used by ``flow_builder_tools._flow_events_var``:
a ``contextvars.ContextVar`` scoped to a single assistant request. Tools that
are pure-read (``search_components``, ``describe_component``, ``get_field_value``)
memoize results within a request so the LLM repeating the same call doesn't
re-invoke the underlying registry / canvas walk.

These tests fix the contract:
  - hits return the cached value without invoking the producer
  - misses invoke the producer and store its result
  - errors are NOT cached (a flaky network call must be retried)
  - the cache is bounded (LRU eviction)
  - contexts spawned by ``asyncio.gather`` get independent caches
"""

from __future__ import annotations

import asyncio
from contextvars import copy_context

import pytest
from lfx.mcp.tool_cache import (
    MAX_CACHE_ENTRIES,
    cached_tool_call,
    reset_tool_cache,
)


class TestCachedToolCallHits:
    def setup_method(self):
        reset_tool_cache()

    def test_cached_tool_call_should_return_producer_value_on_first_call(self):
        producer_calls = 0

        def producer():
            nonlocal producer_calls
            producer_calls += 1
            return {"result": "value-1"}

        result = cached_tool_call("describe_component", {"name": "ChatInput"}, producer)

        assert result == {"result": "value-1"}
        assert producer_calls == 1

    def test_cached_tool_call_should_return_cached_value_on_second_call_same_args(self):
        producer_calls = 0

        def producer():
            nonlocal producer_calls
            producer_calls += 1
            return {"result": f"value-{producer_calls}"}

        first = cached_tool_call("describe_component", {"name": "ChatInput"}, producer)
        second = cached_tool_call("describe_component", {"name": "ChatInput"}, producer)

        assert first == second
        # Producer ran only once — the second call was served from cache.
        assert producer_calls == 1

    def test_cached_tool_call_should_distinguish_args(self):
        # Same tool, different args → independent cache entries.
        producer_calls: dict[str, int] = {}

        def producer_for(name: str):
            def producer():
                producer_calls[name] = producer_calls.get(name, 0) + 1
                return {"name": name}

            return producer

        chat = cached_tool_call("describe_component", {"name": "ChatInput"}, producer_for("ChatInput"))
        agent = cached_tool_call("describe_component", {"name": "Agent"}, producer_for("Agent"))

        assert chat == {"name": "ChatInput"}
        assert agent == {"name": "Agent"}
        assert producer_calls == {"ChatInput": 1, "Agent": 1}

    def test_cached_tool_call_should_distinguish_tool_names(self):
        # Same args, different tools → independent entries.
        def search_producer():
            return ["a", "b"]

        def describe_producer():
            return {"described": True}

        s = cached_tool_call("search_components", {"q": "x"}, search_producer)
        d = cached_tool_call("describe_component", {"q": "x"}, describe_producer)

        assert s == ["a", "b"]
        assert d == {"described": True}

    def test_cached_tool_call_should_be_order_insensitive_on_dict_args(self):
        # The serializer must be stable across key insertion order, otherwise
        # the same logical call would miss the cache.
        producer_calls = 0

        def producer():
            nonlocal producer_calls
            producer_calls += 1
            return producer_calls

        cached_tool_call("t", {"a": 1, "b": 2}, producer)
        cached_tool_call("t", {"b": 2, "a": 1}, producer)

        assert producer_calls == 1


class TestCachedToolCallDoesNotCacheErrors:
    def setup_method(self):
        reset_tool_cache()

    def test_cached_tool_call_should_propagate_producer_exception(self):
        def producer():
            msg = "boom"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="boom"):
            cached_tool_call("t", {"x": 1}, producer)

    def test_cached_tool_call_should_not_cache_errors_so_subsequent_calls_retry(self):
        attempts = 0

        def flaky_producer():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                msg = "transient"
                raise RuntimeError(msg)
            return {"recovered": True}

        with pytest.raises(RuntimeError):
            cached_tool_call("t", {"x": 1}, flaky_producer)

        # Second call must NOT return a cached exception — it must rerun.
        result = cached_tool_call("t", {"x": 1}, flaky_producer)
        assert result == {"recovered": True}
        assert attempts == 2


class TestCachedToolCallBoundedSize:
    def setup_method(self):
        reset_tool_cache()

    def test_cached_tool_call_should_cap_at_max_cache_entries(self):
        # Insert one more than the cap; the oldest entry must be evicted.
        producer_calls = 0

        def make_producer(value: int):
            def producer():
                nonlocal producer_calls
                producer_calls += 1
                return value

            return producer

        for i in range(MAX_CACHE_ENTRIES + 1):
            cached_tool_call("t", {"i": i}, make_producer(i))

        # Now re-call the oldest one (i=0) — it should miss (was evicted)
        # and the producer should run again.
        re_producer_called = False

        def re_producer():
            nonlocal re_producer_called
            re_producer_called = True
            return 0

        cached_tool_call("t", {"i": 0}, re_producer)
        assert re_producer_called, "Oldest entry should have been LRU-evicted"


class TestCachedToolCallContextIsolation:
    def setup_method(self):
        reset_tool_cache()

    def test_cached_tool_call_should_isolate_child_writes_from_parent(self):
        # ContextVar isolation contract for fresh (post-reset) contexts:
        # writes made in a child context do NOT leak back to the parent.
        # This is the production scenario — request handler calls
        # reset_tool_cache() at start, so any asyncio.gather child task
        # lazily allocates its own cache locally.
        producer_calls = 0

        def producer():
            nonlocal producer_calls
            producer_calls += 1
            return "value"

        # Parent has no prior allocation (setup_method reset). Child
        # populates its own cache.
        def child_call():
            cached_tool_call("t", {"x": 1}, producer)

        copy_context().run(child_call)
        assert producer_calls == 1

        # Back in parent: another call must also miss — the child's
        # lazily-allocated dict never reached the parent context.
        cached_tool_call("t", {"x": 1}, producer)
        assert producer_calls == 2, "Parent must not inherit child's cache"

    def test_cached_tool_call_should_isolate_across_asyncio_gather_tasks(self):
        # Each asyncio task runs in its own copied context, so sibling tasks
        # must not see each other's cached entries.
        async def task(label: str, counter: list[int]):
            def producer():
                counter[0] += 1
                return label

            # Two calls — second should hit cache *within this task*.
            cached_tool_call("t", {"label": label}, producer)
            cached_tool_call("t", {"label": label}, producer)

        async def main():
            counters = [[0], [0]]
            await asyncio.gather(
                task("alpha", counters[0]),
                task("beta", counters[1]),
            )
            return counters

        counters = asyncio.run(main())
        # Each task ran the producer exactly once (hits within the task).
        assert counters[0] == [1]
        assert counters[1] == [1]


class TestFlowBuilderToolsIntegration:
    """B3 — read-only flow-builder tools memoize results within a request.

    These exercise the integration: calling the tool's method twice with
    the same args must hit the cache on the second call. Mutation tools
    (add_component, build_flow_from_spec, etc.) MUST NOT be cached — they
    have side effects.
    """

    def setup_method(self):
        reset_tool_cache()

    def test_search_components_should_use_request_cache(self):
        from lfx.mcp.flow_builder_tools import SearchComponentTypes

        tool = SearchComponentTypes()
        tool.query = "ChatInput"

        # Two back-to-back calls. The underlying registry walk should
        # happen ONCE per (tool_name, args). We assert this via a side
        # channel: patching the inner load_local_registry to count calls.
        import lfx.mcp.flow_builder_tools.read_tools as fbt  # B2: patch the resolution site

        calls = 0
        original = fbt._load_registry_user_aware

        def counting_loader():
            nonlocal calls
            calls += 1
            return original()

        fbt._load_registry_user_aware = counting_loader
        try:
            tool.search_components()
            tool.search_components()
        finally:
            fbt._load_registry_user_aware = original

        assert calls == 1, "search_components must hit cache on repeat call"

    def test_describe_component_should_use_request_cache(self):
        from lfx.mcp.flow_builder_tools import DescribeComponentType

        tool = DescribeComponentType()
        tool.component_type = "ChatInput"

        import lfx.mcp.flow_builder_tools.read_tools as fbt  # B2: patch the resolution site

        calls = 0
        original = fbt._load_registry_user_aware

        def counting_loader():
            nonlocal calls
            calls += 1
            return original()

        fbt._load_registry_user_aware = counting_loader
        try:
            tool.describe_component()
            tool.describe_component()
        finally:
            fbt._load_registry_user_aware = original

        assert calls == 1, "describe_component must hit cache on repeat call"

    def test_describe_component_with_different_types_should_miss_cache(self):
        from lfx.mcp.flow_builder_tools import DescribeComponentType

        tool = DescribeComponentType()

        import lfx.mcp.flow_builder_tools.read_tools as fbt  # B2: patch the resolution site

        calls = 0
        original = fbt._load_registry_user_aware

        def counting_loader():
            nonlocal calls
            calls += 1
            return original()

        fbt._load_registry_user_aware = counting_loader
        try:
            tool.component_type = "ChatInput"
            tool.describe_component()
            tool.component_type = "ChatOutput"
            tool.describe_component()
        finally:
            fbt._load_registry_user_aware = original

        # Two distinct component_type args → two loader calls.
        assert calls == 2

    def test_reset_tool_cache_should_force_refetch_on_next_describe(self):
        from lfx.mcp.flow_builder_tools import DescribeComponentType

        tool = DescribeComponentType()
        tool.component_type = "ChatInput"

        import lfx.mcp.flow_builder_tools.read_tools as fbt  # B2: patch the resolution site

        calls = 0
        original = fbt._load_registry_user_aware

        def counting_loader():
            nonlocal calls
            calls += 1
            return original()

        fbt._load_registry_user_aware = counting_loader
        try:
            tool.describe_component()  # miss → 1
            reset_tool_cache()
            tool.describe_component()  # miss again after reset → 2
        finally:
            fbt._load_registry_user_aware = original

        assert calls == 2


class TestResetToolCache:
    def test_reset_tool_cache_should_drop_existing_entries(self):
        producer_calls = 0

        def producer():
            nonlocal producer_calls
            producer_calls += 1
            return "v"

        cached_tool_call("t", {"x": 1}, producer)
        reset_tool_cache()
        cached_tool_call("t", {"x": 1}, producer)

        assert producer_calls == 2

    def test_reset_tool_cache_should_be_idempotent_when_no_cache_exists(self):
        # Calling reset on a fresh context (no entries) must not raise.
        reset_tool_cache()
        reset_tool_cache()
