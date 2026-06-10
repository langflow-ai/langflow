from unittest.mock import MagicMock

import pytest
from lfx.components.perplexity.perplexity import PerplexityComponent
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template
from lfx.inputs.inputs import DropdownInput, FloatInput, IntInput, SecretStrInput, SliderInput

from tests.base import ComponentTestBaseWithoutClient


class TestPerplexityComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return PerplexityComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "dummy-key",  # pragma: allowlist secret
            "model_name": "llama-3.1-sonar-small-128k-online",
            "temperature": 0.75,
            "max_tokens": 50,
        }

    @pytest.fixture
    def file_names_mapping(self):
        # No historical version snapshots to validate this component against.
        return []

    def test_initialization(self, component_class):
        component = component_class()
        assert component.display_name == "Perplexity"
        assert component.description == "Generate text using Perplexity LLMs."
        assert component.icon == "Perplexity"
        # The class name / identifier must remain stable: it keys saved flows.
        assert component.name == "PerplexityModel"

    def test_inputs(self):
        inputs = {inp.name: inp for inp in PerplexityComponent().inputs}
        assert isinstance(inputs["model_name"], DropdownInput)
        assert isinstance(inputs["api_key"], SecretStrInput)
        assert isinstance(inputs["temperature"], SliderInput)
        assert isinstance(inputs["max_tokens"], IntInput)
        assert isinstance(inputs["top_p"], FloatInput)
        assert isinstance(inputs["n"], IntInput)
        assert inputs["api_key"].required is True
        assert inputs["model_name"].value == "llama-3.1-sonar-small-128k-online"
        assert "llama-3.1-sonar-small-128k-online" in inputs["model_name"].options

    def test_template(self, default_kwargs):
        component = PerplexityComponent(**default_kwargs)
        frontend_node, _ = build_custom_component_template(Component(_code=component._code))
        assert isinstance(frontend_node, dict)
        assert "template" in frontend_node
        input_names = [inp["name"] for inp in frontend_node["template"].values() if isinstance(inp, dict)]
        for expected in ["model_name", "api_key", "temperature", "max_tokens", "top_p", "n"]:
            assert expected in input_names

    def test_build_model(self, component_class, default_kwargs, mocker):
        # Regression guard for the langchain-community 0.4.2 migration: ChatPerplexity
        # moved out of langchain_community.chat_models into the standalone
        # langchain_perplexity package. build_model must construct that class with the
        # inputs mapped onto its kwargs.
        mock_chat = mocker.patch("lfx.components.perplexity.perplexity.ChatPerplexity", return_value=MagicMock())
        component = component_class(**default_kwargs)
        component.top_p = 0.9
        component.n = 2

        model = component.build_model()

        mock_chat.assert_called_once_with(
            model="llama-3.1-sonar-small-128k-online",
            temperature=0.75,
            pplx_api_key="dummy-key",
            top_p=0.9,
            n=2,
            max_tokens=50,
        )
        assert model is mock_chat.return_value

    def test_build_model_applies_defaults(self, component_class, mocker):
        # top_p falls back to None and n falls back to 1 when left unset; a falsy
        # temperature falls back to 0.75.
        mock_chat = mocker.patch("lfx.components.perplexity.perplexity.ChatPerplexity", return_value=MagicMock())
        component = component_class(api_key="dummy-key", model_name="llama-3.1-8b-instruct", max_tokens=10)
        component.temperature = 0
        component.top_p = None
        component.n = None

        component.build_model()

        _, kwargs = mock_chat.call_args
        assert kwargs["top_p"] is None
        assert kwargs["n"] == 1
        assert kwargs["temperature"] == 0.75
        assert kwargs["pplx_api_key"] == "dummy-key"
