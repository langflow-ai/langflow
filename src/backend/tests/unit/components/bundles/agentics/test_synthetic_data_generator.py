"""Unit tests for Agentics SyntheticDataGenerator component."""

from __future__ import annotations

import pytest

try:
    import agentics  # noqa: F401
    import crewai  # noqa: F401
except ImportError:
    pytest.skip("agentics-py and crewai not installed", allow_module_level=True)

from lfx.components.agentics.synthetic_data_generator import SyntheticDataGenerator


@pytest.mark.unit
class TestSyntheticDataGeneratorComponent:
    """Tests for SyntheticDataGenerator component metadata."""

    def test_should_have_correct_display_name(self):
        """Test that component has correct display name."""
        assert SyntheticDataGenerator.display_name == "aGenerate"

    def test_should_have_correct_icon(self):
        """Test that component has correct icon."""
        assert SyntheticDataGenerator.icon == "Agentics"

    def test_should_have_correct_description(self):
        """Test that component has correct description."""
        assert "mock data" in SyntheticDataGenerator.description.lower()
        assert "schema" in SyntheticDataGenerator.description.lower()

    def test_should_have_required_inputs(self):
        """Test that component has all required inputs."""
        input_names = {i.name for i in SyntheticDataGenerator.inputs}

        assert "model" in input_names
        assert "api_key" in input_names
        assert "schema" in input_names
        assert "batch_size" in input_names

    def test_should_have_source_input_optional(self):
        """Test that component has optional source input for learning from examples."""
        input_names = {i.name for i in SyntheticDataGenerator.inputs}
        assert "source" in input_names

    def test_should_have_dataframe_output(self):
        """Test that component has DataFrame output."""
        output_names = {o.name for o in SyntheticDataGenerator.outputs}
        assert "states" in output_names

    def test_should_have_provider_specific_inputs(self):
        """Test that component has provider-specific inputs."""
        input_names = {i.name for i in SyntheticDataGenerator.inputs}

        assert "base_url_ibm_watsonx" in input_names
        assert "project_id" in input_names
        assert "ollama_base_url" in input_names

    def test_should_have_model_input_with_real_time_refresh(self):
        """Test that model input has real_time_refresh enabled."""
        model_input = next((i for i in SyntheticDataGenerator.inputs if i.name == "model"), None)
        assert model_input is not None
        assert model_input.real_time_refresh is True

    def test_should_have_schema_with_table_schema(self):
        """Test that schema input has table_schema defined."""
        schema_input = next((i for i in SyntheticDataGenerator.inputs if i.name == "schema"), None)
        assert schema_input is not None
        assert schema_input.table_schema is not None
        assert len(schema_input.table_schema) > 0

        field_names = {field["name"] for field in schema_input.table_schema}
        assert "name" in field_names
        assert "description" in field_names
        assert "type" in field_names
        assert "multiple" in field_names

    def test_should_have_batch_size_with_default_value(self):
        """Test that batch_size input has correct default value."""
        batch_input = next((i for i in SyntheticDataGenerator.inputs if i.name == "batch_size"), None)
        assert batch_input is not None
        assert batch_input.value == 10

    def test_should_have_batch_size_not_advanced(self):
        """Test that batch_size input is not marked as advanced."""
        batch_input = next((i for i in SyntheticDataGenerator.inputs if i.name == "batch_size"), None)
        assert batch_input is not None
        assert batch_input.advanced is False

    def test_should_have_api_key_as_advanced(self):
        """Test that api_key input is marked as advanced."""
        api_key_input = next((i for i in SyntheticDataGenerator.inputs if i.name == "api_key"), None)
        assert api_key_input is not None
        assert api_key_input.advanced is True

    def test_should_have_output_with_correct_method(self):
        """Test that output has correct method name."""
        output = next((o for o in SyntheticDataGenerator.outputs if o.name == "states"), None)
        assert output is not None
        assert output.method == "aGenerate"
