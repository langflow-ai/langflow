"""Regression tests for max_tokens propagation through unified models.

Verifies that the Agent/LanguageModel max_tokens field reaches the LLM
constructor with the correct provider-specific parameter name.

Regression: In v1.8.0 the unified models refactor stopped propagating
max_tokens_field_name in the model option metadata returned by
get_language_model_options(). This caused:
  - Google Generative AI: max_output_tokens silently dropped (wrong kwarg name)
  - Anthropic: always used default 1024 (value never overridden)
  - OpenAI: max_tokens absent from payload
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lfx.base.models.model_metadata import MODEL_PROVIDER_METADATA
from lfx.base.models.unified_models import get_language_model_options, get_llm


# ---------------------------------------------------------------------------
# 1. get_language_model_options must include max_tokens_field_name
# ---------------------------------------------------------------------------

class TestModelOptionsIncludeMaxTokensFieldName:
    """Every provider option returned by get_language_model_options must carry
    the provider's max_tokens_field_name so that get_llm can map the generic
    'max_tokens' input to the correct LLM constructor kwarg."""

    def test_all_provider_options_have_max_tokens_field_name(self):
        """Each model option must include max_tokens_field_name in metadata."""
        options = get_language_model_options(user_id=None)

        # Group by provider to give a clear failure message
        providers_seen: set[str] = set()
        for opt in options:
            provider = opt.get("provider")
            metadata = opt.get("metadata", {})

            # Skip disabled-provider sentinel entries
            if metadata.get("is_disabled_provider"):
                continue

            providers_seen.add(provider)
            assert "max_tokens_field_name" in metadata, (
                f"Option '{opt.get('name')}' from provider '{provider}' "
                "is missing 'max_tokens_field_name' in its metadata"
            )

        # Sanity: we actually checked real providers
        assert len(providers_seen) > 0, "No model options were returned"

    @pytest.mark.parametrize(
        "provider,expected_field",
        [
            ("OpenAI", "max_tokens"),
            ("Anthropic", "max_tokens"),
            ("Google Generative AI", "max_output_tokens"),
            ("Ollama", "max_tokens"),
            ("IBM WatsonX", "max_tokens"),
        ],
    )
    def test_provider_max_tokens_field_name_matches_metadata(
        self, provider: str, expected_field: str
    ):
        """The max_tokens_field_name in options must match MODEL_PROVIDER_METADATA."""
        options = get_language_model_options(user_id=None)
        provider_options = [
            o for o in options
            if o.get("provider") == provider
            and not o.get("metadata", {}).get("is_disabled_provider")
        ]

        if not provider_options:
            pytest.skip(f"No options returned for provider '{provider}'")

        for opt in provider_options:
            actual = opt["metadata"]["max_tokens_field_name"]
            assert actual == expected_field, (
                f"Model '{opt['name']}' ({provider}): "
                f"max_tokens_field_name='{actual}', expected '{expected_field}'"
            )


# ---------------------------------------------------------------------------
# 2. get_llm must pass max_tokens under the correct provider-specific kwarg
# ---------------------------------------------------------------------------

class TestGetLlmMaxTokensKwarg:
    """get_llm must translate the generic max_tokens value into the correct
    provider-specific constructor kwarg (e.g. max_output_tokens for Google)."""

    @staticmethod
    def _make_model_selection(
        provider: str, model_name: str = "test-model"
    ) -> list[dict]:
        """Build a minimal model selection list as the Agent would pass to get_llm."""
        provider_meta = MODEL_PROVIDER_METADATA.get(provider, {})
        mapping = provider_meta.get("mapping", {})
        metadata = {
            "model_class": mapping.get("model_class", "ChatOpenAI"),
            "model_name_param": mapping.get("model_param", "model"),
            "api_key_param": "api_key",
        }
        # Include max_tokens_field_name (the fix under test)
        if "max_tokens_field_name" in provider_meta:
            metadata["max_tokens_field_name"] = provider_meta["max_tokens_field_name"]
        return [{"name": model_name, "provider": provider, "metadata": metadata}]

    @pytest.mark.parametrize(
        "provider,expected_kwarg",
        [
            ("OpenAI", "max_tokens"),
            ("Anthropic", "max_tokens"),
            ("Google Generative AI", "max_output_tokens"),
        ],
    )
    def test_max_tokens_kwarg_name_per_provider(
        self, provider: str, expected_kwarg: str
    ):
        """get_llm must pass the user's max_tokens value under the correct kwarg."""
        model_selection = self._make_model_selection(provider)
        model_class_name = model_selection[0]["metadata"]["model_class"]

        mock_cls = MagicMock()
        with (
            patch(
                "lfx.base.models.unified_models.get_model_class",
                return_value=mock_cls,
            ),
            patch(
                "lfx.base.models.unified_models.get_api_key_for_provider",
                return_value="fake-key",
            ),
        ):
            get_llm(
                model=model_selection,
                user_id=None,
                api_key="fake-key",
                max_tokens=4096,
            )

        # The model class should have been called once
        mock_cls.assert_called_once()
        call_kwargs = mock_cls.call_args[1]

        assert expected_kwarg in call_kwargs, (
            f"Expected kwarg '{expected_kwarg}' not found in constructor call "
            f"for provider '{provider}'. Got: {list(call_kwargs.keys())}"
        )
        assert call_kwargs[expected_kwarg] == 4096

    def test_max_tokens_not_passed_when_none(self):
        """When max_tokens is None, no max_tokens kwarg should be passed."""
        model_selection = self._make_model_selection("OpenAI")

        mock_cls = MagicMock()
        with (
            patch(
                "lfx.base.models.unified_models.get_model_class",
                return_value=mock_cls,
            ),
            patch(
                "lfx.base.models.unified_models.get_api_key_for_provider",
                return_value="fake-key",
            ),
        ):
            get_llm(
                model=model_selection,
                user_id=None,
                api_key="fake-key",
                max_tokens=None,
            )

        call_kwargs = mock_cls.call_args[1]
        assert "max_tokens" not in call_kwargs
        assert "max_output_tokens" not in call_kwargs

    def test_max_tokens_not_passed_when_zero(self):
        """When max_tokens is 0, it should be treated as unset."""
        model_selection = self._make_model_selection("OpenAI")

        mock_cls = MagicMock()
        with (
            patch(
                "lfx.base.models.unified_models.get_model_class",
                return_value=mock_cls,
            ),
            patch(
                "lfx.base.models.unified_models.get_api_key_for_provider",
                return_value="fake-key",
            ),
        ):
            get_llm(
                model=model_selection,
                user_id=None,
                api_key="fake-key",
                max_tokens=0,
            )

        call_kwargs = mock_cls.call_args[1]
        # 0 does not satisfy >= 1, so it should not be passed
        assert "max_tokens" not in call_kwargs

    def test_get_llm_falls_back_to_provider_metadata(self):
        """Even if max_tokens_field_name is missing from model metadata,
        get_llm should fall back to MODEL_PROVIDER_METADATA."""
        # Build a model selection WITHOUT max_tokens_field_name in metadata
        model_selection = [{
            "name": "gemini-2.0-flash",
            "provider": "Google Generative AI",
            "metadata": {
                "model_class": "ChatGoogleGenerativeAIFixed",
                "model_name_param": "model",
                "api_key_param": "google_api_key",
                # intentionally omit max_tokens_field_name
            },
        }]

        mock_cls = MagicMock()
        with (
            patch(
                "lfx.base.models.unified_models.get_model_class",
                return_value=mock_cls,
            ),
            patch(
                "lfx.base.models.unified_models.get_api_key_for_provider",
                return_value="fake-key",
            ),
        ):
            get_llm(
                model=model_selection,
                user_id=None,
                api_key="fake-key",
                max_tokens=2048,
            )

        call_kwargs = mock_cls.call_args[1]
        # Should fall back to "max_output_tokens" from MODEL_PROVIDER_METADATA
        assert "max_output_tokens" in call_kwargs, (
            "get_llm should fall back to MODEL_PROVIDER_METADATA for "
            "max_tokens_field_name when it is missing from model metadata"
        )
        assert call_kwargs["max_output_tokens"] == 2048
