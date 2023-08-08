from fastapi.testclient import TestClient
from langflow.services.utils import get_settings_manager


def test_prompts_settings(client: TestClient):
    settings_manager = get_settings_manager()
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    prompts = json_response["prompts"]
    assert set(prompts.keys()) == set(settings_manager.settings.PROMPTS)


def test_prompt_template(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    prompts = json_response["prompts"]

    prompt = prompts["PromptTemplate"]
    template = prompt["template"]
    assert template["input_variables"] == {
        "required": True,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "input_variables",
        "type": "str",
        "list": True,
        "advanced": False,
        "info": "",
    }

    assert template["output_parser"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "output_parser",
        "type": "BaseOutputParser",
        "list": False,
        "advanced": False,
        "info": "",
    }

    assert template["partial_variables"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "partial_variables",
        "type": "code",
        "list": False,
        "advanced": False,
        "info": "",
    }

    assert template["template"] == {
        "required": True,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": True,
        "password": False,
        "name": "template",
        "type": "prompt",
        "list": False,
        "advanced": False,
        "info": "",
    }

    assert template["template_format"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "f-string",
        "password": False,
        "name": "template_format",
        "type": "str",
        "list": False,
        "advanced": False,
        "info": "",
    }

    assert template["validate_template"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": True,
        "password": False,
        "name": "validate_template",
        "type": "bool",
        "list": False,
        "advanced": False,
        "info": "",
    }
