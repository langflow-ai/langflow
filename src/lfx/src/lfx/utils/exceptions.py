def format_syntax_error_message(exc: SyntaxError) -> str:
    """Format a SyntaxError message for returning to the frontend."""
    if exc.text is None:
        return f"Syntax error in code. Error on line {exc.lineno}"
    return f"Syntax error in code. Error on line {exc.lineno}: {exc.text.strip()}"


def get_causing_exception(exc: BaseException) -> BaseException:
    """Get the causing exception from an exception."""
    if hasattr(exc, "__cause__") and exc.__cause__:
        return get_causing_exception(exc.__cause__)
    return exc


def module_not_found_hint(exc: BaseException) -> str | None:
    """Return ``pip install`` guidance for a *plain* ModuleNotFoundError, else None.

    Components import their provider SDK lazily, so a flow loaded on an
    engine-only ``lfx`` (no bundles) fails deep in the vertex build with a bare
    ``No module named '...'``. The ``lfx run`` CLI catches this with a
    dependency preflight, but the server run path does not, so this maps the
    missing module to its package and hands the same guidance to the UI/API.

    Only plain ``No module named '<x>'`` errors are rewritten. Bundle-shim
    ModuleNotFoundErrors already carry a curated "components moved to ..."
    message (their ``str()`` does not start with "No module named"), so they
    are left untouched and keep flowing through unchanged.
    """
    if not isinstance(exc, ModuleNotFoundError) or not exc.name:
        return None
    if not str(exc).startswith("No module named"):
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
