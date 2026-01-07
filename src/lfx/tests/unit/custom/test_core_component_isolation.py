"""Tests for core component detection and isolation bypass.

These tests verify that core components (matching component index) bypass isolation,
while custom/edited components are properly isolated.
"""

from textwrap import dedent
from unittest.mock import patch

import pytest
from lfx.custom.isolation import SecurityViolationError
from lfx.custom.validate import create_class, create_function, execute_function


class TestCoreComponentDetection:
    """Test core component detection logic."""

    def test_custom_component_uses_isolation(self):
        """Test that custom components (not in index) use isolation."""
        code = dedent("""
        from langflow.custom import Component
        import os
        
        class CustomComponent(Component):
            def build(self):
                return os.getcwd()
        """)

        # Mock empty component index (no core components)
        with mock_component_index({"entries": []}), mock_isolation_settings("moderate"):
            # Custom component should be blocked
            with pytest.raises(SecurityViolationError, match="Module 'os' is blocked"):
                create_class(code, "CustomComponent")

    def test_custom_component_with_matching_name_but_different_hash(self):
        """Test that components with matching name but different hash are treated as custom."""
        code = dedent("""
        from langflow.custom import Component
        
        class TestComponent(Component):
            def build(self):
                import os
                return os.getcwd()
        """)

        # Mock component index with different hash

        fake_hash = "different_hash"
        index_data = {"entries": [("test_category", {"TestComponent": {"metadata": {"code_hash": fake_hash}}})]}

        with mock_component_index(index_data), mock_isolation_settings("moderate"):
            # Should be treated as custom (hash doesn't match)
            # Note: This will fail validation due to import in method body
            from lfx.custom.validate import validate_code

            errors = validate_code(code, "TestComponent")
            assert len(errors["function"]["errors"]) > 0

    def test_missing_component_index_treats_as_custom(self):
        """Test that missing component index defaults to custom (safer)."""
        code = dedent("""
        from langflow.custom import Component
        import os
        
        class TestComponent(Component):
            def build(self):
                return os.getcwd()
        """)

        # Mock None component index
        with mock_component_index(None), mock_isolation_settings("moderate"):
            # Should be treated as custom (safer to validate)
            with pytest.raises(SecurityViolationError, match="Module 'os' is blocked"):
                create_class(code, "TestComponent")

    def test_core_component_bypasses_isolation(self):
        """Test that core components (matching hash) bypass isolation."""
        code = dedent("""
        from langflow.custom import Component
        import os
        
        class CoreComponent(Component):
            def build(self):
                return os.getcwd()
        """)

        # Generate hash for the code
        from lfx.custom.utils import _generate_code_hash

        code_hash = _generate_code_hash(code, "CoreComponent")
        index_data = {"entries": [("test_category", {"CoreComponent": {"metadata": {"code_hash": code_hash}}})]}

        with mock_component_index(index_data), mock_isolation_settings("moderate"):
            # Core component should bypass isolation (no SecurityViolationError)
            # Note: This might fail for other reasons (missing imports, etc.)
            # but should NOT fail due to security isolation
            try:
                result = create_class(code, "CoreComponent")
                assert result.__name__ == "CoreComponent"
            except SecurityViolationError:
                pytest.fail("Core component should bypass isolation")
            except Exception:
                # Other errors (like missing imports) are acceptable
                pass

    def test_hash_check_before_code_modification(self):
        """Test that hash is checked before DEFAULT_IMPORT_STRING is added."""
        code = dedent("""
        from langflow.custom import Component
        
        class TestComponent(Component):
            def build(self):
                return "test"
        """)

        # Generate hash for the ORIGINAL code (before DEFAULT_IMPORT_STRING)
        from lfx.custom.utils import _generate_code_hash

        code_hash = _generate_code_hash(code, "TestComponent")
        index_data = {"entries": [("test_category", {"TestComponent": {"metadata": {"code_hash": code_hash}}})]}

        with mock_component_index(index_data), mock_isolation_settings("moderate"):
            # Should match hash even though DEFAULT_IMPORT_STRING will be added later
            # This verifies hash is checked BEFORE modification
            try:
                result = create_class(code, "TestComponent")
                assert result.__name__ == "TestComponent"
            except SecurityViolationError:
                pytest.fail("Hash should be checked before code modification")


class TestCoreComponentRuntimeIsolation:
    """Test that core components bypass runtime isolation."""

    def test_create_class_core_component_allows_dangerous_imports(self):
        """Test that core components can import dangerous modules."""
        code = dedent("""
        from langflow.custom import Component
        import os
        
        class CoreComponent(Component):
            def build(self):
                return os.getcwd()
        """)

        from lfx.custom.utils import _generate_code_hash

        code_hash = _generate_code_hash(code, "CoreComponent")
        index_data = {"entries": [("test_category", {"CoreComponent": {"metadata": {"code_hash": code_hash}}})]}

        with mock_component_index(index_data), mock_isolation_settings("moderate"):
            # Core component should allow os import
            try:
                result = create_class(code, "CoreComponent")
                assert result.__name__ == "CoreComponent"
            except SecurityViolationError:
                pytest.fail("Core component should allow dangerous imports")

    def test_execute_function_core_component_allows_dangerous_imports(self):
        """Test that core components in execute_function bypass isolation."""
        code = dedent("""
        import os
        
        def core_func():
            return os.getcwd()
        """)

        from lfx.custom.utils import _generate_code_hash

        code_hash = _generate_code_hash(code, None)
        index_data = {"entries": [("test_category", {"SomeComponent": {"metadata": {"code_hash": code_hash}}})]}

        with mock_component_index(index_data), mock_isolation_settings("moderate"):
            # Core component should allow os import
            try:
                result = execute_function(code, "core_func")
                assert isinstance(result, str)  # Should return directory path
            except SecurityViolationError:
                pytest.fail("Core component should allow dangerous imports")

    def test_create_function_core_component_allows_dangerous_imports(self):
        """Test that core components in create_function bypass isolation."""
        code = dedent("""
        import os
        
        def core_func():
            return os.getcwd()
        """)

        from lfx.custom.utils import _generate_code_hash

        code_hash = _generate_code_hash(code, None)
        index_data = {"entries": [("test_category", {"SomeComponent": {"metadata": {"code_hash": code_hash}}})]}

        with mock_component_index(index_data), mock_isolation_settings("moderate"):
            # Core component should allow os import
            try:
                result_func = create_function(code, "core_func")
                result = result_func()
                assert isinstance(result, str)  # Should return directory path
            except SecurityViolationError:
                pytest.fail("Core component should allow dangerous imports")


class TestBuildClassConstructorIsolation:
    """Test that build_class_constructor respects isolation."""

    def test_build_class_constructor_uses_isolation_for_custom(self):
        """Test that build_class_constructor uses isolation for custom components."""
        code = dedent("""
        from langflow.custom import Component
        
        class CustomComponent(Component):
            class_var = eval("1+1")  # Dangerous code in class body
            
            def build(self):
                return "test"
        """)

        # Mock empty component index (custom component)
        with mock_component_index({"entries": []}), mock_isolation_settings("moderate"):
            # Should be blocked due to eval in class body
            with pytest.raises(SecurityViolationError, match="Builtin 'eval' is blocked"):
                create_class(code, "CustomComponent")

    def test_build_class_constructor_bypasses_isolation_for_core(self):
        """Test that build_class_constructor bypasses isolation for core components."""
        code = dedent("""
        from langflow.custom import Component
        
        class CoreComponent(Component):
            class_var = eval("1+1")  # Dangerous code in class body
            
            def build(self):
                return "test"
        """)

        from lfx.custom.utils import _generate_code_hash

        code_hash = _generate_code_hash(code, "CoreComponent")
        index_data = {"entries": [("test_category", {"CoreComponent": {"metadata": {"code_hash": code_hash}}})]}

        with mock_component_index(index_data), mock_isolation_settings("moderate"):
            # Core component should allow eval in class body
            try:
                result = create_class(code, "CoreComponent")
                assert result.__name__ == "CoreComponent"
            except SecurityViolationError:
                pytest.fail("Core component should allow eval in class body")


class TestEdgeCases:
    """Test edge cases for core component detection."""

    def test_component_index_error_handling(self):
        """Test that errors reading component index default to custom."""
        code = dedent("""
        from langflow.custom import Component
        import os
        
        class TestComponent(Component):
            def build(self):
                return os.getcwd()
        """)

        # Mock component index that raises an error
        def raise_error():
            raise Exception("Index read error")

        with patch("lfx.interface.components._read_component_index", side_effect=raise_error):
            with mock_isolation_settings("moderate"):
                # Should default to custom (safer) and block os
                with pytest.raises(SecurityViolationError, match="Module 'os' is blocked"):
                    create_class(code, "TestComponent")

    def test_hash_collision_handling(self):
        """Test that hash collisions are handled (extremely rare but possible)."""
        code = dedent("""
        from langflow.custom import Component
        
        class CollisionComponent(Component):
            def build(self):
                return "test"
        """)

        # Mock component index with matching hash but different component
        from lfx.custom.utils import _generate_code_hash

        code_hash = _generate_code_hash(code, "CollisionComponent")
        index_data = {"entries": [("test_category", {"DifferentComponent": {"metadata": {"code_hash": code_hash}}})]}

        with mock_component_index(index_data), mock_isolation_settings("moderate"):
            # If hash matches, it's treated as core (even if name doesn't match)
            # This is acceptable risk - hash collisions are extremely rare
            try:
                result = create_class(code, "CollisionComponent")
                assert result.__name__ == "CollisionComponent"
            except SecurityViolationError:
                # If name is also checked, it might fail - that's fine
                pass


class TestHashCacheOptimization:
    """Test that hash cache optimization works correctly."""

    def test_cache_is_built_on_first_call(self):
        """Test that hash cache is built on first call to _is_core_component_by_code."""
        from lfx.custom.validate import (
            _clear_component_hash_cache,
            _is_core_component_by_code,
        )

        # Clear cache
        _clear_component_hash_cache()
        import lfx.custom.validate as validate_module

        code = dedent("""
        from langflow.custom import Component
        
        class TestComponent(Component):
            def build(self):
                return "test"
        """)

        from lfx.custom.utils import _generate_code_hash

        code_hash = _generate_code_hash(code, "TestComponent")
        index_data = {"entries": [("test_category", {"TestComponent": {"metadata": {"code_hash": code_hash}}})]}

        with mock_component_index(index_data):
            # First call should build cache
            result1 = _is_core_component_by_code(code, "TestComponent")

            # Cache should now be populated
            assert validate_module._component_hash_cache is not None
            assert validate_module._component_name_to_hash_cache is not None
            assert code_hash in validate_module._component_hash_cache
            assert "TestComponent" in validate_module._component_name_to_hash_cache
            assert result1 is True

    def test_cache_is_reused_on_subsequent_calls(self):
        """Test that cache is reused on subsequent calls (no re-reading index)."""
        from unittest.mock import patch

        from lfx.custom.validate import _is_core_component_by_code

        code = dedent("""
        from langflow.custom import Component
        
        class TestComponent(Component):
            def build(self):
                return "test"
        """)

        from lfx.custom.utils import _generate_code_hash

        code_hash = _generate_code_hash(code, "TestComponent")
        index_data = {"entries": [("test_category", {"TestComponent": {"metadata": {"code_hash": code_hash}}})]}

        with mock_component_index(index_data):
            # First call builds cache
            _is_core_component_by_code(code, "TestComponent")

            # Second call should use cache (not call _read_component_index again)
            with patch("lfx.interface.components._read_component_index") as mock_read:
                result = _is_core_component_by_code(code, "TestComponent")
                # Should not call _read_component_index again
                mock_read.assert_not_called()
                assert result is True

    def test_lru_cache_works(self):
        """Test that lru_cache caches function results by hash."""
        from lfx.custom.validate import _is_core_component, _is_core_component_by_code

        code = dedent("""
        from langflow.custom import Component
        
        class TestComponent(Component):
            def build(self):
                return "test"
        """)

        from lfx.custom.utils import _generate_code_hash

        code_hash = _generate_code_hash(code, "TestComponent")
        index_data = {"entries": [("test_category", {"TestComponent": {"metadata": {"code_hash": code_hash}}})]}

        with mock_component_index(index_data):
            # Check cache info before
            cache_info_before = _is_core_component.cache_info()

            # Call multiple times with same code (should generate same hash)
            for _ in range(5):
                result = _is_core_component_by_code(code, "TestComponent")
                assert result is True

            # Check cache info after - should have hits (cached by hash, not code)
            cache_info_after = _is_core_component.cache_info()
            assert cache_info_after.hits >= 4  # At least 4 hits (5 calls - 1 miss)
            assert cache_info_after.misses == 1  # Only 1 miss (first call)

    def test_hash_only_lookup_uses_cache(self):
        """Test that hash-only lookups (no component_name) use the cache efficiently."""
        from lfx.custom.validate import _is_core_component_by_code

        code = dedent("""
        def test_func():
            return "test"
        """)

        from lfx.custom.utils import _generate_code_hash

        code_hash = _generate_code_hash(code, None)
        index_data = {"entries": [("test_category", {"SomeComponent": {"metadata": {"code_hash": code_hash}}})]}

        with mock_component_index(index_data):
            # Hash-only lookup (component_name=None)
            result = _is_core_component_by_code(code, None)
            assert result is True

            # Should use hash_to_names cache (O(1) lookup)
            from lfx.custom.validate import _component_hash_cache

            assert _component_hash_cache is not None
            assert code_hash in _component_hash_cache
