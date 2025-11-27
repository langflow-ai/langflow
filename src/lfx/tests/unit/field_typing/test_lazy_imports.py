"""Tests for field_typing lazy import mechanism.

These tests verify that the __getattr__ lazy import pattern in field_typing/__init__.py
works correctly and returns the expected types.
"""

import pytest


class TestFieldTypingLazyImports:
    """Test that field_typing exports are accessible via lazy imports."""

    def test_input_import(self):
        """Test that Input can be imported from field_typing."""
        from lfx.field_typing import Input
        from lfx.template.field.base import Input as DirectInput

        assert Input is DirectInput

    def test_output_import(self):
        """Test that Output can be imported from field_typing."""
        from lfx.field_typing import Output
        from lfx.template.field.base import Output as DirectOutput

        assert Output is DirectOutput

    def test_range_spec_import(self):
        """Test that RangeSpec can be imported from field_typing."""
        from lfx.field_typing import RangeSpec
        from lfx.field_typing.range_spec import RangeSpec as DirectRangeSpec

        assert RangeSpec is DirectRangeSpec

    def test_data_import(self):
        """Test that Data can be imported from field_typing."""
        from lfx.field_typing import Data
        from lfx.schema.data import Data as DirectData

        assert Data is DirectData

    def test_constants_imports(self):
        """Test that constants from langchain are accessible."""
        from lfx.field_typing import (
            AgentExecutor,
            BaseChatMemory,
            BaseChatModel,
            BaseDocumentCompressor,
            BaseLanguageModel,
            BaseLLM,
            BaseLoader,
            BaseMemory,
            BaseOutputParser,
            BasePromptTemplate,
            BaseRetriever,
            Chain,
            ChatPromptTemplate,
            Document,
            Embeddings,
            PromptTemplate,
            TextSplitter,
            Tool,
            VectorStore,
        )

        # Verify they are not None (actual types or stubs)
        assert AgentExecutor is not None
        assert BaseChatMemory is not None
        assert BaseChatModel is not None
        assert BaseDocumentCompressor is not None
        assert BaseLanguageModel is not None
        assert BaseLLM is not None
        assert BaseLoader is not None
        assert BaseMemory is not None
        assert BaseOutputParser is not None
        assert BasePromptTemplate is not None
        assert BaseRetriever is not None
        assert Chain is not None
        assert ChatPromptTemplate is not None
        assert Document is not None
        assert Embeddings is not None
        assert PromptTemplate is not None
        assert TextSplitter is not None
        assert Tool is not None
        assert VectorStore is not None

    def test_type_aliases_import(self):
        """Test that type aliases are accessible."""
        from lfx.field_typing import (
            Callable,
            Code,
            LanguageModel,
            NestedDict,
            Object,
            Retriever,
            Text,
        )

        assert Callable is not None
        assert Code is not None
        assert LanguageModel is not None
        assert NestedDict is not None
        assert Object is not None
        assert Retriever is not None
        assert Text is not None

    def test_invalid_attribute_raises_error(self):
        """Test that accessing invalid attribute raises AttributeError."""
        import lfx.field_typing

        with pytest.raises(AttributeError, match="has no attribute 'NonExistentType'"):
            _ = lfx.field_typing.NonExistentType

    def test_all_exports_are_accessible(self):
        """Test that all items in __all__ are accessible."""
        import lfx.field_typing

        for name in lfx.field_typing.__all__:
            attr = getattr(lfx.field_typing, name)
            assert attr is not None, f"{name} should be accessible"

    def test_repeated_access_returns_same_object(self):
        """Test that repeated access returns the same object (caching works)."""
        from lfx.field_typing import Data as Data1
        from lfx.field_typing import Data as Data2

        assert Data1 is Data2

    def test_constants_match_direct_imports(self):
        """Test that constants from field_typing match direct imports from constants module."""
        from lfx.field_typing import Data, Document, Object
        from lfx.field_typing.constants import Data as DirectData
        from lfx.field_typing.constants import Document as DirectDocument
        from lfx.field_typing.constants import Object as DirectObject

        assert Data is DirectData
        assert Document is DirectDocument
        assert Object is DirectObject


class TestFieldTypingModuleStructure:
    """Test the structure of the field_typing module."""

    def test_all_list_exists(self):
        """Test that __all__ is defined."""
        import lfx.field_typing

        assert hasattr(lfx.field_typing, "__all__")
        assert isinstance(lfx.field_typing.__all__, list)
        assert len(lfx.field_typing.__all__) > 0

    def test_getattr_function_exists(self):
        """Test that __getattr__ is defined for lazy loading."""
        import lfx.field_typing

        # The module should have __getattr__ defined
        # We verify this indirectly by checking we can access lazy attributes
        assert hasattr(lfx.field_typing, "Input") or "Input" in lfx.field_typing.__all__

    def test_constants_names_set_exists(self):
        """Test that _CONSTANTS_NAMES is defined."""
        import lfx.field_typing

        assert hasattr(lfx.field_typing, "_CONSTANTS_NAMES")
        assert isinstance(lfx.field_typing._CONSTANTS_NAMES, set)
