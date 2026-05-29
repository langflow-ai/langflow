"""Bug 2 [P1] — get_llm error messages must point users to the real fix.

The pre-fix template at
``lfx.base.models.unified_models.instantiation.get_llm`` reads::

    {provider} API key is required when using {provider} provider.
    Please provide it in the component or configure it globally as {variable_name}.

Two failure modes drop user-actionable context:

1. ``provider`` arrives as literal ``"Unknown"`` (or empty/None) because
   the frontend ``ModelInputComponent`` falls back to ``provider: "Unknown"``
   when a model option lacks a provider — see
   ``src/frontend/.../modelInputComponent/index.tsx`` and the live
   reproduction in ``PR-12575-bug-2-backend-log.txt``. The template then
   emits the literal ``Unknown API key is required when using Unknown
   provider. Please provide it in the component or configure it globally
   as UNKNOWN_API_KEY.``, which gives zero hint about what to do.

2. The user (or the assistant) passed a custom variable name as
   ``api_key`` (e.g. ``"MY_GOOGLE_KEY"``) and the resolver couldn't find
   it. The template rebuilds the canonical variable name
   (``GOOGLE_API_KEY``), losing the reference the user actually tried —
   so a typo in the variable name becomes invisible.

Reference: PR-12575 OPEN BUG #2 backend log
``ValueError: Unknown API key is required when using Unknown provider.
Please provide it in the component or configure it globally as
UNKNOWN_API_KEY.``
"""

from __future__ import annotations

from unittest.mock import patch

import lfx.base.models.unified_models as unified_models_module
import pytest
from lfx.base.models.unified_models.instantiation import get_llm


def _model(provider: str | None, *, name: str = "gemini-3.5-flash") -> list[dict]:
    """Build a minimal model dict with the given provider for get_llm."""
    return [
        {
            "name": name,
            "provider": provider,
            "icon": "GoogleGenerativeAI",
            "metadata": {
                "api_key_param": "google_api_key",
                "model_class": "ChatGoogleGenerativeAI",
                "model_name_param": "model",
            },
        }
    ]


class TestGetLlmInvalidProviderMessage:
    """Bug 2 — provider arriving as 'Unknown'/empty/None must NOT yield the broken template."""

    @pytest.mark.parametrize("invalid_provider", ["Unknown", "", None])
    def test_should_point_user_to_reselect_when_provider_is_invalid(self, invalid_provider):
        """Post-fix message must instruct the user to reselect the model in the dropdown."""
        with (
            patch.object(unified_models_module, "get_api_key_for_provider", return_value=None),
            pytest.raises(ValueError, match="reselect a model"),
        ):
            get_llm(model=_model(invalid_provider), user_id=None, api_key="GOOGLE_API_KEY")


class TestGetLlmInvalidProviderMessageStrings:
    """Companion suite that asserts pre-fix template markers are gone from the message."""

    @pytest.mark.parametrize("invalid_provider", ["Unknown", "", None])
    def test_message_strips_pre_fix_template_markers(self, invalid_provider):
        """Regression-marker assertions on the captured error string."""
        with patch.object(unified_models_module, "get_api_key_for_provider", return_value=None):
            try:
                get_llm(model=_model(invalid_provider), user_id=None, api_key="GOOGLE_API_KEY")
                pytest.fail("Expected ValueError to be raised by get_llm")
            except ValueError as e:
                msg = str(e)

        assert "Unknown API key is required" not in msg, f"Pre-fix 'Unknown API key' template leaked through: {msg!r}"
        assert "UNKNOWN_API_KEY" not in msg, f"Pre-fix 'UNKNOWN_API_KEY' fallback leaked through: {msg!r}"
        assert " API key is required when using  provider" not in msg, (
            f"Pre-fix empty-provider template leaked through: {msg!r}"
        )
        assert "model" in msg.lower(), f"Expected message to mention model selection, got: {msg!r}"


class TestGetLlmPreservesReferencedVariableName:
    """Bug 2 — error must name the variable the user tried, not the canonical key."""

    def test_should_name_user_variable_when_custom_api_key_var_does_not_resolve(self):
        """Error must reference the user-supplied variable so the user can fix it."""
        with (
            patch.object(unified_models_module, "get_api_key_for_provider", return_value=None),
            pytest.raises(ValueError, match="MY_CUSTOM_GOOGLE_KEY"),
        ):
            get_llm(
                model=_model("Google Generative AI"),
                user_id=None,
                api_key="MY_CUSTOM_GOOGLE_KEY",
            )

    def test_should_keep_canonical_message_when_no_api_key_was_provided(self):
        """Characterization: ``api_key`` is None → existing canonical message path is unchanged."""
        with (
            patch.object(unified_models_module, "get_api_key_for_provider", return_value=None),
            pytest.raises(ValueError, match="GOOGLE_API_KEY"),
        ):
            get_llm(model=_model("Google Generative AI"), user_id=None, api_key=None)
