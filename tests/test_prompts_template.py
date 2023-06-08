from fastapi.testclient import TestClient
from langflow.settings import settings


def test_prompts_settings(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    prompts = json_response["prompts"]
    assert set(prompts.keys()) == set(settings.prompts)


def test_prompt_template(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    prompts = json_response["prompts"]

    prompt = prompts["PromptTemplate"]
    template = prompt["template"]
    assert template["input_variables"] == {
        "required": True,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "input_variables",
        "type": "str",
        "list": True,
        "advanced": False,
    }
    assert template["output_parser"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "output_parser",
        "type": "BaseOutputParser",
        "list": False,
        "advanced": False,
    }
    assert template["partial_variables"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "partial_variables",
        "type": "code",
        "list": False,
        "advanced": False,
    }
    assert template["template"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": True,
        "password": False,
        "name": "template",
        "type": "prompt",
        "list": False,
        "advanced": False,
    }
    assert template["template_format"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "f-string",
        "password": False,
        "name": "template_format",
        "type": "str",
        "list": False,
        "advanced": False,
    }
    assert template["validate_template"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": True,
        "password": False,
        "name": "validate_template",
        "type": "bool",
        "list": False,
        "advanced": False,
    }


def test_few_shot_prompt_template(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    prompts = json_response["prompts"]

    prompt = prompts["FewShotPromptTemplate"]
    template = prompt["template"]
    # Test other fields in the template similar to PromptTemplate
    assert template["examples"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": True,
        "password": False,
        "name": "examples",
        "type": "prompt",
        "list": True,
        "advanced": False,
    }
    assert template["example_selector"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "example_selector",
        "type": "BaseExampleSelector",
        "list": False,
        "advanced": False,
    }
    assert template["example_prompt"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "example_prompt",
        "type": "PromptTemplate",
        "list": False,
        "advanced": False,
    }
    assert template["suffix"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": True,
        "password": False,
        "name": "suffix",
        "type": "prompt",
        "list": False,
        "advanced": False,
    }
    assert template["example_separator"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "\n\n",
        "password": False,
        "name": "example_separator",
        "type": "str",
        "list": False,
        "advanced": False,
    }
    assert template["prefix"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": True,
        "value": "",
        "password": False,
        "name": "prefix",
        "type": "prompt",
        "list": False,
        "advanced": False,
    }


def test_zero_shot_prompt(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    prompts = json_response["prompts"]
    prompt = prompts["ZeroShotPrompt"]
    template = prompt["template"]
    assert template["prefix"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": True,
        "value": "Answer the following questions as best you can. You have access to the following tools:",  # noqa: E501
        "password": False,
        "name": "prefix",
        "type": "prompt",
        "list": False,
        "advanced": False,
    }
    assert template["suffix"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": True,
        "value": "Begin!\n\nQuestion: {input}\nThought:{agent_scratchpad}",
        "password": False,
        "name": "suffix",
        "type": "prompt",
        "list": False,
        "advanced": False,
    }
    assert template["format_instructions"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": True,
        "value": "Use the following format:\n\nQuestion: the input question you must answer\nThought: you should always think about what to do\nAction: the action to take, should be one of [{tool_names}]\nAction Input: the input to the action\nObservation: the result of the action\n... (this Thought/Action/Action Input/Observation can repeat N times)\nThought: I now know the final answer\nFinal Answer: the final answer to the original input question",  # noqa: E501
        "password": False,
        "name": "format_instructions",
        "type": "prompt",
        "list": False,
        "advanced": False,
    }
