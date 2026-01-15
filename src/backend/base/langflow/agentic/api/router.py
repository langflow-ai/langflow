"""Langflow Assistant API router.

This module provides the API endpoints for the Langflow Assistant, an AI-powered
assistant that helps users with Langflow-related questions, guidance, and component
creation.
"""

import asyncio
import json
import os
import re
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from lfx.base.models.unified_models import (
    get_model_provider_variable_mapping,
    get_unified_models_detailed,
)
from lfx.custom.validate import create_class, extract_class_name
from lfx.log.logger import logger
from lfx.run.base import run_flow
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE
from langflow.services.variable.service import DatabaseVariableService, VariableService

# Constants
MAX_VALIDATION_RETRIES = 3
LANGFLOW_ASSISTANT_FLOW = "LangflowAssistant.json"

# Preferred providers in order of priority (first available will be default)
PREFERRED_PROVIDERS = ["Anthropic", "OpenAI", "Google Generative AI", "Groq"]

# Default models per provider (used when user hasn't set a preference)
DEFAULT_MODELS: dict[str, str] = {
    "Anthropic": "claude-sonnet-4-5-20250514",
    "OpenAI": "gpt-5.2",
    "Google Generative AI": "gemini-2.0-flash",
    "Groq": "llama-3.3-70b-versatile",
}

# Provider to LangChain model class mapping
MODEL_CLASS_MAP: dict[str, str] = {
    "OpenAI": "ChatOpenAI",
    "Anthropic": "ChatAnthropic",
    "Google Generative AI": "ChatGoogleGenerativeAI",
    "Groq": "ChatGroq",
    "Ollama": "ChatOllama",
}

# Validation retry error message template
VALIDATION_RETRY_TEMPLATE = """The previous component code has an error. Please fix it.

ERROR:
{error}

BROKEN CODE:
```python
{code}
```

Please provide a corrected version of the component code."""


class AssistantRequest(BaseModel):
    """Request model for assistant interactions."""

    flow_id: str
    component_id: str | None = None
    field_name: str | None = None
    input_value: str | None = None
    max_retries: int | None = None
    model_name: str | None = None
    provider: str | None = None


class ValidationResult(BaseModel):
    """Result of component code validation."""

    is_valid: bool
    code: str | None = None
    error: str | None = None
    class_name: str | None = None


MAX_ERROR_MESSAGE_LENGTH = 150
MIN_MEANINGFUL_PART_LENGTH = 10

ERROR_PATTERNS: list[tuple[list[str], str]] = [
    (["rate_limit", "429"], "Rate limit exceeded. Please wait a moment and try again."),
    (["authentication", "api_key", "unauthorized", "401"], "Authentication failed. Check your API key."),
    (["quota", "billing", "insufficient"], "API quota exceeded. Please check your account billing."),
    (["timeout", "timed out"], "Request timed out. Please try again."),
    (["connection", "network"], "Connection error. Please check your network and try again."),
    (["500", "internal server error"], "Server error. Please try again later."),
]


def _extract_friendly_error(error_msg: str) -> str:
    """Convert technical API errors into user-friendly messages."""
    error_lower = error_msg.lower()

    for patterns, friendly_message in ERROR_PATTERNS:
        if any(pattern in error_lower or pattern in error_msg for pattern in patterns):
            return friendly_message

    if "model" in error_lower and ("not found" in error_lower or "does not exist" in error_lower):
        return "Model not available. Please select a different model."

    if "content" in error_lower and any(term in error_lower for term in ["filter", "policy", "safety"]):
        return "Request blocked by content policy. Please modify your prompt."

    return _truncate_error_message(error_msg)


def _truncate_error_message(error_msg: str) -> str:
    """Truncate long error messages, preserving meaningful content."""
    if len(error_msg) <= MAX_ERROR_MESSAGE_LENGTH:
        return error_msg

    if ":" in error_msg:
        for part in error_msg.split(":"):
            stripped = part.strip()
            if MIN_MEANINGFUL_PART_LENGTH < len(stripped) < MAX_ERROR_MESSAGE_LENGTH:
                return stripped

    return f"{error_msg[:MAX_ERROR_MESSAGE_LENGTH]}..."


PYTHON_CODE_BLOCK_PATTERN = r"```python\s*([\s\S]*?)```"
GENERIC_CODE_BLOCK_PATTERN = r"```\s*([\s\S]*?)```"
UNCLOSED_PYTHON_BLOCK_PATTERN = r"```python\s*([\s\S]*)$"
UNCLOSED_GENERIC_BLOCK_PATTERN = r"```\s*([\s\S]*)$"


def extract_python_code(text: str) -> str | None:
    """Extract Python code from markdown code blocks.

    Handles both closed (```python ... ```) and unclosed blocks.
    Returns the first code block that appears to be a Langflow component.
    """
    matches = _find_code_blocks(text)
    if not matches:
        return None

    return _find_component_code(matches) or matches[0].strip()


def _find_code_blocks(text: str) -> list[str]:
    """Find all code blocks in text, handling both closed and unclosed blocks."""
    matches = re.findall(PYTHON_CODE_BLOCK_PATTERN, text, re.IGNORECASE)
    if matches:
        return matches

    matches = re.findall(GENERIC_CODE_BLOCK_PATTERN, text)
    if matches:
        return matches

    return _find_unclosed_code_block(text)


def _find_unclosed_code_block(text: str) -> list[str]:
    """Handle LLM responses that don't close the code block with ```."""
    for pattern in [UNCLOSED_PYTHON_BLOCK_PATTERN, UNCLOSED_GENERIC_BLOCK_PATTERN]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            code = match.group(1).rstrip("`").strip()
            return [code] if code else []

    return []


def _find_component_code(matches: list[str]) -> str | None:
    """Find the first match that looks like a Langflow component."""
    for match in matches:
        if "class " in match and "Component" in match:
            return match.strip()
    return None


def validate_component_code(code: str) -> ValidationResult:
    """Validate component code by attempting to create the class."""
    try:
        class_name = extract_class_name(code)
        create_class(code, class_name)

        return ValidationResult(is_valid=True, code=code, class_name=class_name)
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
        return ValidationResult(is_valid=False, code=code, error=f"{type(e).__name__}: {e}")


router = APIRouter(prefix="/agentic", tags=["Agentic"])

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


def inject_model_into_flow(
    flow_data: dict,
    provider: str,
    model_name: str,
    api_key_var: str,
) -> dict:
    """Inject model configuration into the flow's Agent component.

    Args:
        flow_data: The flow JSON as a dict
        provider: The provider name (e.g., "OpenAI", "Anthropic")
        model_name: The model name (e.g., "gpt-4o", "claude-sonnet-4-5-20250929")
        api_key_var: The API key variable name (e.g., "OPENAI_API_KEY")

    Returns:
        Modified flow data with the model configuration injected
    """
    model_class = MODEL_CLASS_MAP.get(provider, "ChatOpenAI")

    # Create the model value structure
    model_value = [{
        "category": provider,
        "icon": provider.replace(" ", ""),
        "metadata": {
            "api_key_param": "api_key",
            "context_length": 128000,
            "model_class": model_class,
            "model_name_param": "model",
        },
        "name": model_name,
        "provider": provider,
    }]

    # Find and update the Agent node
    for node in flow_data.get("data", {}).get("nodes", []):
        node_data = node.get("data", {})
        if node_data.get("type") == "Agent":
            template = node_data.get("node", {}).get("template", {})
            if "model" in template:
                template["model"]["value"] = model_value
            if "api_key" in template:
                template["api_key"]["value"] = api_key_var
            break

    return flow_data


async def execute_flow_file(
    flow_filename: str,
    input_value: str | None = None,
    global_variables: dict[str, str] | None = None,
    *,
    verbose: bool = False,
    user_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> dict:
    """Execute a flow from a JSON file.

    Args:
        flow_filename: Name of the flow file (e.g., "MyFlow.json")
        input_value: Input value to pass to the flow
        global_variables: Dict of global variables to inject into the flow context
        verbose: Whether to enable verbose logging
        user_id: User ID for components that require user context (e.g., AgentComponent)
        provider: Model provider to inject into Agent nodes
        model_name: Model name to inject into Agent nodes
        api_key_var: API key variable name to inject into Agent nodes

    Returns:
        dict: Result from flow execution

    Raises:
        HTTPException: If flow file not found or execution fails
    """
    flow_path = FLOWS_BASE_PATH / flow_filename

    if not flow_path.exists():
        raise HTTPException(status_code=404, detail=f"Flow file '{flow_filename}' not found")

    try:
        flow_data = json.loads(flow_path.read_text())

        if provider and model_name and api_key_var:
            flow_data = inject_model_into_flow(flow_data, provider, model_name, api_key_var)

        flow_json = json.dumps(flow_data)
        result = await run_flow(
            flow_json=flow_json,
            input_value=input_value,
            global_variables=global_variables or {},
            verbose=verbose,
            check_variables=False,
            user_id=user_id,
        )
    except Exception as e:
        logger.error(f"Flow execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Error executing flow: {e}") from e

    return result


@router.post("/execute/{flow_name}")
async def execute_named_flow(
    flow_name: str,
    request: AssistantRequest,
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
    """Extract text from flow execution result."""
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
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
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
        provider: Model provider to inject into Agent nodes
        model_name: Model name to inject into Agent nodes
        api_key_var: API key variable name to inject into Agent nodes

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
            provider=provider,
            model_name=model_name,
            api_key_var=api_key_var,
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
        current_input = VALIDATION_RETRY_TEMPLATE.format(error=validation.error, code=code)
        logger.info("Retrying with error context...")

    # This should not be reached, but just in case
    return result


VALIDATION_UI_DELAY_SECONDS = 0.3


async def execute_flow_with_validation_streaming(
    flow_filename: str,
    input_value: str,
    global_variables: dict[str, str],
    *,
    max_retries: int = MAX_VALIDATION_RETRIES,
    user_id: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    api_key_var: str | None = None,
) -> AsyncGenerator[str, None]:
    """Execute flow with validation, yielding SSE progress events."""
    current_input = input_value
    total_attempts = max_retries + 1

    for attempt in range(1, total_attempts + 1):
        yield _sse_progress("generating", attempt, total_attempts)

        try:
            result = await execute_flow_file(
                flow_filename=flow_filename,
                input_value=current_input,
                global_variables=global_variables,
                verbose=True,
                user_id=user_id,
                provider=provider,
                model_name=model_name,
                api_key_var=api_key_var,
            )
        except HTTPException as e:
            friendly_msg = _extract_friendly_error(str(e.detail))
            logger.error(f"Flow execution failed: {friendly_msg}")
            yield _sse_error(friendly_msg)
            return
        except (ValueError, RuntimeError, OSError) as e:
            friendly_msg = _extract_friendly_error(str(e))
            logger.error(f"Flow execution failed: {friendly_msg}")
            yield _sse_error(friendly_msg)
            return

        response_text = extract_response_text(result)
        code = extract_python_code(response_text)

        if not code:
            yield _sse_complete(result)
            return

        yield _sse_progress("validating", attempt, total_attempts)
        await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

        validation = validate_component_code(code)

        if validation.is_valid:
            logger.info(f"Component '{validation.class_name}' validated successfully")
            yield _sse_complete({
                **result,
                "validated": True,
                "class_name": validation.class_name,
                "component_code": code,
                "validation_attempts": attempt,
            })
            return

        if attempt >= total_attempts:
            logger.warning(f"Validation failed after {attempt} attempts: {validation.error}")
            yield _sse_complete({
                **result,
                "validated": False,
                "validation_error": validation.error,
                "validation_attempts": attempt,
                "component_code": code,
            })
            return

        current_input = VALIDATION_RETRY_TEMPLATE.format(error=validation.error, code=code)


def _sse_progress(step: str, attempt: int, max_attempts: int) -> str:
    """Format SSE progress event."""
    data = {"event": "progress", "step": step, "attempt": attempt, "max_attempts": max_attempts}
    return f"data: {json.dumps(data)}\n\n"


def _sse_complete(data: dict) -> str:
    """Format SSE complete event."""
    return f"data: {json.dumps({'event': 'complete', 'data': data})}\n\n"


def _sse_error(message: str) -> str:
    """Format SSE error event."""
    return f"data: {json.dumps({'event': 'error', 'message': message})}\n\n"


async def get_enabled_providers_for_user(
    user_id: UUID | str,
    session: AsyncSession,
) -> tuple[list[str], dict[str, bool]]:
    """Get enabled providers for a user using the Model Providers API logic.

    Returns:
        Tuple of (enabled_providers list, provider_status dict)
    """
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        return [], {}

    # Get all credential variables for the user
    all_variables = await variable_service.get_all(user_id=user_id, session=session)

    # Get credential variable names
    credential_names = {var.name for var in all_variables if var.type == CREDENTIAL_TYPE}

    if not credential_names:
        return [], {}

    # Get the provider-variable mapping
    provider_variable_map = get_model_provider_variable_mapping()

    enabled_providers = []
    provider_status = {}

    for provider, var_name in provider_variable_map.items():
        is_enabled = var_name in credential_names
        provider_status[provider] = is_enabled
        if is_enabled:
            enabled_providers.append(provider)

    return enabled_providers, provider_status


async def check_api_key(
    variable_service: VariableService,
    user_id: UUID | str,
    key_name: str,
    session: AsyncSession,
) -> str | None:
    """Check if an API key is available from global variables or environment."""
    api_key = None

    # First try global variables
    try:
        api_key = await variable_service.get_variable(user_id, key_name, "", session)
    except ValueError:
        logger.debug(f"{key_name} not found in global variables, checking environment")

    # Then try environment
    if not api_key:
        api_key = os.getenv(key_name)

    return api_key


@router.get("/check-config")
async def check_assistant_config(
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Check if the Langflow Assistant is properly configured.

    Returns available providers with their configured status and available models.
    Uses the same logic as the Model Providers API to determine enabled providers and models.
    """
    user_id = current_user.id
    variable_service = get_variable_service()

    # Get enabled providers (same logic as /models/enabled_providers)
    enabled_providers: list[str] = []
    if isinstance(variable_service, DatabaseVariableService):
        all_variables = await variable_service.get_all(user_id=user_id, session=session)
        credential_names = {var.name for var in all_variables if var.type == CREDENTIAL_TYPE}

        if credential_names:
            provider_variable_map = get_model_provider_variable_mapping()
            for provider, var_name in provider_variable_map.items():
                if var_name in credential_names:
                    enabled_providers.append(provider)

    # Get models for enabled providers only
    all_providers = []

    if enabled_providers:
        # Get detailed models for enabled providers (language models only)
        models_by_provider = get_unified_models_detailed(
            providers=enabled_providers,
            include_unsupported=False,
            include_deprecated=False,
            model_type="language",
        )

        for provider_dict in models_by_provider:
            provider_name = provider_dict.get("provider")
            models = provider_dict.get("models", [])

            # Get all available models for this provider (not deprecated/unsupported)
            model_list = []
            for model in models:
                model_name = model.get("model_name")
                display_name = model.get("display_name", model_name)
                metadata = model.get("metadata", {})

                is_deprecated = metadata.get("deprecated", False)
                is_not_supported = metadata.get("not_supported", False)

                # Include all models that are not deprecated/unsupported
                if not is_deprecated and not is_not_supported:
                    model_list.append({
                        "name": model_name,
                        "display_name": display_name,
                    })

            # Get default model for this provider
            default_model = DEFAULT_MODELS.get(provider_name)
            if not default_model and model_list:
                default_model = model_list[0]["name"]

            if model_list:  # Only add provider if it has enabled models
                all_providers.append({
                    "name": provider_name,
                    "configured": True,
                    "default_model": default_model,
                    "models": model_list,
                })

    # Determine the default provider based on priority
    default_provider = None
    default_model = None

    # Get list of providers that have models
    providers_with_models = [p["name"] for p in all_providers]

    for preferred in PREFERRED_PROVIDERS:
        if preferred in providers_with_models:
            default_provider = preferred
            # Find the provider's default model
            for p in all_providers:
                if p["name"] == preferred:
                    default_model = p["default_model"]
                    break
            break

    # If no preferred provider found, use first one with models
    if not default_provider and all_providers:
        default_provider = all_providers[0]["name"]
        default_model = all_providers[0]["default_model"]

    return {
        "configured": len(enabled_providers) > 0,
        "configured_providers": enabled_providers,
        "providers": all_providers,
        "default_provider": default_provider,
        "default_model": default_model,
    }


@router.post("/assist")
async def assist(
    request: AssistantRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Chat with the Langflow Assistant.

    This endpoint executes the LangflowAssistant.json flow to help users with
    Langflow-related questions, guidance, and component creation.

    The assistant can:
    - Answer questions about Langflow concepts and features
    - Provide guidance on building flows
    - Help create custom components (with automatic validation)
    - Assist with troubleshooting and best practices

    If the response contains component code, it validates the code and
    retries with error feedback if validation fails.
    """
    variable_service = get_variable_service()
    user_id = current_user.id

    # Get provider-variable mapping
    provider_variable_map = get_model_provider_variable_mapping()

    # Get enabled providers for this user
    enabled_providers, _ = await get_enabled_providers_for_user(user_id, session)

    if not enabled_providers:
        raise HTTPException(
            status_code=400,
            detail="No model provider is configured. Please configure at least one model provider in Settings.",
        )

    # Determine provider to use
    provider = request.provider
    if not provider:
        # Use first preferred provider that is enabled
        for preferred in PREFERRED_PROVIDERS:
            if preferred in enabled_providers:
                provider = preferred
                break
        # Fallback to first enabled provider
        if not provider:
            provider = enabled_providers[0]

    # Validate provider is enabled
    if provider not in enabled_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider}' is not configured. Available providers: {enabled_providers}",
        )

    # Get API key variable name for the provider
    api_key_name = provider_variable_map.get(provider)
    if not api_key_name:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {provider}",
        )

    # Use default model if not specified
    model_name = request.model_name
    if not model_name:
        model_name = DEFAULT_MODELS.get(provider)

    # Check for API key
    api_key = await check_api_key(variable_service, user_id, api_key_name, session)

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{api_key_name} is required for the Langflow Assistant with {provider}. "
                "Please configure it in Settings > Model Providers."
            ),
        )

    # Prepare global variables
    global_vars = {
        "USER_ID": str(user_id),
        "FLOW_ID": request.flow_id,
        api_key_name: api_key,
        "MODEL_NAME": model_name,
        "PROVIDER": provider,
    }

    input_preview = request.input_value[:50] if request.input_value else "None"
    logger.info(f"Executing {LANGFLOW_ASSISTANT_FLOW} with {provider}/{model_name}, input: {input_preview}...")

    # Execute flow with validation loop (validates component code if present)
    max_retries = request.max_retries if request.max_retries is not None else MAX_VALIDATION_RETRIES
    return await execute_flow_with_validation(
        flow_filename=LANGFLOW_ASSISTANT_FLOW,
        input_value=request.input_value or "",
        global_variables=global_vars,
        max_retries=max_retries,
        user_id=str(user_id),
        provider=provider,
        model_name=model_name,
        api_key_var=api_key_name,
    )


@router.post("/assist/stream")
async def assist_stream(
    request: AssistantRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> StreamingResponse:
    """Chat with the Langflow Assistant with streaming progress updates.

    Returns Server-Sent Events (SSE) with progress updates during generation
    and validation. Events include:
    - progress: {"step": "generating"|"validating", "attempt": 1, "max_attempts": 4}
    - complete: Final result with validated component or response
    - error: Error message if something went wrong
    """
    variable_service = get_variable_service()
    user_id = current_user.id

    # Get provider-variable mapping
    provider_variable_map = get_model_provider_variable_mapping()

    # Get enabled providers for this user
    enabled_providers, _ = await get_enabled_providers_for_user(user_id, session)

    if not enabled_providers:
        raise HTTPException(
            status_code=400,
            detail="No model provider is configured. Please configure at least one model provider in Settings.",
        )

    # Determine provider to use
    provider = request.provider
    if not provider:
        for preferred in PREFERRED_PROVIDERS:
            if preferred in enabled_providers:
                provider = preferred
                break
        if not provider:
            provider = enabled_providers[0]

    # Validate provider is enabled
    if provider not in enabled_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider}' is not configured. Available providers: {enabled_providers}",
        )

    # Get API key variable name for the provider
    api_key_name = provider_variable_map.get(provider)
    if not api_key_name:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {provider}",
        )

    # Use default model if not specified
    model_name = request.model_name
    if not model_name:
        model_name = DEFAULT_MODELS.get(provider)

    # Check for API key
    api_key = await check_api_key(variable_service, user_id, api_key_name, session)

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{api_key_name} is required for the Langflow Assistant with {provider}. "
                "Please configure it in Settings > Model Providers."
            ),
        )

    # Prepare global variables
    global_vars = {
        "USER_ID": str(user_id),
        "FLOW_ID": request.flow_id,
        api_key_name: api_key,
        "MODEL_NAME": model_name,
        "PROVIDER": provider,
    }

    max_retries = request.max_retries if request.max_retries is not None else MAX_VALIDATION_RETRIES

    return StreamingResponse(
        execute_flow_with_validation_streaming(
            flow_filename=LANGFLOW_ASSISTANT_FLOW,
            input_value=request.input_value or "",
            global_variables=global_vars,
            max_retries=max_retries,
            user_id=str(user_id),
            provider=provider,
            model_name=model_name,
            api_key_var=api_key_name,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
