"""Unit tests for Agentics SemanticMap component."""

from __future__ import annotations

import pytest
from lfx.components.agentics.semantic_map import SemanticMap


@pytest.mark.unit
class TestSemanticMapComponent:
    """Tests for SemanticMap component metadata."""

    def test_should_have_correct_display_name(self):
        """Test that component has correct display name."""
        assert SemanticMap.display_name == "SemanticMap"

    def test_should_have_correct_icon(self):
        """Test that component has correct icon."""
        assert SemanticMap.icon == "Agentics"

    def test_should_have_required_inputs(self):
        """Test that component has all required inputs."""
        input_names = {i.name for i in SemanticMap.inputs}

        assert "model" in input_names
        assert "api_key" in input_names
        assert "source" in input_names
        assert "generated_fields" in input_names
        assert "instructions" in input_names
        assert "append_to_input_columns" in input_names

    def test_should_have_dataframe_output(self):
        """Test that component has DataFrame output."""
        output_names = {o.name for o in SemanticMap.outputs}
        assert "states" in output_names

    def test_should_have_provider_specific_inputs(self):
        """Test that component has provider-specific inputs."""
        input_names = {i.name for i in SemanticMap.inputs}

        assert "base_url_ibm_watsonx" in input_names
        assert "project_id" in input_names
        assert "ollama_base_url" in input_names

    def test_should_have_model_input_with_real_time_refresh(self):
        """Test that model input has real_time_refresh enabled."""
        model_input = next((i for i in SemanticMap.inputs if i.name == "model"), None)
        assert model_input is not None
        assert model_input.real_time_refresh is True

    def test_should_have_generated_fields_with_table_schema(self):
        """Test that generated_fields input has table_schema defined."""
        fields_input = next((i for i in SemanticMap.inputs if i.name == "generated_fields"), None)
        assert fields_input is not None
        assert fields_input.table_schema is not None
        assert len(fields_input.table_schema) > 0

        field_names = {field["name"] for field in fields_input.table_schema}
        assert "name" in field_names
        assert "description" in field_names
        assert "type" in field_names
        assert "multiple" in field_names

    def test_should_have_append_to_input_columns_as_boolean(self):
        """Test that append_to_input_columns input is a boolean."""
        append_input = next((i for i in SemanticMap.inputs if i.name == "append_to_input_columns"), None)
        assert append_input is not None
        assert append_input.value is True
