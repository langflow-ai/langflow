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
from pydantic import Field, create_model

from lfx.components.models_and_agents.structured_output.prompt_fallback_invoker import (
    parse_and_validate_fallback_content,
)
from lfx.components.models_and_agents.structured_output.schema_preprocessing import (
    preprocess_schema,
)
from lfx.helpers.base_model import build_model_from_schema
from lfx.log.logger import logger
from lfx.schema.data import Data

LIST_FIELD_NAME = "objects"


def _get_list_field_name(record_model: type[BaseModel]) -> str:
    """Return an envelope field name that cannot collide with the record schema."""
    field_name = LIST_FIELD_NAME
    while field_name in record_model.model_fields:
        field_name += "_"
    return field_name


def _wrap_in_list_container(record_model: type[BaseModel], list_field_name: str) -> type[BaseModel]:
    """Wrap the record model in a list container, as the Structured Output component does.

    The schema table describes ONE record. Handing that model straight to the provider
    declares every field as a scalar, so a request like "list the South American countries"
    can only come back with one -- which is what the provider correctly did, while the
    default format instructions asked it to capture every instance (LE-2392).
    """
    return create_model(
        "OutputModel",
        __doc__="A list of extracted records.",
        **{
            list_field_name: (
                list[record_model],  # type: ignore[valid-type]
                Field(description="Every record that matches the schema.", min_length=1),
            )
        },
    )


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

    record_model = build_model_from_schema(preprocess_schema(output_schema))
    list_field_name = _get_list_field_name(record_model)
    output_model = _wrap_in_list_container(record_model, list_field_name)

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
                extra={"strategy": "native", "reason": type(exc).__name__},
            )
            fallback_reason = "native_raised_not_implemented"
        else:
            return _wrap_payload(payload, envelope_key=list_field_name)

    await logger.adebug(
        "structured_output.fallback_invoked",
        extra={"strategy": "prompt_fallback", "reason": fallback_reason},
    )
    augmented_prompt = _build_augmented_system_prompt(system_prompt, format_instructions, output_model)
    raw_content = await run_prompt_fallback(augmented_prompt)
    parsed = parse_and_validate_fallback_content(raw_content, record_model, envelope_key=list_field_name)
    return _wrap_payload(parsed, envelope_key=list_field_name)


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


def _wrap_payload(payload: dict[str, Any] | list[Any], *, envelope_key: str = LIST_FIELD_NAME) -> Data:
    if isinstance(payload, dict):
        # Unwrap the list container so the records, not the envelope, drive the shape.
        records = payload.get(envelope_key)
        if isinstance(records, list):
            return _wrap_payload(records, envelope_key=envelope_key)
        return Data(data=payload)
    if len(payload) == 1 and isinstance(payload[0], dict):
        return Data(data=payload[0])
    return Data(data={"results": payload})
