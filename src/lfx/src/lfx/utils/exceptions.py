def format_syntax_error_message(exc: SyntaxError) -> str:
    """Format a SyntaxError message for returning to the frontend."""
    if exc.text is None:
        return f"Syntax error in code. Error on line {exc.lineno}"
    return f"Syntax error in code. Error on line {exc.lineno}: {exc.text.strip()}"


def get_causing_exception(exc: BaseException) -> BaseException:
    """Get the causing exception from an exception.

    Walks the ``__cause__`` chain to the root cause, with one stop condition: a
    bundle-shim ``ModuleNotFoundError`` carries a curated "components moved to
    ..." message and is itself raised ``from`` the raw ``No module named '<x>'``
    import error it wraps. Stop at that curated error so its actionable message
    wins instead of unwrapping past it to the bare cause underneath.
    """
    if _is_curated_module_not_found(exc):
        return exc
    if getattr(exc, "__cause__", None):
        return get_causing_exception(exc.__cause__)
    return exc


def _is_curated_module_not_found(exc: BaseException) -> bool:
    """True for a ModuleNotFoundError carrying a curated (non-raw) message.

    The interpreter's own import errors read ``No module named '<x>'``; anything
    else is a hand-written message (e.g. a bundle shim's "components moved to
    ...") that we should surface verbatim rather than rewrite.
    """
    return isinstance(exc, ModuleNotFoundError) and not str(exc).startswith("No module named")


def module_not_found_hint(exc: BaseException) -> str | None:
    """Return actionable install guidance for a ModuleNotFoundError, else None.

    Components import their provider SDK lazily, so a flow loaded on an
    engine-only ``lfx`` (no bundles) fails deep in the vertex build with a bare
    ``No module named '...'``. The ``lfx run`` CLI catches this with a
    dependency preflight, but the server run path does not, so this maps the
    missing module to its package and hands the same guidance to the UI/API.

    A graduated bundle shim already raises a curated "components moved to ..."
    ModuleNotFoundError (its ``str()`` does not start with "No module named").
    That message is more actionable than anything we could regenerate from the
    raw cause it wraps, so it is surfaced verbatim. Only plain
    ``No module named '<x>'`` errors are rewritten into ``pip install`` guidance.
    """
    if not isinstance(exc, ModuleNotFoundError):
        return None
    if _is_curated_module_not_found(exc):
        return str(exc)
    if not exc.name:
        return None
    from lfx.utils.flow_requirements import format_missing_module_error

    return format_missing_module_error(exc.name)


def format_exception_message(exc: Exception) -> str:
    """Format an exception message for returning to the frontend."""
    # We need to check if the __cause__ is a SyntaxError
    # If it is, we need to return the message of the SyntaxError
    causing_exception = get_causing_exception(exc)
    if isinstance(causing_exception, SyntaxError):
        return format_syntax_error_message(causing_exception)
    hint = module_not_found_hint(causing_exception)
    if hint is not None:
        return hint
    return str(exc)
