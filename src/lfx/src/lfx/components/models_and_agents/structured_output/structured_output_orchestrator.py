"""Choose between native (with_structured_output) and prompt-fallback strategies."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from lfx.components.models_and_agents.structured_output.native_structured_invoker import (
    invoke_with_native_structured_output,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pydantic import BaseModel
from lfx.components.models_and_agents.structured_output.prompt_fallback_invoker import (
    parse_and_validate_fallback_content,
)
from lfx.components.models_and_agents.structured_output.schema_preprocessing import (
    preprocess_schema,
)
from lfx.helpers.base_model import build_model_from_schema
from lfx.log.logger import logger
from lfx.schema.data import Data


async def orchestrate_structured_output(
    *,
    llm: Any,
    output_schema: list[dict[str, Any]],
    system_prompt: str,
    format_instructions: str,
    input_value: str,
    run_prompt_fallback: Callable[[str], Awaitable[str]],
    prefer_native: bool = True,
) -> Data:
    """Run structured output via native LLM API when available, otherwise via prompt fallback.

    Set prefer_native=False to force the prompt fallback even when the LLM supports
    with_structured_output (e.g. when the agent has tools that must execute first).
    """
    if not output_schema:
        await logger.adebug(
            "structured_output.short_circuited",
            extra={"strategy": "none", "reason": "empty_schema"},
        )
        return Data(data={"content": input_value})

    output_model = build_model_from_schema(preprocess_schema(output_schema))

    fallback_reason = "llm_lacks_with_structured_output"
    if prefer_native and _supports_native_structured_output(llm):
        await logger.adebug(
            "structured_output.native_invoked",
            extra={"strategy": "native"},
        )
        try:
            payload = await invoke_with_native_structured_output(
                llm=llm,
                model_cls=output_model,
                system_prompt=system_prompt,
                input_value=input_value,
            )
        except NotImplementedError as exc:
            # LangChain wrappers commonly inherit `with_structured_output` but raise
            # NotImplementedError at bind- or invocation-time when the provider does
            # not actually support it. Recover transparently via the prompt fallback.
            await logger.adebug(
                "structured_output.native_unsupported",
                extra={"strategy": "native", "reason": str(exc)},
            )
            fallback_reason = "native_raised_not_implemented"
        else:
            return _wrap_payload(payload)

    await logger.adebug(
        "structured_output.fallback_invoked",
        extra={"strategy": "prompt_fallback", "reason": fallback_reason},
    )
    augmented_prompt = _build_augmented_system_prompt(system_prompt, format_instructions, output_model)
    raw_content = await run_prompt_fallback(augmented_prompt)
    parsed = parse_and_validate_fallback_content(raw_content, output_model)
    return _wrap_payload(parsed)


def _supports_native_structured_output(llm: Any) -> bool:
    method = getattr(llm, "with_structured_output", None)
    return callable(method)


def _build_augmented_system_prompt(
    system_prompt: str,
    format_instructions: str,
    output_model: type[BaseModel],
) -> str:
    schema_json = json.dumps(output_model.model_json_schema(), indent=2)
    parts: list[str] = []
    if system_prompt:
        parts.append(system_prompt)
    if format_instructions:
        parts.append(f"Format instructions: {format_instructions}")
    parts.append(
        "You must respond ONLY with a JSON object matching this schema. "
        "Do not include explanations, markdown, or any text outside the JSON.\n"
        f"Schema:\n{schema_json}"
    )
    return "\n\n".join(parts)


def _wrap_payload(payload: dict[str, Any] | list[Any]) -> Data:
    if isinstance(payload, dict):
        return Data(data=payload)
    if len(payload) == 1 and isinstance(payload[0], dict):
        return Data(data=payload[0])
    return Data(data={"results": payload})
