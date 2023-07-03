from fastapi.testclient import TestClient


def test_zero_shot_agent(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    agents = json_response["agents"]

    zero_shot_agent = agents["ZeroShotAgent"]
    assert set(zero_shot_agent["base_classes"]) == {
        "ZeroShotAgent",
        "BaseSingleActionAgent",
        "Agent",
        "function",
    }
    template = zero_shot_agent["template"]

    assert template["llm_chain"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "llm_chain",
        "type": "LLMChain",
        "list": False,
        "advanced": False,
        "info": "",
    }
    assert template["allowed_tools"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "allowed_tools",
        "type": "Tool",
        "list": True,
        "advanced": False,
        "info": "",
    }


def test_json_agent(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    agents = json_response["agents"]

    json_agent = agents["JsonAgent"]
    assert json_agent["base_classes"] == ["AgentExecutor"]
    template = json_agent["template"]

    assert template["toolkit"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "toolkit",
        "type": "BaseToolkit",
        "list": False,
        "advanced": False,
        "info": "",
    }
    assert template["llm"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "llm",
        "type": "BaseLanguageModel",
        "list": False,
        "advanced": False,
        "display_name": "LLM",
        "info": "",
    }


def test_csv_agent(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    agents = json_response["agents"]

    csv_agent = agents["CSVAgent"]
    assert csv_agent["base_classes"] == ["AgentExecutor"]
    template = csv_agent["template"]

    assert template["path"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "",
        "suffixes": [".csv"],
        "fileTypes": ["csv"],
        "password": False,
        "name": "path",
        "type": "file",
        "list": False,
        "file_path": None,
        "advanced": False,
        "info": "",
    }
    assert template["llm"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "llm",
        "type": "BaseLanguageModel",
        "list": False,
        "advanced": False,
        "display_name": "LLM",
        "info": "",
    }


def test_initialize_agent(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    agents = json_response["agents"]

    initialize_agent = agents["AgentInitializer"]
    assert initialize_agent["base_classes"] == ["AgentExecutor", "function"]
    template = initialize_agent["template"]

    assert template["agent"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "zero-shot-react-description",
        "password": False,
        "options": [
            "zero-shot-react-description",
            "react-docstore",
            "self-ask-with-search",
            "conversational-react-description",
            "openai-functions",
            "openai-multi-functions",
        ],
        "name": "agent",
        "type": "str",
        "list": True,
        "advanced": False,
        "info": "",
    }
    assert template["memory"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "memory",
        "type": "BaseChatMemory",
        "list": False,
        "advanced": False,
        "info": "",
    }
    assert template["tools"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "tools",
        "type": "Tool",
        "list": True,
        "advanced": False,
        "info": "",
    }
    assert template["llm"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "llm",
        "type": "BaseLanguageModel",
        "list": False,
        "advanced": False,
        "display_name": "LLM",
        "info": "",
    }
