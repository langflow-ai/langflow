"""Temperature 0 is in range for the Cohere component and must reach ChatCohere.

``inputs`` declares ``range_spec=RangeSpec(min=0, max=2, step=0.01)``, so 0 is a value
the UI offers. ``temperature or 0.75`` reads that 0 as "unset" and substitutes the
default, so a deliberately deterministic model is built as a creative one.
"""

from unittest.mock import patch

import pytest

pytest.importorskip("lfx_cohere")


def _build(temperature):
    from lfx_cohere.components.cohere.cohere_models import CohereComponent

    component = CohereComponent()
    component._attributes = {
        "cohere_api_key": "co-test-key",  # pragma: allowlist secret
        "temperature": temperature,
    }
    with patch("lfx_cohere.components.cohere.cohere_models.ChatCohere", create=True) as mock_cls:
        component.build_model()
    return mock_cls.call_args.kwargs


def test_zero_temperature_reaches_the_provider():
    assert _build(0.0)["temperature"] == 0.0


def test_unset_temperature_still_falls_back():
    assert _build(None)["temperature"] == 0.75
