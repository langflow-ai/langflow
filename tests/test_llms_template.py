from fastapi.testclient import TestClient
from langflow.settings import settings


def test_llms_settings(client: TestClient):
    response = client.get("/all")
    assert response.status_code == 200
    json_response = response.json()
    llms = json_response["llms"]
    assert set(llms.keys()) == set(settings.llms)


def test_hugging_face_hub(client: TestClient):
    response = client.get("/all")
    assert response.status_code == 200
    json_response = response.json()
    language_models = json_response["llms"]

    model = language_models["HuggingFaceHub"]
    template = model["template"]

    assert template["cache"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "cache",
        "type": "bool",
        "list": False,
    }
    assert template["verbose"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": False,
        "password": False,
        "name": "verbose",
        "type": "bool",
        "list": False,
    }
    assert template["client"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "client",
        "type": "Any",
        "list": False,
    }
    assert template["repo_id"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "gpt2",
        "password": False,
        "name": "repo_id",
        "type": "str",
        "list": False,
    }
    assert template["task"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "task",
        "type": "str",
        "list": False,
    }
    assert template["model_kwargs"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "model_kwargs",
        "type": "code",
        "list": False,
    }
    assert template["huggingfacehub_api_token"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": True,
        "name": "huggingfacehub_api_token",
        "type": "str",
        "list": False,
    }


def test_openai(client: TestClient):
    response = client.get("/all")
    assert response.status_code == 200
    json_response = response.json()
    language_models = json_response["llms"]

    model = language_models["OpenAI"]
    template = model["template"]

    assert template["cache"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "cache",
        "type": "bool",
        "list": False,
    }
    assert template["verbose"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "verbose",
        "type": "bool",
        "list": False,
    }
    assert template["client"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "client",
        "type": "Any",
        "list": False,
    }
    assert template["model_name"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "text-davinci-003",
        "password": False,
        "options": [
            "text-davinci-003",
            "text-davinci-002",
            "text-curie-001",
            "text-babbage-001",
            "text-ada-001",
        ],
        "name": "model_name",
        "type": "str",
        "list": True,
    }
    # Add more assertions for other properties here
    assert template["temperature"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": 0.7,
        "password": False,
        "name": "temperature",
        "type": "float",
        "list": False,
    }
    assert template["max_tokens"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": 256,
        "password": True,
        "name": "max_tokens",
        "type": "int",
        "list": False,
    }
    assert template["top_p"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 1,
        "password": False,
        "name": "top_p",
        "type": "float",
        "list": False,
    }
    assert template["frequency_penalty"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 0,
        "password": False,
        "name": "frequency_penalty",
        "type": "float",
        "list": False,
    }
    assert template["presence_penalty"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 0,
        "password": False,
        "name": "presence_penalty",
        "type": "float",
        "list": False,
    }
    assert template["n"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 1,
        "password": False,
        "name": "n",
        "type": "int",
        "list": False,
    }
    assert template["best_of"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 1,
        "password": False,
        "name": "best_of",
        "type": "int",
        "list": False,
    }
    assert template["model_kwargs"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "model_kwargs",
        "type": "code",
        "list": False,
    }
    assert template["openai_api_key"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "",
        "password": True,
        "name": "openai_api_key",
        "display_name": "OpenAI API Key",
        "type": "str",
        "list": False,
    }
    assert template["batch_size"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 20,
        "password": False,
        "name": "batch_size",
        "type": "int",
        "list": False,
    }
    assert template["request_timeout"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "request_timeout",
        "type": "Union[float, Tuple[float, float], NoneType]",
        "list": False,
    }
    assert template["logit_bias"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "logit_bias",
        "type": "code",
        "list": False,
    }
    assert template["max_retries"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 6,
        "password": False,
        "name": "max_retries",
        "type": "int",
        "list": False,
    }
    assert template["streaming"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": False,
        "password": False,
        "name": "streaming",
        "type": "bool",
        "list": False,
    }


def test_chat_open_ai(client: TestClient):
    response = client.get("/all")
    assert response.status_code == 200
    json_response = response.json()
    language_models = json_response["llms"]

    model = language_models["ChatOpenAI"]
    template = model["template"]

    assert template["verbose"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": False,
        "password": False,
        "name": "verbose",
        "type": "bool",
        "list": False,
    }
    assert template["client"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "client",
        "type": "Any",
        "list": False,
    }
    assert template["model_name"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "gpt-3.5-turbo",
        "password": False,
        "options": ["gpt-3.5-turbo", "gpt-4", "gpt-4-32k"],
        "name": "model_name",
        "type": "str",
        "list": True,
    }
    assert template["temperature"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": 0.7,
        "password": False,
        "name": "temperature",
        "type": "float",
        "list": False,
    }
    assert template["model_kwargs"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "model_kwargs",
        "type": "code",
        "list": False,
    }
    assert template["openai_api_key"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "",
        "password": True,
        "name": "openai_api_key",
        "display_name": "OpenAI API Key",
        "type": "str",
        "list": False,
    }
    assert template["request_timeout"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 60,
        "password": False,
        "name": "request_timeout",
        "type": "int",
        "list": False,
    }
    assert template["max_retries"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 6,
        "password": False,
        "name": "max_retries",
        "type": "int",
        "list": False,
    }
    assert template["streaming"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": False,
        "password": False,
        "name": "streaming",
        "type": "bool",
        "list": False,
    }
    assert template["n"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 1,
        "password": False,
        "name": "n",
        "type": "int",
        "list": False,
    }

    assert template["max_tokens"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": True,
        "name": "max_tokens",
        "type": "int",
        "list": False,
    }
    assert template["_type"] == "ChatOpenAI"
    assert (
        model["description"]
        == "Wrapper around OpenAI Chat large language models.To use, you should have the ``openai`` python package installed, and theenvironment variable ``OPENAI_API_KEY`` set with your API key.Any parameters that are valid to be passed to the openai.create call can be passedin, even if not explicitly saved on this class."
    )
    assert set(model["base_classes"]) == {
        "BaseChatModel",
        "ChatOpenAI",
        "BaseLanguageModel",
    }
