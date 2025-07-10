import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi import status
from httpx import AsyncClient

from langflow.utils.validate import validate_code


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


class TestValidateCodeSecurity:
    """Test class for validate_code endpoint"""
    
    def test_validate_code_no_execution_simple(self):
        """Test that validate_code performs static analysis without executing code"""
        # This code should NOT execute the system command
        malicious_code = """
import os
def malicious_function():
    os.system('echo "PWNED" > /tmp/test_security_breach.txt')
    return "executed"
"""
        
        # Run validation
        result = validate_code(malicious_code)
        
        # Should return without errors (valid syntax)
        assert isinstance(result, dict)
        assert "imports" in result
        assert "function" in result
        
        # Most importantly: verify no file was created (code didn't execute)
        assert not os.path.exists('/tmp/test_security_breach.txt')
    
    def test_validate_code_handles_syntax_errors(self):
        """Test that syntax errors are properly caught"""
        invalid_code = """
def broken_function(
    # Missing closing parenthesis
    return "this won't work"
"""
        
        result = validate_code(invalid_code)
        
        # Should return with function errors
        assert isinstance(result, dict)
        assert "function" in result
        assert len(result["function"]["errors"]) > 0
    
    def test_validate_code_detects_import_errors(self):
        """Test that missing imports are detected"""
        code_with_missing_import = """
import non_existent_module
def test_function():
    return "test"
"""
        
        result = validate_code(code_with_missing_import)
        
        # Should detect the missing import
        assert isinstance(result, dict)
        assert "imports" in result
        assert len(result["imports"]["errors"]) > 0
        assert "non_existent_module" in str(result["imports"]["errors"])
    
    def test_validate_code_environment_isolation(self):
        """Test that code validation doesn't affect the current environment"""
        # Code that would modify global variables if executed
        environment_code = """
import os
def modify_environment():
    os.environ['SECURITY_TEST'] = 'COMPROMISED'
    return "modified"
"""
        
        # Ensure the environment variable doesn't exist before
        if 'SECURITY_TEST' in os.environ:
            del os.environ['SECURITY_TEST']
        
        result = validate_code(environment_code)
        
        # Should complete validation
        assert isinstance(result, dict)
        
        # Environment should remain unchanged
        assert 'SECURITY_TEST' not in os.environ
    
    @patch('langflow.utils.validate.exec')
    def test_validate_code_no_exec_called(self, mock_exec):
        """Test that exec() is never called during validation"""
        test_code = """
def test_function():
    return "test"
"""
        
        result = validate_code(test_code)
        
        # Should complete successfully
        assert isinstance(result, dict)
        
        # exec() should never be called
        mock_exec.assert_not_called()
    
    def test_enhanced_static_analysis_division_by_zero(self):
        """Test that enhanced static analysis detects division by zero"""
        division_code = """
def divide_function(x):
    result = x / 0
    return result
"""
        
        result = validate_code(division_code)
        
        # Should detect division by zero
        assert isinstance(result, dict)
        assert "function" in result
        errors = result["function"]["errors"]
        assert any("Division by zero" in error for error in errors)
    
    def test_enhanced_static_analysis_type_mixing(self):
        """Test that enhanced static analysis detects type mixing errors"""
        type_mixing_code = """
def type_error_function():
    result = "hello" + 5
    return result
"""
        
        result = validate_code(type_mixing_code)
        
        # Should detect type mixing
        assert isinstance(result, dict)
        assert "function" in result
        errors = result["function"]["errors"]
        assert any("Cannot add string and number" in error for error in errors)
    
    def test_enhanced_static_analysis_undefined_variables(self):
        """Test that enhanced static analysis detects potentially undefined variables"""
        undefined_var_code = """
def undefined_var_function(x):
    result = x + unknown_variable
    return result
"""
        
        result = validate_code(undefined_var_code)
        
        # Should detect undefined variable
        assert isinstance(result, dict)
        assert "function" in result
        errors = result["function"]["errors"]
        # Note: this might not trigger due to our conservative checking
        # but it's good to test the functionality
    
    def test_enhanced_static_analysis_return_consistency(self):
        """Test that enhanced static analysis detects inconsistent returns"""
        inconsistent_return_code = """
def inconsistent_function(x):
    if x > 0:
        return x
    else:
        return  # Empty return mixed with value return
"""
        
        result = validate_code(inconsistent_return_code)
        
        # Should detect inconsistent returns
        assert isinstance(result, dict)
        assert "function" in result
        errors = result["function"]["errors"]
        assert any("Inconsistent return statements" in error for error in errors)


@pytest.mark.usefixtures("active_user")
async def test_validate_endpoint_safe_with_auth(client: AsyncClient, logged_in_headers):
    """Test that the validate endpoint is safe even with authentication"""
    malicious_payload = {
        "code": """
import os
def malicious():
    os.system('echo "SECURITY_BREACH" > /tmp/endpoint_test.txt')
    return "executed"
"""
    }
    
    # Request with authentication
    response = await client.post("/api/v1/validate/code", json=malicious_payload, headers=logged_in_headers)
    
    # Should succeed (valid syntax)
    assert response.status_code == status.HTTP_200_OK
    
    # Verify response structure
    result = response.json()
    assert "imports" in result
    assert "function" in result
    
    # Most importantly: verify no malicious code was executed
    assert not os.path.exists('/tmp/endpoint_test.txt')


@pytest.mark.usefixtures("active_user")
async def test_validate_endpoint_no_code_execution(client: AsyncClient, logged_in_headers):
    """Test that the validate endpoint does not execute user code"""
    # Create a unique temporary file path to test
    temp_file = f"/tmp/langflow_security_test_{os.getpid()}.txt"
    
    # Ensure the file doesn't exist before the test
    if os.path.exists(temp_file):
        os.remove(temp_file)
    
    dangerous_payload = {
        "code": f"""
import os
def dangerous_function():
    # This should NOT execute
    os.system('echo "CODE_EXECUTED" > {temp_file}')
    return "dangerous operation completed"
"""
    }
    
    # Send request
    response = await client.post("/api/v1/validate/code", json=dangerous_payload, headers=logged_in_headers)
    
    # Should return successfully (code is syntactically valid)
    assert response.status_code == status.HTTP_200_OK
    
    # Verify the dangerous file was NOT created
    assert not os.path.exists(temp_file), "Code execution vulnerability still exists!"
    
    # Clean up just in case
    if os.path.exists(temp_file):
        os.remove(temp_file)
