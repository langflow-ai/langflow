from fastapi.testclient import TestClient
from langflow.services.getters import get_settings_service


def test_prompts_settings(client: TestClient, logged_in_headers):
    settings_service = get_settings_service()
    response = client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200
    json_response = response.json()
    prompts = json_response["prompts"]
    assert set(prompts.keys()) == set(settings_service.settings.PROMPTS)


def test_prompt_template(client: TestClient, logged_in_headers):
    response = client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200
    json_response = response.json()
    prompts = json_response["prompts"]

    prompt = prompts["PromptTemplate"]
    template = prompt["template"]
    assert template["input_variables"] == {
        "required": True,
        "dynamic": True,
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
        "dynamic": True,
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
        "dynamic": True,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "partial_variables",
        "type": "dict",
        "list": False,
        "advanced": False,
        "info": "",
    }

    assert template["template"] == {
        "required": True,
        "dynamic": True,
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
        "dynamic": True,
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
        "dynamic": True,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": False,
        "password": False,
        "name": "validate_template",
        "type": "bool",
        "list": False,
        "advanced": False,
        "info": "",
    }
