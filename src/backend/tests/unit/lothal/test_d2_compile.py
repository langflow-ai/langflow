"""The D2 compile-validation helper (Epic D.3).

`compile_d2` shells out to the `d2` binary to answer "does this D2 compile?" for
the ARCHITECTURE diagram gate. Two layers are tested here:

- The pure error-cleaning and the missing-binary contract, which need no binary
  and run everywhere.
- The real compiler round-trip (valid → ok, invalid → error), which needs the
  `d2` binary and is skipped when it isn't installed (the backend images install
  it; a bare host may not). This keeps CI honest where d2 exists without making
  the suite depend on it.
"""

import asyncio
import shutil

import pytest
from langflow.lothal import d2_compile
from langflow.lothal.d2_compile import (
    D2CompilerUnavailableError,
    _clean_compiler_error,
    compile_d2,
    render_d2,
)

VALID_D2 = """\
shape: sequence_diagram
user: User
api: API
user -> api: submit
api -> user: 200 OK"""

# Missing destination after the arrow — d2 rejects this at compile time.
INVALID_D2 = "user -> : broken"

d2_available = shutil.which("d2") is not None
requires_d2 = pytest.mark.skipif(not d2_available, reason="the `d2` binary is not installed")


# --- error cleaning (no binary) ----------------------------------------------


def test_clean_compiler_error_strips_d2_boilerplate():
    raw = "err: failed to compile -: -:1:1: connection missing destination\nerr: -:2:7: missing value after colon\n"
    cleaned = _clean_compiler_error(raw)
    assert cleaned == "1:1: connection missing destination\n2:7: missing value after colon"
    # The noise the model doesn't need is gone.
    assert "failed to compile" not in cleaned
    assert "err:" not in cleaned


def test_clean_compiler_error_falls_back_when_nothing_left():
    # Defensive: never return an empty string the retry prompt would dangle on.
    assert _clean_compiler_error("   \n  ") == "D2 source failed to compile."


# --- missing binary (no binary) ----------------------------------------------


async def test_missing_binary_raises_unavailable(monkeypatch):
    monkeypatch.setattr(d2_compile.shutil, "which", lambda _: None)
    with pytest.raises(D2CompilerUnavailableError):
        await compile_d2(VALID_D2)


async def test_render_missing_binary_raises_unavailable(monkeypatch):
    monkeypatch.setattr(d2_compile.shutil, "which", lambda _: None)
    with pytest.raises(D2CompilerUnavailableError):
        await render_d2(VALID_D2)


async def test_launch_failure_after_which_raises_unavailable(monkeypatch):
    """A binary that `which` finds but that fails to launch is still "unavailable".

    `shutil.which` can succeed yet the exec fail (the file vanished, lost its
    execute bit, fork limits, …). Those `OSError`s (incl. `FileNotFoundError`/
    `PermissionError`) must be normalised to `D2CompilerUnavailableError`, not
    bubble up as a raw 500.
    """
    monkeypatch.setattr(d2_compile.shutil, "which", lambda _: "/usr/local/bin/d2")

    async def _boom(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(d2_compile.asyncio, "create_subprocess_exec", _boom)

    with pytest.raises(D2CompilerUnavailableError, match="launch"):
        await compile_d2(VALID_D2)


# --- timeout (no binary; fake hanging process) -------------------------------


async def test_compile_timeout_kills_process_and_raises_unavailable(monkeypatch):
    """A compiler that never finishes is killed and reported as unavailable.

    Exercises the real `asyncio.wait_for` timeout path with a tiny timeout and a
    fake process whose `communicate` hangs: the process must be killed and a
    `D2CompilerUnavailableError` raised (an environment fault, not a verdict on
    the source — so the engine skips the gate rather than blaming the model).
    """
    monkeypatch.setattr(d2_compile, "_D2_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(d2_compile.shutil, "which", lambda _: "/usr/local/bin/d2")

    killed = {"called": False}

    class _HangingProc:
        returncode = None

        async def communicate(self, _input):
            await asyncio.sleep(10)  # never returns within the 0.05s timeout

        def kill(self):
            killed["called"] = True

        async def wait(self):
            return -9

    async def _fake_exec(*_args, **_kwargs):
        return _HangingProc()

    monkeypatch.setattr(d2_compile.asyncio, "create_subprocess_exec", _fake_exec)

    with pytest.raises(D2CompilerUnavailableError, match="did not finish"):
        await compile_d2(VALID_D2)
    assert killed["called"] is True  # the runaway process was reaped, not leaked


# --- real compiler round-trip (requires d2) ----------------------------------


@requires_d2
async def test_valid_d2_compiles():
    result = await compile_d2(VALID_D2)
    assert result.ok is True
    assert result.error is None


@requires_d2
async def test_invalid_d2_returns_compiler_error():
    result = await compile_d2(INVALID_D2)
    assert result.ok is False
    assert result.error
    # The complaint is the real compiler's, fed back to the model verbatim on retry.
    assert "connection missing destination" in result.error
    # Boilerplate cleaned: no `err:` prefix leaks into the retry prompt.
    assert not result.error.startswith("err:")


@requires_d2
async def test_render_valid_d2_returns_svg():
    result = await render_d2(VALID_D2)
    assert result.ok is True
    assert result.error is None
    # Real SVG markup — what the frontend now displays instead of compiling itself.
    assert result.svg
    assert "<svg" in result.svg
    # The base64 element-id classes click-to-anchor (D.7) reads are present: the
    # server-rendered SVG carries the same id scheme as the old browser render.
    assert "class=" in result.svg


@requires_d2
async def test_render_invalid_d2_returns_error_not_svg():
    result = await render_d2(INVALID_D2)
    assert result.ok is False
    assert result.svg is None
    assert result.error
    assert "connection missing destination" in result.error
