"""Unit tests for Agentics main component."""

from __future__ import annotations

import pytest
from lfx.components.agentics.agentics import AgenticsComponent
from lfx.components.agentics.constants import (
    TRANSDUCTION_AMAP,
    TRANSDUCTION_AREDUCE,
    TRANSDUCTION_GENERATE,
)


@pytest.mark.unit
class TestAgenticsComponent:
    """Tests for AgenticsComponent metadata."""

    def test_should_have_correct_display_name(self):
        """Test that component has correct display name."""
        assert AgenticsComponent.display_name == "Agentics"

    def test_should_have_correct_icon(self):
        """Test that component has correct icon."""
        assert AgenticsComponent.icon == "Agentics"

    def test_should_have_correct_description(self):
        """Test that component has correct description."""
        assert "among" in AgenticsComponent.description.lower()
        assert "amongs" not in AgenticsComponent.description.lower()

    def test_should_have_required_inputs(self):
        """Test that component has all required inputs."""
        input_names = {i.name for i in AgenticsComponent.inputs}

        assert "model" in input_names
        assert "api_key" in input_names
        assert "source" in input_names
        assert "transduction_type" in input_names
        assert "atype_name" in input_names
        assert "schema" in input_names
        assert "instructions" in input_names
        assert "merge_source" in input_names
        assert "batch_size" in input_names

    def test_should_have_dataframe_output(self):
        """Test that component has DataFrame output."""
        output_names = {o.name for o in AgenticsComponent.outputs}
        assert "states" in output_names

    def test_should_have_provider_specific_inputs(self):
        """Test that component has provider-specific inputs."""
        input_names = {i.name for i in AgenticsComponent.inputs}

        assert "base_url_ibm_watsonx" in input_names
        assert "project_id" in input_names
        assert "ollama_base_url" in input_names

    def test_should_have_valid_transduction_type_options(self):
        """Test that transduction_type dropdown has valid options."""
        transduction_input = next((i for i in AgenticsComponent.inputs if i.name == "transduction_type"), None)
        assert transduction_input is not None
        assert TRANSDUCTION_AMAP in transduction_input.options
        assert TRANSDUCTION_AREDUCE in transduction_input.options
        assert TRANSDUCTION_GENERATE in transduction_input.options

    def test_should_have_model_input_with_real_time_refresh(self):
        """Test that model input has real_time_refresh enabled."""
        model_input = next((i for i in AgenticsComponent.inputs if i.name == "model"), None)
        assert model_input is not None
        assert model_input.real_time_refresh is True

    def test_should_have_schema_input_with_table_schema(self):
        """Test that schema input has table_schema defined."""
        schema_input = next((i for i in AgenticsComponent.inputs if i.name == "schema"), None)
        assert schema_input is not None
        assert schema_input.table_schema is not None
        assert len(schema_input.table_schema) > 0

        field_names = {field["name"] for field in schema_input.table_schema}
        assert "name" in field_names
        assert "description" in field_names
        assert "type" in field_names
        assert "multiple" in field_names
