"""Unit tests for Agentics components."""

from __future__ import annotations

import pytest

try:
    import agentics  # noqa: F401
    import crewai  # noqa: F401
except ImportError:
    pytest.skip("agentics-py and crewai not installed", allow_module_level=True)

from lfx.components.agentics import AgenerateComponent, AMapComponent, AreduceComponent
from lfx.components.agentics.constants import (
    TRANSDUCTION_AMAP,
    TRANSDUCTION_AREDUCE,
    TRANSDUCTION_GENERATE,
)
from lfx.components.agentics.inputs.common_inputs import GENERATED_FIELDS_TABLE_SCHEMA


@pytest.mark.unit
class TestAMapComponent:
    """Tests for AMapComponent (aMap) component metadata."""

    def test_should_have_correct_display_name(self):
        """Test that component has correct display name."""
        assert AMapComponent.display_name == "aMap"

    def test_should_have_correct_icon(self):
        """Test that component has correct icon."""
        assert AMapComponent.icon == "Agentics"

    def test_should_have_correct_description(self):
        """Test that component has correct description."""
        assert "augment" in AMapComponent.description.lower()
        assert "dataframe" in AMapComponent.description.lower()

    def test_should_have_required_inputs(self):
        """Test that component has all required inputs."""
        input_names = {i.name for i in AMapComponent.inputs}

        assert "model" in input_names
        assert "api_key" in input_names
        assert "source" in input_names
        assert "schema" in input_names
        assert "instructions" in input_names

    def test_should_have_dataframe_output(self):
        """Test that component has DataFrame output."""
        output_names = {o.name for o in AMapComponent.outputs}
        assert "states" in output_names

    def test_should_have_provider_specific_inputs(self):
        """Test that component has provider-specific inputs."""
        input_names = {i.name for i in AMapComponent.inputs}

        assert "base_url_ibm_watsonx" in input_names
        assert "project_id" in input_names
        assert "ollama_base_url" in input_names

    def test_should_have_valid_transduction_constants(self):
        """Test that transduction type constants are defined."""
        assert TRANSDUCTION_AMAP == "amap"
        assert TRANSDUCTION_AREDUCE == "areduce"
        assert TRANSDUCTION_GENERATE == "generate"

    def test_should_have_model_input_with_real_time_refresh(self):
        """Test that model input has real_time_refresh enabled."""
        model_input = next((i for i in AMapComponent.inputs if i.name == "model"), None)
        assert model_input is not None
        assert model_input.real_time_refresh is True

    def test_should_have_schema_input_with_table_schema(self):
        """Test that schema input has table_schema defined."""
        schema_input = next((i for i in AMapComponent.inputs if i.name == "schema"), None)
        assert schema_input is not None
        assert schema_input.table_schema is not None
        assert len(schema_input.table_schema) > 0

        field_names = {field["name"] for field in schema_input.table_schema}
        assert "name" in field_names
        assert "description" in field_names
        assert "type" in field_names
        assert "multiple" in field_names


@pytest.mark.unit
class TestAreduceComponent:
    """Tests for AreduceComponent (aReduce) component metadata."""

    def test_should_have_correct_display_name(self):
        """Test that component has correct display name."""
        assert AreduceComponent.display_name == "aReduce"

    def test_should_have_correct_icon(self):
        """Test that component has correct icon."""
        assert AreduceComponent.icon == "Agentics"

    def test_should_have_required_inputs(self):
        """Test that component has all required inputs."""
        input_names = {i.name for i in AreduceComponent.inputs}

        assert "model" in input_names
        assert "api_key" in input_names
        assert "source" in input_names
        assert "schema" in input_names

    def test_should_have_states_output(self):
        """Test that component has states output."""
        output_names = {o.name for o in AreduceComponent.outputs}
        assert "states" in output_names


@pytest.mark.unit
class TestAgenerateComponent:
    """Tests for AgenerateComponent (aGenerate) component metadata."""

    def test_should_have_correct_display_name(self):
        """Test that component has correct display name."""
        assert AgenerateComponent.display_name == "aGenerate"

    def test_should_have_correct_icon(self):
        """Test that component has correct icon."""
        assert AgenerateComponent.icon == "Agentics"

    def test_should_have_batch_size_input(self):
        """Test that component has batch_size input."""
        input_names = {i.name for i in AgenerateComponent.inputs}
        assert "batch_size" in input_names

    def test_should_have_states_output(self):
        """Test that component has states output."""
        output_names = {o.name for o in AgenerateComponent.outputs}
        assert "states" in output_names


@pytest.mark.unit
class TestAgenticsSharedSchema:
    """Tests for shared schema structure across Agentics components."""

    def test_generated_fields_schema_has_required_fields(self):
        """Test that GENERATED_FIELDS_TABLE_SCHEMA has required fields."""
        field_names = {field["name"] for field in GENERATED_FIELDS_TABLE_SCHEMA}
        assert "name" in field_names
        assert "description" in field_names
        assert "type" in field_names
        assert "multiple" in field_names
