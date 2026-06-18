"""Compile and render D2 source via the canonical `d2` binary (Epic D.3 / D.6).

Epic D made D2 the stored diagram artifact (D.1/D.2). The backend is the single
D2 authority: it both **validates** that generated D2 compiles (the D.3 gate, so
we never persist source the canvas can't show) and **renders** it to SVG for the
`/diagram` read (D.6), so the frontend just displays the SVG and ships no D2
compiler of its own.

We shell out to the `d2` Go binary (installed in the backend image): `d2 - -`
reads the source on stdin and writes the rendered SVG to stdout. Return code 0
means it compiled; non-zero means it didn't, and the binary's stderr is the
compiler complaint — fed back to the model on its one corrective retry
(generation's D.3 loop), or simply meaning "nothing to render" on a read.

Two public functions over one runner:

- `compile_d2(src)` — validation only; discards the SVG, returns ok/error.
- `render_d2(src)` — returns the rendered SVG (or the compiler error).

Pure of DB and LLM: just a subprocess. Both resolve to a result for a reachable
compiler; a *missing* binary is a distinct operational fault
(`D2CompilerUnavailableError`) the caller decides how to degrade, rather than a
compile failure we'd wrongly blame on the model (generation) or surface as a
broken diagram (read).
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass

# The d2 subcommand-less form compiles one input to one output. `-` for both ends
# reads source from stdin and writes the rendered SVG to stdout, so no temp files
# are touched and concurrent calls can't collide on a path.
_D2_BINARY = "d2"
_D2_ARGS = ("-", "-")

# A focused sequence diagram compiles in milliseconds; this cap only exists so a
# pathological process can never hang a request. A timeout is treated as the
# compiler being unavailable (an operational fault), not a bad diagram.
_D2_TIMEOUT_SECONDS = 15.0


class D2CompilerUnavailableError(RuntimeError):
    """The `d2` binary is not installed / not on PATH (or it timed out).

    An environment fault, not a bad diagram: the source was never judged. Distinct
    from a compile failure so callers don't mistake "couldn't check" for "invalid"
    and wrongly blame the model.
    """


@dataclass(frozen=True)
class D2CompileResult:
    """Outcome of one `compile_d2` call. `error` is set iff `ok` is False."""

    ok: bool
    error: str | None = None


@dataclass(frozen=True)
class D2RenderResult:
    """Outcome of one `render_d2` call. Exactly one of `svg`/`error` is set.

    `ok` is the rendered-successfully predicate, so callers can branch on it
    without inspecting which field is populated.
    """

    svg: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.svg is not None


def _clean_compiler_error(stderr: str) -> str:
    """Tidy d2's stderr into a compact message worth feeding back to the model.

    d2 prefixes each line with ``err: `` and the first line with
    ``failed to compile -: ``, and uses ``-`` as the stdin "filename" in its
    ``-:line:col:`` position refs. We drop that boilerplate but keep the
    ``line:col: message`` detail, which is exactly what tells the model where to
    fix the source.
    """
    lines: list[str] = []
    for raw in stderr.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = line.removeprefix("err: ").removeprefix("failed to compile -: ").removeprefix("-:")
        if line:
            lines.append(line)
    cleaned = "\n".join(lines).strip()
    return cleaned or stderr.strip() or "D2 source failed to compile."


async def _run_d2(src: str, *, capture_svg: bool) -> tuple[int, bytes, str]:
    """Run `d2 - -` on `src`, returning `(returncode, stdout, stderr)`.

    `stdout` (the rendered SVG) is captured only when `capture_svg` is set;
    otherwise it is discarded so a validation call doesn't buffer markup it will
    never read. Raises `D2CompilerUnavailableError` if the binary is missing or
    does not finish within the timeout — an environment fault, not a verdict.
    """
    binary = shutil.which(_D2_BINARY)
    if binary is None:
        msg = "The `d2` compiler binary was not found on PATH."
        raise D2CompilerUnavailableError(msg)

    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            *_D2_ARGS,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE if capture_svg else asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        # `which` found the binary, but launch can still fail (it vanished, lost
        # the execute bit, fork limits, …). That's an environment fault, not a
        # verdict on the source — keep the unavailable-compiler contract.
        msg = f"Could not launch the `d2` compiler ({binary})."
        raise D2CompilerUnavailableError(msg) from exc
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(src.encode()), timeout=_D2_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        msg = f"The `d2` compiler did not finish within {_D2_TIMEOUT_SECONDS:.0f}s."
        raise D2CompilerUnavailableError(msg) from exc

    return proc.returncode or 0, stdout or b"", stderr.decode(errors="replace")


async def compile_d2(src: str) -> D2CompileResult:
    """Compile-check `src`, returning whether it compiles and the error if not.

    Feeds `src` to the `d2` binary and discards the rendered SVG — only the exit
    code and any error text matter here. Always resolves for a reachable compiler
    (a failure is ``D2CompileResult(ok=False, error=...)``, never an exception),
    so the generation engine can fold the error into its retry prompt. Raises
    `D2CompilerUnavailableError` if the binary is missing.
    """
    returncode, _, stderr = await _run_d2(src, capture_svg=False)
    if returncode == 0:
        return D2CompileResult(ok=True)
    return D2CompileResult(ok=False, error=_clean_compiler_error(stderr))


async def render_d2(src: str) -> D2RenderResult:
    """Render `src` to an SVG string, returning the SVG or the compiler error.

    The server-side render path for `/diagram` (D.6): the stored D2 is rendered
    here and the SVG handed to the frontend, which no longer compiles D2 itself.
    Always resolves for a reachable compiler (a failure is
    ``D2RenderResult(error=...)``, never an exception). Raises
    `D2CompilerUnavailableError` if the binary is missing.
    """
    returncode, stdout, stderr = await _run_d2(src, capture_svg=True)
    if returncode == 0:
        return D2RenderResult(svg=stdout.decode(errors="replace"))
    return D2RenderResult(error=_clean_compiler_error(stderr))
