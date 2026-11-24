"""LE-2551 / H1-3984888 — provider install hints must name real PyPI packages.

Five "integration not installed" error messages in
``lfx.base.models.model_input_constants`` told users to run
``pip install <name>`` where ``<name>`` does not exist on PyPI, while the
genuine LangChain integration ships under a different name. A developer who
copied the suggested command would install from a PyPI project that is
currently unregistered — if such a name were later registered by a third
party, the same command would install attacker-controlled code.

Wrong (404 on PyPI) -> correct (200 on PyPI):

- ``langchain-ibm-watsonx`` -> ``langchain-ibm``
- ``langchain-google-generative-ai`` -> ``langchain-google-genai``
- ``langchain-azure-openai`` -> ``langchain-openai``
- ``langchain-nvidia`` -> ``langchain-nvidia-ai-endpoints``
- ``langchain-amazon-bedrock`` -> ``langchain-aws``

The correct names also match the actual dependencies declared by the provider
bundles (e.g. ``src/bundles/amazon/pyproject.toml`` depends on
``langchain-aws``, ``src/bundles/ibm/pyproject.toml`` on ``langchain-ibm``).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from lfx.base.models import model_input_constants

# (helper, component module whose absence triggers the hint, wrong name, correct name)
PROVIDER_CASES = [
    (
        model_input_constants._get_watsonx_inputs_and_fields,
        "lfx.components.ibm.watsonx",
        "langchain-ibm-watsonx",
        "langchain-ibm",
    ),
    (
        model_input_constants._get_google_generative_ai_inputs_and_fields,
        "lfx.components.google.google_generative_ai",
        "langchain-google-generative-ai",
        "langchain-google-genai",
    ),
    (
        model_input_constants._get_azure_inputs_and_fields,
        "lfx.components.azure.azure_openai",
        "langchain-azure-openai",
        "langchain-openai",
    ),
    (
        model_input_constants._get_nvidia_inputs_and_fields,
        "lfx.components.nvidia.nvidia",
        "langchain-nvidia",
        "langchain-nvidia-ai-endpoints",
    ),
    (
        model_input_constants._get_amazon_bedrock_inputs_and_fields,
        "lfx_amazon.components.amazon.amazon_bedrock_model",
        "langchain-amazon-bedrock",
        "langchain-aws",
    ),
]

UNREGISTERED_NAMES = [wrong for _, _, wrong, _ in PROVIDER_CASES]


class TestProviderInstallHints:
    """Each missing-provider ImportError must name the exact PyPI distribution."""

    @pytest.mark.parametrize(
        ("helper", "module", "wrong_name", "correct_name"),
        PROVIDER_CASES,
        ids=["watsonx", "google-generative-ai", "azure-openai", "nvidia", "amazon-bedrock"],
    )
    def test_error_message_names_real_pypi_package(self, helper, module, wrong_name, correct_name):
        # A None entry in sys.modules makes the import of `module` raise ImportError.
        with patch.dict(sys.modules, {module: None}), pytest.raises(ImportError) as excinfo:
            helper()

        message = str(excinfo.value)
        assert f"pip install {correct_name}`" in message
        assert f"pip install {wrong_name}`" not in message

    def test_module_source_contains_no_unregistered_package_names(self):
        """Guard against reintroducing any of the five unregistered names anywhere in the module."""
        source = Path(model_input_constants.__file__).read_text(encoding="utf-8")
        for name in UNREGISTERED_NAMES:
            assert f"pip install {name}`" not in source, (
                f"unregistered PyPI package name {name!r} present in module source"
            )
