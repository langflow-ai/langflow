"""Test metadata functionality in custom utils."""

from unittest.mock import Mock, patch

import pytest

from lfx.custom.utils import _generate_code_hash


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

    @patch("lfx.custom.utils.ComponentFrontendNode")
    def test_build_from_inputs_adds_metadata_with_module(self, mock_frontend_class):
        """Test that build_custom_component_template_from_inputs adds metadata when module_name is provided."""
        from lfx.custom.custom_component.component import Component
        from lfx.custom.utils import build_custom_component_template_from_inputs

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
        with patch("lfx.custom.utils.get_component_instance") as mock_get_instance:
            mock_instance = Mock()
            mock_instance.get_template_config = Mock(return_value={})
            mock_instance._get_field_order = Mock(return_value=[])
            mock_get_instance.return_value = mock_instance

            # Mock add_code_field to return the frontend node
            with (
                patch("lfx.custom.utils.add_code_field", return_value=mock_frontend),
                patch("lfx.custom.utils.reorder_fields"),
            ):
                # Call the function
                template, _ = build_custom_component_template_from_inputs(test_component, module_name="test.module")

        # Verify metadata was added
        assert "module" in mock_frontend.metadata
        assert mock_frontend.metadata["module"] == "test.module"
        assert "code_hash" in mock_frontend.metadata
        assert len(mock_frontend.metadata["code_hash"]) == 12

    @patch("lfx.custom.utils.CustomComponentFrontendNode")
    def test_build_template_adds_metadata_with_module(self, mock_frontend_class):
        """Test that build_custom_component_template adds metadata when module_name is provided."""
        from lfx.custom.custom_component.custom_component import CustomComponent
        from lfx.custom.utils import build_custom_component_template

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
        with patch("lfx.custom.utils.run_build_config") as mock_run_build:
            mock_instance = Mock()
            mock_instance._get_field_order = Mock(return_value=[])
            mock_run_build.return_value = ({}, mock_instance)

            with (
                patch("lfx.custom.utils.add_extra_fields"),
                patch("lfx.custom.utils.add_code_field", return_value=mock_frontend),
                patch("lfx.custom.utils.add_base_classes"),
                patch("lfx.custom.utils.add_output_types"),
                patch("lfx.custom.utils.reorder_fields"),
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
