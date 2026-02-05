"""Unit tests for Agentics SemanticAggregator component."""

from __future__ import annotations

import pytest
from lfx.components.agentics.semantic_aggregator import SemanticAggregator


@pytest.mark.unit
class TestSemanticAggregatorComponent:
    """Tests for SemanticAggregator component metadata."""

    def test_should_have_correct_display_name(self):
        """Test that component has correct display name."""
        assert SemanticAggregator.display_name == "Semantic Aggregator"

    def test_should_have_correct_icon(self):
        """Test that component has correct icon."""
        assert SemanticAggregator.icon == "Agentics"

    def test_should_have_correct_description(self):
        """Test that component has correct description."""
        assert "single row" in SemanticAggregator.description.lower()

    def test_should_have_required_inputs(self):
        """Test that component has all required inputs."""
        input_names = {i.name for i in SemanticAggregator.inputs}

        assert "model" in input_names
        assert "api_key" in input_names
        assert "source" in input_names
        assert "generated_fields" in input_names
        assert "instructions" in input_names

    def test_should_have_dataframe_output(self):
        """Test that component has DataFrame output."""
        output_names = {o.name for o in SemanticAggregator.outputs}
        assert "states" in output_names

    def test_should_have_provider_specific_inputs(self):
        """Test that component has provider-specific inputs."""
        input_names = {i.name for i in SemanticAggregator.inputs}

        assert "base_url_ibm_watsonx" in input_names
        assert "project_id" in input_names
        assert "ollama_base_url" in input_names

    def test_should_have_model_input_with_real_time_refresh(self):
        """Test that model input has real_time_refresh enabled."""
        model_input = next((i for i in SemanticAggregator.inputs if i.name == "model"), None)
        assert model_input is not None
        assert model_input.real_time_refresh is True

    def test_should_have_generated_fields_with_table_schema(self):
        """Test that generated_fields input has table_schema defined."""
        fields_input = next((i for i in SemanticAggregator.inputs if i.name == "generated_fields"), None)
        assert fields_input is not None
        assert fields_input.table_schema is not None
        assert len(fields_input.table_schema) > 0

        field_names = {field["name"] for field in fields_input.table_schema}
        assert "name" in field_names
        assert "description" in field_names
        assert "type" in field_names
        assert "multiple" in field_names

    def test_should_have_instructions_as_advanced(self):
        """Test that instructions input is marked as advanced."""
        instructions_input = next((i for i in SemanticAggregator.inputs if i.name == "instructions"), None)
        assert instructions_input is not None
        assert instructions_input.advanced is True

    def test_should_have_api_key_as_advanced(self):
        """Test that api_key input is marked as advanced."""
        api_key_input = next((i for i in SemanticAggregator.inputs if i.name == "api_key"), None)
        assert api_key_input is not None
        assert api_key_input.advanced is True

    def test_should_have_source_as_required(self):
        """Test that source input is marked as required."""
        source_input = next((i for i in SemanticAggregator.inputs if i.name == "source"), None)
        assert source_input is not None
        assert source_input.required is True

    def test_should_have_output_with_correct_method(self):
        """Test that output has correct method name."""
        output = next((o for o in SemanticAggregator.outputs if o.name == "states"), None)
        assert output is not None
        assert output.method == "semantic_aggregation"
