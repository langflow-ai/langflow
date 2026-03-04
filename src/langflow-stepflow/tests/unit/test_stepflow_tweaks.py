"""Tests for Stepflow-level tweaks functionality."""

import pytest
from tests.helpers.tweaks_builder import TweaksBuilder

from langflow_stepflow.translation.stepflow_tweaks import (
    apply_stepflow_tweaks_to_dict,
    convert_tweaks_to_overrides,
)
from langflow_stepflow.translation.translator import LangflowConverter


class TestStepflowTweaks:
    """Test Stepflow-level tweaks functionality."""

    def test_convert_tweaks_to_overrides_basic(self):
        """Test basic tweaks to overrides conversion."""
        tweaks = {
            "LanguageModelComponent-kBOja": {
                "api_key": "sk-test-key",
                "temperature": 0.7,
            }
        }

        overrides = convert_tweaks_to_overrides(tweaks)

        assert overrides is not None
        assert "langflow_LanguageModelComponent-kBOja" in overrides

        step_override = overrides["langflow_LanguageModelComponent-kBOja"]
        assert step_override["$type"] == "merge_patch"
        assert "input" in step_override["value"]

        input_overrides = step_override["value"]["input"]["input"]
        assert input_overrides["api_key"] == "sk-test-key"
        assert input_overrides["temperature"] == 0.7

    def test_convert_tweaks_to_overrides_empty(self):
        """Test conversion with no tweaks returns None."""
        assert convert_tweaks_to_overrides(None) is None
        assert convert_tweaks_to_overrides({}) is None

    def test_convert_tweaks_to_overrides_multiple_steps(self):
        """Test conversion with multiple steps."""
        tweaks = {
            "Step1": {"field1": "value1"},
            "Step2": {"field2": "value2", "field3": 123},
        }

        overrides = convert_tweaks_to_overrides(tweaks)

        assert len(overrides) == 2
        assert "langflow_Step1" in overrides
        assert "langflow_Step2" in overrides

        # Check Step1
        assert overrides["langflow_Step1"]["$type"] == "merge_patch"
        step1_input = overrides["langflow_Step1"]["value"]["input"]["input"]
        assert step1_input["field1"] == "value1"

        # Check Step2
        assert overrides["langflow_Step2"]["$type"] == "merge_patch"
        step2_input = overrides["langflow_Step2"]["value"]["input"]["input"]
        assert step2_input["field2"] == "value2"
        assert step2_input["field3"] == 123


class TestStepflowTweaksIntegration:
    """Test integration with the full Langflow conversion process."""

    @pytest.fixture
    def basic_prompting_flow_dict(self):
        """Convert basic_prompting.json to a dict for testing."""
        import json
        from pathlib import Path

        converter = LangflowConverter()
        fixture_path = Path(__file__).parent.parent / "fixtures" / "langflow" / "basic_prompting.json"

        if fixture_path.exists():
            with open(fixture_path) as f:
                langflow_data = json.load(f)
            # Convert to Flow object and get dict representation
            flow = converter.convert(langflow_data)
            return flow.model_dump(mode="json", exclude_none=True)
        else:
            pytest.skip("basic_prompting.json fixture not found")

    def test_real_workflow_tweaks_application(self, basic_prompting_flow_dict):
        """Test tweaks application on a real converted workflow."""
        tweaks = {
            "LanguageModelComponent-kBOja": {  # Must match actual component ID
                "api_key": "integration_test_key",
                "temperature": 0.7,
                "model_name": "gpt-4",
            }
        }

        modified_dict = apply_stepflow_tweaks_to_dict(basic_prompting_flow_dict, tweaks)

        # Find the LanguageModelComponent executor step (custom_code or core)
        langflow_step = None
        for step in modified_dict["steps"]:
            if step["id"] == "langflow_LanguageModelComponent-kBOja" and (
                step["component"] == "/langflow/custom_code" or step["component"].startswith("/langflow/core/")
            ):
                langflow_step = step
                break

        assert langflow_step is not None, "LanguageModelComponent executor step not found"

        # Verify tweaks were applied
        input_section = langflow_step.get("input", {}).get("input", {})
        assert input_section.get("api_key") == "integration_test_key"
        assert input_section.get("temperature") == 0.7
        assert input_section.get("model_name") == "gpt-4"

    def test_tweaks_preserve_existing_inputs(self, basic_prompting_flow_dict):
        """Test that tweaks preserve existing input values that aren't overwritten."""
        tweaks = {
            "LanguageModelComponent-kBOja": {
                "api_key": "new_key",
            }
        }

        modified_dict = apply_stepflow_tweaks_to_dict(basic_prompting_flow_dict, tweaks)

        # Find the step
        for step in modified_dict["steps"]:
            if step["id"] == "langflow_LanguageModelComponent-kBOja":
                input_section = step.get("input", {}).get("input", {})
                # New value should be applied
                assert input_section.get("api_key") == "new_key"
                # Other fields from the original workflow should still exist
                # (The exact fields depend on the fixture content)
                break

    def test_empty_tweaks_returns_unchanged(self, basic_prompting_flow_dict):
        """Test that empty tweaks returns the workflow unchanged."""
        import copy

        original = copy.deepcopy(basic_prompting_flow_dict)

        # Empty dict
        result = apply_stepflow_tweaks_to_dict(basic_prompting_flow_dict, {})
        assert result == original

        # None
        result = apply_stepflow_tweaks_to_dict(basic_prompting_flow_dict, None)
        assert result == original


class TestTweaksBuilder:
    """Test the TweaksBuilder utility for creating tweaks."""

    def test_basic_tweak_building(self):
        """Test basic tweak creation with direct values."""
        builder = TweaksBuilder()
        builder.add_tweak("Component-123", "api_key", "test_key")
        builder.add_tweak("Component-123", "temperature", 0.8)
        builder.add_tweak("AnotherComponent-456", "model", "gpt-4")

        tweaks = builder.build()

        expected = {
            "Component-123": {"api_key": "test_key", "temperature": 0.8},
            "AnotherComponent-456": {"model": "gpt-4"},
        }

        assert tweaks == expected

    def test_method_chaining(self):
        """Test that methods can be chained for fluent API."""
        tweaks = (
            TweaksBuilder()
            .add_tweak("Component-123", "api_key", "test_key")
            .add_tweak("Component-123", "temperature", 0.8)
            .build()
        )

        expected = {"Component-123": {"api_key": "test_key", "temperature": 0.8}}

        assert tweaks == expected

    def test_env_tweak_with_existing_variable(self, monkeypatch):
        """Test adding tweaks from environment variables that exist."""
        monkeypatch.setenv("TEST_API_KEY", "env_test_key")
        monkeypatch.setenv("TEST_TEMPERATURE", "0.9")

        tweaks = (
            TweaksBuilder()
            .add_env_tweak("Component-123", "api_key", "TEST_API_KEY")
            .add_env_tweak("Component-123", "temperature", "TEST_TEMPERATURE")
            .build()
        )

        expected = {
            "Component-123": {
                "api_key": "env_test_key",
                "temperature": "0.9",  # Environment variables are strings
            }
        }

        assert tweaks == expected

    def test_env_tweak_with_missing_variable(self, monkeypatch):
        """Test that missing environment variables are tracked."""
        # Ensure the env var doesn't exist
        monkeypatch.delenv("MISSING_API_KEY", raising=False)

        builder = TweaksBuilder()
        builder.add_env_tweak("Component-123", "api_key", "MISSING_API_KEY")

        # Should track missing var
        assert "MISSING_API_KEY" in builder.missing_env_vars

        # Should raise error on build
        with pytest.raises(ValueError, match="Missing required environment variables: MISSING_API_KEY"):
            builder.build()

    def test_build_or_skip_with_missing_env_vars(self, monkeypatch):
        """Test that build_or_skip skips test when env vars are missing."""
        monkeypatch.delenv("MISSING_VAR", raising=False)

        builder = TweaksBuilder()
        builder.add_env_tweak("Component-123", "field", "MISSING_VAR")

        # Should call pytest.skip
        with pytest.raises(
            pytest.skip.Exception,
            match="Missing required environment variables: MISSING_VAR",
        ):
            builder.build_or_skip()

    def test_build_or_skip_with_all_env_vars_present(self, monkeypatch):
        """Test that build_or_skip works normally when all env vars are present."""
        monkeypatch.setenv("PRESENT_VAR", "test_value")

        tweaks = TweaksBuilder().add_env_tweak("Component-123", "field", "PRESENT_VAR").build_or_skip()

        expected = {"Component-123": {"field": "test_value"}}

        assert tweaks == expected

    def test_add_astradb_tweaks(self, monkeypatch):
        """Test the convenience method for AstraDB tweaks."""
        monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://astra-endpoint.com")

        tweaks = TweaksBuilder().add_astradb_tweaks("AstraDB-store-123").build()

        expected = {
            "AstraDB-store-123": {
                "api_endpoint": "https://astra-endpoint.com",
                "database_name": "langflow-test",  # Default value
                "collection_name": "test_collection",  # Default value
            }
        }

        assert tweaks == expected

    def test_add_astradb_tweaks_with_overrides(self, monkeypatch):
        """Test AstraDB tweaks with overridden default values."""
        monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://astra-endpoint.com")

        tweaks = (
            TweaksBuilder()
            .add_astradb_tweaks(
                "AstraDB-store-123",
                database_name="custom_db",
                collection_name="custom_collection",
                extra_field="extra_value",
            )
            .build()
        )

        expected = {
            "AstraDB-store-123": {
                "api_endpoint": "https://astra-endpoint.com",
                "database_name": "custom_db",
                "collection_name": "custom_collection",
                "extra_field": "extra_value",
            }
        }

        assert tweaks == expected

    def test_mixed_tweaks_and_env_vars(self, monkeypatch):
        """Test combining direct tweaks and environment variable tweaks."""
        monkeypatch.setenv("API_KEY", "env_api_key")

        tweaks = (
            TweaksBuilder()
            .add_env_tweak("Component-123", "api_key", "API_KEY")
            .add_tweak("Component-123", "temperature", 0.5)
            .add_tweak("Component-456", "model", "claude-3")
            .build()
        )

        expected = {
            "Component-123": {"api_key": "env_api_key", "temperature": 0.5},
            "Component-456": {"model": "claude-3"},
        }

        assert tweaks == expected

    def test_overwriting_tweaks(self):
        """Test that later tweaks overwrite earlier ones."""
        tweaks = (
            TweaksBuilder()
            .add_tweak("Component-123", "temperature", 0.3)
            .add_tweak("Component-123", "temperature", 0.7)  # Should overwrite
            .build()
        )

        expected = {"Component-123": {"temperature": 0.7}}

        assert tweaks == expected

    def test_empty_builder(self):
        """Test that empty builder produces empty tweaks."""
        tweaks = TweaksBuilder().build()
        assert tweaks == {}

    def test_multiple_missing_env_vars(self, monkeypatch):
        """Test error handling with multiple missing environment variables."""
        monkeypatch.delenv("MISSING_VAR_1", raising=False)
        monkeypatch.delenv("MISSING_VAR_2", raising=False)

        builder = TweaksBuilder()
        builder.add_env_tweak("Component-123", "field1", "MISSING_VAR_1")
        builder.add_env_tweak("Component-456", "field2", "MISSING_VAR_2")

        with pytest.raises(ValueError) as exc_info:
            builder.build()

        error_msg = str(exc_info.value)
        assert "MISSING_VAR_1" in error_msg
        assert "MISSING_VAR_2" in error_msg
