"""Temperature 0 is in range for the Ollama component and must reach ChatOllama.

``inputs`` declares ``range_spec=RangeSpec(min=0, max=1, step=0.01)``, so 0 is a value
the UI offers. ``self.temperature or None`` turns that 0 into ``None``, the parameter
is then dropped by the ``v is not None`` filter, and Ollama falls back to its own
sampling default instead of running greedily.
"""

from unittest.mock import patch

import pytest

pytest.importorskip("lfx_ollama")


def _build(temperature):
    from lfx_ollama.components.ollama.ollama import ChatOllamaComponent

    component = ChatOllamaComponent()
    component._attributes = {
        "base_url": "http://localhost:11434",
        "model_name": "llama3",
        "temperature": temperature,
        "mirostat": "Disabled",
        "mirostat_eta": None,
        "mirostat_tau": None,
        "enable_structured_output": False,
        "metadata": None,
        "tags": None,
        "num_ctx": None,
        "num_gpu": None,
        "num_thread": None,
        "repeat_last_n": None,
        "repeat_penalty": None,
        "stop_tokens": None,
        "system": None,
        "tfs_z": None,
        "timeout": None,
        "top_k": None,
        "top_p": None,
        "enable_verbose_output": False,
        "template": None,
        "headers": None,
    }
    with patch("lfx_ollama.components.ollama.ollama.ChatOllama", create=True) as mock_cls:
        component.build_model()
    return mock_cls.call_args.kwargs


def test_zero_temperature_reaches_the_provider():
    assert _build(0.0)["temperature"] == 0.0


def test_unset_temperature_is_dropped():
    assert "temperature" not in _build(None)
