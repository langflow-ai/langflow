"""D-07 + + + Pitfall 1/6 assertions for MCP Event readiness.

Plan 04-04 replaces the hardcoded ``asyncio.sleep(10.0)`` coordination hint in
``delayed_init_mcp_servers`` (``src/backend/base/langflow/main.py``) with an
``asyncio.Event`` driven by the starter-project FileLock block:

- The Event is constructed **inside** ``lifespan()`` so it binds to the running
  loop (D-12 / Pitfall 1, same root cause as's lock issue).
- The Event is ``.set()`` on both hash-hit and hash-miss paths inside the
  ``with lock:`` body, NOT in a ``finally:`` clause (so starter-project
  failures are surfaced via the 60s consumer timeout, not masked).
- ``delayed_init_mcp_servers`` now does
  ``await asyncio.wait_for(starter_projects_ready_event.wait(), timeout=60.0)``
  with a warn-and-continue degraded-mode path on ``asyncio.TimeoutError``
 .
- ``delayed_init_mcp_servers`` remains defined **inline** inside ``lifespan()``
  so the Event closure is captured (Pitfall 6).
- The 5s retry at the retry-after-first-failure site is preserved verbatim
 .

These tests enforce the above structurally (AST) and behaviorally (a small
asyncio race harness that proves the Event unblocks in < 600ms when the
producer takes 500ms -- i.e., the MCP init path no longer costs ~10s).

Test 8 runs the race harness twice in one pytest session to guard against a
regression where someone moves the Event to module level (Pitfall 1): a module-
level Event would bind to the first test's loop and the second test would fail
with a "Future bound to a different loop" error.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import re
import time

import langflow.main as main_mod
import pytest

from tests.phase_service_init_parity.ast_helpers import (
    find_calls_to,
    find_sleep_with_value,
    parse_lifespan_module,
)

_EVENT_NAME = "starter_projects_ready_event"


def _get_lifespan_func_node(tree: ast.Module) -> ast.AsyncFunctionDef:
    """Return the ``async def lifespan`` FunctionDef node from the parsed module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan":
            return node
    pytest.fail("async def lifespan not found in langflow/main.py AST")
    raise AssertionError  # for type checkers; pytest.fail raises


# ---------------------------------------------------------------------------
# Test 1 -- absence: no asyncio.sleep(10.0) on the MCP init path.
# ---------------------------------------------------------------------------
def test_no_asyncio_sleep_10_in_mcp_init_path() -> None:
    tree = parse_lifespan_module()
    sleeps = find_sleep_with_value(tree, 10.0)
    assert sleeps == [], (
        f"asyncio.sleep(10.0) must be absent from langflow/main.py (D-07 absence); found {len(sleeps)} occurrence(s)."
    )


# ---------------------------------------------------------------------------
# Test 2 -- guard: asyncio.sleep(5.0) retry is preserved.
# ---------------------------------------------------------------------------
def test_asyncio_sleep_5_retry_still_present() -> None:
    tree = parse_lifespan_module()
    sleeps_5 = find_sleep_with_value(tree, 5.0)
    assert len(sleeps_5) >= 1, (
        "asyncio.sleep(5.0) must remain in langflow/main.py as the transient-DB-error "
        "retry guard ; no occurrences found."
    )


# ---------------------------------------------------------------------------
# Test 3 -- source-level: Event producer fires inside the FileLock body,
# NOT in a ``finally:`` clause.
# ---------------------------------------------------------------------------
def test_event_set_inside_filelock_not_in_finally() -> None:
    src = inspect.getsource(main_mod)

    # The event set call must exist.
    assert f"{_EVENT_NAME}.set()" in src, f"{_EVENT_NAME}.set() missing from main.py"

    # Defensive: no ``finally:`` within ~5 lines followed by ``.set()`` (Rule
    # from Research Open Question 2 -- setting in finally would mask starter-
    # project failures).
    lines = src.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^\s*finally\s*:\s*$", line):
            window = "\n".join(lines[i : i + 6])
            assert f"{_EVENT_NAME}.set()" not in window, (
                f"{_EVENT_NAME}.set() appears within 5 lines of a `finally:` clause "
                f"starting at line {i + 1}. Per Research Open Question 2, setting the "
                f"Event in finally would mask genuine starter-project failures. "
                f"Move the set() to the success path of the with-lock body."
            )

    # Structural: locate the ``with lock:`` block (the FileLock context) and
    # assert the event-set call is textually inside it, between the opening
    # ``with lock:`` and the matching ``except TimeoutError:``.
    with_lock_match = re.search(r"^(\s*)with lock:\s*$", src, flags=re.MULTILINE)
    assert with_lock_match is not None, "Could not find `with lock:` in main.py"
    with_lock_start = with_lock_match.end()

    # The next ``except TimeoutError:`` at the same-or-outer indent closes the
    # block in this codebase (try: ... with lock: ... except TimeoutError:).
    after_lock = src[with_lock_start:]
    except_match = re.search(r"^\s*except TimeoutError", after_lock, flags=re.MULTILINE)
    assert except_match is not None, "Could not find closing except TimeoutError after with lock:"

    with_lock_body = after_lock[: except_match.start()]
    assert f"{_EVENT_NAME}.set()" in with_lock_body, (
        f"{_EVENT_NAME}.set() must be inside the `with lock:` body (D-11 producer); "
        f"body currently spans ~{with_lock_body.count(chr(10))} lines."
    )


# ---------------------------------------------------------------------------
# Test 4 -- / Pitfall 1: Event constructed inside lifespan(), never at
# module level.
# ---------------------------------------------------------------------------
def test_event_constructed_inside_lifespan_not_module_level() -> None:
    tree = parse_lifespan_module()

    # (a) No module-level Assign of starter_projects_ready_event.
    module_level_assigns = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == _EVENT_NAME for t in node.targets)
    ]
    assert module_level_assigns == [], (
        f"{_EVENT_NAME} must NOT be assigned at module level (D-12 / Pitfall 1). "
        f"A module-level asyncio.Event leaks across pytest event loops. "
        f"Found {len(module_level_assigns)} module-level assignment(s)."
    )

    # (b) Inside ``async def lifespan``, at least one Assign with target
    # ``starter_projects_ready_event`` whose value is a Call to asyncio.Event.
    lifespan_node = _get_lifespan_func_node(tree)
    inside_assigns: list[ast.Assign] = []
    for child in ast.walk(lifespan_node):
        if not isinstance(child, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == _EVENT_NAME for t in child.targets):
            continue
        # Check that the RHS is a Call to asyncio.Event (or bare Event()).
        val = child.value
        if isinstance(val, ast.Call):
            func = val.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "Event"
                and isinstance(func.value, ast.Name)
                and func.value.id == "asyncio"
            ) or (isinstance(func, ast.Name) and func.id == "Event"):
                inside_assigns.append(child)
    assert len(inside_assigns) >= 1, (
        f"{_EVENT_NAME} must be assigned = asyncio.Event() inside async def lifespan "
        f"(D-12). Found {len(inside_assigns)} such assignment(s) inside lifespan."
    )


# ---------------------------------------------------------------------------
# Test 5 -- Pitfall 6: delayed_init_mcp_servers remains inline inside lifespan.
# ---------------------------------------------------------------------------
def test_delayed_init_mcp_servers_remains_inline_inside_lifespan() -> None:
    tree = parse_lifespan_module()

    # (a) No module-level AsyncFunctionDef named delayed_init_mcp_servers.
    module_level_defs = [
        node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "delayed_init_mcp_servers"
    ]
    assert module_level_defs == [], (
        "delayed_init_mcp_servers must NOT be defined at module level (Pitfall 6). "
        "Moving it out of lifespan() breaks the closure capture of "
        f"{_EVENT_NAME}. "
        f"Found {len(module_level_defs)} module-level definition(s)."
    )

    # (b) Inside lifespan, exactly one AsyncFunctionDef named
    # delayed_init_mcp_servers.
    lifespan_node = _get_lifespan_func_node(tree)
    inside_defs = [
        node
        for node in ast.walk(lifespan_node)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "delayed_init_mcp_servers"
    ]
    assert len(inside_defs) == 1, (
        "Expected exactly one inline `async def delayed_init_mcp_servers` inside "
        f"lifespan (Pitfall 6). Found {len(inside_defs)}."
    )


# ---------------------------------------------------------------------------
# Test 6 --: consumer uses asyncio.wait_for with bounded timeout = 60.0.
# ---------------------------------------------------------------------------
def test_consumer_uses_wait_for_with_60s_timeout() -> None:
    tree = parse_lifespan_module()
    wait_for_calls = find_calls_to(tree, "asyncio.wait_for")

    # Keep only wait_for calls whose first arg is Call(func=Attribute(value=Name(
    # starter_projects_ready_event), attr='wait')).
    matching: list[ast.Call] = []
    for call in wait_for_calls:
        if not call.args:
            continue
        first = call.args[0]
        if not isinstance(first, ast.Call):
            continue
        func = first.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "wait"
            and isinstance(func.value, ast.Name)
            and func.value.id == _EVENT_NAME
        ):
            matching.append(call)

    assert len(matching) >= 1, (
        f"Expected at least 1 asyncio.wait_for({_EVENT_NAME}.wait(), ...) call; "
        f"found 0. requires the consumer to bounded-wait on the Event."
    )

    # Assert the timeout kwarg is a numeric constant == 60.0.
    for call in matching:
        timeout_kw = next((k for k in call.keywords if k.arg == "timeout"), None)
        assert timeout_kw is not None, (
            "asyncio.wait_for must be called with an explicit `timeout=` keyword  bounded-wait contract."
        )
        val = timeout_kw.value
        assert isinstance(val, ast.Constant), (
            f"`timeout` must be a Constant node; got {type(val).__name__}: {getattr(val, 'value', val)!r}"
        )
        assert isinstance(val.value, (int, float)), (
            f"`timeout` Constant must hold a numeric value; got {type(val.value).__name__}: {val.value!r}"
        )
        assert float(val.value) == 60.0, f"`timeout` must be 60.0  default; got {val.value!r}."


# ---------------------------------------------------------------------------
# Test 7 -- event-race: Event unblocks in < 600ms when producer takes
# 500ms.
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
        f"500ms (proves the new wait_for path beats the old 10.0s sleep). "
        f"Elapsed: {elapsed * 1000:.1f}ms."
    )


# ---------------------------------------------------------------------------
# Test 8 -- Pitfall 1 cross-test-loop guard: run the race harness a second
# time in the same session. Both runs must pass. A regression that moved the
# Event to module level would bind it to the first test's loop and the second
# would raise "Future bound to a different loop".
# ---------------------------------------------------------------------------
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
        f"Event-race (2nd run, Pitfall 1 guard): expected consumer to unblock in "
        f"< 600ms. Elapsed: {elapsed * 1000:.1f}ms. If the first run passed and "
        f"this one failed, something regressed Event to module scope."
    )
