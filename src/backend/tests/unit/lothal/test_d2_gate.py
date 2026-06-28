"""The shared D2 compile-validation gate (Story D.3), tested at its own seam.

`d2_gate.compile_validated_d2` turns one model round-trip into compile-validated
D2 for both Architecture-stage engines (generation iterates it per diagram,
refinement runs it on the edited diagram). It used to be exercised only through
the old single-diagram engines; Epic E.6 retired those, so the gate is pinned
here directly — call the gate, control its two seams (`call_llm`, `compile_d2`),
and assert the gate's behaviour:

- a stray markdown fence is stripped and an empty reply is a bad round-trip
  (`LLMConnectionError` → 502), rejected before the compiler is even called;
- D2 that fails to compile triggers exactly one corrective retry carrying the
  reply and the compiler's own error; a second failure raises; an unavailable
  compiler degrades to storing the source unvalidated (no retry).

The compiler subprocess itself is covered in `test_d2_compile.py`; here
`compile_d2` is stubbed so the gate logic is deterministic without the binary.
"""

import pytest
from langflow.lothal.d2_compile import D2CompileResult, D2CompilerUnavailableError
from langflow.lothal.engines import d2_gate
from langflow.lothal.engines.d2_gate import compile_validated_d2, count_messages, extract_d2
from langflow.lothal.llm import LLMConnectionError

D2_SOURCE = """\
shape: sequence_diagram
user: User
api: API
db: Database

user -> api: submit form
api -> db: insert row
db -> api: ok
api -> user: 200 OK"""


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace the gate's `call_llm` with a stub returning queued replies and capturing calls."""
    captured = {"calls": [], "replies": []}

    async def _call_llm(messages, **kwargs):
        captured["calls"].append({"messages": messages, "kwargs": kwargs})
        return captured["replies"][len(captured["calls"]) - 1]

    monkeypatch.setattr(d2_gate, "call_llm", _call_llm)
    return captured


@pytest.fixture
def fake_compile(monkeypatch):
    """Replace the gate's `compile_d2` with a stub returning queued results and capturing calls.

    Queue `results` with `D2CompileResult`s (or a `D2CompilerUnavailableError`
    instance to simulate a missing binary). Any call past the queue's end returns
    a successful compile, so happy-path tests need not configure it.
    """
    captured = {"calls": [], "results": []}

    async def _compile_d2(src):
        captured["calls"].append(src)
        results = captured["results"]
        idx = len(captured["calls"]) - 1
        outcome = results[idx] if idx < len(results) else D2CompileResult(ok=True)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(d2_gate, "compile_d2", _compile_d2)
    return captured


# --- happy path --------------------------------------------------------------


async def test_valid_reply_returns_extracted_d2(fake_llm, fake_compile):
    fake_llm["replies"] = [D2_SOURCE]

    result = await compile_validated_d2([{"role": "user", "content": "build it"}])

    assert result == D2_SOURCE
    assert len(fake_llm["calls"]) == 1  # compiled first time → no retry
    # The gate compiles the extracted D2, not the raw reply.
    assert fake_compile["calls"] == [D2_SOURCE]


async def test_reply_wrapped_in_code_fence_is_unwrapped(fake_llm, fake_compile):
    fake_llm["replies"] = [f"```d2\n{D2_SOURCE}\n```"]

    result = await compile_validated_d2([{"role": "user", "content": "build it"}])

    # The fence is stripped before storing and before the compile gate sees it.
    assert result == D2_SOURCE
    assert fake_compile["calls"] == [D2_SOURCE]
    assert len(fake_llm["calls"]) == 1


# --- empty round-trip --------------------------------------------------------


async def test_empty_reply_raises_connection_error(fake_llm, fake_compile):
    fake_llm["replies"] = ["   \n  "]

    with pytest.raises(LLMConnectionError, match="empty diagram"):
        await compile_validated_d2([{"role": "user", "content": "build it"}])

    assert len(fake_llm["calls"]) == 1
    assert fake_compile["calls"] == []  # rejected before the compile gate


# --- compile-validation gate -------------------------------------------------


async def test_uncompilable_d2_retries_once_then_succeeds(fake_llm, fake_compile):
    bad_d2 = "user -> : broken"
    fake_llm["replies"] = [bad_d2, D2_SOURCE]
    fake_compile["results"] = [
        D2CompileResult(ok=False, error="1:1: connection missing destination"),
        D2CompileResult(ok=True),
    ]

    result = await compile_validated_d2([{"role": "user", "content": "build it"}])

    # The second, compilable attempt is what gets returned.
    assert result == D2_SOURCE
    assert len(fake_llm["calls"]) == 2
    assert fake_compile["calls"] == [bad_d2, D2_SOURCE]

    # The retry resends the conversation plus the bad reply and the compiler error
    # as a correction, so attempt two is a fix rather than a blind redo.
    retry_messages = fake_llm["calls"][1]["messages"]
    assert {"role": "assistant", "content": bad_d2} in retry_messages
    correction = retry_messages[-1]
    assert correction["role"] == "user"
    assert "connection missing destination" in correction["content"]


async def test_uncompilable_twice_raises_connection_error(fake_llm, fake_compile):
    fake_llm["replies"] = ["first bad", "second bad"]
    fake_compile["results"] = [
        D2CompileResult(ok=False, error="1:1: connection missing destination"),
        D2CompileResult(ok=False, error="2:1: missing value after colon"),
    ]

    with pytest.raises(LLMConnectionError, match="failed to compile twice"):
        await compile_validated_d2([{"role": "user", "content": "build it"}])

    # Exactly one corrective retry; the final (second) compiler error is surfaced.
    assert len(fake_llm["calls"]) == 2
    assert len(fake_compile["calls"]) == 2


async def test_compiler_unavailable_skips_gate_and_stores(fake_llm, fake_compile):
    # A missing binary is an environment fault, not a bad diagram: store the source
    # unvalidated rather than fail the turn or wrongly trigger a retry.
    fake_llm["replies"] = [D2_SOURCE]
    fake_compile["results"] = [D2CompilerUnavailableError("no d2 on PATH")]

    result = await compile_validated_d2([{"role": "user", "content": "build it"}])

    assert result == D2_SOURCE
    assert len(fake_llm["calls"]) == 1  # no retry — the gate was skipped, not failed


# --- pure helpers ------------------------------------------------------------


def test_extract_d2_strips_fence_and_rejects_empty():
    assert extract_d2(f"```d2\n{D2_SOURCE}\n```") == D2_SOURCE
    with pytest.raises(LLMConnectionError, match="empty diagram"):
        extract_d2("   \n  ")


def test_count_messages_counts_connection_lines_only():
    # Four arrows in D2_SOURCE; declarations and the blank line don't count.
    assert count_messages(D2_SOURCE) == 4
    # A trailing `#` comment is stripped before counting, so a commented-out arrow
    # and a comment that merely mentions `->` are not counted.
    assert count_messages("a -> b: real  # but a -> b in the comment is ignored") == 1
    assert count_messages("# a -> b: commented out\nx: just a node") == 0
    # Every D2 connection operator variant counts.
    assert count_messages("a -> b\nc <- d\ne <-> f\ng -- h\ni --> j") == 5
