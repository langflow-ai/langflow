"""Tests for lfx.utils.exceptions formatting helpers.

Focus: a flow loaded on an engine-only ``lfx`` (no bundles) fails deep in the
vertex build with a bare ``No module named '...'``. ``format_exception_message``
must turn that into actionable ``pip install`` guidance on the server run path,
while letting the bundle-shim "components moved to ..." messages win verbatim.
"""

from lfx.utils.exceptions import (
    format_exception_message,
    get_causing_exception,
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


def _raise_like_shim(raw: ModuleNotFoundError) -> ModuleNotFoundError:
    """Reproduce how a graduated bundle shim re-raises its curated message.

    A shim catches the raw ``No module named 'lfx_<provider>'`` import error and
    re-raises a curated "components moved to ..." ModuleNotFoundError ``from`` it,
    so the chain bottoms out at the raw error two levels down.
    """
    msg = (
        "The 'datastax' components moved to the 'lfx-datastax' distribution. "
        "Install it with:  pip install lfx-datastax   "
        "(or 'pip install langflow', which bundles it)."
    )
    try:
        raise ModuleNotFoundError(msg, name="lfx_datastax") from raw
    except ModuleNotFoundError as curated:
        return curated


class TestModuleNotFoundHint:
    def test_plain_module_not_found_gets_guidance(self):
        exc = ModuleNotFoundError("No module named 'langchain_chroma'", name="langchain_chroma")
        hint = module_not_found_hint(exc)
        assert hint is not None
        assert "pip install langchain-chroma" in hint

    def test_shim_message_is_surfaced_verbatim(self):
        # Bundle shims raise a ModuleNotFoundError whose message is already the
        # curated "components moved to ..." guidance. It is more actionable than
        # anything we could regenerate, so surface it as-is instead of clobbering
        # it with the bare-module mapping.
        shim = ModuleNotFoundError(
            "The 'datastax' components moved to the 'lfx-datastax' distribution. "
            "Install it with:  pip install lfx-datastax   "
            "(or 'pip install langflow', which bundles it).",
            name="lfx_datastax",
        )
        hint = module_not_found_hint(shim)
        assert hint == str(shim)
        assert "pip install langflow" in hint

    def test_non_module_error_returns_none(self):
        assert module_not_found_hint(ValueError("boom")) is None

    def test_module_error_without_name_returns_none(self):
        # A plain ModuleNotFoundError lacking ``.name`` carries no module to map.
        assert module_not_found_hint(ModuleNotFoundError("No module named 'x'")) is None


class TestGetCausingException:
    def test_stops_at_curated_shim_error(self):
        # The real 3-level chain: a curated shim ModuleNotFoundError is itself
        # raised ``from`` the raw "No module named" cause. The walk must stop at
        # the curated error, not unwrap past it to the bare cause.
        raw = ModuleNotFoundError("No module named 'lfx_datastax'", name="lfx_datastax")
        curated = _raise_like_shim(raw)
        wrapped = _wrap_like_create_class(curated)
        assert get_causing_exception(wrapped) is curated

    def test_unwraps_plain_module_not_found_to_root(self):
        # No curated message in the chain: still walk to the deepest cause.
        cause = ModuleNotFoundError("No module named 'langchain_chroma'", name="langchain_chroma")
        wrapped = _wrap_like_create_class(cause)
        assert get_causing_exception(wrapped) is cause


class TestFormatExceptionMessage:
    def test_wrapped_module_not_found_surfaces_guidance(self):
        # The exact shape Gabriel hit: create_class wraps the SDK import failure.
        cause = ModuleNotFoundError("No module named 'langchain_chroma'", name="langchain_chroma")
        wrapped = _wrap_like_create_class(cause)
        msg = format_exception_message(wrapped)
        assert "pip install langchain-chroma" in msg

    def test_graduated_shim_message_wins_over_raw_cause(self):
        # The graduated case Gabriel flagged: the chain bottoms out at the raw
        # "No module named 'lfx_datastax'", so the old deepest-cause walk dropped
        # the curated text and regenerated a bare "pip install lfx-datastax".
        # The curated shim message must win verbatim instead.
        raw = ModuleNotFoundError("No module named 'lfx_datastax'", name="lfx_datastax")
        curated = _raise_like_shim(raw)
        wrapped = _wrap_like_create_class(curated)
        msg = format_exception_message(wrapped)
        assert "moved to the 'lfx-datastax' distribution" in msg
        # The "or pip install langflow, which bundles it" clause is the part that
        # the regenerated bare-module guidance cannot reproduce.
        assert "pip install langflow" in msg
        # Not the create_class wrapper, and not the regenerated bare-module text.
        assert not msg.startswith("Error creating class")
        assert "moved out of the lfx engine" not in msg

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
