"""Test metadata functionality in custom utils."""

from unittest.mock import Mock, patch

import pytest
from langflow.custom.utils import _generate_code_hash


class TestCodeHashGeneration:
    """Test the _generate_code_hash function."""

    def test_hash_generation_basic(self):
        """Test basic hash generation."""
        source = "def test(): pass"
        modname = "test_module"
        class_name = "TestClass"

        result = _generate_code_hash(source, modname, class_name)

        assert isinstance(result, str)
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_empty_source_raises(self):
        """Test that empty source raises ValueError."""
        with pytest.raises(ValueError, match="Empty source code"):
            _generate_code_hash("", "mod", "cls")

    def test_hash_none_source_raises(self):
        """Test that None source raises ValueError."""
        with pytest.raises(ValueError, match="Empty source code"):
            _generate_code_hash(None, "mod", "cls")

    def test_hash_consistency(self):
        """Test that same code produces same hash."""
        source = "class A: pass"
        hash1 = _generate_code_hash(source, "mod", "A")
        hash2 = _generate_code_hash(source, "mod", "A")
        assert hash1 == hash2

    def test_hash_different_code(self):
        """Test that different code produces different hash."""
        hash1 = _generate_code_hash("class A: pass", "mod", "A")
        hash2 = _generate_code_hash("class B: pass", "mod", "B")
        assert hash1 != hash2


class TestMetadataInTemplateBuilders:
    """Test metadata addition in template building functions."""

    @patch("langflow.custom.utils.ComponentFrontendNode")
    def test_build_from_inputs_adds_metadata_with_module(self, mock_frontend_class):
        """Test that build_custom_component_template_from_inputs adds metadata when module_name is provided."""
        from langflow.custom.custom_component.component import Component
        from langflow.custom.utils import build_custom_component_template_from_inputs

        # Setup mock frontend node
        mock_frontend = Mock()
        mock_frontend.metadata = {}
        mock_frontend.outputs = []
        mock_frontend.to_dict = Mock(return_value={"test": "data"})
        mock_frontend.validate_component = Mock()
        mock_frontend.set_base_classes_from_outputs = Mock()
        mock_frontend_class.from_inputs.return_value = mock_frontend

        # Create test component
        test_component = Mock(spec=Component)
        test_component.__class__.__name__ = "TestComponent"
        test_component._code = "class TestComponent: pass"
        test_component.template_config = {"inputs": []}

        # Mock get_component_instance to return a mock instance
        with patch("langflow.custom.utils.get_component_instance") as mock_get_instance:
            mock_instance = Mock()
            mock_instance.get_template_config = Mock(return_value={})
            mock_instance._get_field_order = Mock(return_value=[])
            mock_get_instance.return_value = mock_instance

            # Mock add_code_field to return the frontend node
            with (
                patch("langflow.custom.utils.add_code_field", return_value=mock_frontend),
                patch("langflow.custom.utils.reorder_fields"),
            ):
                # Call the function
                template, _ = build_custom_component_template_from_inputs(test_component, module_name="test.module")

        # Verify metadata was added
        assert "module" in mock_frontend.metadata
        assert mock_frontend.metadata["module"] == "test.module"
        assert "code_hash" in mock_frontend.metadata
        assert len(mock_frontend.metadata["code_hash"]) == 12

    @patch("langflow.custom.utils.CustomComponentFrontendNode")
    def test_build_template_adds_metadata_with_module(self, mock_frontend_class):
        """Test that build_custom_component_template adds metadata when module_name is provided."""
        from langflow.custom.custom_component.custom_component import CustomComponent
        from langflow.custom.utils import build_custom_component_template

        # Setup mock frontend node
        mock_frontend = Mock()
        mock_frontend.metadata = {}
        mock_frontend.to_dict = Mock(return_value={"test": "data"})
        mock_frontend_class.return_value = mock_frontend

        # Create test component
        test_component = Mock(spec=CustomComponent)
        test_component.__class__.__name__ = "CustomTestComponent"
        test_component._code = "class CustomTestComponent: pass"
        test_component.template_config = {"display_name": "Test"}
        test_component.get_function_entrypoint_args = []
        test_component._get_function_entrypoint_return_type = []

        # Mock helper functions
        with patch("langflow.custom.utils.run_build_config") as mock_run_build:
            mock_instance = Mock()
            mock_instance._get_field_order = Mock(return_value=[])
            mock_run_build.return_value = ({}, mock_instance)

            with (
                patch("langflow.custom.utils.add_extra_fields"),
                patch("langflow.custom.utils.add_code_field", return_value=mock_frontend),
                patch("langflow.custom.utils.add_base_classes"),
                patch("langflow.custom.utils.add_output_types"),
                patch("langflow.custom.utils.reorder_fields"),
            ):
                # Call the function
                template, _ = build_custom_component_template(test_component, module_name="custom.test")

        # Verify metadata was added
        assert "module" in mock_frontend.metadata
        assert mock_frontend.metadata["module"] == "custom.test"
        assert "code_hash" in mock_frontend.metadata
        assert len(mock_frontend.metadata["code_hash"]) == 12

    def test_hash_generation_unicode(self):
        """Test hash generation with unicode characters."""
        source = "# Test with unicode: 你好 🌟\nclass Component: pass"
        result = _generate_code_hash(source, "unicode_mod", "Component")

        assert isinstance(result, str)
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)


class TestDependencyAnalyzer:
    """Test dependency analysis functionality."""

    def test_top_level_basic(self):
        """Test extracting top level package name."""
        from langflow.custom.dependency_analyzer import _top_level

        assert _top_level("numpy") == "numpy"
        assert _top_level("numpy.array") == "numpy"
        assert _top_level("requests.adapters.HTTPAdapter") == "requests"

    def test_is_relative(self):
        """Test relative import detection."""
        from langflow.custom.dependency_analyzer import _is_relative

        assert _is_relative(".module") is True
        assert _is_relative("..parent") is True
        assert _is_relative("...grandparent") is True
        assert _is_relative("module") is False
        assert _is_relative(None) is False

    def test_analyze_dependencies_basic(self):
        """Test basic dependency analysis."""
        from langflow.custom.dependency_analyzer import analyze_dependencies

        code = """
import os
import sys
from typing import List
import numpy as np
from requests import get
"""

        deps = analyze_dependencies(code, resolve_versions=False)

        # Should find external dependencies only (stdlib imports filtered out)
        assert len(deps) == 2

        # Check external dependencies
        dep_names = [d["name"] for d in deps]
        assert "numpy" in dep_names
        assert "requests" in dep_names

        # Stdlib imports should be filtered out
        assert "os" not in dep_names
        assert "sys" not in dep_names
        assert "typing" not in dep_names

    def test_analyze_dependencies_optional_detection(self):
        """Test that all dependencies are treated as required (no optional detection)."""
        from langflow.custom.dependency_analyzer import analyze_dependencies

        code = """
import os
try:
    import optional_package
    HAS_OPTIONAL = True
except ImportError:
    HAS_OPTIONAL = False

try:
    from another_optional import something
except ImportError:
    pass  # This is now treated as a regular dependency
"""

        deps = analyze_dependencies(code, resolve_versions=False)

        # Should find external dependencies only (stdlib imports filtered out)
        assert len(deps) == 2  # optional_package, another_optional
        dep_names = [d["name"] for d in deps]
        assert "optional_package" in dep_names
        assert "another_optional" in dep_names

        # Stdlib imports should be filtered out
        assert "os" not in dep_names

    def test_analyze_component_dependencies(self):
        """Test component-specific dependency analysis."""
        from langflow.custom.dependency_analyzer import analyze_component_dependencies

        component_code = """
import os
import sys
from typing import Dict, List
from langflow.custom import CustomComponent
import numpy as np

class TestComponent(CustomComponent):
    def build(self):
        return {"test": "value"}
"""

        result = analyze_component_dependencies(component_code)

        # Check structure
        assert "total_dependencies" in result
        assert "dependencies" in result

        # Should have some dependencies (only external dependencies)
        assert result["total_dependencies"] > 0

        # Should have dependencies list
        assert isinstance(result["dependencies"], list)

        # Verify no duplicate packages in dependencies
        package_names = [pkg["name"] for pkg in result["dependencies"]]
        assert len(package_names) == len(set(package_names)), "No duplicate packages should exist"

    def test_analyze_component_dependencies_error_handling(self):
        """Test error handling in component dependency analysis."""
        from langflow.custom.dependency_analyzer import analyze_component_dependencies

        # Test with invalid Python code
        invalid_code = "import os\nthis is not valid python syntax!!!"

        result = analyze_component_dependencies(invalid_code)

        # Should return minimal info on error
        assert result["total_dependencies"] == 0
        assert result["dependencies"] == []

    def test_dependency_info_dataclass(self):
        """Test DependencyInfo dataclass creation."""
        from langflow.custom.dependency_analyzer import DependencyInfo

        dep = DependencyInfo(
            name="numpy",
            version="1.21.0",
            is_local=False,
        )

        assert dep.name == "numpy"
        assert dep.version == "1.21.0"
        assert not dep.is_local

    def test_no_optional_dependency_classification(self):
        """Test that the simplified analyzer doesn't classify any dependencies as optional."""
        from langflow.custom.dependency_analyzer import analyze_dependencies

        # Code with various import patterns that previously might have been considered optional
        code = """
import os
try:
    import package_a
    HAS_A = True
except ImportError:
    HAS_A = False

try:
    import package_b
except ImportError:
    pass

try:
    from package_c import something
except (ImportError, ModuleNotFoundError):
    something = None
"""
        deps = analyze_dependencies(code, resolve_versions=False)

        # Should find external dependencies only (stdlib filtered out)
        dep_names = [d["name"] for d in deps]
        assert "package_a" in dep_names
        assert "package_b" in dep_names
        assert "package_c" in dep_names

        # Stdlib imports should be filtered out
        assert "os" not in dep_names

        # All found dependencies should be external (not local)
        for dep in deps:
            assert not dep["is_local"], f"Dependency {dep['name']} should not be local"


class TestMetadataWithDependencies:
    """Test metadata functionality including dependencies."""

    def test_build_component_metadata_includes_dependencies(self):
        """Test that build_component_metadata includes dependency analysis."""
        from langflow.custom.custom_component.component import Component
        from langflow.custom.utils import build_component_metadata

        # Setup mock frontend node
        mock_frontend = Mock()
        mock_frontend.metadata = {}

        # Create test component with real code
        test_component = Mock(spec=Component)
        test_component._code = """
import os
import sys
from typing import List

class TestComponent:
    def build(self):
        return {"test": "value"}
"""

        # Call the function
        build_component_metadata(mock_frontend, test_component, "test.module", "TestComponent")

        # Verify metadata was added
        assert "module" in mock_frontend.metadata
        assert "code_hash" in mock_frontend.metadata
        assert "dependencies" in mock_frontend.metadata

        # Verify dependency analysis results
        dep_info = mock_frontend.metadata["dependencies"]
        # Only external dependencies are tracked now (stdlib filtered out)
        assert dep_info["total_dependencies"] == 0  # No external deps in this test code
        assert "dependencies" in dep_info
        assert isinstance(dep_info["dependencies"], list)

    def test_build_component_metadata_handles_analysis_error(self):
        """Test that build_component_metadata handles dependency analysis errors gracefully."""
        from langflow.custom.custom_component.component import Component
        from langflow.custom.utils import build_component_metadata

        # Setup mock frontend node
        mock_frontend = Mock()
        mock_frontend.metadata = {}

        # Create test component with invalid Python code
        test_component = Mock(spec=Component)
        test_component._code = "import os\nthis is not valid python syntax!!!"

        # Call the function - should not raise exception
        build_component_metadata(mock_frontend, test_component, "test.module", "TestComponent")

        # Should not raise exception and should set minimal dependency info
        assert "dependencies" in mock_frontend.metadata
        dep_info = mock_frontend.metadata["dependencies"]
        assert dep_info["total_dependencies"] == 0
        assert dep_info["dependencies"] == []

    def test_build_component_metadata_with_external_dependencies(self):
        """Test dependency analysis with external packages."""
        from langflow.custom.custom_component.component import Component
        from langflow.custom.utils import build_component_metadata

        # Setup mock frontend node
        mock_frontend = Mock()
        mock_frontend.metadata = {}

        # Create test component with external dependencies
        test_component = Mock(spec=Component)
        test_component._code = """
import os
from langflow.custom import CustomComponent

class TestComponent(CustomComponent):
    def build(self):
        return {"test": "value"}
"""

        # Call the function
        build_component_metadata(mock_frontend, test_component, "test.module", "TestComponent")

        # Verify dependency analysis results
        dep_info = mock_frontend.metadata["dependencies"]
        assert dep_info["total_dependencies"] == 1  # Only langflow (os is stdlib, filtered out)

        # Check for dependencies
        package_names = [pkg["name"] for pkg in dep_info["dependencies"]]
        assert "langflow" in package_names  # langflow should be detected as external
        assert "os" not in package_names  # os is stdlib, should be filtered out

    def test_build_component_metadata_with_optional_dependencies(self):
        """Test dependency analysis with optional dependencies."""
        from langflow.custom.custom_component.component import Component
        from langflow.custom.utils import build_component_metadata

        # Setup mock frontend node
        mock_frontend = Mock()
        mock_frontend.metadata = {}

        # Create test component with optional dependencies
        test_component = Mock(spec=Component)
        test_component._code = """
import os
try:
    import some_optional_package
    HAS_OPTIONAL = True
except ImportError:
    HAS_OPTIONAL = False

class TestComponent:
    def build(self):
        return {"test": "value"}
"""

        # Call the function
        build_component_metadata(mock_frontend, test_component, "test.module", "TestComponent")

        # Verify dependency analysis results
        dep_info = mock_frontend.metadata["dependencies"]
        assert dep_info["total_dependencies"] == 1  # Only some_optional_package (os is stdlib, filtered out)

        # Verify the dependencies are found
        package_names = [pkg["name"] for pkg in dep_info["dependencies"]]
        assert "some_optional_package" in package_names
        assert "os" not in package_names  # os is stdlib, should be filtered out

    def test_build_component_metadata_with_real_component(self):
        """Test dependency analysis with a real component."""
        from langflow.custom.custom_component.component import Component
        from langflow.custom.utils import build_component_metadata

        # Setup mock frontend node
        mock_frontend = Mock()
        mock_frontend.metadata = {}

        # Use real component code based on LMStudio component
        real_component_code = """from typing import Any
from urllib.parse import urljoin

import httpx
from langchain_openai import ChatOpenAI

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel

class LMStudioModelComponent(LCModelComponent):
    display_name = "LM Studio"
    description = "Generate text using LM Studio Local LLMs."
    icon = "LMStudio"
    name = "LMStudioModel"

    def build(self):
        return {"test": "value"}
"""

        # Create test component
        test_component = Mock(spec=Component)
        test_component._code = real_component_code

        # Call the function
        build_component_metadata(
            mock_frontend, test_component, "langflow.components.lmstudio", "LMStudioModelComponent"
        )

        # Verify metadata was added
        assert "module" in mock_frontend.metadata
        assert "code_hash" in mock_frontend.metadata
        assert "dependencies" in mock_frontend.metadata

        # Verify dependency analysis results
        dep_info = mock_frontend.metadata["dependencies"]
        assert dep_info["total_dependencies"] > 0

        # Check that external dependencies are found (stdlib filtered out)
        package_names = [pkg["name"] for pkg in dep_info["dependencies"]]

        # External packages should be found
        assert "httpx" in package_names  # external
        assert "langchain_openai" in package_names  # external
        assert "langflow" in package_names  # project dependency

        # Stdlib imports should be filtered out
        assert "typing" not in package_names
        assert "urllib" not in package_names
