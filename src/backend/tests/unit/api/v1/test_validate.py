import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.usefixtures("active_user")
async def test_post_validate_code(client: AsyncClient, logged_in_headers):
    good_code = """
from pprint import pprint
var = {"a": 1, "b": 2}
pprint(var)
    """
    response = await client.post("api/v1/validate/code", json={"code": good_code}, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "imports" in result, "The result must have an 'imports' key"
    assert "function" in result, "The result must have a 'function' key"


@pytest.mark.usefixtures("active_user")
async def test_post_validate_prompt(client: AsyncClient, logged_in_headers):
    basic_case = {
        "name": "string",
        "template": "string",
        "custom_fields": {},
        "frontend_node": {
            "template": {},
            "description": "string",
            "icon": "string",
            "is_input": True,
            "is_output": True,
            "is_composition": True,
            "base_classes": ["string"],
            "name": "",
            "display_name": "",
            "documentation": "",
            "custom_fields": {},
            "output_types": [],
            "full_path": "string",
            "pinned": False,
            "conditional_paths": [],
            "frozen": False,
            "outputs": [],
            "field_order": [],
            "beta": False,
            "minimized": False,
            "error": "string",
            "edited": False,
            "metadata": {},
        },
    }
    response = await client.post("api/v1/validate/prompt", json=basic_case, headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(result, dict), "The result must be a dictionary"
    assert "frontend_node" in result, "The result must have a 'frontend_node' key"
    assert "input_variables" in result, "The result must have an 'input_variables' key"


@pytest.mark.usefixtures("active_user")
async def test_post_validate_prompt_with_invalid_data(client: AsyncClient, logged_in_headers):
    invalid_case = {
        "name": "string",
        # Missing required fields
        "frontend_node": {"template": {}, "is_input": True},
    }
    response = await client.post("api/v1/validate/prompt", json=invalid_case, headers=logged_in_headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_post_validate_code_with_unauthenticated_user(client: AsyncClient):
    code = """
    print("Hello World")
    """
    response = await client.post("api/v1/validate/code", json={"code": code}, headers={"Authorization": "Bearer fake"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# Security tests to verify dangerous operations are blocked by default
@pytest.mark.usefixtures("active_user")
async def test_validate_code_blocks_dangerous_imports_by_default(client: AsyncClient, logged_in_headers):
    """Test that dangerous imports are blocked by default."""
    # Code with dangerous imports should be blocked
    dangerous_code = """
import os
import subprocess

def test():
    return os.getcwd()
"""
    response = await client.post("api/v1/validate/code", json={"code": dangerous_code}, headers=logged_in_headers)
    result = response.json()
    assert response.status_code == status.HTTP_200_OK
    # Should have errors - dangerous imports are blocked
    assert len(result["imports"]["errors"]) > 0 or len(result["function"]["errors"]) > 0
    # Should mention that module is blocked
    all_errors = result["imports"]["errors"] + result["function"]["errors"]
    assert any(
        "blocked" in str(err).lower() or "os" in str(err).lower() or "subprocess" in str(err).lower()
        for err in all_errors
    )


@pytest.mark.usefixtures("active_user")
async def test_validate_code_blocks_dangerous_builtins_by_default(client: AsyncClient, logged_in_headers):
    """Test that dangerous builtins are blocked by default."""
    # Code using dangerous builtins in default args should be blocked
    # (function-definition-time execution catches this)
    dangerous_code = """
def test(x=open('/etc/passwd', 'r').read()):
    return x
"""
    response = await client.post("api/v1/validate/code", json={"code": dangerous_code}, headers=logged_in_headers)
    result = response.json()
    assert response.status_code == status.HTTP_200_OK
    # Should have errors - dangerous builtins are blocked
    assert len(result["function"]["errors"]) > 0
    # Should mention that builtin is blocked
    assert any("blocked" in str(err).lower() or "open" in str(err).lower() for err in result["function"]["errors"])


@pytest.mark.usefixtures("active_user")
async def test_validate_code_allows_safe_code(client: AsyncClient, logged_in_headers):
    """Test that legitimate safe code still works."""
    safe_code = """
from typing import List, Optional

def process(items: List[str]) -> Optional[str]:
    return items[0] if items else None
"""
    response = await client.post("api/v1/validate/code", json={"code": safe_code}, headers=logged_in_headers)
    result = response.json()
    assert response.status_code == status.HTTP_200_OK
    # Should have no errors for safe code
    assert len(result["imports"]["errors"]) == 0
    assert len(result["function"]["errors"]) == 0


@pytest.mark.usefixtures("active_user")
async def test_validate_code_allows_safe_imports(client: AsyncClient, logged_in_headers):
    """Test that safe imports are allowed."""
    # Code with safe imports should work
    safe_code = """
from typing import List, Optional
import json
import math

def test(items: List[str]) -> Optional[str]:
    return json.dumps({"count": math.sqrt(len(items))})
"""
    response = await client.post("api/v1/validate/code", json={"code": safe_code}, headers=logged_in_headers)
    result = response.json()
    assert response.status_code == status.HTTP_200_OK
    # Should execute without errors - safe imports are allowed
    assert len(result["imports"]["errors"]) == 0
    assert len(result["function"]["errors"]) == 0


@pytest.mark.usefixtures("active_user")
async def test_validate_code_allows_third_party_libraries(client: AsyncClient, logged_in_headers):
    """Test that third-party libraries (not in a whitelist) can be imported.

    Users should be able to import legitimate third-party libraries like AI libraries,
    data processing libraries, etc. We only block dangerous system-level modules.
    """
    # Try importing a common third-party library that wouldn't be in a whitelist
    # Using 'requests' as an example - it's a legitimate library but not dangerous
    # Note: This test will fail if 'requests' isn't installed, but that's okay
    # The important thing is that if it IS installed, it should be allowed
    third_party_code = """
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def test():
    return HAS_REQUESTS
"""
    response = await client.post("api/v1/validate/code", json={"code": third_party_code}, headers=logged_in_headers)
    result = response.json()
    assert response.status_code == status.HTTP_200_OK
    # Should execute without errors - third-party libraries are allowed
    # (unless they're in BLOCKED_MODULES like 'os', 'subprocess', etc.)
    assert len(result["imports"]["errors"]) == 0
    assert len(result["function"]["errors"]) == 0


@pytest.mark.usefixtures("active_user")
async def test_validate_code_allows_langflow_modules(client: AsyncClient, logged_in_headers):
    """Test that langflow.* modules are allowed."""
    # Code importing langflow.* modules should work
    langflow_code = """
import langflow
from langflow.schema import Data

def test():
    return Data(data={"test": "value"})
"""
    response = await client.post("api/v1/validate/code", json={"code": langflow_code}, headers=logged_in_headers)
    result = response.json()
    assert response.status_code == status.HTTP_200_OK
    # Should execute without errors - langflow.* modules are allowed
    assert len(result["imports"]["errors"]) == 0
    assert len(result["function"]["errors"]) == 0


@pytest.mark.usefixtures("active_user")
async def test_validate_code_allows_lfx_modules(client: AsyncClient, logged_in_headers):
    """Test that lfx.* modules are allowed."""
    # Code importing lfx.* modules should work
    lfx_code = """
import lfx
from lfx.custom import Component

def test():
    return Component()
"""
    response = await client.post("api/v1/validate/code", json={"code": lfx_code}, headers=logged_in_headers)
    result = response.json()
    assert response.status_code == status.HTTP_200_OK
    # Should execute without errors - lfx.* modules are allowed
    assert len(result["imports"]["errors"]) == 0
    assert len(result["function"]["errors"]) == 0


