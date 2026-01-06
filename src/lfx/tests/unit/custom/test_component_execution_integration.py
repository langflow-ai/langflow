"""Integration tests for component execution with isolation.

These tests verify that components can actually execute in flows,
ensuring that isolation doesn't break real-world component execution.
"""

from textwrap import dedent

import pytest
from lfx.custom.eval import eval_custom_component_code
from lfx.custom.isolation import SecurityViolationError


class TestComponentExecution:
    """Test that components can execute successfully."""

    def test_safe_custom_component_executes(self):
        """Test that safe custom components can execute."""
        code = dedent("""
        from langflow.custom import Component
        import json
        import math
        
        class SafeComponent(Component):
            def build(self):
                data = {"value": math.sqrt(16)}
                return json.dumps(data)
        """)

        # Mock empty component index (custom component)
        with mock_component_index({"entries": []}), mock_isolation_settings("moderate"):
            # Should execute successfully
            component_class = eval_custom_component_code(code)
            assert component_class.__name__ == "SafeComponent"

            # Can instantiate
            instance = component_class()
            assert instance is not None

    def test_custom_component_with_dangerous_import_fails(self):
        """Test that custom components with dangerous imports are blocked."""
        code = dedent("""
        from langflow.custom import Component
        import os
        
        class DangerousComponent(Component):
            def build(self):
                return os.getcwd()
        """)

        # Mock empty component index (custom component)
        with mock_component_index({"entries": []}), mock_isolation_settings("moderate"):
            # Should be blocked
            with pytest.raises(SecurityViolationError, match="Module 'os' is blocked"):
                eval_custom_component_code(code)

    def test_core_component_executes_with_dangerous_import(self):
        """Test that core components can execute even with dangerous imports."""
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
            # Core component should execute successfully (bypasses isolation)
            try:
                component_class = eval_custom_component_code(code)
                assert component_class.__name__ == "CoreComponent"

                # Can instantiate
                instance = component_class()
                assert instance is not None
            except SecurityViolationError:
                pytest.fail("Core component should bypass isolation")

    def test_component_with_class_level_assignment(self):
        """Test that components with class-level assignments execute correctly."""
        code = dedent("""
        from langflow.custom import Component
        import json
        
        class ComponentWithClassVar(Component):
            DEFAULT_VALUE = json.dumps({"key": "value"})
            
            def build(self):
                return self.DEFAULT_VALUE
        """)

        # Mock empty component index (custom component)
        with mock_component_index({"entries": []}), mock_isolation_settings("moderate"):
            # Should execute successfully
            component_class = eval_custom_component_code(code)
            assert component_class.__name__ == "ComponentWithClassVar"

            # Can instantiate and access class variable
            instance = component_class()
            assert hasattr(component_class, "DEFAULT_VALUE")
            assert component_class.DEFAULT_VALUE == '{"key": "value"}'

    def test_component_with_method_imports(self):
        """Test that components with imports in methods are handled correctly."""
        code = dedent("""
        from langflow.custom import Component
        
        class ComponentWithMethodImport(Component):
            def build(self):
                import json
                return json.dumps({"test": True})
        """)

        # Mock empty component index (custom component)
        with mock_component_index({"entries": []}), mock_isolation_settings("moderate"):
            # Should execute successfully (import in method is runtime, not blocked at definition)
            component_class = eval_custom_component_code(code)
            assert component_class.__name__ == "ComponentWithMethodImport"

            # Can instantiate
            instance = component_class()
            assert instance is not None

    def test_component_with_dangerous_builtin_in_class_body(self):
        """Test that dangerous builtins in class body are blocked for custom components."""
        code = dedent("""
        from langflow.custom import Component
        
        class DangerousClassBody(Component):
            value = eval("1+1")  # Dangerous code in class body
            
            def build(self):
                return self.value
        """)

        # Mock empty component index (custom component)
        with mock_component_index({"entries": []}), mock_isolation_settings("moderate"):
            # Should be blocked
            with pytest.raises(SecurityViolationError, match="Builtin 'eval' is blocked"):
                eval_custom_component_code(code)

    def test_component_with_dangerous_builtin_in_class_body_core(self):
        """Test that core components allow dangerous builtins in class body."""
        code = dedent("""
        from langflow.custom import Component
        
        class CoreDangerousClassBody(Component):
            value = eval("1+1")  # Dangerous code in class body
            
            def build(self):
                return self.value
        """)

        # Generate hash for the code
        from lfx.custom.utils import _generate_code_hash

        code_hash = _generate_code_hash(code, "CoreDangerousClassBody")
        index_data = {
            "entries": [("test_category", {"CoreDangerousClassBody": {"metadata": {"code_hash": code_hash}}})]
        }

        with mock_component_index(index_data), mock_isolation_settings("moderate"):
            # Core component should allow eval in class body
            try:
                component_class = eval_custom_component_code(code)
                assert component_class.__name__ == "CoreDangerousClassBody"
                assert component_class.value == 2
            except SecurityViolationError:
                pytest.fail("Core component should allow dangerous builtins in class body")


class TestComponentBuildMethod:
    """Test that component build() methods execute correctly."""

    def test_build_method_executes(self):
        """Test that build() method can execute."""
        code = dedent("""
        from langflow.custom import Component
        import json
        
        class TestComponent(Component):
            def build(self):
                return json.dumps({"result": "success"})
        """)

        # Mock empty component index (custom component)
        with mock_component_index({"entries": []}), mock_isolation_settings("moderate"):
            component_class = eval_custom_component_code(code)
            instance = component_class()

            # Build method should execute
            result = instance.build()
            assert result == '{"result": "success"}'

    def test_build_method_with_imports(self):
        """Test that build() method can use imports."""
        code = dedent("""
        from langflow.custom import Component
        
        class TestComponent(Component):
            def build(self):
                import json
                import math
                return json.dumps({"sqrt": math.sqrt(16)})
        """)

        # Mock empty component index (custom component)
        with mock_component_index({"entries": []}), mock_isolation_settings("moderate"):
            component_class = eval_custom_component_code(code)
            instance = component_class()

            # Build method should execute with runtime imports
            result = instance.build()
            assert result == '{"sqrt": 4.0}'


class TestComponentWithInputs:
    """Test components that use Langflow inputs."""

    def test_component_with_str_input(self):
        """Test component with StrInput."""
        code = dedent("""
        from langflow.custom import Component
        from langflow.io import StrInput, Output
        
        class ComponentWithInput(Component):
            def build(self):
                text_input = self.get_input("text")
                return {"output": text_input}
            
            def inputs(self):
                return [StrInput(name="text", display_name="Text")]
        """)

        # Mock empty component index (custom component)
        with mock_component_index({"entries": []}), mock_isolation_settings("moderate"):
            # Should execute successfully
            component_class = eval_custom_component_code(code)
            assert component_class.__name__ == "ComponentWithInput"

            # Can instantiate
            instance = component_class()
            assert instance is not None
            assert hasattr(instance, "inputs")
