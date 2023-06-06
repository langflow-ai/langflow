from fastapi.testclient import TestClient
from langflow.settings import settings


def test_chains_settings(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    chains = json_response["chains"]
    assert set(chains.keys()) == set(settings.chains)


# Test the ConversationChain object
def test_conversation_chain(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    chains = json_response["chains"]

    chain = chains["ConversationChain"]

    # Test the base classes, template, memory, verbose, llm, input_key, output_key, and _type objects
    assert set(chain["base_classes"]) == {
        "function",
        "LLMChain",
        "ConversationChain",
        "Chain",
    }
    template = chain["template"]
    assert template["memory"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "memory",
        "type": "BaseMemory",
        "list": False,
        "advanced": False,
    }
    assert template["verbose"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "verbose",
        "type": "bool",
        "list": False,
        "advanced": True,
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
    }
    assert template["input_key"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "input",
        "password": False,
        "name": "input_key",
        "type": "str",
        "list": False,
        "advanced": True,
    }
    assert template["output_key"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "response",
        "password": False,
        "name": "output_key",
        "type": "str",
        "list": False,
        "advanced": True,
    }
    assert template["_type"] == "ConversationChain"

    # Test the description object
    assert (
        chain["description"]
        == "Chain to have a conversation and load context from memory."
    )


def test_llm_chain(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    chains = json_response["chains"]
    chain = chains["LLMChain"]

    # Test the base classes, template, memory, verbose, llm, input_key, output_key, and _type objects
    assert set(chain["base_classes"]) == {"function", "LLMChain", "Chain"}
    template = chain["template"]
    assert template["memory"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "memory",
        "type": "BaseMemory",
        "list": False,
        "advanced": False,
    }
    assert template["verbose"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": False,
        "password": False,
        "name": "verbose",
        "type": "bool",
        "list": False,
        "advanced": True,
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
    }
    assert template["output_key"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "text",
        "password": False,
        "name": "output_key",
        "type": "str",
        "list": False,
        "advanced": True,
    }


def test_llm_checker_chain(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    chains = json_response["chains"]
    chain = chains["LLMCheckerChain"]

    # Test the base classes, template, memory, verbose, llm, input_key, output_key, and _type objects
    assert set(chain["base_classes"]) == {"function", "LLMCheckerChain", "Chain"}
    template = chain["template"]
    assert template["memory"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "memory",
        "type": "BaseMemory",
        "list": False,
        "advanced": False,
    }
    assert template["verbose"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": False,
        "password": False,
        "name": "verbose",
        "type": "bool",
        "list": False,
        "advanced": True,
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
    }
    assert template["input_key"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "query",
        "password": False,
        "name": "input_key",
        "type": "str",
        "list": False,
        "advanced": True,
    }
    assert template["output_key"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "result",
        "password": False,
        "name": "output_key",
        "type": "str",
        "list": False,
        "advanced": True,
    }
    assert template["_type"] == "LLMCheckerChain"

    # Test the description object
    assert (
        chain["description"] == "Chain for question-answering with self-verification."
    )


def test_llm_math_chain(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    chains = json_response["chains"]

    chain = chains["LLMMathChain"]

    # Test the base classes, template, memory, verbose, llm, input_key, output_key, and _type objects
    assert set(chain["base_classes"]) == {"function", "LLMMathChain", "Chain"}
    template = chain["template"]
    assert template["memory"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "memory",
        "type": "BaseMemory",
        "list": False,
        "advanced": False,
    }
    assert template["verbose"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": False,
        "password": False,
        "name": "verbose",
        "type": "bool",
        "list": False,
        "advanced": True,
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
    }
    assert template["input_key"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "question",
        "password": False,
        "name": "input_key",
        "type": "str",
        "list": False,
        "advanced": True,
    }
    assert template["output_key"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": "answer",
        "password": False,
        "name": "output_key",
        "type": "str",
        "list": False,
        "advanced": True,
    }
    assert template["_type"] == "LLMMathChain"

    # Test the description object
    assert (
        chain["description"]
        == "Chain that interprets a prompt and executes python code to do math."
    )


def test_series_character_chain(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    chains = json_response["chains"]

    chain = chains["SeriesCharacterChain"]

    # Test the base classes, template, memory, verbose, llm, input_key, output_key, and _type objects
    assert set(chain["base_classes"]) == {
        "function",
        "LLMChain",
        "BaseCustomChain",
        "Chain",
        "ConversationChain",
        "SeriesCharacterChain",
    }
    template = chain["template"]

    assert template["llm"] == {
        "required": True,
        "display_name": "LLM",
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "llm",
        "type": "BaseLanguageModel",
        "list": False,
        "advanced": False,
    }
    assert template["character"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "character",
        "type": "str",
        "list": False,
        "advanced": False,
    }
    assert template["series"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "series",
        "type": "str",
        "list": False,
        "advanced": False,
    }
    assert template["_type"] == "SeriesCharacterChain"

    # Test the description object
    assert (
        chain["description"]
        == "SeriesCharacterChain is a chain you can use to have a conversation with a character from a series."
    )


def test_mid_journey_prompt_chain(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    chains = json_response["chains"]
    chain = chains["MidJourneyPromptChain"]
    assert isinstance(chain, dict)

    # Test the base_classes object
    assert set(chain["base_classes"]) == {
        "LLMChain",
        "BaseCustomChain",
        "Chain",
        "ConversationChain",
        "MidJourneyPromptChain",
    }

    # Test the template object
    template = chain["template"]

    assert template["llm"] == {
        "required": True,
        "display_name": "LLM",
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "llm",
        "type": "BaseLanguageModel",
        "list": False,
        "advanced": False,
    }
    # Test the description object
    assert (
        chain["description"]
        == "MidJourneyPromptChain is a chain you can use to generate new MidJourney prompts."
    )


def test_time_travel_guide_chain(client: TestClient):
    response = client.get("api/v1/all")
    assert response.status_code == 200
    json_response = response.json()
    chains = json_response["chains"]
    chain = chains["TimeTravelGuideChain"]
    assert isinstance(chain, dict)

    # Test the base_classes object
    assert set(chain["base_classes"]) == {
        "LLMChain",
        "BaseCustomChain",
        "TimeTravelGuideChain",
        "Chain",
        "ConversationChain",
    }

    # Test the template object
    template = chain["template"]

    assert template["llm"] == {
        "required": True,
        "placeholder": "",
        "display_name": "LLM",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "llm",
        "type": "BaseLanguageModel",
        "list": False,
        "advanced": False,
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
    }

    assert chain["description"] == "Time travel guide chain to be used in the flow."
