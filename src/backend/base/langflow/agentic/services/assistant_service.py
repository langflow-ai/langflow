"""Assistant service with validation and retry logic."""

import asyncio
from collections.abc import AsyncGenerator

from fastapi import HTTPException
from lfx.log.logger import logger

from langflow.agentic.helpers.code_extraction import extract_python_code
from langflow.agentic.helpers.error_handling import extract_friendly_error
from langflow.agentic.helpers.sse import format_complete_event, format_error_event, format_progress_event
from langflow.agentic.helpers.validation import validate_component_code
from langflow.agentic.services.flow_executor import execute_flow_file, extract_response_text

MAX_VALIDATION_RETRIES = 3
VALIDATION_UI_DELAY_SECONDS = 0.3
LANGFLOW_ASSISTANT_FLOW = "LangflowAssistant.json"

VALIDATION_RETRY_TEMPLATE = """The previous component code has an error. Please fix it.

ERROR:
{error}

BROKEN CODE:
```python
{code}
```

Please provide a corrected version of the component code."""


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
    """
    current_input = input_value
    attempt = 0

    while attempt <= max_retries:
        attempt += 1
        logger.info(f"Component generation attempt {attempt}/{max_retries + 1}")

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

        response_text = extract_response_text(result)
        code = extract_python_code(response_text)

        if not code:
            logger.debug("No Python code found in response, returning as-is")
            return result

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

        logger.warning(f"Validation failed (attempt {attempt}): {validation.error}")

        if attempt > max_retries:
            logger.error(f"Max retries ({max_retries}) reached. Returning last result with error.")
            return {
                **result,
                "validated": False,
                "validation_error": validation.error,
                "validation_attempts": attempt,
            }

        current_input = VALIDATION_RETRY_TEMPLATE.format(error=validation.error, code=code)
        logger.info("Retrying with error context...")

    return result


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
        yield format_progress_event("generating", attempt, total_attempts)

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
            friendly_msg = extract_friendly_error(str(e.detail))
            logger.error(f"Flow execution failed: {friendly_msg}")
            yield format_error_event(friendly_msg)
            return
        except (ValueError, RuntimeError, OSError) as e:
            friendly_msg = extract_friendly_error(str(e))
            logger.error(f"Flow execution failed: {friendly_msg}")
            yield format_error_event(friendly_msg)
            return

        response_text = extract_response_text(result)
        code = extract_python_code(response_text)

        if not code:
            yield format_complete_event(result)
            return

        yield format_progress_event("validating", attempt, total_attempts)
        await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

        validation = validate_component_code(code)

        if validation.is_valid:
            logger.info(f"Component '{validation.class_name}' validated successfully")
            yield format_complete_event({
                **result,
                "validated": True,
                "class_name": validation.class_name,
                "component_code": code,
                "validation_attempts": attempt,
            })
            return

        if attempt >= total_attempts:
            logger.warning(f"Validation failed after {attempt} attempts: {validation.error}")
            yield format_complete_event({
                **result,
                "validated": False,
                "validation_error": validation.error,
                "validation_attempts": attempt,
                "component_code": code,
            })
            return

        current_input = VALIDATION_RETRY_TEMPLATE.format(error=validation.error, code=code)
