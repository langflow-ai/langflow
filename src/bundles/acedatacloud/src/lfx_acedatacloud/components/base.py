"""Shared component implementation; each user-facing service has a named class."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DictInput,
    DropdownInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from lfx.schema.data import Data
from lfx_acedatacloud.client import normalize, post_json
from lfx_acedatacloud.specs import FACE_PATHS, SERVICES, Field, Service

TRACE_QUERY_SERVICES = frozenset({"gpt_image", "midjourney", "veo"})
MAX_WAIT_SECONDS = 240


def _key(value: Any) -> str:
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def _field_input(field: Field) -> Any:
    kwargs = {
        "name": field.name,
        "display_name": field.label,
        "required": field.required,
        "value": field.default,
    }
    if field.options:
        return DropdownInput(**kwargs, options=list(field.options), combobox=field.name == "model")
    if field.kind == "multiline":
        return MultilineInput(**kwargs, tool_mode=True)
    if field.kind == "int":
        return IntInput(**kwargs)
    if field.kind == "bool":
        return BoolInput(**kwargs)
    return MessageTextInput(**kwargs, tool_mode=True)


def generation_inputs(service_name: str) -> list[Any]:
    service = SERVICES[service_name]
    return [
        SecretStrInput(name="api_key", display_name="Ace Data Cloud API key", required=True),
        *(_field_input(field) for field in service.fields),
        DictInput(
            name="extra_parameters",
            display_name="Additional route parameters",
            value={"async": True} if service.task_path else {},
            advanced=True,
            info="Only published fields for this action are accepted. Async media tasks default to true.",
        ),
    ]


def task_inputs(service_name: str) -> list[Any]:
    service = SERVICES[service_name]
    inputs = [
        SecretStrInput(name="api_key", display_name="Ace Data Cloud API key", required=True),
        HandleInput(
            name="submitted_task",
            display_name="Submitted task",
            input_types=["Data", "JSON"],
            required=False,
            info=f"Connect the {service.display} generation result to query the same task.",
        ),
        MessageTextInput(
            name="task_id",
            display_name="Task ID",
            required=False,
            info="Or paste an existing task ID. No generation is performed by this component.",
        ),
    ]
    if service_name in TRACE_QUERY_SERVICES:
        inputs.append(
            MessageTextInput(
                name="trace_id",
                display_name="Trace ID",
                required=False,
                advanced=True,
                info="Use a trace ID from request history if the paid submission timed out before returning a task ID.",
            )
        )
    inputs.append(
        IntInput(
            name="wait_seconds",
            display_name="Wait up to seconds",
            value=0,
            advanced=True,
            info="0 makes one read-only query; at most 240 seconds queries only this task.",
        )
    )
    return inputs


def _payload(service: Service, component: Component) -> tuple[str, dict[str, Any], dict[str, str]]:
    body = dict(service.fixed)
    for field in service.fields:
        value = getattr(component, field.name, field.default)
        if isinstance(value, str):
            value = value.strip()
        if field.required and (value is None or value == ""):
            msg = f"{field.label} is required."
            raise ValueError(msg)
        if value is not None and value != "":
            body[field.name] = value
    extra = getattr(component, "extra_parameters", None) or {}
    if not isinstance(extra, dict):
        msg = "Additional route parameters must be an object."
        raise TypeError(msg)
    unknown = set(extra) - set(service.advanced)
    if unknown:
        msg = f"Unsupported additional parameter: {min(unknown)}."
        raise ValueError(msg)
    if set(extra) & set(body):
        msg = "Additional parameters may not override a visible or fixed field."
        raise ValueError(msg)
    body.update({k: v for k, v in extra.items() if v is not None})
    path = service.path
    if service.prompt_as_content:
        body["content"] = [{"type": "text", "text": body.pop("prompt")}]
    if service.name == "face_transform":
        action = body.pop("action", "keypoints")
        if action not in FACE_PATHS:
            msg = "Unsupported face action."
            raise ValueError(msg)
        path = FACE_PATHS[action]
        if action == "swap":
            if not body.get("source_image_url") or not body.get("target_image_url"):
                msg = "Face swap requires both source and target image URLs."
                raise ValueError(msg)
            body.pop("image_url", None)
        else:
            if not body.get("image_url"):
                msg = "Image URL is required for this face action."
                raise ValueError(msg)
            body.pop("source_image_url", None)
            body.pop("target_image_url", None)
    if service.name == "google_search" and body.get("image_size") and body.get("type") != "images":
        msg = "Image size applies only to image search."
        raise ValueError(msg)
    headers = {}
    if service.fish_model_header:
        headers["model"] = str(body.pop("model"))
    for count_name in ("n", "count", "duration", "number", "page"):
        if count_name in body and isinstance(body[count_name], int) and body[count_name] <= 0:
            msg = f"{count_name} must be positive."
            raise ValueError(msg)
    return path, body, headers


class AceGenerationComponent(Component):
    """Base for one explicit service action. Subclasses set service_name."""

    service_name: str = ""
    outputs: ClassVar[list[Output]] = [Output(display_name="Result and task ID", name="result", method="run")]

    async def run(self) -> Data:
        service = SERVICES[self.service_name]
        path, body, headers = _payload(service, self)
        payload = await post_json(path, _key(self.api_key), body, headers=headers)
        return Data(data=normalize(payload, service=self.service_name))


class AceTaskComponent(Component):
    """Read only the submitted task ID; a workflow retry never generates media."""

    service_name: str = ""
    outputs: ClassVar[list[Output]] = [Output(display_name="Task result", name="result", method="run")]

    async def run(self) -> Data:
        service = SERVICES[self.service_name]
        if not service.task_path:
            msg = f"{service.display} has no async task endpoint."
            raise ValueError(msg)
        submitted = getattr(self, "submitted_task", None)
        linked = submitted.data if isinstance(submitted, Data) else submitted if isinstance(submitted, dict) else None
        if linked is not None and linked.get("service") != self.service_name:
            msg = "The connected task belongs to a different Ace Data Cloud service."
            raise ValueError(msg)
        task_id = str((linked or {}).get("task_id") or getattr(self, "task_id", "") or "").strip()
        if linked is not None and not task_id and linked.get("status") in {"succeeded", "failed"}:
            return Data(data=linked)
        trace_id = str(getattr(self, "trace_id", "") or "").strip() if self.service_name in TRACE_QUERY_SERVICES else ""
        if not task_id and not trace_id:
            msg = "Connect a submitted task or enter its task or trace ID."
            raise ValueError(msg)
        wait_seconds = int(getattr(self, "wait_seconds", 0) or 0)
        if not 0 <= wait_seconds <= MAX_WAIT_SECONDS:
            msg = "Wait seconds must be from 0 to 240."
            raise ValueError(msg)
        deadline = asyncio.get_running_loop().time() + wait_seconds
        lookup = {"action": "retrieve", "id": task_id} if task_id else {"action": "retrieve", "trace_id": trace_id}
        while True:
            payload = await post_json(
                service.task_path,
                _key(self.api_key),
                lookup,
            )
            resolved_id = task_id or (
                str(payload.get("id") or payload.get("task_id") or "") if isinstance(payload, dict) else ""
            )
            result = normalize(
                payload,
                service=self.service_name,
                retrieved=True,
                requested_task_id=resolved_id,
                requested_trace_id=trace_id,
            )
            if result["status"] != "pending" or asyncio.get_running_loop().time() >= deadline:
                return Data(data=result)
            await asyncio.sleep(min(5, max(0, deadline - asyncio.get_running_loop().time())))
