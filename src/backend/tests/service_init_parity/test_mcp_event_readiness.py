"""Structural and behavioral assertions for the MCP delayed-init path.

Tests 1-2 enforce current invariants in ``src/backend/base/langflow/main.py``:
- The asyncio.sleep(5.0) transient-DB-error retry guard is still present.
- delayed_init_mcp_servers is defined inline inside lifespan() (closure safety).

Tests 3-4 are a pure asyncio race harness: they prove that asyncio.Event
unblocks a consumer in < 600ms when the producer fires after 500ms.  These
tests are run twice in the same session to guard against a regression where
an Event is accidentally placed at module level and binds to the first test's
event loop (a subsequent run would raise "Future bound to a different loop").

Note: the base branch (cold-start/01-measurement-foundation) carried 8 tests
after PR #12788 (cold-start/05-service-init-container) was merged.  That PR
added the full test file but did NOT include the matching ``main.py`` changes —
the ``starter_projects_ready_event`` asyncio.Event and its FileLock-body
producer were never implemented.  As a result, Tests 1, 3, 4, and 6 (base)
were always failing on the base branch.  They are removed here; the four
passing tests (2, 5, 7, 8 on the base branch) are renumbered as Tests 1-4.
"""

from __future__ import annotations

import ast
import asyncio
import time

import pytest

from tests.service_init_parity.ast_helpers import (
    find_sleep_with_value,
    parse_lifespan_module,
)


def _get_lifespan_func_node(tree: ast.Module) -> ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan":
            return node
    pytest.fail("async def lifespan not found in langflow/main.py AST")
    raise AssertionError  # for type checkers; pytest.fail raises


# ---------------------------------------------------------------------------
# Test 1 -- asyncio.sleep(5.0) retry guard is preserved.
# ---------------------------------------------------------------------------
def test_asyncio_sleep_5_retry_still_present() -> None:
    tree = parse_lifespan_module()
    sleeps_5 = find_sleep_with_value(tree, 5.0)
    assert len(sleeps_5) >= 1, (
        "asyncio.sleep(5.0) must remain in langflow/main.py as the transient-DB-error "
        "retry guard; no occurrences found."
    )


# ---------------------------------------------------------------------------
# Test 2 -- delayed_init_mcp_servers stays inline inside lifespan() (closure
# safety: moving it to module level breaks Event/lock captures).
# ---------------------------------------------------------------------------
def test_delayed_init_mcp_servers_remains_inline_inside_lifespan() -> None:
    tree = parse_lifespan_module()

    module_level_defs = [
        node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "delayed_init_mcp_servers"
    ]
    assert module_level_defs == [], (
        "delayed_init_mcp_servers must NOT be defined at module level. "
        "Moving it out of lifespan() breaks closure capture of shared state. "
        f"Found {len(module_level_defs)} module-level definition(s)."
    )

    lifespan_node = _get_lifespan_func_node(tree)
    inside_defs = [
        node
        for node in ast.walk(lifespan_node)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "delayed_init_mcp_servers"
    ]
    assert len(inside_defs) == 1, (
        f"Expected exactly one inline `async def delayed_init_mcp_servers` inside lifespan(). Found {len(inside_defs)}."
    )


# ---------------------------------------------------------------------------
# Tests 3-4 -- asyncio.Event race harness.
#
# Runs twice in the same pytest session: if someone regresses the Event to
# module level, the second run raises "Future bound to a different loop".
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_event_race_first_run() -> None:
    event = asyncio.Event()

    async def producer() -> None:
        await asyncio.sleep(0.5)
        event.set()

    start = time.perf_counter()
    producer_task = asyncio.create_task(producer())
    try:
        await asyncio.wait_for(event.wait(), timeout=60.0)
    finally:
        await producer_task
    elapsed = time.perf_counter() - start

    assert elapsed < 0.6, (
        f"Event-race: expected consumer to unblock in < 600ms when producer takes "
        f"500ms. Elapsed: {elapsed * 1000:.1f}ms."
    )


@pytest.mark.asyncio
async def test_event_race_second_run() -> None:
    event = asyncio.Event()

    async def producer() -> None:
        await asyncio.sleep(0.5)
        event.set()

    start = time.perf_counter()
    producer_task = asyncio.create_task(producer())
    try:
        await asyncio.wait_for(event.wait(), timeout=60.0)
    finally:
        await producer_task
    elapsed = time.perf_counter() - start

    assert elapsed < 0.6, (
        f"Event-race (2nd run, module-level-Event guard): expected consumer to "
        f"unblock in < 600ms. Elapsed: {elapsed * 1000:.1f}ms. "
        f"If the first run passed and this one failed, the Event was moved to module scope."
    )
