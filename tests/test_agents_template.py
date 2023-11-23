from fastapi.testclient import TestClient


def test_zero_shot_agent(client: TestClient, logged_in_headers):
    response = client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200
    json_response = response.json()
    agents = json_response["agents"]

    zero_shot_agent = agents["ZeroShotAgent"]
    assert set(zero_shot_agent["base_classes"]) == {
        "ZeroShotAgent",
        "BaseSingleActionAgent",
        "Agent",
        "Callable",
    }
    template = zero_shot_agent["template"]

    assert template["tools"] == {
        "required": True,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "tools",
        "type": "BaseTool",
        "list": True,
        "advanced": False,
        "info": "",
    }

    # Additional assertions for other template variables
    assert template["callback_manager"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "callback_manager",
        "type": "BaseCallbackManager",
        "list": False,
        "advanced": False,
        "info": "",
    }
    assert template["llm"] == {
        "required": True,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "llm",
        "type": "BaseLanguageModel",
        "list": False,
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
        "type": "AgentOutputParser",
        "list": False,
        "advanced": False,
        "info": "",
    }
    assert template["input_variables"] == {
        "required": False,
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
    assert template["prefix"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": True,
        "value": "Answer the following questions as best you can. You have access to the following tools:",
        "password": False,
        "name": "prefix",
        "type": "str",
        "list": False,
        "advanced": False,
        "info": "",
    }
    assert template["suffix"] == {
        "required": False,
        "dynamic": False,
        "placeholder": "",
        "show": True,
        "multiline": True,
        "value": "Begin!\n\nQuestion: {input}\nThought:{agent_scratchpad}",
        "password": False,
        "name": "suffix",
        "type": "str",
        "list": False,
        "advanced": False,
        "info": "",
    }


def test_json_agent(client: TestClient, logged_in_headers):
    response = client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200
    json_response = response.json()
    agents = json_response["agents"]

    json_agent = agents["JsonAgent"]
    assert json_agent["base_classes"] == ["AgentExecutor"]
    template = json_agent["template"]

    assert template["toolkit"] == {
        "required": True,
        "dynamic": False,
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
        "dynamic": False,
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


def test_csv_agent(client: TestClient, logged_in_headers):
    response = client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200
    json_response = response.json()
    agents = json_response["agents"]

    csv_agent = agents["CSVAgent"]
    assert csv_agent["base_classes"] == ["AgentExecutor"]
    template = csv_agent["template"]

    assert template["path"] == {
        "required": True,
        "dynamic": False,
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
        "dynamic": False,
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


def test_initialize_agent(client: TestClient, logged_in_headers):
    response = client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200
    json_response = response.json()
    agents = json_response["agents"]

    initialize_agent = agents["AgentInitializer"]
    assert initialize_agent["base_classes"] == ["AgentExecutor", "Callable"]
    template = initialize_agent["template"]

    assert template["agent"] == {
        "required": True,
        "dynamic": False,
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
        "dynamic": False,
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
        "required": True,
        "dynamic": False,
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
        "dynamic": False,
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
