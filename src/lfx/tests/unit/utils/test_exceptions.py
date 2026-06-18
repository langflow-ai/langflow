"""Tests for lfx.utils.exceptions formatting helpers.

Focus: a flow loaded on an engine-only ``lfx`` (no bundles) fails deep in the
vertex build with a bare ``No module named '...'``. ``format_exception_message``
must turn that into actionable ``pip install`` guidance on the server run path,
while leaving the bundle-shim "components moved to ..." messages untouched.
"""

from lfx.utils.exceptions import (
    format_exception_message,
    module_not_found_hint,
)


def _wrap_like_create_class(exc: Exception) -> ValueError:
    """Reproduce how ``custom.validate.create_class`` wraps a build failure.

    It catches the original exception and re-raises a ValueError whose
    ``__cause__`` is the original, e.g. a ModuleNotFoundError raised when a
    component imports a provider SDK that is not installed.
    """
    msg = f"Error creating class. {type(exc).__name__}({exc!s})."
    try:
        raise ValueError(msg) from exc
    except ValueError as wrapped:
        return wrapped


class TestModuleNotFoundHint:
    def test_plain_module_not_found_gets_guidance(self):
        exc = ModuleNotFoundError("No module named 'langchain_chroma'", name="langchain_chroma")
        hint = module_not_found_hint(exc)
        assert hint is not None
        assert "pip install langchain-chroma" in hint

    def test_shim_message_is_left_untouched(self):
        # Bundle shims raise a ModuleNotFoundError whose message is already the
        # curated "components moved to ..." guidance; do not clobber it.
        shim = ModuleNotFoundError(
            "The 'datastax' components moved to the 'lfx-datastax' distribution. "
            "Install it with:  pip install lfx-datastax",
            name="lfx_bundles",
        )
        assert module_not_found_hint(shim) is None

    def test_non_module_error_returns_none(self):
        assert module_not_found_hint(ValueError("boom")) is None

    def test_module_error_without_name_returns_none(self):
        # A ModuleNotFoundError lacking ``.name`` carries no module to map.
        assert module_not_found_hint(ModuleNotFoundError("No module named 'x'")) is None


class TestFormatExceptionMessage:
    def test_wrapped_module_not_found_surfaces_guidance(self):
        # The exact shape Gabriel hit: create_class wraps the SDK import failure.
        cause = ModuleNotFoundError("No module named 'langchain_chroma'", name="langchain_chroma")
        wrapped = _wrap_like_create_class(cause)
        msg = format_exception_message(wrapped)
        assert "pip install langchain-chroma" in msg

    def test_wrapped_shim_message_passes_through(self):
        shim = ModuleNotFoundError(
            "The 'datastax' components moved to the 'lfx-datastax' distribution. "
            "Install it with:  pip install lfx-datastax",
            name="lfx_bundles",
        )
        wrapped = _wrap_like_create_class(shim)
        msg = format_exception_message(wrapped)
        # Falls through to str(exc): the curated message stays actionable.
        assert "moved to the 'lfx-datastax' distribution" in msg
        assert "pip install lfx-datastax" in msg

    def test_syntax_error_still_handled(self):
        try:
            compile("def (:", "<flow>", "exec")
        except SyntaxError as syn:
            wrapped = _wrap_like_create_class(syn)
            msg = format_exception_message(wrapped)
            assert "Syntax error in code" in msg

    def test_unrelated_error_is_unchanged(self):
        msg = format_exception_message(ValueError("something else"))
        assert msg == "something else"
