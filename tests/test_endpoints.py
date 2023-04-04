import json
from typing import Dict
from fastapi.testclient import TestClient
from langflow.interface.tools.constants import CUSTOM_TOOLS
from pathlib import Path

import pytest


def test_post_predict(client: TestClient):
    with open(Path(__file__).parent / "data" / "Build_error.json") as f:
        data = f.read()
        json_data = json.loads(data)
    data: Dict = json_data["data"]
    data["message"] = "I'm Bob"
    response = client.post("/predict", json=data)
    assert response.status_code == 200
    data["message"] = "What is my name?"
    data["chatHistory"] = ["I'm Bob"]
    response = client.post("/predict", json=data)
    assert response.status_code == 200
    assert "Bob" in response.json()["result"]


def test_get_all(client: TestClient):
    response = client.get("/all")
    assert response.status_code == 200
    json_response = response.json()
    # We need to test the custom nodes
    assert "ZeroShotPrompt" in json_response["prompts"]
    # All CUSTOM_TOOLS(dict) should be in the response
    assert all(tool in json_response["tools"] for tool in CUSTOM_TOOLS.keys())


def test_post_validate_code(client: TestClient):
    # Test case with a valid import and function
    code1 = """
import math

def square(x):
    return x ** 2
"""
    response1 = client.post("/validate/code", json={"code": code1})
    assert response1.status_code == 200
    assert response1.json() == {"imports": {"errors": []}, "function": {"errors": []}}

    # Test case with an invalid import and valid function
    code2 = """
import non_existent_module

def square(x):
    return x ** 2
"""
    response2 = client.post("/validate/code", json={"code": code2})
    assert response2.status_code == 200
    assert response2.json() == {
        "imports": {"errors": ["No module named 'non_existent_module'"]},
        "function": {"errors": []},
    }

    # Test case with a valid import and invalid function syntax
    code3 = """
import math

def square(x)
    return x ** 2
"""
    response3 = client.post("/validate/code", json={"code": code3})
    assert response3.status_code == 200
    assert response3.json() == {
        "imports": {"errors": []},
        "function": {"errors": ["expected ':' (<unknown>, line 4)"]},
    }

    # Test case with invalid JSON payload
    response4 = client.post("/validate/code", json={"invalid_key": code1})
    assert response4.status_code == 422

    # Test case with an empty code string
    response5 = client.post("/validate/code", json={"code": ""})
    assert response5.status_code == 200
    assert response5.json() == {"imports": {"errors": []}, "function": {"errors": []}}

    # Test case with a syntax error in the code
    code6 = """
import math

def square(x)
    return x ** 2
"""
    response6 = client.post("/validate/code", json={"code": code6})
    assert response6.status_code == 200
    assert response6.json() == {
        "imports": {"errors": []},
        "function": {"errors": ["expected ':' (<unknown>, line 4)"]},
    }


VALID_PROMPT = """
I want you to act as a naming consultant for new companies.

Here are some examples of good company names:

- search engine, Google
- social media, Facebook
- video sharing, YouTube

The name should be short, catchy and easy to remember.

What is a good name for a company that makes {product}?
"""

INVALID_PROMPT = "This is an invalid prompt without any input variable."


def test_valid_prompt(client: TestClient):
    response = client.post("/validate/prompt", json={"template": VALID_PROMPT})
    assert response.status_code == 200
    assert response.json() == {"input_variables": ["product"], "valid": True}


def test_invalid_prompt(client: TestClient):
    response = client.post("/validate/prompt", json={"template": INVALID_PROMPT})
    assert response.status_code == 200
    assert response.json() == {"input_variables": [], "valid": False}


@pytest.mark.parametrize(
    "prompt,expected_input_variables,expected_validity",
    [
        ("{color} is my favorite color.", ["color"], True),
        ("The weather is {weather} today.", ["weather"], True),
        ("This prompt has no variables.", [], False),
        ("{a}, {b}, and {c} are variables.", ["a", "b", "c"], True),
    ],
)
def test_various_prompts(client, prompt, expected_input_variables, expected_validity):
    response = client.post("/validate/prompt", json={"template": prompt})
    assert response.status_code == 200
    assert response.json() == {
        "input_variables": expected_input_variables,
        "valid": expected_validity,
    }
