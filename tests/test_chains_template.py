from fastapi.testclient import TestClient


# Test the ConversationChain object
def test_conversation_chain(client: TestClient):
    response = client.get("/all")
    assert response.status_code == 200
    json_response = response.json()
    chains = json_response["chains"]

    chain = chains["ConversationChain"]

    # Test the base classes, template, memory, verbose, llm, input_key, output_key, and _type objects
    assert set(chain["base_classes"]) == {"LLMChain", "ConversationChain", "Chain"}
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
    assert template["llm"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "llm",
        "type": "BaseLanguageModel",
        "list": False,
    }
    assert template["input_key"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "input",
        "password": False,
        "name": "input_key",
        "type": "str",
        "list": False,
    }
    assert template["output_key"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "response",
        "password": False,
        "name": "output_key",
        "type": "str",
        "list": False,
    }
    assert template["_type"] == "ConversationChain"

    # Test the description object
    assert (
        chain["description"]
        == "Chain to have a conversation and load context from memory."
    )


def test_llm_chain(client: TestClient):
    response = client.get("/all")
    assert response.status_code == 200
    json_response = response.json()
    chains = json_response["chains"]
    chain = chains["LLMChain"]

    # Test the base classes, template, memory, verbose, llm, input_key, output_key, and _type objects
    assert set(chain["base_classes"]) == {"LLMChain", "Chain"}
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
    assert template["llm"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "llm",
        "type": "BaseLanguageModel",
        "list": False,
    }
    assert template["output_key"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "text",
        "password": False,
        "name": "output_key",
        "type": "str",
        "list": False,
    }


def test_llm_checker_chain(client: TestClient):
    response = client.get("/all")
    assert response.status_code == 200
    json_response = response.json()
    chains = json_response["chains"]
    chain = chains["LLMCheckerChain"]

    # Test the base classes, template, memory, verbose, llm, input_key, output_key, and _type objects
    assert set(chain["base_classes"]) == {"LLMCheckerChain", "Chain"}
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
    assert template["llm"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "llm",
        "type": "BaseLLM",
        "list": False,
    }
    assert template["input_key"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "query",
        "password": False,
        "name": "input_key",
        "type": "str",
        "list": False,
    }
    assert template["output_key"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "result",
        "password": False,
        "name": "output_key",
        "type": "str",
        "list": False,
    }
    assert template["_type"] == "LLMCheckerChain"

    # Test the description object
    assert (
        chain["description"] == "Chain for question-answering with self-verification."
    )


def test_llm_math_chain(client: TestClient):
    response = client.get("/all")
    assert response.status_code == 200
    json_response = response.json()
    chains = json_response["chains"]

    chain = chains["LLMMathChain"]

    # Test the base classes, template, memory, verbose, llm, input_key, output_key, and _type objects
    assert set(chain["base_classes"]) == {"LLMMathChain", "Chain"}
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
    assert template["llm"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "llm",
        "type": "BaseLanguageModel",
        "list": False,
    }
    assert template["input_key"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "question",
        "password": False,
        "name": "input_key",
        "type": "str",
        "list": False,
    }
    assert template["output_key"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "answer",
        "password": False,
        "name": "output_key",
        "type": "str",
        "list": False,
    }
    assert template["_type"] == "LLMMathChain"

    # Test the description object
    assert (
        chain["description"]
        == "Chain that interprets a prompt and executes python code to do math."
    )


def test_series_character_chain(client: TestClient):
    response = client.get("/all")
    assert response.status_code == 200
    json_response = response.json()
    chains = json_response["chains"]

    chain = chains["SeriesCharacterChain"]

    # Test the base classes, template, memory, verbose, llm, input_key, output_key, and _type objects
    assert set(chain["base_classes"]) == {
        "LLMChain",
        "BaseCustomChain",
        "Chain",
        "ConversationChain",
        "SeriesCharacterChain",
    }
    template = chain["template"]
    assert template["memory"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": {
            "chat_memory": {"messages": []},
            "output_key": None,
            "input_key": None,
            "return_messages": False,
            "human_prefix": "Human",
            "ai_prefix": "AI",
            "memory_key": "history",
        },
        "password": False,
        "name": "memory",
        "type": "BaseMemory",
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
    assert template["llm"] == {
        "required": True,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "password": False,
        "name": "llm",
        "type": "BaseLanguageModel",
        "list": False,
    }
    assert template["input_key"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "input",
        "password": False,
        "name": "input_key",
        "type": "str",
        "list": False,
    }
    assert template["output_key"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "response",
        "password": False,
        "name": "output_key",
        "type": "str",
        "list": False,
    }
    assert template["template"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": True,
        "value": "I want you to act like {character} from {series}.\nI want you to respond and answer like {character}. do not write any explanations. only answer like {character}.\nYou must know all of the knowledge of {character}.\nCurrent conversation:\n{history}\nHuman: {input}\n{character}:",  # noqa: E501
        "password": False,
        "name": "template",
        "type": "str",
        "list": False,
    }
    assert template["ai_prefix_value"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "character",
        "password": False,
        "name": "ai_prefix_value",
        "type": "str",
        "list": False,
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
    }
    assert template["_type"] == "SeriesCharacterChain"

    # Test the description object
    assert (
        chain["description"]
        == "SeriesCharacterChain is a chain you can use to have a conversation with a character from a series."
    )


def test_mid_journey_prompt_chain(client: TestClient):
    response = client.get("/all")
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
    assert template["memory"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": {
            "chat_memory": {"messages": []},
            "output_key": None,
            "input_key": None,
            "return_messages": False,
            "human_prefix": "Human",
            "ai_prefix": "AI",
            "memory_key": "history",
        },
        "password": False,
        "name": "memory",
        "type": "BaseMemory",
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
    # Continue with other template object assertions
    assert template["prompt"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": {
            "input_variables": ["history", "input"],
            "output_parser": None,
            "partial_variables": {},
            "template": "The following is a friendly conversation between a human and an AI. The AI is talkative and provides lots of specific details from its context. If the AI does not know the answer to a question, it truthfully says it does not know.\n\nCurrent conversation:\n{history}\nHuman: {input}\nAI:",  # noqa: E501
            "template_format": "f-string",
            "validate_template": True,
            "_type": "prompt",
        },
        "password": False,
        "name": "prompt",
        "type": "BasePromptTemplate",
        "list": False,
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
    }
    assert template["output_key"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "response",
        "password": False,
        "name": "output_key",
        "type": "str",
        "list": False,
    }
    assert template["input_key"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "input",
        "password": False,
        "name": "input_key",
        "type": "str",
        "list": False,
    }
    assert template["template"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": True,
        "value": 'I want you to act as a prompt generator for Midjourney\'s artificial intelligence program.\n    Your job is to provide detailed and creative descriptions that will inspire unique and interesting images from the AI.\n    Keep in mind that the AI is capable of understanding a wide range of language and can interpret abstract concepts, so feel free to be as imaginative and descriptive as possible.\n    For example, you could describe a scene from a futuristic city, or a surreal landscape filled with strange creatures.\n    The more detailed and imaginative your description, the more interesting the resulting image will be. Here is your first prompt:\n    "A field of wildflowers stretches out as far as the eye can see, each one a different color and shape. In the distance, a massive tree towers over the landscape, its branches reaching up to the sky like tentacles."\n\n    Current conversation:\n    {history}\n    Human: {input}\n    AI:',  # noqa: E501
        "password": False,
        "name": "template",
        "type": "str",
        "list": False,
    }
    assert template["ai_prefix_value"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "ai_prefix_value",
        "type": "str",
        "list": False,
    }
    # Test the description object
    assert (
        chain["description"]
        == "MidJourneyPromptChain is a chain you can use to generate new MidJourney prompts."
    )


def test_time_travel_guide_chain(client: TestClient):
    response = client.get("/all")
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
    assert template["memory"] == {
        "required": False,
        "placeholder": "",
        "show": True,
        "multiline": False,
        "value": {
            "chat_memory": {"messages": []},
            "output_key": None,
            "input_key": None,
            "return_messages": False,
            "human_prefix": "Human",
            "ai_prefix": "AI",
            "memory_key": "history",
        },
        "password": False,
        "name": "memory",
        "type": "BaseMemory",
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

    assert template["prompt"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": {
            "input_variables": ["history", "input"],
            "output_parser": None,
            "partial_variables": {},
            "template": "The following is a friendly conversation between a human and an AI. The AI is talkative and provides lots of specific details from its context. If the AI does not know the answer to a question, it truthfully says it does not know.\n\nCurrent conversation:\n{history}\nHuman: {input}\nAI:",  # noqa: E501
            "template_format": "f-string",
            "validate_template": True,
            "_type": "prompt",
        },
        "password": False,
        "name": "prompt",
        "type": "BasePromptTemplate",
        "list": False,
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
    }
    assert template["output_key"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "response",
        "password": False,
        "name": "output_key",
        "type": "str",
        "list": False,
    }

    assert template["input_key"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "value": "input",
        "password": False,
        "name": "input_key",
        "type": "str",
        "list": False,
    }

    assert template["template"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": True,
        "value": "I want you to act as my time travel guide. You are helpful and creative. I will provide you with the historical period or future time I want to visit and you will suggest the best events, sights, or people to experience. Provide the suggestions and any necessary information.\n    Current conversation:\n    {history}\n    Human: {input}\n    AI:",  # noqa: E501
        "password": False,
        "name": "template",
        "type": "str",
        "list": False,
    }
    assert template["ai_prefix_value"] == {
        "required": False,
        "placeholder": "",
        "show": False,
        "multiline": False,
        "password": False,
        "name": "ai_prefix_value",
        "type": "str",
        "list": False,
    }
    assert chain["description"] == ""
