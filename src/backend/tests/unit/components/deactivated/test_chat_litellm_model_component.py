import pytest

from langflow.components.deactivated.chat_litellm_model import ChatLiteLLMModelComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestChatLiteLLMModelComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ChatLiteLLMModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Hello, how are you?",
            "model": "gpt-3.5-turbo",
            "api_key": "test_api_key",
            "provider": "OpenAI",
            "temperature": 0.7,
            "kwargs": {},
            "model_kwargs": {},
            "top_p": 0.5,
            "top_k": 35,
            "n": 1,
            "max_tokens": 256,
            "max_retries": 6,
            "verbose": False,
            "stream": False,
            "system_message": "You are a helpful assistant.",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "chat_lite_llm", "file_name": "ChatLiteLLMModelComponent"},
        ]

    async def test_build_model_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None
        assert isinstance(model, LanguageModel)

    async def test_build_model_missing_azure_fields(self, component_class):
        component = component_class(
            input_value="Hello",
            model="gpt-3.5-turbo",
            provider="Azure",
            api_key="test_api_key",
            kwargs={},
            model_kwargs={},
        )
        with pytest.raises(ValueError, match="Missing api_base on kwargs"):
            component.build_model()

        component.model_kwargs = {"api_version": "2021-06-01"}
        with pytest.raises(ValueError, match="Missing api_base on kwargs"):
            component.build_model()

    async def test_import_error_handling(self, component_class, default_kwargs):
        with pytest.patch("langflow.components.chat_lite_llm.litellm", side_effect=ImportError):
            component = component_class(**default_kwargs)
            with pytest.raises(ChatLiteLLMException, match="Could not import litellm python package"):
                component.build_model()
