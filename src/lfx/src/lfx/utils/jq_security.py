"""Reject jq programs that can reach server state outside their input data.

The Data Operations / Parse JSON components evaluate a user-supplied jq program
through the in-process libjq binding. jq's ``$ENV`` / ``env`` builtins expose the
entire server process environment — including ``LANGFLOW_SECRET_KEY`` (the Fernet
master key encrypting every tenant's stored credentials), the database URL, and
deployment-level provider API keys — as ordinary program output. These are plain
data components, so they are not gated by ``allow_custom_components`` /
``block_code_interpreter_components`` and run even on hardened deployments.

Because libjq evaluates in-process, the environment cannot be scrubbed per
evaluation; instead the program is validated before ``jq.compile`` and any
reference to a dangerous builtin is rejected (fail closed). This extends the
existing "server secrets are never user-reachable" invariant (see
``env_var_security.py`` and ``file_path_security.py``) to the jq path.
"""

from __future__ import annotations

import re

# jq builtins that must never be reachable from a user-supplied program:
#  - env: full process-environment disclosure (the crown-jewel leak).
#  - input / inputs: read values outside the component's declared input data.
#
# ``getpath`` is deliberately NOT here. It indexes the value it is applied to and
# reads nothing else, so ``getpath(["a", "b"])`` is an ordinary field selection --
# the equivalent of ``.a.b`` with a computed path. The only way to point it at
# server state is to feed it ``env``/``$ENV`` first, and both of those are
# rejected in their own right. Blocking it only broke working flows.
_DANGEROUS_BARE_BUILTINS = ("env", "input", "inputs")

# A builtin is only dangerous when invoked as a bare jq function, i.e. not
# preceded by "." (field access on the input data, e.g. ".env"), "$" (a
# user-defined variable, e.g. "$inputs"), or a word character (a longer
# identifier such as "environment" or "my_input").
_BARE_BUILTIN_RE = re.compile(r"(?<![.$\w])(" + "|".join(_DANGEROUS_BARE_BUILTINS) + r")\b")

# jq variables with fixed dangerous semantics: $ENV exposes the process
# environment, $__loc__ discloses source location information. Unlike builtins
# they are spelled with a leading "$" and cannot be shadowed or reached via
# field access. jq identifiers are case-sensitive, so "$env" stays a normal
# user variable.
_DANGEROUS_VARIABLE_RE = re.compile(r"\$(ENV|__loc__)\b")


def _mask_strings_and_comments(program: str) -> str:
    r"""Blank string-literal contents and comments, keeping interpolated code visible.

    Returns a same-length string in which characters that jq would treat as
    string-literal text or comment text are replaced with spaces, so the
    identifier scan neither false-positives on prose like ``"environment"`` nor
    on quoted field names like ``."env"``. ``\( ... )`` string interpolations
    are live jq code and are left visible — masking them would be a bypass.
    Comments (``#`` to end-of-line) are not executable, so they are masked.
    """
    out = list(program)
    n = len(program)
    i = 0
    in_string = False
    stack: list[int] = []  # paren depth of each open interpolation's code
    while i < n:
        ch = program[i]
        if in_string:
            if ch == "\\" and i + 1 < n:
                if program[i + 1] == "(":
                    # Interpolation: mask the backslash, keep "(", scan as code.
                    out[i] = " "
                    in_string = False
                    stack.append(1)
                else:
                    # Escape sequence: mask both characters.
                    out[i] = out[i + 1] = " "
                i += 2
                continue
            if ch == '"':
                in_string = False
                i += 1
                continue
            out[i] = " "
            i += 1
            continue
        # Code mode.
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "#":
            while i < n and program[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if stack:  # inside an interpolation; find the paren that ends it
            if ch == "(":
                stack[-1] += 1
            elif ch == ")":
                stack[-1] -= 1
                if stack[-1] == 0:
                    stack.pop()
                    in_string = True
        i += 1
    return "".join(out)


_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _mask_object_keys(scanned: str) -> str:
    r"""Blank bare identifiers sitting in jq object-key position.

    Takes the output of :func:`_mask_strings_and_comments` and returns a
    same-length string with object *keys* blanked out, so the builtin scan sees
    only identifiers that are actually function references.

    A bare identifier in key position never invokes a builtin. jq object keys are
    identifiers, keywords, string literals, ``$var`` or ``(expr)``; a bare one is
    a literal key, and the ``{k}`` shorthand expands to ``{k: .k}`` -- field
    access on the input. So ``{env: .a}``, ``{input: .a}`` and ``{env}`` are all
    ordinary transformations, and ``. as {env: $e}`` is an ordinary destructuring
    pattern.

    ``$``-prefixed keys are deliberately left visible: ``{$ENV}`` expands to
    ``{"ENV": $ENV}`` and really does disclose the environment, so it must still
    reach :data:`_DANGEROUS_VARIABLE_RE`.

    Quote characters are skipped rather than tracked. String *contents* are
    already blanked by the previous pass, and the interpolated code that
    survives inside them is paren-balanced by construction, so the container
    stack stays aligned while ``\(env)`` remains visible under a ``(`` frame
    (never key position) and is still rejected.
    """
    out = list(scanned)
    # Open containers, innermost last. Each entry is [opening char, expecting_key].
    # ``expecting_key`` only means anything for "{" frames: it is True at "{" and
    # after a ",", and False after the ":" that starts the value.
    stack: list[list] = []
    i, n = 0, len(scanned)
    while i < n:
        ch = scanned[i]
        if ch == "{":
            stack.append(["{", True])
        elif ch in "([":
            stack.append([ch, False])
        elif ch in ")]}":
            if stack:
                stack.pop()
        elif stack and stack[-1][0] == "{" and ch in ":,":
            stack[-1][1] = ch == ","
        else:
            match = _IDENTIFIER_RE.match(scanned, i)
            if match:
                in_key_position = bool(stack) and stack[-1][0] == "{" and stack[-1][1]
                # ".env" / "$env" are already exempt downstream; leave them be.
                qualified = i > 0 and scanned[i - 1] in ".$"
                if in_key_position and not qualified:
                    out[match.start() : match.end()] = " " * (match.end() - match.start())
                i = match.end()
                continue
        i += 1
    return "".join(out)


def validate_jq_program(program: str) -> None:
    """Reject a jq program that references dangerous builtins or variables.

    Args:
        program: The jq program about to be compiled.

    Raises:
        ValueError: If the program is empty/non-string, or references ``$ENV``,
            ``env``, ``$__loc__``, ``input`` or ``inputs`` as a jq
            builtin/variable.
    """
    if not program or not isinstance(program, str):
        msg = "A jq program is required and must be a string."
        raise ValueError(msg)

    scanned = _mask_object_keys(_mask_strings_and_comments(program))

    match = _DANGEROUS_VARIABLE_RE.search(scanned)
    if match:
        msg = (
            f"The jq variable '{match.group(0)}' is not allowed: it exposes server state "
            "outside the component's input data."
        )
        raise ValueError(msg)

    match = _BARE_BUILTIN_RE.search(scanned)
    if match:
        msg = f"The jq builtin '{match.group(1)}' is not allowed: it reads state outside the component's input data."
        raise ValueError(msg)
