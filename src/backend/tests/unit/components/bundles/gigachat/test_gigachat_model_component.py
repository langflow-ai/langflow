import pytest
from langchain_gigachat import GigaChat
from lfx.components.gigachat.gigachat_models import GigaChatComponent
from lfx.custom import Component
from lfx.custom.utils import build_custom_component_template

from tests.base import ComponentTestBaseWithoutClient


class TestGigaChatComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return GigaChatComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model": "GigaChat-2",
            "scope": "GIGACHAT_API_PERS",
            "credentials": "test-api-key",
            "timeout": 700,
            "profanity_check": True,
            "verify_ssl_certs": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_template(self, component_class, default_kwargs):
        gigachat = component_class(**default_kwargs)
        component = Component(_code=gigachat._code)
        frontend_node, _ = build_custom_component_template(component)

        # Verify basic structure
        assert isinstance(frontend_node, dict)

        # Verify inputs
        assert "template" in frontend_node
        input_names = [input_["name"] for input_ in frontend_node["template"].values() if isinstance(input_, dict)]

        expected_inputs = ["max_tokens", "model", "credentials", "temperature", "repetition_penalty", "top_p"]

        for input_name in expected_inputs:
            assert input_name in input_names

    def test_build_model_integration(self, component_class):
        component = component_class()
        component.model = "GigaChat-2-Max"
        component.base_url = "https://gigachat.devices.sberbank.ru/api/v1"
        model = component.build_model()
        assert isinstance(model, GigaChat)
        assert model.model == "GigaChat-2-Max"
        assert model.base_url == "https://gigachat.devices.sberbank.ru/api/v1"
