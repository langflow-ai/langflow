import pytest
from fastapi.testclient import TestClient
from langflow.interface.tools.constants import CUSTOM_TOOLS


def test_get_all(client: TestClient):
    response = client.get("api/v1/all")
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
    response1 = client.post("api/v1/validate/code", json={"code": code1})
    assert response1.status_code == 200
    assert response1.json() == {"imports": {"errors": []}, "function": {"errors": []}}

    # Test case with an invalid import and valid function
    code2 = """
import non_existent_module

def square(x):
    return x ** 2
"""
    response2 = client.post("api/v1/validate/code", json={"code": code2})
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
    response3 = client.post("api/v1/validate/code", json={"code": code3})
    assert response3.status_code == 200
    assert response3.json() == {
        "imports": {"errors": []},
        "function": {"errors": ["expected ':' (<unknown>, line 4)"]},
    }

    # Test case with invalid JSON payload
    response4 = client.post("api/v1/validate/code", json={"invalid_key": code1})
    assert response4.status_code == 422

    # Test case with an empty code string
    response5 = client.post("api/v1/validate/code", json={"code": ""})
    assert response5.status_code == 200
    assert response5.json() == {"imports": {"errors": []}, "function": {"errors": []}}

    # Test case with a syntax error in the code
    code6 = """
import math

def square(x)
    return x ** 2
"""
    response6 = client.post("api/v1/validate/code", json={"code": code6})
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
    response = client.post("api/v1/validate/prompt", json={"template": VALID_PROMPT})
    assert response.status_code == 200
    assert response.json() == {"input_variables": ["product"]}


def test_invalid_prompt(client: TestClient):
    response = client.post("api/v1/validate/prompt", json={"template": INVALID_PROMPT})
    assert response.status_code == 200
    assert response.json() == {"input_variables": []}


@pytest.mark.parametrize(
    "prompt,expected_input_variables",
    [
        ("{color} is my favorite color.", ["color"]),
        ("The weather is {weather} today.", ["weather"]),
        ("This prompt has no variables.", []),
        ("{a}, {b}, and {c} are variables.", ["a", "b", "c"]),
    ],
)
def test_various_prompts(client, prompt, expected_input_variables):
    response = client.post("api/v1/validate/prompt", json={"template": prompt})
    assert response.status_code == 200
    assert response.json() == {
        "input_variables": expected_input_variables,
    }
