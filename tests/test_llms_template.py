from fastapi.testclient import TestClient


def test_openai(client: TestClient, logged_in_headers):
    response = client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200
    json_response = response.json()
    language_models = json_response["llms"]

    model = language_models["OpenAI"]
    template = model["template"]

    assert template["cache"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "cache",
        "type": "bool",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["verbose"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "verbose",
        "type": "bool",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["client"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "client",
        "type": "Any",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["model_name"] == {
        "required": False,
        "dynamic": False,
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
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    # Add more assertions for other properties here
    assert template["temperature"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": 0.7,
        "password": False,
        "name": "temperature",
        "type": "float",
        "list": False,
        "advanced": False,
        "info": "",
        "rangeSpec": {"max": 1.0, "min": -1.0, "step": 0.1},
        "fileTypes": [],
    }
    assert template["max_tokens"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": 256,
        "password": True,
        "name": "max_tokens",
        "type": "int",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["top_p"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 1,
        "password": False,
        "name": "top_p",
        "type": "float",
        "list": False,
        "advanced": False,
        "info": "",
        "rangeSpec": {"max": 1.0, "min": -1.0, "step": 0.1},
        "fileTypes": [],
    }
    assert template["frequency_penalty"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 0,
        "password": False,
        "name": "frequency_penalty",
        "type": "float",
        "list": False,
        "advanced": False,
        "info": "",
        "rangeSpec": {"max": 1.0, "min": -1.0, "step": 0.1},
        "fileTypes": [],
    }
    assert template["presence_penalty"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 0,
        "password": False,
        "name": "presence_penalty",
        "type": "float",
        "list": False,
        "advanced": False,
        "info": "",
        "rangeSpec": {"max": 1.0, "min": -1.0, "step": 0.1},
        "fileTypes": [],
    }
    assert template["n"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 1,
        "password": False,
        "name": "n",
        "type": "int",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["best_of"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 1,
        "password": False,
        "name": "best_of",
        "type": "int",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["model_kwargs"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "model_kwargs",
        "type": "dict",
        "list": False,
        "advanced": True,
        "info": "",
        "fileTypes": [],
    }
    assert template["openai_api_key"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "",
        "password": True,
        "name": "openai_api_key",
        "display_name": "OpenAI API Key",
        "type": "str",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["batch_size"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 20,
        "password": False,
        "name": "batch_size",
        "type": "int",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["request_timeout"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "request_timeout",
        "type": "float",
        "list": False,
        "advanced": False,
        "info": "",
        "rangeSpec": {"max": 1.0, "min": -1.0, "step": 0.1},
        "fileTypes": [],
    }
    assert template["logit_bias"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "logit_bias",
        "type": "dict",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["max_retries"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 2,
        "password": False,
        "name": "max_retries",
        "type": "int",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["streaming"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": False,
        "password": False,
        "name": "streaming",
        "type": "bool",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }


def test_chat_open_ai(client: TestClient, logged_in_headers):
    response = client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200
    json_response = response.json()
    language_models = json_response["llms"]

    model = language_models["ChatOpenAI"]
    template = model["template"]

    assert template["verbose"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": False,
        "password": False,
        "name": "verbose",
        "type": "bool",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["client"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "client",
        "type": "Any",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["model_name"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "gpt-4-1106-preview",
        "password": False,
        "options": [
            "gpt-4-1106-preview",
            "gpt-4-vision-preview",
            "gpt-4",
            "gpt-4-32k",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
        ],
        "name": "model_name",
        "type": "str",
        "list": True,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["temperature"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": 0.7,
        "password": False,
        "name": "temperature",
        "type": "float",
        "list": False,
        "advanced": False,
        "info": "",
        "rangeSpec": {"max": 1.0, "min": -1.0, "step": 0.1},
        "fileTypes": [],
    }
    assert template["model_kwargs"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "model_kwargs",
        "type": "dict",
        "list": False,
        "advanced": True,
        "info": "",
        "fileTypes": [],
    }
    assert template["openai_api_key"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "",
        "password": True,
        "name": "openai_api_key",
        "display_name": "OpenAI API Key",
        "type": "str",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["request_timeout"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "request_timeout",
        "type": "float",
        "list": False,
        "advanced": False,
        "info": "",
        "rangeSpec": {"max": 1.0, "min": -1.0, "step": 0.1},
        "fileTypes": [],
    }
    assert template["max_retries"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 2,
        "password": False,
        "name": "max_retries",
        "type": "int",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["streaming"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": False,
        "password": False,
        "name": "streaming",
        "type": "bool",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["n"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": 1,
        "password": False,
        "name": "n",
        "type": "int",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }

    assert template["max_tokens"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": True,
        "name": "max_tokens",
        "type": "int",
        "list": False,
        "advanced": False,
        "info": "",
        "fileTypes": [],
    }
    assert template["_type"] == "ChatOpenAI"
    assert (
        model["description"] == "`OpenAI` Chat large language models API."  # noqa E501
    )
    assert set(model["base_classes"]) == {
        "BaseLLM",
        "BaseChatModel",
        "ChatOpenAI",
        "BaseLanguageModel",
    }


# Commenting this out for now, as it requires to activate the nodes
# def test_azure_open_ai(client: TestClient):
#     response = client.get("/all")
#     assert response.status_code == 200
#     json_response = response.json()
#     language_models = json_response["llms"]

#     model = language_models["AzureOpenAI"]
#     template = model["template"]

#     assert template["model_name"]["show"] is False
#     assert template["deployment_name"] == {
#         "required": False,
#         "placeholder": "",
#         "show": True,
#         "multiline": False,
#         "value": "",
#         "password": False,
#         "name": "deployment_name",
#         "advanced": False,
#         "type": "str",
#         "list": False,
#     }


# def test_azure_chat_open_ai(client: TestClient):
#     response = client.get("/all")
#     assert response.status_code == 200
#     json_response = response.json()
#     language_models = json_response["llms"]

#     model = language_models["AzureChatOpenAI"]
#     template = model["template"]

#     assert template["model_name"]["show"] is False
#     assert template["deployment_name"] == {
#         "required": False,
#         "placeholder": "",
#         "show": True,
#         "multiline": False,
#         "value": "",
#         "password": False,
#         "name": "deployment_name",
#         "advanced": False,
#         "type": "str",
#         "list": False,
#     }
#     assert template["openai_api_type"] == {
#         "required": False,
#         "placeholder": "",
#         "show": False,
#         "multiline": False,
#         "value": "azure",
#         "password": False,
#         "name": "openai_api_type",
#         "display_name": "OpenAI API Type",
#         "advanced": False,
#         "type": "str",
#         "list": False,
#     }
#     assert template["openai_api_version"] == {
#         "required": False,
#         "placeholder": "",
#         "show": True,
#         "multiline": False,
#         "value": "2023-03-15-preview",
#         "password": False,
#         "name": "openai_api_version",
#         "display_name": "OpenAI API Version",
#         "advanced": False,
#         "type": "str",
#         "list": False,
#     }
