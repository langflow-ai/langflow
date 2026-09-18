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
#  - getpath: retained as defense-in-depth per the remediation guidance; it has
#    no legitimate use in the simple field selections these components are for.
_DANGEROUS_BARE_BUILTINS = ("env", "input", "inputs", "getpath")

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
    depth = 0  # paren depth while scanning an interpolation's code
    stack: list[str] = []  # one "string" frame per open interpolation
    while i < n:
        ch = program[i]
        if in_string:
            if ch == "\\" and i + 1 < n:
                if program[i + 1] == "(":
                    # Interpolation: mask the backslash, keep "(", scan as code.
                    out[i] = " "
                    in_string = False
                    depth = 1
                    stack.append("string")
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
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    stack.pop()
                    in_string = True
        i += 1
    return "".join(out)


def validate_jq_program(program: str) -> None:
    """Reject a jq program that references dangerous builtins or variables.

    Args:
        program: The jq program about to be compiled.

    Raises:
        ValueError: If the program is empty/non-string, or references ``$ENV``,
            ``env``, ``$__loc__``, ``input``, ``inputs``, or ``getpath`` as a
            jq builtin/variable.
    """
    if not program or not isinstance(program, str):
        msg = "A jq program is required and must be a string."
        raise ValueError(msg)

    scanned = _mask_strings_and_comments(program)

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
