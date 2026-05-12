"""Tests that langflow.field_typing.constants is genuinely lazy.

Before the fix, the module did a bulk
``from lfx.field_typing.constants import (AgentExecutor, ...)`` which triggered
lfx's PEP 562 __getattr__ for every symbol in the list, eagerly pulling all of
langchain at module import time.  Additionally, ``Message`` and ``DataFrame``
were imported eagerly at module scope, each transitively pulling 15-80 more
langchain modules.

After the fix the module uses PEP 562 __getattr__ itself:
- The module body only imports cheap non-langchain symbols.
- All langchain symbols, LANGCHAIN_BASE_TYPES, and CUSTOM_COMPONENT_SUPPORTED_TYPES
  are resolved on first access.
- Message and DataFrame are resolved lazily in __getattr__ and cached in globals().

The subprocess in test_module_body_is_langchain_free provides the cleanest
signal: a fresh interpreter has no cached modules, so any langchain pull caused
by the module body shows up unambiguously.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def _constants_path() -> str:
    """Return the absolute path to langflow/field_typing/constants.py."""
    import langflow.field_typing.constants as _m

    return str(Path(_m.__file__).absolute())


CONSTANTS_PATH = _constants_path()

# Langchain top-level packages that must not appear after a bare import.
_HEAVY = ("langchain_core", "langchain_classic", "langchain_text_splitters")


class TestFieldTypingConstantsLazy:
    """langflow.field_typing.constants must not pull langchain at import time."""

    def test_module_body_is_langchain_free(self):
        """Loading constants.py in a fresh interpreter must pull zero langchain modules.

        Uses a subprocess so the test is unaffected by langchain modules that
        pytest or other tests may have already imported in the current process.
        Loads the file via importlib.util.spec_from_file_location to bypass
        langflow.field_typing.__init__ (which has separate, pre-existing eager
        imports outside the scope of this fix).
        """
        script = f"""
import sys, importlib.util

before = frozenset(m for m in sys.modules if m.startswith({_HEAVY!r}))

spec = importlib.util.spec_from_file_location("_lf_constants_test", {CONSTANTS_PATH!r})
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

after = frozenset(m for m in sys.modules if m.startswith({_HEAVY!r}))
new = sorted(after - before)
if new:
    sys.stderr.write("LOADED:" + ",".join(new[:10]) + chr(10))
    sys.exit(1)
"""
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", script],
            capture_output=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise AssertionError(
                "langflow.field_typing.constants module body pulled langchain modules "
                "into sys.modules. The module must be langchain-free at import time; "
                "langchain symbols are resolved lazily via __getattr__.\n" + stderr
            )

    def test_cheap_symbols_do_not_pull_langchain(self):
        """Accessing Code, NestedDict, Object, Data, Callable, Text must not trigger langchain.

        These symbols are defined in lfx or stdlib and carry no langchain dependency.
        Accessing them via the module attribute must return immediately without
        importing any langchain package.
        """
        import langflow.field_typing.constants as mod

        before = frozenset(m for m in sys.modules if m.startswith(_HEAVY))

        for name in ("Code", "NestedDict", "Object", "Data", "Callable", "Text"):
            val = getattr(mod, name)
            assert val is not None, f"langflow.field_typing.constants.{name} must be non-None"

        after = frozenset(m for m in sys.modules if m.startswith(_HEAVY))
        pulled = sorted(after - before)
        assert not pulled, (
            f"Accessing non-langchain symbols from langflow.field_typing.constants "
            f"pulled {len(pulled)} langchain modules: {pulled[:5]}. These symbols "
            f"must be resolved without touching langchain."
        )

    def test_langchain_symbols_accessible_on_demand(self):
        """All langchain symbols are accessible when explicitly requested."""
        import langflow.field_typing.constants as mod

        symbols = [
            "AgentExecutor",
            "BaseChatModel",
            "BaseLLM",
            "BaseRetriever",
            "TextSplitter",
            "VectorStore",
            "Embeddings",
            "Document",
            "LanguageModel",
            "Retriever",
        ]
        for name in symbols:
            val = getattr(mod, name)
            assert val is not None, f"langflow.field_typing.constants.{name} must resolve to a class"

    def test_message_and_dataframe_accessible_on_demand(self):
        """Message and DataFrame are lazy (not pulled on import) but accessible on access."""
        import langflow.field_typing.constants as mod

        msg = mod.Message
        assert msg is not None
        assert "Message" in msg.__name__

        df = mod.DataFrame
        assert df is not None

    def test_custom_component_supported_types_contains_message_and_dataframe(self):
        """CUSTOM_COMPONENT_SUPPORTED_TYPES must include langflow-specific Message and DataFrame."""
        import langflow.field_typing.constants as mod

        cst = mod.CUSTOM_COMPONENT_SUPPORTED_TYPES
        assert isinstance(cst, dict)
        assert "Message" in cst, "Message must be in CUSTOM_COMPONENT_SUPPORTED_TYPES"
        assert "DataFrame" in cst, "DataFrame must be in CUSTOM_COMPONENT_SUPPORTED_TYPES"
        assert cst["Message"] is mod.Message, "CUSTOM_COMPONENT_SUPPORTED_TYPES['Message'] must match mod.Message"

    def test_langchain_base_types_accessible(self):
        """LANGCHAIN_BASE_TYPES must resolve to a non-empty dict on access."""
        import langflow.field_typing.constants as mod

        lbt = mod.LANGCHAIN_BASE_TYPES
        assert isinstance(lbt, dict)
        assert len(lbt) > 0

    def test_unknown_attribute_raises_attribute_error(self):
        """Accessing a non-existent attribute must raise AttributeError."""
        import langflow.field_typing.constants as mod

        with pytest.raises(AttributeError):
            _ = mod.ThisSymbolDefinitelyDoesNotExist123
