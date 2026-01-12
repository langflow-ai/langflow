"""Agentic API router for executing arbitrary flows."""

import os
import re
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException
from lfx.custom.validate import create_class, extract_class_name
from lfx.log.logger import logger
from lfx.run.base import run_flow
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.deps import get_variable_service
from langflow.services.variable.service import VariableService

# Constants
MAX_VALIDATION_RETRIES = 3
COMPONENT_CREATION_FLOW = "ComponentCreation.json"
ANTHROPIC_API_KEY_NAME = "ANTHROPIC_API_KEY"


class FlowExecutionRequest(BaseModel):
    """Request model for flow execution."""

    flow_id: str
    component_id: str | None = None
    field_name: str | None = None
    input_value: str | None = None
    max_retries: int | None = None


class ValidationResult(BaseModel):
    """Result of component code validation."""

    is_valid: bool
    code: str | None = None
    error: str | None = None
    class_name: str | None = None


def extract_python_code(text: str) -> str | None:
    """Extract Python code from markdown code blocks.

    Looks for ```python ... ``` blocks in the text and extracts the code.
    If multiple blocks are found, returns the first one that looks like a component.

    Args:
        text: The text containing potential code blocks

    Returns:
        The extracted Python code or None if no code block found
    """
    # Pattern to match ```python ... ``` blocks
    pattern = r"```python\s*([\s\S]*?)```"
    matches = re.findall(pattern, text, re.IGNORECASE)

    if not matches:
        # Try without language specifier
        pattern = r"```\s*([\s\S]*?)```"
        matches = re.findall(pattern, text)

    if not matches:
        return None

    # Return the first match that looks like a component (contains "class" and "Component")
    for match in matches:
        if "class " in match and "Component" in match:
            return match.strip()

    # If no component-like code found, return the first match
    return matches[0].strip() if matches else None


def validate_component_code(code: str) -> ValidationResult:
    """Validate component code by attempting to create the class.

    Uses the same validation logic as the /api/v1/custom_component endpoint.

    Args:
        code: The Python code to validate

    Returns:
        ValidationResult with is_valid=True if code is valid,
        otherwise is_valid=False with error message
    """
    try:
        # Extract the class name from the code
        class_name = extract_class_name(code)

        # Try to create the class - this will raise if invalid
        create_class(code, class_name)

        return ValidationResult(
            is_valid=True,
            code=code,
            class_name=class_name,
        )
    except (
        ValueError,
        TypeError,
        SyntaxError,
        NameError,
        ModuleNotFoundError,
        AttributeError,
        ImportError,
        RuntimeError,
        KeyError,
    ) as e:
        return ValidationResult(
            is_valid=False,
            code=code,
            error=f"{type(e).__name__}: {e}",
        )


router = APIRouter(prefix="/forge", tags=["Component Forge"])

# Base path for flow JSON files
FLOWS_BASE_PATH = Path(__file__).parent.parent / "flows"


async def get_global_variable(
    variable_service: VariableService,
    user_id: UUID | str,
    variable_name: str,
    session: AsyncSession,
) -> str:
    """Get a global variable from Langflow variable service."""
    try:
        return await variable_service.get_variable(user_id, variable_name, "", session)
    except ValueError as e:
        logger.error(f"Failed to retrieve {variable_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve {variable_name}: {e}") from e


async def execute_flow_file(
    flow_filename: str,
    input_value: str | None = None,
    global_variables: dict[str, str] | None = None,
    *,
    verbose: bool = False,
    user_id: str | None = None,
) -> dict:
    """Execute a flow from a JSON file.

    Args:
        flow_filename: Name of the flow file (e.g., "MyFlow.json")
        input_value: Input value to pass to the flow
        global_variables: Dict of global variables to inject into the flow context
        verbose: Whether to enable verbose logging
        user_id: User ID for components that require user context (e.g., AgentComponent)

    Returns:
        dict: Result from flow execution

    Raises:
        HTTPException: If flow file not found or execution fails
    """
    flow_path = FLOWS_BASE_PATH / flow_filename

    if not flow_path.exists():
        raise HTTPException(status_code=404, detail=f"Flow file '{flow_filename}' not found")

    try:
        logger.debug(f"Executing flow: {flow_path}")
        result = await run_flow(
            script_path=flow_path,
            input_value=input_value,
            global_variables=global_variables or {},
            verbose=verbose,
            check_variables=False,
            user_id=user_id,
        )
    except Exception as e:
        logger.error(f"Error executing flow: {e}")
        raise HTTPException(status_code=500, detail=f"Error executing flow: {e}") from e
    else:
        logger.debug("Flow execution completed successfully")
        return result


@router.post("/execute/{flow_name}")
async def execute_named_flow(
    flow_name: str,
    request: FlowExecutionRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Execute a named flow from the flows directory.

    Args:
        flow_name: Name of the flow file (without .json extension)
        request: Flow execution request with input parameters
        current_user: Current authenticated user
        session: Database session

    Returns:
        dict: Flow execution result
    """
    variable_service = get_variable_service()
    user_id = current_user.id

    # Build global variables
    global_vars = {
        "USER_ID": str(user_id),
        "FLOW_ID": request.flow_id,
    }

    if request.component_id:
        global_vars["COMPONENT_ID"] = request.component_id
    if request.field_name:
        global_vars["FIELD_NAME"] = request.field_name

    # Try to get OPENAI_API_KEY if available (optional)
    try:
        openai_key = await get_global_variable(variable_service, user_id, "OPENAI_API_KEY", session)
        global_vars["OPENAI_API_KEY"] = openai_key
    except HTTPException:
        logger.debug("OPENAI_API_KEY not configured, continuing without it")

    # Execute the flow
    flow_filename = f"{flow_name}.json"
    return await execute_flow_file(
        flow_filename=flow_filename,
        input_value=request.input_value,
        global_variables=global_vars,
        verbose=True,
    )


def extract_response_text(result: dict) -> str:
    """Extract text from flow execution result.

    Args:
        result: The flow execution result dict

    Returns:
        The extracted text content
    """
    if "result" in result:
        return result["result"]
    if "text" in result:
        return result["text"]
    if "exception_message" in result:
        return result["exception_message"]
    return str(result)


async def execute_flow_with_validation(
    flow_filename: str,
    input_value: str,
    global_variables: dict[str, str],
    *,
    max_retries: int = MAX_VALIDATION_RETRIES,
    user_id: str | None = None,
) -> dict:
    """Execute flow and validate the generated component code.

    If the response contains Python code, it validates the code.
    If validation fails, re-executes the flow with error context.
    Continues until valid code is generated or max retries reached.

    Args:
        flow_filename: Name of the flow file
        input_value: Initial input value
        global_variables: Global variables for flow execution
        max_retries: Maximum number of validation retries
        user_id: User ID for components that require user context

    Returns:
        dict with validated result or error information
    """
    current_input = input_value
    attempt = 0

    while attempt <= max_retries:
        attempt += 1
        logger.info(f"Component generation attempt {attempt}/{max_retries + 1}")

        # Execute the flow
        result = await execute_flow_file(
            flow_filename=flow_filename,
            input_value=current_input,
            global_variables=global_variables,
            verbose=True,
            user_id=user_id,
        )

        # Extract response text
        response_text = extract_response_text(result)

        # Try to extract Python code from the response
        code = extract_python_code(response_text)

        # If no code found, return the response as-is (might be a regular message)
        if not code:
            logger.debug("No Python code found in response, returning as-is")
            return result

        # Validate the extracted code
        logger.info("Validating generated component code...")
        validation = validate_component_code(code)

        if validation.is_valid:
            logger.info(f"Component '{validation.class_name}' validated successfully!")
            return {
                **result,
                "validated": True,
                "class_name": validation.class_name,
                "component_code": code,
                "validation_attempts": attempt,
            }

        # Validation failed - prepare error feedback for retry
        logger.warning(f"Validation failed (attempt {attempt}): {validation.error}")

        if attempt > max_retries:
            # Max retries reached, return with error info
            logger.error(f"Max retries ({max_retries}) reached. Returning last result with error.")
            return {
                **result,
                "validated": False,
                "validation_error": validation.error,
                "validation_attempts": attempt,
            }

        # Prepare input for retry with error context
        current_input = (
            f"The previous component code has an error. Please fix it.\n\n"
            f"ERROR:\n{validation.error}\n\n"
            f"BROKEN CODE:\n```python\n{code}\n```\n\n"
            f"Please provide a corrected version of the component code."
        )
        logger.info("Retrying with error context...")

    # This should not be reached, but just in case
    return result


async def check_anthropic_api_key(
    variable_service: VariableService,
    user_id: UUID | str,
    session: AsyncSession,
) -> str | None:
    """Check if ANTHROPIC_API_KEY is available from global variables or environment."""
    anthropic_key = None

    # First try global variables
    try:
        anthropic_key = await variable_service.get_variable(user_id, ANTHROPIC_API_KEY_NAME, "", session)
    except ValueError:
        logger.debug(f"{ANTHROPIC_API_KEY_NAME} not found in global variables, checking environment")

    # Then try environment
    if not anthropic_key:
        anthropic_key = os.getenv(ANTHROPIC_API_KEY_NAME)

    return anthropic_key


@router.get("/check-config")
async def check_forge_config(
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Check if Component Forge is properly configured.

    Returns whether the ANTHROPIC_API_KEY is available for using Claude Sonnet 4.5.
    """
    variable_service = get_variable_service()
    anthropic_key = await check_anthropic_api_key(variable_service, current_user.id, session)

    return {
        "configured": anthropic_key is not None,
        "missing": [] if anthropic_key else ["ANTHROPIC_API_KEY"],
    }


@router.post("/prompt")
async def run_prompt_flow(
    request: FlowExecutionRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Execute the component creation flow with validation.

    This endpoint executes the ComponentCreation.json flow which uses
    Claude Sonnet 4.5 to help create Langflow components based on user input.

    If the response contains component code, it validates the code and
    retries with error feedback if validation fails (up to MAX_VALIDATION_RETRIES times).
    """
    variable_service = get_variable_service()
    user_id = current_user.id

    # Check for ANTHROPIC_API_KEY (required for Claude Sonnet 4.5)
    anthropic_key = await check_anthropic_api_key(variable_service, user_id, session)

    if not anthropic_key:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{ANTHROPIC_API_KEY_NAME} is required for Component Forge. "
                "Please configure it in your environment or global variables."
            ),
        )

    # Prepare global variables (API key passed via global_vars, not environment)
    global_vars = {
        "USER_ID": str(user_id),
        "FLOW_ID": request.flow_id,
        ANTHROPIC_API_KEY_NAME: anthropic_key,
    }

    input_preview = request.input_value[:50] if request.input_value else "None"
    logger.debug(f"Executing {COMPONENT_CREATION_FLOW} with input: {input_preview}...")

    # Execute flow with validation loop
    max_retries = request.max_retries if request.max_retries is not None else MAX_VALIDATION_RETRIES
    return await execute_flow_with_validation(
        flow_filename=COMPONENT_CREATION_FLOW,
        input_value=request.input_value or "",
        global_variables=global_vars,
        max_retries=max_retries,
        user_id=str(user_id),
    )
