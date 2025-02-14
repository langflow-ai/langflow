import pytest

from langflow.components.models import ChatOllamaComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestChatOllamaComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ChatOllamaComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "base_url": "http://localhost:11434",
            "model_name": "example-model",
            "temperature": 0.5,
            "format": "json",
            "metadata": {},
            "mirostat": "Disabled",
            "mirostat_eta": None,
            "mirostat_tau": None,
            "num_ctx": 2048,
            "num_gpu": 1,
            "num_thread": 4,
            "repeat_last_n": 64,
            "repeat_penalty": 1.1,
            "tfs_z": 1.0,
            "timeout": 30,
            "top_k": 40,
            "top_p": 0.9,
            "verbose": True,
            "tags": "test",
            "stop_tokens": "",
            "system": "default",
            "tool_model_enabled": False,
            "template": "Hello, world!",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "chat_ollama", "file_name": "ChatOllama"},
            {"version": "1.1.0", "module": "chat_ollama", "file_name": "chat_ollama"},
        ]

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None

    async def test_is_valid_ollama_url(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        valid_url = await component.is_valid_ollama_url("http://localhost:11434")
        assert valid_url is True

    async def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = await component.update_build_config(build_config, "Mirostat", "mirostat")
        assert updated_config["mirostat_eta"]["advanced"] is False
        assert updated_config["mirostat_tau"]["advanced"] is False

    async def test_get_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        models = await component.get_model("http://localhost:11434")
        assert isinstance(models, list)

    async def test_supports_tool_calling(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        supports_tool = component.supports_tool_calling("llama3.3")
        assert supports_tool is True
