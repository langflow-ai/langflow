#!/usr/bin/env python3
"""CI guard: a log call must not render the caught exception into its message.

``logger.error(f"failed: {e}")`` puts the exception text in the *message*, and the message
is the one field that crosses the export boundary.

``_OTEL_LOG_SKIP_KEYS`` in ``lfx/log/logger.py`` drops ``exc_info`` on the way out and
derives ``error.type`` and ``error.chain`` from it instead. So an exception attached as
``exc_info`` stays local, while the same exception interpolated into the message is
exported verbatim -- and provider errors routinely embed the prompt, the completion, or
the API key that was rejected.

It also costs the triage signal. ``error()`` sets no ``exc_info`` of its own, so a record
written this way carries no ``error.type`` at all: the call site trades the one field an
operator can act on for the one they must not receive.

To be clear about what this does *not* buy: ``exc_info=e`` still renders the full
traceback, message included, to stdout and the log file, because ``format_exc_info`` and
``ConsoleRenderer`` are in the console chain. The console is the developer's and the APM
is the operator's; this guard is about the second one.

Write ``logger.error("failed", exc_info=e)``, or interpolate the type alone with
``type(e).__name__``. Both are accepted here.

Why an AST check and not ruff's flake8-logging-format (G004), measured against the nine
statements the logs-boundary work fixed by hand:

* G004 catches five of the nine and misses four. It does not know structlog's ``aerror``
  and ``aexception``, which is exactly where those four lived.
* It cannot see the lazy form ``logger.error("boom: %s", e)`` -- which is what G004's own
  fix message tells you to write, and which still renders the exception into the body.
* It fires on ``logger.error(f"failed for flow {flow_id}")``, which is not this problem.
* ``logger-objects`` is matched per import path, and this repo has at least five
  (``lfx.log.logger``, ``lfx.log``, ``lfx.logging``, ``langflow.logging.logger``,
  ``langflow.logging``), so a config-only approach silently misses the aliases.

This check keys on the name bound by ``except ... as NAME`` instead of on formatting
style, so a flow id in an f-string is not a finding and a bare ``aerror`` is.

Known gap: only the log call's own arguments are inspected. Binding the text first::

    msg = f"failed: {e}"
    logger.error(msg)

passes. Catching that needs dataflow within the handler, which is a different and much
larger check. The direct form is what the fixed call sites looked like and what a new one
is most likely to look like, so this is a deliberate stopping point rather than an
oversight.

Usage::

    python scripts/lint/check_logged_exception_text.py           # scan default roots
    python scripts/lint/check_logged_exception_text.py FILE...   # check specific files
    python scripts/lint/check_logged_exception_text.py --root path/to/pkg

Exit codes:
    0 -- no exception text rendered into a log message
    1 -- one or more findings (or a file failed to parse)
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# The flow execution path. Scoped rather than repo-wide on purpose: this is where a leaked
# exception message carries flow content, and a bounded set can be held at zero without a
# baseline file. Widen it as other paths are cleaned, never with a baseline.
DEFAULT_ROOTS = (
    "src/lfx/src/lfx/base/agents",
    "src/lfx/src/lfx/graph",
    "src/lfx/src/lfx/components/models_and_agents",
)

# structlog's async variants are the reason ruff's rule is not enough on its own.
LOG_METHODS = frozenset(
    {
        "debug",
        "info",
        "warning",
        "warn",
        "error",
        "exception",
        "critical",
        "fatal",
        "adebug",
        "ainfo",
        "awarning",
        "awarn",
        "aerror",
        "aexception",
        "acritical",
        "afatal",
    }
)

# The one keyword that is a traceback channel rather than a rendered field. Deliberately
# just this one: ``error=str(e)`` and ``exception=f"{e}"`` read as exception-shaped, but a
# structured processor renders their values into the record like any other field, so
# allowlisting them by name would wave through the exact leak this guard exists to catch.
EXCEPTION_KEYWORDS = frozenset({"exc_info"})


def _is_log_call(node: ast.Call) -> bool:
    """True for ``<anything>.<log method>(...)``.

    Matched on the attribute name rather than on the receiver, because the receiver is a
    module-level ``logger`` reached through five different import paths, plus ``self.log``
    and bound locals. Keying on the method name over-matches slightly (a domain object
    with its own ``.error()``), which is the safe direction: a false positive is one
    review comment, a false negative is a leak.
    """
    return isinstance(node.func, ast.Attribute) and node.func.attr in LOG_METHODS


def _is_type_name_of(node: ast.expr, target: str) -> bool:
    """True for ``type(target).__name__``, the sanctioned way to name the failure."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "__name__"
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "type"
        and len(node.value.args) == 1
        and isinstance(node.value.args[0], ast.Name)
        and node.value.args[0].id == target
    )


def _references(node: ast.expr, target: str) -> bool:
    """True if ``target`` is read anywhere in this expression, ignoring the type-only form.

    ``type(e).__name__`` is pruned before the walk rather than filtered after it, so
    ``f"{type(e).__name__}: {e}"`` still reports: the second slot is a real finding and a
    post-hoc filter on the whole expression would swallow it.
    """
    # Every Name node that belongs to a type(target).__name__ subexpression. Collected up
    # front so the scan below is a membership test rather than a nested walk per candidate.
    type_only_names = {
        name
        for sub in ast.walk(node)
        if _is_type_name_of(sub, target)
        for name in ast.walk(sub)
        if isinstance(name, ast.Name)
    }
    return any(
        isinstance(child, ast.Name) and child.id == target and child not in type_only_names for child in ast.walk(node)
    )


def _findings_in_call(call: ast.Call, target: str) -> str | None:
    """Return a short reason if this log call renders ``target``, else None."""
    for arg in call.args:
        if _references(arg, target):
            if isinstance(arg, ast.JoinedStr):
                return "f-string interpolates the exception"
            if isinstance(arg, ast.Name):
                # The lazy form: logger.error("boom: %s", e). Still rendered into the body.
                return "exception passed as a message argument"
            return "exception rendered into the message"
    for keyword in call.keywords:
        if keyword.arg in EXCEPTION_KEYWORDS or keyword.arg is None:
            # exc_info=e is the fix, not the bug. **kwargs is opaque; assume good faith.
            continue
        if keyword.value is not None and _references(keyword.value, target):
            return f"exception rendered into {keyword.arg}="
    return None


def _walk_live_scope(node: ast.AST, target: str):
    """Yield every node under ``node`` where the enclosing binding of ``target`` is live.

    Descent stops at a nested ``except ... as <target>``, because that handler rebinds the
    name and owns its own body. ``ast.walk`` cannot express this: it flattens the whole
    subtree, so skipping the nested handler node still visits its children and the same log
    call gets reported twice, once per binding.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ExceptHandler) and child.name == target:
            continue
        yield child
        yield from _walk_live_scope(child, target)


def _check_file(path: Path) -> list[tuple[str, int, str, str]]:
    rel = str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:  # A file that will not parse cannot be cleared.
        return [(rel, exc.lineno or 0, "unparseable", str(exc.msg))]

    lines = source.splitlines()
    findings: list[tuple[str, int, str, str]] = []
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler) or not handler.name:
            continue
        target = handler.name
        for node in _walk_live_scope(handler, target):
            if not isinstance(node, ast.Call) or not _is_log_call(node):
                continue
            reason = _findings_in_call(node, target)
            if reason:
                snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                findings.append((rel, node.lineno, reason, snippet[:120]))
    return findings


def _iter_py_files(roots: list[Path]):
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            yield root
        elif root.is_dir():
            yield from sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="specific files to check")
    parser.add_argument("--root", action="append", help="directory to scan (repeatable)")
    args = parser.parse_args()

    if args.files:
        targets = [Path(f) for f in args.files if f.endswith(".py")]
    else:
        roots = [Path(r) if Path(r).is_absolute() else REPO_ROOT / r for r in (args.root or DEFAULT_ROOTS)]
        targets = list(_iter_py_files(roots))

    findings: list[tuple[str, int, str, str]] = []
    for path in targets:
        findings.extend(_check_file(path))

    if not findings:
        return 0

    print("ERROR: log call(s) render a caught exception into the message.\n")
    print("       The text reaches stdout and the log file regardless of OTLP settings, and")
    print("       provider errors embed prompts, completions and rejected keys. error() also")
    print("       sets no exc_info, so the exported record loses error.type -- the only triage")
    print("       signal left once log bodies are withheld.\n")
    for rel, lineno, reason, snippet in sorted(findings):
        print(f"  {rel}:{lineno}  [{reason}]")
        if snippet:
            print(f"      {snippet}")
    print(
        '\nFix: logger.error("what failed", exc_info=exc) keeps the traceback as structured\n'
        'data. To name the failure inline, interpolate the type only: f"...{type(exc).__name__}".\n'
        "Both forms are accepted by this check."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
