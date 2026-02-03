"""Unit tests for Agentics SemanticFilter component."""

from __future__ import annotations

import pytest
from lfx.components.agentics.semantic_filter import SemanticFilter


@pytest.mark.unit
class TestSemanticFilterComponent:
    """Tests for SemanticFilter component metadata."""

    def test_should_have_correct_display_name(self):
        """Test that component has correct display name."""
        assert SemanticFilter.display_name == "SemanticFilter"

    def test_should_have_correct_icon(self):
        """Test that component has correct icon."""
        assert SemanticFilter.icon == "Agentics"

    def test_should_have_required_inputs(self):
        """Test that component has all required inputs."""
        input_names = {i.name for i in SemanticFilter.inputs}

        assert "model" in input_names
        assert "api_key" in input_names
        assert "source" in input_names
        assert "predicate_template" in input_names
        assert "batch_size" in input_names

    def test_should_have_dataframe_output(self):
        """Test that component has DataFrame output."""
        output_names = {o.name for o in SemanticFilter.outputs}
        assert "states" in output_names

    def test_should_have_provider_specific_inputs(self):
        """Test that component has provider-specific inputs."""
        input_names = {i.name for i in SemanticFilter.inputs}

        assert "base_url_ibm_watsonx" in input_names
        assert "project_id" in input_names
        assert "ollama_base_url" in input_names

    def test_should_have_model_input_with_real_time_refresh(self):
        """Test that model input has real_time_refresh enabled."""
        model_input = next((i for i in SemanticFilter.inputs if i.name == "model"), None)
        assert model_input is not None
        assert model_input.real_time_refresh is True

    def test_should_have_predicate_template_input(self):
        """Test that predicate_template input is configured correctly."""
        predicate_input = next((i for i in SemanticFilter.inputs if i.name == "predicate_template"), None)
        assert predicate_input is not None

    def test_should_have_batch_size_as_advanced(self):
        """Test that batch_size input is marked as advanced."""
        batch_input = next((i for i in SemanticFilter.inputs if i.name == "batch_size"), None)
        assert batch_input is not None
        assert batch_input.advanced is True

    def test_should_have_api_key_as_advanced(self):
        """Test that api_key input is marked as advanced."""
        api_key_input = next((i for i in SemanticFilter.inputs if i.name == "api_key"), None)
        assert api_key_input is not None
        assert api_key_input.advanced is True
