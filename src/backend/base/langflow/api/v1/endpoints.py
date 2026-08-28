from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator, Collection, Mapping
from copy import deepcopy
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID, uuid4

import orjson
import sqlalchemy as sa
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import (
    add_code_field_to_build_config,
    build_custom_component_template,
    get_instance_name,
    update_component_build_config,
)
from lfx.exceptions.tweaks import TweakRefusedError
from lfx.graph.graph.base import Graph
from lfx.graph.schema import RunOutputs
from lfx.log.logger import logger
from lfx.observability import execution_protocol
from lfx.schema.legacy_render import project_payload_to_v1
from lfx.schema.schema import InputValueRequest
from lfx.services.model_provider_policy import (
    ModelProviderPolicyError,
    ModelProviderPolicyPurpose,
    aresolve_model_provider_policy,
    reset_current_model_provider_policy_context,
    set_current_model_provider_policy_context,
)
from lfx.services.settings.service import SettingsService
from lfx.utils.component_aliases import ComponentIdentityIndex, build_component_identity_index
from lfx.utils.flow_validation import (
    CustomComponentValidationError,
    admin_only_build_required,
    prepare_flow_build_for_user,
)
from lfx.workflow.end_user_identity import (
    EndUserIdentityRequiredError,
    end_user_required_detail,
    resolve_serving_scope,
)

from langflow.api.utils import (
    CurrentActiveUser,
    DbSession,
    extract_global_variables_from_headers,
    parse_value,
    release_db_transaction,
)
from langflow.api.utils.execution_errors import caller_owns_flow as _caller_owns_flow
from langflow.api.utils.execution_errors import error_for_client
from langflow.api.v1.custom_component_policy import (
    CatalogPolicyHTTPException,
    enforce_catalog_policy_for_component_type,
    resolve_component_code_for_action,
)
from langflow.api.v1.files import get_flow
from langflow.api.v1.global_variable_defaults import apply_global_variable_defaults
from langflow.api.v1.model_provider_policy_scope import (
    ProviderPolicyAttributesDependency,
    provider_policy_attributes_for_flow,
    scoped_model_provider_policy_for_flow,
)
from langflow.api.v1.run_validation import raise_if_hitl_unsupported
from langflow.api.v1.schemas import (
    ConfigResponse,
    CustomComponentRequest,
    CustomComponentResponse,
    PublicConfigResponse,
    RunResponse,
    SimplifiedAPIRequest,
    TaskStatusResponse,
    UpdateCustomComponentRequest,
    UploadFileResponse,
)
from langflow.api.warm_graph import try_warm_run_graph
from langflow.events.event_manager import create_stream_tokens_event_manager
from langflow.exceptions.api import APIException, InvalidChatInputError
from langflow.exceptions.serialization import SerializationError
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.interface.initialize.loading import update_params_with_load_from_db_fields
from langflow.processing.process import process_tweaks, run_graph_internal
from langflow.schema.graph import Tweaks
from langflow.services.auth.utils import (
    api_key_security,
    get_current_user_for_sse,
    get_optional_user,
)
from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.authorization.access_ceiling import (
    external_access_allows,
    get_current_external_access_context,
)
from langflow.services.cache.utils import save_uploaded_file
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.flow.utils import get_all_webhook_components_in_flow
from langflow.services.database.models.jobs.model import JobType
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import (
    get_auth_service,
    get_catalog_policy_service,
    get_job_service,
    get_memory_base_service,
    get_session_service,
    get_settings_service,
    get_task_service,
    get_telemetry_service,
)
from langflow.services.event_manager import create_webhook_event_manager, webhook_event_manager
from langflow.services.telemetry.schema import RunPayload
from langflow.utils.compression import compress_response
from langflow.utils.version import get_version_info

if TYPE_CHECKING:
    from langflow.events.event_manager import EventManager

router = APIRouter(tags=["Base"])

# SSE Constants
SSE_HEARTBEAT_TIMEOUT_SECONDS = 30.0


def _has_nonempty_tweaks(tweaks: Tweaks | dict | None) -> bool:
    """Handle both the Tweaks RootModel and ordinary mappings."""
    return bool(getattr(tweaks, "root", tweaks))


def _enforce_owner_only_tweaks(
    flow: Flow | FlowRead,
    user: User | UserRead,
    tweaks: Tweaks | dict | None,
) -> None:
    """Reject caller-controlled graph mutation without revealing a shared flow."""
    if _has_nonempty_tweaks(tweaks) and not _caller_owns_flow(flow, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")


def _graph_executes_as_actor(
    graph: Graph,
    user: User | UserRead,
    *,
    flow_id: UUID | str,
) -> bool:
    """Reject cached graphs whose instantiated components retain another principal."""
    actor_id = str(user.id)
    if str(getattr(graph, "flow_id", None)) != str(flow_id):
        return False
    if str(getattr(graph, "user_id", None)) != actor_id:
        return False
    for vertex in getattr(graph, "vertices", []):
        component = getattr(vertex, "custom_component", None)
        component_user_id = getattr(component, "_user_id", None)
        if component_user_id is not None and str(component_user_id) != actor_id:
            return False
    return True


_SIMPLIFIED_API_FORM_FIELDS = (
    "input_value",
    "input_type",
    "output_type",
    "output_component",
    "session_id",
    "user_id",
)


async def _parse_multipart_form_data(http_request: Request) -> SimplifiedAPIRequest:
    """Parse SimplifiedAPIRequest fields from a multipart/form-data request.

    Reads the form via ``http_request.form()`` so uploaded file streams are not
    consumed by an upstream JSON parse attempt. Only string-valued fields that
    map to ``SimplifiedAPIRequest`` are extracted; any ``UploadFile`` entries
    (e.g. inline file uploads) are intentionally ignored here and remain
    available to downstream handlers.
    """
    form = await http_request.form()
    data: dict = {}

    for field in _SIMPLIFIED_API_FORM_FIELDS:
        value = form.get(field)
        if isinstance(value, str):
            data[field] = value

    raw_tweaks = form.get("tweaks")
    if isinstance(raw_tweaks, (str, bytes)) and raw_tweaks:
        try:
            data["tweaks"] = orjson.loads(raw_tweaks)
        except orjson.JSONDecodeError as exc:
            logger.warning(f"Failed to parse 'tweaks' form field as JSON: {exc}")

    return SimplifiedAPIRequest(**data)


async def parse_input_request_from_body(http_request: Request) -> SimplifiedAPIRequest:
    """Parse SimplifiedAPIRequest from HTTP request body.

    This function handles the case where FastAPI can't automatically parse the request body
    due to the presence of a Request parameter in the endpoint signature.

    Supports both ``application/json`` and ``multipart/form-data`` bodies. For
    multipart requests, form fields matching ``SimplifiedAPIRequest`` (including
    ``session_id``) are extracted via ``request.form()`` rather than being lost
    to a failing JSON parse.

    Args:
        http_request: The FastAPI Request object

    Returns:
        SimplifiedAPIRequest: Parsed request or default instance if parsing fails
    """
    content_type = (http_request.headers.get("content-type") or "").lower()

    try:
        if content_type.startswith("multipart/form-data"):
            return await _parse_multipart_form_data(http_request)

        body = await http_request.body()
        if body:
            body_data = orjson.loads(body)
            return SimplifiedAPIRequest(**body_data)
        return SimplifiedAPIRequest()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to parse request body: {exc}")
        return SimplifiedAPIRequest()


@router.get("/all")
async def get_all(
    request: Request,
    current_user: CurrentActiveUser,
    provider_policy_attributes: ProviderPolicyAttributesDependency,
    *,
    include_blocked: bool = False,
):
    """Retrieve all component types with compression for better performance.

    Returns a compressed response containing all available component types,
    with display_names translated to the locale indicated by Accept-Language.
    """
    if include_blocked and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can include blocked catalog components.",
        )

    from langflow.interface.components import get_and_cache_all_types_dict, get_component_identity_index
    from langflow.utils.i18n import build_component_display_names, translate_component_dict

    try:
        catalog_policy_snapshot = get_catalog_policy_service().snapshot
        all_types_en = await get_and_cache_all_types_dict(settings_service=get_settings_service())
        component_identity_index = get_component_identity_index(all_types_en)
        visible_types_en = await _filter_component_palette_by_provider_policy(
            all_types_en,
            user_id=current_user.id,
            attributes=provider_policy_attributes,
        )
        if not include_blocked:
            visible_types_en = _filter_component_palette_by_catalog_policy(
                visible_types_en,
                blocked_component_keys=catalog_policy_snapshot.blocked_component_keys,
                component_identity_index=component_identity_index,
            )

        locale = getattr(request.state, "locale", "en")
        all_types = translate_component_dict(visible_types_en, locale) if locale != "en" else visible_types_en

        component_display_names = build_component_display_names(visible_types_en)
        return compress_response({**all_types, "component_display_names": component_display_names})

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _filter_component_palette_by_provider_policy(
    all_types: dict[str, dict[str, dict]],
    *,
    user_id: UUID | str | None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, dict[str, dict]]:
    """Return a request-local palette with denied model providers removed.

    The component registry is a process-wide cache. Copy category mappings and
    never delete from the cached object, otherwise one user's policy decision
    would leak into every later request. Unrelated components in mixed bundles
    have no ``model_provider_id`` and always remain present.
    """
    provider_ids = {
        provider_id
        for components in all_types.values()
        for component in components.values()
        if isinstance(component, dict)
        and isinstance((metadata := component.get("metadata")), dict)
        and isinstance((provider_id := metadata.get("model_provider_id")), str)
        and provider_id
    }
    policy = await aresolve_model_provider_policy(
        user_id=user_id,
        providers=provider_ids,
        purpose=ModelProviderPolicyPurpose.DISCOVER,
        attributes=attributes,
    )
    return {
        category: {
            name: component
            for name, component in components.items()
            if not isinstance(component, dict)
            or not isinstance(component.get("metadata"), dict)
            or not (provider_id := component["metadata"].get("model_provider_id"))
            or policy.allows(provider_id)
        }
        for category, components in all_types.items()
    }


def _filter_component_palette_by_catalog_policy(
    all_types: dict[str, dict[str, dict]],
    *,
    blocked_component_keys: Collection[str],
    component_identity_index: ComponentIdentityIndex | None = None,
) -> dict[str, dict[str, dict]]:
    """Return shallow category copies with canonically blocked components removed.

    Policy keys and component-registry keys use the same collision-aware
    identity resolver as flow/runtime validation. Category order, component
    order, and empty categories are preserved. Component payloads remain
    shared with the process-wide cache and are never mutated or deep-copied.
    """
    identity_index = component_identity_index or build_component_identity_index(all_types)
    blocked_identities = identity_index.resolve_many(blocked_component_keys)
    return {
        category: {
            component_key: component
            for component_key, component in components.items()
            if identity_index.resolve(component_key).isdisjoint(blocked_identities)
        }
        for category, components in all_types.items()
    }


def validate_input_and_tweaks(input_request: SimplifiedAPIRequest) -> None:
    # If the input_value is not None and the input_type is "chat"
    # then we need to check the tweaks if the ChatInput component is present
    # and if its input_value is not None
    # if so, we raise an error
    if not input_request.tweaks:
        return

    for key, value in input_request.tweaks.items():
        if not isinstance(value, dict):
            continue

        input_value = value.get("input_value")
        if input_value is None:
            continue

        request_has_input = input_request.input_value is not None

        if any(chat_key in key for chat_key in ("ChatInput", "Chat Input")):
            if request_has_input and input_request.input_type == "chat":
                msg = "If you pass an input_value to the chat input, you cannot pass a tweak with the same name."
                raise InvalidChatInputError(msg)

        elif (
            any(text_key in key for text_key in ("TextInput", "Text Input"))
            and request_has_input
            and input_request.input_type == "text"
        ):
            msg = "If you pass an input_value to the text input, you cannot pass a tweak with the same name."
            raise InvalidChatInputError(msg)


async def simple_run_flow(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    *,
    stream: bool = False,
    api_key_user: User | None = None,
    event_manager: EventManager | None = None,
    context: dict | None = None,
    run_id: str | None = None,
    expose_error_details: bool = False,
    http_request: Request | None = None,
):
    validate_input_and_tweaks(input_request)
    policy_context_token = set_current_model_provider_policy_context(
        user_id=getattr(api_key_user, "id", None),
        attributes=provider_policy_attributes_for_flow(
            flow,
            is_superuser=bool(getattr(api_key_user, "is_superuser", False)),
            required=True,
        ),
    )
    try:
        task_result: list[RunOutputs] = []
        user_id = api_key_user.id if api_key_user else None
        flow_id_str = str(flow.id)
        if flow.data is None:
            msg = f"Flow {flow_id_str} has no data"
            raise ValueError(msg)
        # The stored graph is caller-controlled: a regular user can persist component source
        # through the flow-write API and then execute it here. Apply the caller-aware
        # component policy to a detached copy so ``custom_component_admin_only`` is enforced
        # on stored bytes, not only on inline build payloads. Returns ``None`` when no
        # caller-specific restriction applies, leaving the existing fast paths untouched.
        sanitized_flow_data = await prepare_flow_build_for_user(
            flow.data,
            is_superuser=bool(getattr(api_key_user, "is_superuser", False)),
        )
        # Opt-in warm fast-path: serve a deepcopy of the pre-built
        # template + apply this run's identity, skipping from_payload and the flow-row
        # rebuild. Returns None (-> cold rebuild below) for tweaks / context / auto-bind
        # flows / HITL / disabled registry / cache-miss. See ``try_warm_run_graph``.
        # Skipped entirely once the policy sanitized the graph: the warm template is built
        # from the unsanitized stored row and would reintroduce the untrusted source.
        graph = (
            None
            if sanitized_flow_data is not None
            else await try_warm_run_graph(flow, input_request, user_id=user_id, context=context, stream=stream)
        )
        if graph is None:
            graph_data = (sanitized_flow_data if sanitized_flow_data is not None else flow.data).copy()
            graph_data = process_tweaks(graph_data, input_request.tweaks or {}, stream=stream)
            raise_if_hitl_unsupported(graph_data)
            # Mirror the Playground's one-time fix in-memory: bind empty fields whose
            # display_name matches a user global variable's default_fields. Without
            # this, API-only workflows never trigger the frontend hook that persists
            # load_from_db=true, so variables with "Apply to Fields" silently fail.
            # See: https://github.com/langflow-ai/langflow/issues/11781
            if user_id is not None:
                graph_data = await apply_global_variable_defaults(graph_data, user_id)
            graph = Graph.from_payload(
                graph_data, flow_id=flow_id_str, user_id=str(user_id), flow_name=flow.name, context=context
            )
        # Forward the caller-supplied identifier to tracing providers without
        # affecting authn/authz. The API-key owner remains the effective user
        # for permissions, global variables, and job ownership.
        if input_request.user_id:
            graph.tracing_user_id = input_request.user_id
        run_id_uuid = uuid4() if run_id is None else UUID(run_id)
        run_id = str(run_id_uuid)
        graph.set_run_id(run_id)

        # Serving-plane end-user session scoping (shared with the v2 workflow router):
        # merge an identified end-user into the effective session_id so per-user memory
        # is isolated, and mark an anonymous run non-persisting. resolve_serving_scope
        # returns None under the default settings (feature off), so v1 /run, webhook and
        # every editor-plane caller are byte-for-byte unchanged. Callers that cannot
        # supply the request (no header available) pass http_request=None and skip it.
        effective_session_id = input_request.session_id
        if http_request is not None:
            try:
                scoped = resolve_serving_scope(
                    http_request=http_request,
                    requested_session_id=input_request.session_id,
                    # run_graph_internal falls back to the flow id when no session id is
                    # supplied; mirror that here so an identified run with no session id
                    # scopes to ``<end-user>::<flow_id>`` rather than a bare flow id.
                    default_session_id=flow_id_str,
                )
            except EndUserIdentityRequiredError as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=end_user_required_detail(exc),
                ) from exc
            if scoped is not None:
                effective_session_id = scoped.session_id
                graph.persist_messages = scoped.persist
                # Carry the end-user identity onto the graph so services (chat memory,
                # and later telemetry / agent file writes) scope per-user state to the
                # end user. None for an anonymous run.
                graph.end_user_id = scoped.end_user_id

        inputs = None
        if input_request.input_value is not None:
            inputs = [
                InputValueRequest(
                    components=[],
                    input_value=input_request.input_value,
                    type=input_request.input_type,
                )
            ]
        if input_request.output_component:
            outputs = [input_request.output_component]
        else:
            outputs = [
                vertex.id
                for vertex in graph.vertices
                if input_request.output_type == "debug"
                or (
                    vertex.is_output
                    and (input_request.output_type == "any" or input_request.output_type in vertex.id.lower())  # type: ignore[operator]
                )
            ]

        # Create a WORKFLOW job record so memory-base on_flow_output can track this run.
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to run flows.",
            )

        try:
            _job_svc = get_job_service()
            await _job_svc.create_job(
                job_id=run_id_uuid,
                flow_id=flow.id,
                user_id=user_id,
                job_type=JobType.WORKFLOW,
                # Record the serving end user (set on the graph by resolve_serving_scope) so
                # status/stop isolate to it; user_id stays the executing SID. See F8. Defensive
                # getattr: the warm-run path may hand back a lightweight graph stand-in without
                # this attribute, matching every other end_user_id read in the codebase.
                end_user_id=getattr(graph, "end_user_id", None),
            )
            # The funnel default. Binding is outermost-wins, so a caller that already named its
            # surface (webhook, mcp, openai_responses) keeps it and only the bare v1 route lands
            # here; a new surface that reuses simple_run_flow is labelled "v1" rather than nothing.
            with execution_protocol("v1"):
                task_result, session_id = await _job_svc.execute_with_status(
                    run_id_uuid,
                    run_graph_internal,
                    graph=graph,
                    flow_id=flow_id_str,
                    session_id=effective_session_id,
                    inputs=inputs,
                    outputs=outputs,
                    stream=stream,
                    event_manager=event_manager,
                )
        except Exception as exc:
            if isinstance(exc, HTTPException):
                if expose_error_details:
                    raise
                raise error_for_client(exc, expose_details=expose_error_details) from exc
            await logger.aerror(
                "Workflow job execution failed for flow %s: %s",
                flow.id,
                str(exc),
                exc_info=True,
            )
            client_error = error_for_client(exc, expose_details=expose_error_details)
            raise APIException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                exception=client_error,
                flow=flow if expose_error_details else None,
            ) from exc

        # Memory-base auto-capture resolves the flow owner's private credentials.
        # Delegated/public executions must never trigger that owner-scoped side effect.
        if flow.user_id is not None and str(flow.user_id) == str(user_id):
            try:
                _run_id_uuid = UUID(graph.run_id) if graph.run_id else None  # type-cast only
                await get_task_service().fire_and_forget_task(
                    get_memory_base_service().on_flow_output,
                    flow_id=flow.id,
                    session_id=session_id,
                    job_id=_run_id_uuid,
                )
            except (RuntimeError, ValueError, OSError):
                await logger.awarning("Memory base hook scheduling failed for flow %s", flow.id, exc_info=True)

        return RunResponse(outputs=task_result, session_id=session_id)

    except sa.exc.StatementError as exc:
        raise ValueError(str(exc)) from exc
    finally:
        reset_current_model_provider_policy_context(policy_context_token)


def _get_vertex_ids_from_flow(flow: Flow) -> list[str]:
    """Extract vertex IDs from flow data."""
    if not flow.data or not flow.data.get("nodes"):
        return []
    return [node.get("id") for node in flow.data.get("nodes", []) if node.get("id")]


async def simple_run_flow_task(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    *,
    stream: bool = False,
    api_key_user: User | None = None,
    event_manager: EventManager | None = None,
    telemetry_service=None,
    start_time: float | None = None,
    run_id: str | None = None,
    emit_events: bool = False,
    flow_id: str | None = None,
    http_request: Request | None = None,
):
    """Run a flow task as a BackgroundTask, therefore it should not throw exceptions.

    Args:
        flow: The flow to execute
        input_request: The simplified API request
        stream: Whether to stream results
        api_key_user: The user executing the flow
        event_manager: Event manager for streaming
        telemetry_service: Service for logging telemetry
        start_time: Start time for duration calculation
        run_id: Unique ID for this run
        emit_events: Whether to emit events to webhook_event_manager (for UI feedback)
        flow_id: Flow ID for event emission (required if emit_events=True)
        http_request: The incoming HTTP request, forwarded so serving-plane end-user
            session scoping can read the trusted identity header (None to skip).
    """
    should_emit = emit_events and flow_id

    # Create an EventManager that forwards events to webhook SSE if we should emit
    webhook_em = None
    if should_emit and event_manager is None and flow_id is not None:
        webhook_em = create_webhook_event_manager(flow_id, run_id)

    # Use provided event_manager or the webhook one
    effective_event_manager = event_manager or webhook_em

    try:
        if should_emit and flow_id is not None:
            vertex_ids = _get_vertex_ids_from_flow(flow)
            await webhook_event_manager.emit(
                flow_id,
                "vertices_sorted",
                {"ids": vertex_ids, "to_run": vertex_ids, "run_id": run_id},
            )

        with execution_protocol("webhook"):
            result = await simple_run_flow(
                flow=flow,
                input_request=input_request,
                stream=stream,
                api_key_user=api_key_user,
                event_manager=effective_event_manager,
                run_id=run_id,
                expose_error_details=api_key_user is not None and _caller_owns_flow(flow, api_key_user),
                http_request=http_request,
            )

        if should_emit and flow_id is not None:
            await webhook_event_manager.emit(flow_id, "end", {"run_id": run_id, "success": True})

        if telemetry_service and start_time is not None:
            await telemetry_service.log_package_run(
                RunPayload(
                    run_is_webhook=True,
                    run_seconds=int(time.perf_counter() - start_time),
                    run_success=True,
                    run_error_message="",
                    run_id=run_id,
                )
            )
        return result  # noqa: TRY300

    except Exception as exc:  # noqa: BLE001
        await logger.aexception(f"Error running flow {flow.id} task")

        if should_emit and flow_id is not None:
            await webhook_event_manager.emit(flow_id, "end", {"run_id": run_id, "success": False, "error": str(exc)})

        if telemetry_service and start_time is not None:
            await telemetry_service.log_package_run(
                RunPayload(
                    run_is_webhook=True,
                    run_seconds=int(time.perf_counter() - start_time),
                    run_success=False,
                    run_error_message=str(exc),
                    run_id=run_id,
                )
            )
        return None


def _v1_run_response(response: RunResponse) -> JSONResponse:
    """Serialize a RunResponse with content_blocks projected to the v1 shape.

    The /run result holds Messages whose content_blocks serialize through the
    shared (v2) Message serializer, so project them at this v1 boundary to keep
    the release-1.11.0 wire shape. The live objects and the v2 path are untouched.
    """
    return JSONResponse(content=project_payload_to_v1(jsonable_encoder(response)))


def _project_run_event(value):
    """Project a /run stream event's content_blocks to the v1 shape.

    Covers add_message events and the final ``end`` result (which nests messages)
    before they reach a v1 client. The v2 path drains a different queue and never
    passes through here. The substring guard skips events that carry no
    content_blocks (tokens, ...).
    """
    if not isinstance(value, (bytes, bytearray)):
        return value
    raw = value.decode("utf-8")
    if "content_blocks" not in raw:
        return value
    try:
        event = json.loads(raw.rstrip("\n"))
    except (ValueError, TypeError):
        return value
    return (json.dumps(project_payload_to_v1(event)) + "\n\n").encode("utf-8")


async def consume_and_yield(queue: asyncio.Queue, client_consumed_queue: asyncio.Queue) -> AsyncGenerator:
    """Consumes events from a queue and yields them to the client while tracking timing metrics.

    This coroutine continuously pulls events from the input queue and yields them to the client.
    It tracks timing metrics for how long events spend in the queue and how long the client takes
    to process them.

    Args:
        queue (asyncio.Queue): The queue containing events to be consumed and yielded
        client_consumed_queue (asyncio.Queue): A queue for tracking when the client has consumed events

    Yields:
        The value from each event in the queue

    Notes:
        - Events are tuples of (event_id, value, put_time)
        - Breaks the loop when receiving a None value, signaling completion
        - Tracks and logs timing metrics for queue time and client processing time
        - Notifies client consumption via client_consumed_queue
    """
    while True:
        event_id, value, put_time = await queue.get()
        if value is None:
            break
        get_time = time.time()
        yield _project_run_event(value)
        get_time_yield = time.time()
        client_consumed_queue.put_nowait(event_id)
        await logger.adebug(
            f"consumed event {event_id} "
            f"(time in queue, {get_time - put_time:.4f}, "
            f"client {get_time_yield - get_time:.4f})"
        )


async def run_flow_generator(
    flow: Flow,
    input_request: SimplifiedAPIRequest,
    api_key_user: User | None,
    event_manager: EventManager,
    client_consumed_queue: asyncio.Queue,
    context: dict | None = None,
    *,
    expose_error_details: bool = False,
    http_request: Request | None = None,
) -> None:
    """Executes a flow asynchronously and manages event streaming to the client.

    This coroutine runs a flow with streaming enabled and handles the event lifecycle,
    including success completion and error scenarios.

    Args:
        flow (Flow): The flow to execute
        input_request (SimplifiedAPIRequest): The input parameters for the flow
        api_key_user (User | None): Optional authenticated user running the flow
        event_manager (EventManager): Manages the streaming of events to the client
        client_consumed_queue (asyncio.Queue): Tracks client consumption of events
        context (dict | None): Optional context to pass to the flow
        expose_error_details: Whether client events may contain owner debugging details.
        http_request: The incoming HTTP request, forwarded so serving-plane end-user
            session scoping can read the trusted identity header (None to skip).

    Events Generated:
        - "add_message": Sent when new messages are added during flow execution
        - "token": Sent for each token generated during streaming
        - "end": Sent when flow execution completes, includes final result
        - "error": Sent if an error occurs during execution

    Notes:
        - Runs the flow with streaming enabled via simple_run_flow()
        - On success, sends the final result via event_manager.on_end()
        - On error, logs the error and sends it via event_manager.on_error()
        - Always sends a final None event to signal completion
    """
    try:
        result = await simple_run_flow(
            flow=flow,
            input_request=input_request,
            stream=True,
            api_key_user=api_key_user,
            event_manager=event_manager,
            context=context,
            expose_error_details=expose_error_details,
            http_request=http_request,
        )
        event_manager.on_end(data={"result": result.model_dump()})
        await client_consumed_queue.get()
    except Exception as e:  # noqa: BLE001 - Catch ALL exceptions to ensure errors are propagated in streaming
        await logger.aerror(f"Error running flow: {e}")
        client_error = error_for_client(e, expose_details=expose_error_details)
        event_manager.on_error(data={"error": str(client_error)})
    finally:
        await event_manager.queue.put((None, None, time.time))


async def get_flow_for_api_key_user(
    flow_id_or_name: str,
    api_key_user: Annotated[UserRead, Depends(api_key_security)],
) -> FlowRead:
    """Auth-aware wrapper around ``get_flow_by_id_or_endpoint_name`` for API-key routes.

    Using the raw helper as a FastAPI ``Depends`` exposed ``user_id`` as a
    plain query parameter that no real caller sets, so flow lookups on the
    ``/run*`` routes bypassed user scoping entirely. This wrapper pulls the
    authenticated user from ``api_key_security`` and passes it to the helper,
    so cross-user access fails closed with 404 at the helper layer.

    When an authorization plugin is registered, the lookup is
    share-aware (load by id, route guard decides access). The OSS pass-through
    default keeps the owner-scoped lookup.
    """
    # These wrappers always pair with ``ensure_flow_permission`` in the route
    # handler, so opting in to share-aware widening is safe.
    return await get_flow_by_id_or_endpoint_name(flow_id_or_name, api_key_user.id, widen_for_shares=True)


async def get_flow_for_current_user(
    flow_id_or_name: str,
    current_user: CurrentActiveUser,
) -> FlowRead:
    """Session-auth variant of :func:`get_flow_for_api_key_user`."""
    return await get_flow_by_id_or_endpoint_name(flow_id_or_name, current_user.id, widen_for_shares=True)


class SseAuth:
    """Helper to carry both authenticated user and flow for SSE subscription."""

    def __init__(self, user: User | UserRead, flow: FlowRead):
        self.user = user
        self.flow = flow


async def get_flow_for_sse_user(
    flow_id_or_name: str,
    user: Annotated[User | UserRead, Depends(get_current_user_for_sse)],
) -> SseAuth:
    """Auth-aware dependency for SSE routes.

    Returns both the SSE user and the flow so the route can call
    ``ensure_flow_permission`` *before* subscribing to the event stream.
    Widening to share-aware lookup is safe here only because the route
    immediately enforces ``flow:read``; without that enforcement, a non-owner
    with cross-user fetch enabled could subscribe to another user's webhook
    event stream and exfiltrate flow id/name plus event payloads.
    """
    flow = await get_flow_by_id_or_endpoint_name(flow_id_or_name, user_id=user.id, widen_for_shares=True)
    return SseAuth(user=user, flow=flow)


class WebhookAuth:
    """Helper to carry both authenticated user and flow for webhook execution."""

    def __init__(self, user: UserRead, flow: FlowRead):
        self.user = user
        self.flow = flow


async def get_webhook_auth(
    flow_id_or_name: str,
    request: Request,
) -> WebhookAuth:
    """Auth-aware dependency that resolves both the webhook user and the flow.

    Centralizes the security logic for webhook run endpoints.
    """
    webhook_user = await get_auth_service().get_webhook_user(flow_id_or_name, request)
    # Webhook route also calls ``ensure_flow_permission`` after, so widening
    # for shared resources is acceptable here.
    flow = await get_flow_by_id_or_endpoint_name(flow_id_or_name, user_id=webhook_user.id, widen_for_shares=True)
    return WebhookAuth(user=webhook_user, flow=flow)


async def _run_flow_internal(
    *,
    background_tasks: BackgroundTasks,
    flow: FlowRead | None,
    input_request: SimplifiedAPIRequest | None,
    stream: bool,
    api_key_user: User | UserRead,
    context: dict | None,
    http_request: Request,
) -> StreamingResponse | RunResponse:
    """Internal function containing the core business logic for running a flow.

    This function is shared between session-based and API key-based authentication endpoints.

    Args:
        background_tasks (BackgroundTasks): FastAPI background task manager
        flow (FlowRead | None): The flow to execute, loaded via dependency
        input_request (SimplifiedAPIRequest | None): Input parameters for the flow
        stream (bool): Whether to stream the response
        api_key_user (User | UserRead): Authenticated user (either from session or API key)
        context (dict | None): Optional context to pass to the flow
        http_request (Request): The incoming HTTP request for extracting global variables

    Returns:
        Union[StreamingResponse, RunResponse]: Either a streaming response for real-time results
        or a RunResponse with the complete execution results

    Raises:
        HTTPException: For flow not found (404) or invalid input (400)
        APIException: For internal execution errors (500)
    """
    # Authorization happens upstream. A granted share may execute the stored
    # graph, but only the owner may mutate it through request tweaks.
    telemetry_service = get_telemetry_service()

    # If input_request is None, manually parse the request body
    # This happens when FastAPI can't automatically parse it due to the Request parameter
    if input_request is None:
        input_request = await parse_input_request_from_body(http_request)

    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")

    expose_error_details = _caller_owns_flow(flow, api_key_user)
    _enforce_owner_only_tweaks(flow, api_key_user, input_request.tweaks)

    # Extract request-level variables from headers with prefix X-LANGFLOW-GLOBAL-VAR-*
    request_variables = extract_global_variables_from_headers(http_request.headers)

    # Merge request variables with existing context
    if request_variables:
        if context is None:
            context = {"request_variables": request_variables}
        else:
            context = context.copy()  # Don't modify the original context
            context["request_variables"] = request_variables

    start_time = time.perf_counter()

    # Required-identity gate must fire BEFORE the streaming branch: that branch returns a
    # StreamingResponse with 200 headers before simple_run_flow runs, so its 401 would only ever
    # arrive as an in-stream error event. Enforce it synchronously here (idempotent with the scope
    # simple_run_flow applies again on the same http_request). The non-stream path also flows
    # through this — harmless, it already surfaced the 401 by propagation. Mirrors the webhook
    # pre-check (I3); kept outside any try so the 401 is not rewritten. See BUG-01.
    try:
        resolve_serving_scope(
            http_request=http_request,
            requested_session_id=input_request.session_id,
            default_session_id=str(flow.id),
        )
    except EndUserIdentityRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=end_user_required_detail(exc),
        ) from exc

    if stream:
        asyncio_queue: asyncio.Queue = asyncio.Queue()
        asyncio_queue_client_consumed: asyncio.Queue = asyncio.Queue()
        event_manager = create_stream_tokens_event_manager(queue=asyncio_queue)
        main_task = asyncio.create_task(
            run_flow_generator(
                flow=flow,
                input_request=input_request,
                api_key_user=api_key_user,
                event_manager=event_manager,
                client_consumed_queue=asyncio_queue_client_consumed,
                context=context,
                expose_error_details=expose_error_details,
                http_request=http_request,
            )
        )

        async def on_disconnect() -> None:
            await logger.adebug("Client disconnected, closing tasks")
            main_task.cancel()

        return StreamingResponse(
            consume_and_yield(asyncio_queue, asyncio_queue_client_consumed),
            background=on_disconnect,
            media_type="text/event-stream",
        )

    run_id = str(uuid4())
    try:
        result = await simple_run_flow(
            flow=flow,
            input_request=input_request,
            stream=stream,
            api_key_user=api_key_user,
            context=context,
            run_id=run_id,
            expose_error_details=expose_error_details,
            http_request=http_request,
        )
        end_time = time.perf_counter()
        background_tasks.add_task(
            telemetry_service.log_package_run,
            RunPayload(
                run_is_webhook=False,
                run_seconds=int(end_time - start_time),
                run_success=True,
                run_error_message="",
                run_id=run_id,
            ),
        )

    except ValueError as exc:
        background_tasks.add_task(
            telemetry_service.log_package_run,
            RunPayload(
                run_is_webhook=False,
                run_seconds=int(time.perf_counter() - start_time),
                run_success=False,
                run_error_message=str(exc),
                run_id=run_id,
            ),
        )
        if "badly formed hexadecimal UUID string" in str(exc):
            # This means the Flow ID is not a valid UUID which means it can't find the flow
            http_error = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
            raise error_for_client(http_error, expose_details=expose_error_details) from exc
        if isinstance(exc, CustomComponentValidationError):
            http_error = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
            raise error_for_client(http_error, expose_details=expose_error_details) from exc
        if "not found" in str(exc):
            http_error = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
            raise error_for_client(http_error, expose_details=expose_error_details) from exc
        client_error = error_for_client(exc, expose_details=expose_error_details)
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            exception=client_error,
            flow=flow if expose_error_details else None,
        ) from exc
    except InvalidChatInputError as exc:
        http_error = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        raise error_for_client(http_error, expose_details=expose_error_details) from exc
    except HTTPException as exc:
        if expose_error_details:
            raise
        raise error_for_client(exc, expose_details=expose_error_details) from exc
    except TweakRefusedError:
        # A refused tweak is a caller error, not a server fault. The generic
        # handler below turns it into a 500 and discards the structured body
        # naming the refused keys, so let the app-level handler answer with 422.
        #
        # Deliberately not routed through error_for_client. That helper only
        # preserves the status of an HTTPException, and this is not one, so
        # redacting would degrade it to RuntimeError -> 500 and reinstate the
        # exact bug this re-raise exists to fix, for delegated callers only.
        # The cost is that the refusal reason tells a non-owner whether the
        # flow declares an allowlist or the deployment refuses tweaks. Accepted:
        # no data, no stack trace, and the refused names are the caller's own
        # request keys. A caller who cannot tell a refused tweak from an applied
        # one is the failure this whole path is here to prevent.
        raise
    except Exception as exc:
        background_tasks.add_task(
            telemetry_service.log_package_run,
            RunPayload(
                run_is_webhook=False,
                run_seconds=int(time.perf_counter() - start_time),
                run_success=False,
                run_error_message=str(exc),
                run_id=run_id,
            ),
        )
        client_error = error_for_client(exc, expose_details=expose_error_details)
        raise APIException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            exception=client_error,
            flow=flow if expose_error_details else None,
        ) from exc

    return _v1_run_response(result)


@router.post("/run/{flow_id_or_name}", response_model=None, response_model_exclude_none=True)
async def simplified_run_flow(
    *,
    background_tasks: BackgroundTasks,
    flow: Annotated[FlowRead, Depends(get_flow_for_api_key_user)],
    input_request: SimplifiedAPIRequest | None = None,
    stream: bool = False,
    api_key_user: Annotated[UserRead, Depends(api_key_security)],
    context: dict | None = None,
    http_request: Request,
):
    """Executes a specified flow by ID with support for streaming and telemetry (API key auth).

    This endpoint executes a flow identified by ID or name, with options for streaming the response
    and tracking execution metrics. It handles both streaming and non-streaming execution modes.
    This endpoint uses API key authentication (Bearer token).

    Args:
        background_tasks (BackgroundTasks): FastAPI background task manager
        flow (FlowRead | None): The flow to execute, loaded via dependency
        input_request (SimplifiedAPIRequest | None): Input parameters for the flow
        stream (bool): Whether to stream the response
        api_key_user (UserRead): Authenticated user from API key
        context (dict | None): Optional context to pass to the flow
        http_request (Request): The incoming HTTP request for extracting global variables

    Returns:
        Union[StreamingResponse, RunResponse]: Either a streaming response for real-time results
        or a RunResponse with the complete execution results

    Raises:
        HTTPException: For flow not found (404) or invalid input (400)
        APIException: For internal execution errors (500)

    Notes:
        - Supports both streaming and non-streaming execution modes
        - Tracks execution time and success/failure via telemetry
        - Handles graceful client disconnection in streaming mode
        - Provides detailed error handling with appropriate HTTP status codes
        - Extracts global variables from HTTP headers with prefix X-LANGFLOW-GLOBAL-VAR-*
        - Merges extracted variables with the context parameter as "request_variables"
        - In streaming mode, uses EventManager to handle events:
            - "add_message": New messages during execution
            - "token": Individual tokens during streaming
            - "end": Final execution result
        - Authentication: Requires API key (Bearer token)
    """
    await ensure_flow_permission(
        api_key_user,
        FlowAction.EXECUTE,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )
    return await _run_flow_internal(
        background_tasks=background_tasks,
        flow=flow,
        input_request=input_request,
        stream=stream,
        api_key_user=api_key_user,
        context=context,
        http_request=http_request,
    )


@router.post(
    "/run/session/{flow_id_or_name}", response_model=None, response_model_exclude_none=True, include_in_schema=False
)
async def simplified_run_flow_session(
    *,
    background_tasks: BackgroundTasks,
    flow: Annotated[FlowRead, Depends(get_flow_for_current_user)],
    input_request: SimplifiedAPIRequest | None = None,
    stream: bool = False,
    api_key_user: CurrentActiveUser,
    session: DbSession,
    context: dict | None = None,
    http_request: Request,
):
    """Executes a specified flow by ID with support for streaming and telemetry (session auth).

    This endpoint executes a flow identified by ID or name, with options for streaming the response
    and tracking execution metrics. It handles both streaming and non-streaming execution modes.
    This endpoint uses session-based authentication (cookies).

    Args:
        background_tasks (BackgroundTasks): FastAPI background task manager
        flow (FlowRead | None): The flow to execute, loaded via dependency
        input_request (SimplifiedAPIRequest | None): Input parameters for the flow
        stream (bool): Whether to stream the response
        api_key_user (User): Authenticated user from session
        session (AsyncSession): Request-scoped DB session (shared with the auth
            dependency); its transaction is released before the flow runs
        context (dict | None): Optional context to pass to the flow
        http_request (Request): The incoming HTTP request for extracting global variables

    Returns:
        Union[StreamingResponse, RunResponse]: Either a streaming response for real-time results
        or a RunResponse with the complete execution results

    Raises:
        HTTPException: For flow not found (404) or invalid input (400)
        APIException: For internal execution errors (500)

    Notes:
        - Supports both streaming and non-streaming execution modes
        - Tracks execution time and success/failure via telemetry
        - Handles graceful client disconnection in streaming mode
        - Provides detailed error handling with appropriate HTTP status codes
        - Extracts global variables from HTTP headers with prefix X-LANGFLOW-GLOBAL-VAR-*
        - Merges extracted variables with the context parameter as "request_variables"
        - In streaming mode, uses EventManager to handle events:
            - "add_message": New messages during execution
            - "token": Individual tokens during streaming
            - "end": Final execution result
        - Authentication: Requires active session (cookies)
        - Feature Flag: Only available when agentic_experience is enabled
    """
    # Feature flag: Only allow access if agentic_experience is enabled
    if not get_settings_service().settings.agentic_experience:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This endpoint is not available",
        )

    await ensure_flow_permission(
        api_key_user,
        FlowAction.EXECUTE,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )

    # ``session`` is the same cached dependency the auth chain used, so this
    # ends the transaction opened by the auth reads before the flow runs —
    # the run can take minutes and would otherwise hold the request
    # transaction (and its pooled connection) open the whole time (#14445).
    # The API-key ``/run`` variant is not affected: ``api_key_security``
    # scopes its own short-lived session.
    await release_db_transaction(session)

    return await _run_flow_internal(
        background_tasks=background_tasks,
        flow=flow,
        input_request=input_request,
        stream=stream,
        api_key_user=api_key_user,
        context=context,
        http_request=http_request,
    )


@router.get("/webhook-events/{flow_id_or_name}", include_in_schema=False)
async def webhook_events_stream(
    auth: Annotated[SseAuth, Depends(get_flow_for_sse_user)],
    request: Request,
    session: DbSession,
):
    """Server-Sent Events (SSE) endpoint for real-time webhook build updates.

    When a flow is open in the UI, this endpoint provides live feedback
    of webhook execution progress, similar to clicking "Play" in the UI.

    Authentication: Requires user to be logged in (via cookie) or provide API key.
    The user must own the flow OR have an authorization-plugin-granted
    ``flow:read`` permission to subscribe to its events.
    """
    flow = auth.flow
    # Enforce flow:read before subscribing — the SSE fetcher uses share-aware
    # lookup, so without this check a non-owner with cross-user fetch enabled
    # would receive another user's webhook event payloads.
    await ensure_flow_permission(
        auth.user,
        FlowAction.READ,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=getattr(flow, "workspace_id", None),
        folder_id=getattr(flow, "folder_id", None),
    )

    # ``session`` is the same cached dependency the SSE auth chain used. The
    # EventSource stream below is indefinite and the session dependency is
    # only torn down when it ends, so without this commit every open tab
    # would hold a pooled connection in an idle transaction (#14445).
    await release_db_transaction(session)

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from the webhook event manager."""
        flow_id_str = str(flow.id)
        queue = await webhook_event_manager.subscribe(flow_id_str)

        try:
            # Send initial connection event
            yield f"event: connected\ndata: {json.dumps({'flow_id': flow_id_str, 'flow_name': flow.name})}\n\n"

            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=SSE_HEARTBEAT_TIMEOUT_SECONDS)
                    event_type = event["event"]
                    payload = event["data"]
                    # add_message carries message.model_dump(), which holds the new
                    # content_blocks union at both the top level and the nested Data
                    # mirror. Project both to the v1 shape for this v1 SSE, matching
                    # the build stream and /run.
                    if event_type == "add_message":
                        payload = project_payload_to_v1(payload)
                    event_data = json.dumps(payload)
                    yield f"event: {event_type}\ndata: {event_data}\n\n"
                except asyncio.TimeoutError:
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': time.time()})}\n\n"

        except asyncio.CancelledError:
            pass
        finally:
            await webhook_event_manager.unsubscribe(flow_id_str, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/webhook/{flow_id_or_name}", response_model=dict, status_code=HTTPStatus.ACCEPTED)  # noqa: RUF100, FAST003
async def webhook_run_flow(
    auth: Annotated[WebhookAuth, Depends(get_webhook_auth)],
    request: Request,
):
    """Run a flow using a webhook request.

    Args:
        auth: Resolved webhook user and flow, scoped to the authenticated caller.
        request: The incoming HTTP request.

    Returns:
        A dictionary containing the status of the task.

    Raises:
        HTTPException: If the flow is not found or if there is an error processing the request.
    """
    telemetry_service = get_telemetry_service()
    start_time = time.perf_counter()
    await logger.adebug("Received webhook request")
    error_msg = ""

    # Webhook user and flow are resolved by the dependency
    webhook_user = auth.user
    flow = auth.flow

    await ensure_flow_permission(
        webhook_user,
        FlowAction.EXECUTE,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )

    try:
        data = await request.body()
    except Exception as exc:
        error_msg = str(exc)
        raise HTTPException(status_code=500, detail=error_msg) from exc

    if not data:
        error_msg = "Request body is empty. You should provide a JSON payload containing the flow ID."
        raise HTTPException(status_code=400, detail=error_msg)

    raise_if_hitl_unsupported(flow.data or {})

    # The run executes in a fire-and-forget background task that never raises, so the identity gate
    # inside simple_run_flow can't surface its 401 from the webhook. Enforce it synchronously here so
    # a required-but-absent end-user identity is rejected BEFORE the task is scheduled (idempotent
    # with the scoping simple_run_flow does again on the same http_request). See I3. Kept outside the
    # try below so the 401 is not rewritten to a 500 by its generic handler.
    try:
        resolve_serving_scope(http_request=request, requested_session_id=None, default_session_id=str(flow.id))
    except EndUserIdentityRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=end_user_required_detail(exc),
        ) from exc

    try:
        # get all webhook components in the flow
        webhook_components = get_all_webhook_components_in_flow(flow.data)
        tweaks = {}

        for component in webhook_components:
            tweaks[component["id"]] = {"data": data.decode() if isinstance(data, bytes) else data}
        input_request = SimplifiedAPIRequest(
            input_value="",
            input_type="chat",
            output_type="chat",
            tweaks=tweaks,
            session_id=None,
        )

        # Check if there are UI listeners connected via SSE
        flow_id_str = str(flow.id)
        has_ui_listeners = webhook_event_manager.has_listeners(flow_id_str)

        await logger.adebug("Starting background task")
        run_id = str(uuid4())

        # Use asyncio.create_task to run in same event loop (needed for SSE)
        background_task = asyncio.create_task(
            simple_run_flow_task(
                flow=flow,
                input_request=input_request,
                api_key_user=webhook_user,
                telemetry_service=telemetry_service,
                start_time=start_time,
                run_id=run_id,
                emit_events=has_ui_listeners,
                flow_id=flow_id_str,
                http_request=request,
            )
        )
        # Fire-and-forget: log exceptions but don't block
        background_task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
    except Exception as exc:
        error_msg = str(exc)
        raise HTTPException(status_code=500, detail=error_msg) from exc

    return {"message": "Task started in the background", "status": "in progress"}


@router.post(
    "/run/advanced/{flow_id_or_name}",
    response_model=RunResponse,
    response_model_exclude_none=True,
)
async def experimental_run_flow(
    *,
    session: DbSession,
    flow: Annotated[Flow, Depends(get_flow_for_api_key_user)],
    inputs: list[InputValueRequest] | None = None,
    outputs: list[str] | None = None,
    tweaks: Annotated[Tweaks | None, Body(embed=True)] = None,
    stream: Annotated[bool, Body(embed=True)] = False,
    session_id: Annotated[None | str, Body(embed=True)] = None,
    api_key_user: Annotated[UserRead, Depends(api_key_security)],
) -> RunResponse:
    """Executes a specified flow by ID with optional input values, output selection, tweaks, and streaming capability.

    This endpoint supports running flows with caching to enhance performance and efficiency.

    ### Parameters:
    - `flow` (Flow): The flow object to be executed, resolved via dependency injection.
    - `inputs` (List[InputValueRequest], optional): A list of inputs specifying the input values and components
      for the flow. Each input can target specific components and provide custom values.
    - `outputs` (List[str], optional): A list of output names to retrieve from the executed flow.
      If not provided, all outputs are returned.
    - `tweaks` (Optional[Tweaks], optional): A dictionary of tweaks to customize the flow execution.
      The tweaks can be used to modify the flow's parameters and components.
      Tweaks can be overridden by the input values.
    - `stream` (bool, optional): Specifies whether the results should be streamed. Defaults to False.
    - `session_id` (Union[None, str], optional): An optional session ID to utilize existing session data for the flow
      execution.
    - `api_key_user` (User): The user associated with the current API key. Automatically resolved from the API key.

    ### Returns:
    A `RunResponse` object containing the selected outputs (or all if not specified) of the executed flow
    and the session ID.
    The structure of the response accommodates multiple inputs, providing a nested list of outputs for each input.

    ### Raises:
    HTTPException: Indicates issues with finding the specified flow, invalid input formats, or internal errors during
    flow execution.

    ### Example usage:
    ```json
    POST /run/flow_id
    x-api-key: YOUR_API_KEY
    Payload:
    {
        "inputs": [
            {"components": ["component1"], "input_value": "value1"},
            {"components": ["component3"], "input_value": "value2"}
        ],
        "outputs": ["Component Name", "component_id"],
        "tweaks": {"parameter_name": "value", "Component Name": {"parameter_name": "value"}, "component_id": {"parameter_name": "value"}}
        "stream": false
    }
    ```

    This endpoint facilitates complex flow executions with customized inputs, outputs, and configurations,
    catering to diverse application requirements.
    """  # noqa: E501
    await ensure_flow_permission(
        api_key_user,
        FlowAction.EXECUTE,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )

    expose_error_details = _caller_owns_flow(flow, api_key_user)
    _enforce_owner_only_tweaks(flow, api_key_user, tweaks)

    flow_id_str = str(flow.id)
    if outputs is None:
        outputs = []
    if inputs is None:
        inputs = [InputValueRequest(components=[], input_value="")]

    graph: Graph | None = None
    if session_id:
        session_service = get_session_service()
        try:
            session_data = await session_service.load_session(session_id, flow_id=flow_id_str)
        except Exception as exc:
            await logger.aexception("Failed to load advanced-run session for flow %s", flow.id)
            client_error = error_for_client(exc, expose_details=expose_error_details)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(client_error)) from exc
        graph, _artifacts = session_data or (None, None)
        if graph is None:
            msg = f"Session {session_id} not found"
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        if not _graph_executes_as_actor(graph, api_key_user, flow_id=flow.id):
            # Cache keys are legacy and not actor-scoped. Reusing an instantiated
            # graph across principals would retain the first actor's component
            # credentials, variables, files, and tweaks. Rebuild the immutable
            # stored flow under the current actor instead.
            await logger.awarning(
                "Ignoring advanced-run graph cached under another execution principal for flow %s",
                flow.id,
            )
            graph = None
        elif admin_only_build_required(is_superuser=bool(getattr(api_key_user, "is_superuser", False))):
            # The cached graph was compiled under whatever component policy was in force when
            # it was cached. Session cache keys carry no policy generation, so a graph cached
            # while admin-only mode was off still embeds the caller's own component source and
            # would execute it unchecked. Rebuild from stored data through the policy instead.
            await logger.awarning(
                "Ignoring advanced-run cached graph that predates the admin-only component policy for flow %s",
                flow.id,
            )
            graph = None

    if graph is None:
        if flow.data is None:
            msg = f"Flow {flow_id_str} has no data"
            if expose_error_details:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
            client_error = error_for_client(ValueError(msg), expose_details=False)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(client_error),
            )
        try:
            # Same caller-aware component policy the other stored-graph run paths apply:
            # the persisted graph is caller-controlled, so admin-only mode must resolve its
            # component source against the server registry before anything is compiled.
            sanitized_flow_data = await prepare_flow_build_for_user(
                flow.data,
                is_superuser=bool(getattr(api_key_user, "is_superuser", False)),
            )
            graph_data = deepcopy(sanitized_flow_data if sanitized_flow_data is not None else flow.data)
            graph_data = process_tweaks(graph_data, tweaks or {})
            raise_if_hitl_unsupported(graph_data)
            with scoped_model_provider_policy_for_flow(
                flow,
                user_id=api_key_user.id,
                is_superuser=bool(getattr(api_key_user, "is_superuser", False)),
            ):
                graph = Graph.from_payload(
                    graph_data,
                    flow_id=flow_id_str,
                    user_id=str(api_key_user.id),
                    flow_name=flow.name,
                )
        except CustomComponentValidationError as exc:
            await logger.aexception("Advanced-run flow validation failed for flow %s", flow.id)
            http_error = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
            raise error_for_client(http_error, expose_details=expose_error_details) from exc
        except HTTPException as exc:
            await logger.aexception("Advanced-run flow validation failed for flow %s", flow.id)
            if expose_error_details:
                # error_for_client returns ``exc`` itself here; re-raise rather
                # than chaining the exception to itself.
                raise
            raise error_for_client(exc, expose_details=expose_error_details) from exc
        except TweakRefusedError:
            # Third run route that applies tweaks, and the generic handler below
            # would turn a refused tweak into a redacted 500 with a stack trace
            # in the logs. Let it through so the app-level handler answers 422
            # naming the refused keys, as the setting documents for every mode.
            raise
        except Exception as exc:
            await logger.aexception("Failed to build advanced-run graph for flow %s", flow.id)
            client_error = error_for_client(exc, expose_details=expose_error_details)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(client_error)) from exc

    # Graph execution below can run for minutes; end any request transaction
    # opened by dependency resolution so it does not pin a pooled connection
    # (Postgres: idle-in-transaction) for the whole run (#14445).
    await release_db_transaction(session)

    try:
        with (
            scoped_model_provider_policy_for_flow(
                flow,
                user_id=api_key_user.id,
                is_superuser=bool(getattr(api_key_user, "is_superuser", False)),
            ),
            execution_protocol("v1.advanced"),
        ):
            task_result, session_id = await run_graph_internal(
                graph=graph,
                flow_id=flow_id_str,
                session_id=session_id,
                inputs=inputs,
                outputs=outputs,
                stream=stream,
            )
    except TweakRefusedError:
        # Let the app-level handler return the documented structured 422.
        raise
    except Exception as exc:
        await logger.aexception("Advanced-run execution failed for flow %s", flow.id)
        if isinstance(exc, HTTPException):
            if expose_error_details:
                raise
            raise error_for_client(exc, expose_details=expose_error_details) from exc
        client_error = error_for_client(exc, expose_details=expose_error_details)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(client_error)) from exc

    # Memory-base auto-capture is owner-scoped; shared callers must not spend or
    # persist through the flow owner's private credentials.
    if _caller_owns_flow(flow, api_key_user):
        try:
            _run_id_uuid = UUID(graph.run_id) if graph.run_id else None  # type-cast only
            await get_task_service().fire_and_forget_task(
                get_memory_base_service().on_flow_output,
                flow_id=flow.id,
                session_id=session_id,
                job_id=_run_id_uuid,
            )
        except (RuntimeError, ValueError, OSError):
            await logger.awarning("Memory base hook scheduling failed for flow %s", flow.id, exc_info=True)

    return _v1_run_response(RunResponse(outputs=task_result, session_id=session_id))


@router.post(
    "/predict/{_flow_id}",
    dependencies=[Depends(api_key_security)],
    include_in_schema=False,
)
@router.post(
    "/process/{_flow_id}",
    dependencies=[Depends(api_key_security)],
    include_in_schema=False,
)
async def process(_flow_id) -> None:
    """Endpoint to process an input with a given flow_id."""
    # Raise a depreciation warning
    await logger.awarning(
        "The /process endpoint is deprecated and will be removed in a future version. Please use /run instead."
    )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="The /process endpoint is deprecated and will be removed in a future version. Please use /run instead.",
    )


@router.get("/task/{_task_id}", deprecated=True, include_in_schema=False)
async def get_task_status(_task_id: str) -> TaskStatusResponse:
    """Get the status of a task by ID (Deprecated).

    This endpoint is deprecated and will be removed in a future version.
    """
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="The /task endpoint is deprecated and will be removed in a future version. Please use /run instead.",
    )


@router.post(
    "/upload/{flow_id}",
    status_code=HTTPStatus.CREATED,
    deprecated=True,
    include_in_schema=False,
)
async def create_upload_file(
    file: UploadFile,
    flow: Annotated[Flow, Depends(get_flow)],
    current_user: CurrentActiveUser,
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
) -> UploadFileResponse:
    """Upload a file for a specific flow (Deprecated).

    This endpoint is deprecated and will be removed in a future version.
    Authorization is handled by the ``get_flow`` dependency, which requires an
    authenticated user and verifies flow ownership.  Mirrors the
    ``max_file_size_upload`` guard on the non-deprecated twin at
    ``/api/v1/files/upload/{flow_id}`` so authenticated callers can't fill
    disk through this route either.
    """
    # Writing a file to a flow's storage is a flow mutation: enforce WRITE so
    # the external access ceiling (e.g. a "viewer") cannot upload via this
    # deprecated route. Mirrors the non-deprecated twin in files.py.
    await ensure_flow_permission(
        current_user,
        FlowAction.WRITE,
        flow_id=flow.id,
        flow_user_id=flow.user_id,
        workspace_id=flow.workspace_id,
        folder_id=flow.folder_id,
    )
    try:
        max_file_size_upload = settings_service.settings.max_file_size_upload
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if file.size is not None and file.size > max_file_size_upload * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File size is larger than the maximum file size {max_file_size_upload}MB.",
        )

    try:
        flow_id_str = str(flow.id)
        file_path = await asyncio.to_thread(save_uploaded_file, file, folder_name=flow_id_str)

        return UploadFileResponse(
            flow_id=flow_id_str,
            file_path=file_path.as_posix(),
        )
    except Exception as exc:
        await logger.aexception("Error saving file")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# get endpoint to return version of langflow
@router.get("/version")
async def get_version():
    return get_version_info()


def _raw_component_parameters(
    template: Mapping[str, Any] | None,
    *,
    field: str | None = None,
    field_value: Any = None,
) -> dict[str, Any]:
    """Parse non-secret component form values for provider preflight."""
    params: dict[str, Any] = {}
    if isinstance(template, Mapping):
        for key, value_dict in template.items():
            if isinstance(value_dict, Mapping):
                params[key] = parse_value(value_dict.get("value"), str(value_dict.get("_input_type")))

    # A real-time-refresh event can be newer than the template snapshot sent
    # beside it, so its value wins for the changed field.
    if field:
        field_template = template.get(field) if isinstance(template, Mapping) else None
        field_input_type = str(field_template.get("_input_type")) if isinstance(field_template, Mapping) else "None"
        params[field] = parse_value(field_value, field_input_type)
    return params


@router.post("/custom_component", status_code=HTTPStatus.OK, include_in_schema=False)
async def custom_component(
    raw_code: CustomComponentRequest,
    user: CurrentActiveUser,
    request: Request,
    provider_policy_attributes: ProviderPolicyAttributesDependency,
) -> CustomComponentResponse:
    # Building a custom component instantiates (and partially executes) posted
    # code. That is a create/write-class action, so enforce the external access
    # ceiling directly: a "viewer" external identity is denied while
    # editor/admin (and all non-external users) pass unchanged. This route is
    # not tied to a single owned resource, so the deny-only primitive is used
    # instead of an ``ensure_*_permission`` guard.
    external_context = get_current_external_access_context()
    if external_context is not None and not external_access_allows("create", external_context):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External credentials do not allow this action",
        )

    settings_service = get_settings_service()
    settings = settings_service.settings
    catalog_policy_snapshot = get_catalog_policy_service().snapshot
    effective_code = resolve_component_code_for_action(
        raw_code.code,
        user=user,
        settings=settings,
        snapshot=catalog_policy_snapshot,
        disabled_detail="Custom component creation is disabled",
        admin_only_detail="Custom component creation is restricted to administrators",
    )

    policy_context_token = set_current_model_provider_policy_context(
        user_id=user.id,
        attributes=provider_policy_attributes,
    )
    try:
        component = Component(_code=effective_code)

        built_frontend_node, component_instance = build_custom_component_template(component, user_id=user.id)
        type_ = get_instance_name(component_instance)
        enforce_catalog_policy_for_component_type(type_, snapshot=catalog_policy_snapshot)
        if isinstance(component_instance, Component):
            # Dynamic configuration may resolve DB-backed credentials or call
            # provider APIs. Refresh the active hierarchy before either hook
            # runs so moved-project and newly inherited grants are current.
            current_template = (
                raw_code.frontend_node.get("template") if isinstance(raw_code.frontend_node, Mapping) else None
            )
            await component_instance.arequire_model_provider_policy(
                ModelProviderPolicyPurpose.CONFIGURE,
                user_id=user.id,
                parameters=_raw_component_parameters(current_template),
            )
        if raw_code.frontend_node is not None:
            built_frontend_node = await component_instance.update_frontend_node(
                built_frontend_node,
                raw_code.frontend_node,
            )

        tool_mode: bool = built_frontend_node.get("tool_mode", False)
        if isinstance(component_instance, Component):
            await component_instance.run_and_validate_update_outputs(
                frontend_node=built_frontend_node,
                field_name="tool_mode",
                field_value=tool_mode,
            )
    except ModelProviderPolicyError as exc:
        # Keep scoped denials indistinguishable from unavailable providers and
        # avoid surfacing an authorization decision as a retryable server error.
        raise HTTPException(status_code=404, detail="Model provider not found") from exc
    finally:
        reset_current_model_provider_policy_context(policy_context_token)
    locale = getattr(request.state, "locale", "en")
    if locale != "en":
        from langflow.utils.i18n import translate_component_node

        try:
            built_frontend_node = translate_component_node(type_, built_frontend_node, locale)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to translate component node", extra={"locale": locale})
    return CustomComponentResponse(data=built_frontend_node, type=type_)


@router.post("/custom_component/update", status_code=HTTPStatus.OK, include_in_schema=False)
async def custom_component_update(
    code_request: UpdateCustomComponentRequest,
    user: CurrentActiveUser,
    request: Request,
    provider_policy_attributes: ProviderPolicyAttributesDependency,
):
    """Update an existing custom component with new code and configuration.

    Processes the provided code and template updates, applies parameter changes (including those loaded from the
    database), updates the component's build configuration, and validates outputs. Returns the updated component node as
    a JSON-serializable dictionary.

    Raises:
        HTTPException: If an error occurs during component building or updating.
        SerializationError: If serialization of the updated component node fails.
    """
    # Updating a custom component instantiates (and partially executes) posted
    # code, a create/write-class action. Enforce the external access ceiling
    # directly so a "viewer" external identity is denied; editor/admin (and all
    # non-external users) pass unchanged. Same action string as ``custom_component``.
    external_context = get_current_external_access_context()
    if external_context is not None and not external_access_allows("create", external_context):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="External credentials do not allow this action",
        )

    settings_service = get_settings_service()
    catalog_policy_snapshot = get_catalog_policy_service().snapshot
    effective_code = resolve_component_code_for_action(
        code_request.code,
        user=user,
        settings=settings_service.settings,
        snapshot=catalog_policy_snapshot,
        disabled_detail="Custom component creation is disabled",
        admin_only_detail="Custom component editing is restricted to administrators",
    )

    policy_context_token = set_current_model_provider_policy_context(
        user_id=user.id,
        attributes=provider_policy_attributes,
    )
    try:
        component = Component(_code=effective_code)
        component_node, cc_instance = build_custom_component_template(
            component,
            user_id=user.id,
        )
        component_type = get_instance_name(cc_instance)
        enforce_catalog_policy_for_component_type(component_type, snapshot=catalog_policy_snapshot)

        template = code_request.get_template()
        params = _raw_component_parameters(template)
        policy_params = _raw_component_parameters(
            template,
            field=code_request.field,
            field_value=code_request.field_value,
        )

        if isinstance(cc_instance, Component):
            # Authorize both fixed-provider components and the raw selected
            # ModelInput provider before load_from_db can hydrate any secret.
            await cc_instance.arequire_model_provider_policy(
                ModelProviderPolicyPurpose.CONFIGURE,
                user_id=user.id,
                parameters=policy_params,
            )

        component_node["tool_mode"] = code_request.tool_mode

        if hasattr(cc_instance, "set_attributes"):
            load_from_db_fields = [
                field_name
                for field_name, field_dict in template.items()
                if isinstance(field_dict, dict) and field_dict.get("load_from_db") and field_dict.get("value")
            ]
            if isinstance(cc_instance, Component):
                # ``fallback_to_env_vars=True`` so a missing variable (e.g. an
                # imported flow referencing ``ANTHROPIC_API_KEY`` when the
                # current user hasn't configured one) degrades to ``None``
                # instead of raising.  This endpoint only refreshes form
                # metadata — it does not execute the component — so we don't
                # need the real credential here.  The runtime build path still
                # calls ``update_params_with_load_from_db_fields`` with its own
                # fallback setting, so this change doesn't relax execution-time
                # requirements.
                params = await update_params_with_load_from_db_fields(
                    cc_instance,
                    params,
                    load_from_db_fields,
                    fallback_to_env_vars=True,
                )
                cc_instance.set_attributes(params)
        updated_build_config = code_request.get_template()
        await update_component_build_config(
            cc_instance,
            build_config=updated_build_config,
            field_value=code_request.field_value,
            field_name=code_request.field,
        )
        if "code" not in updated_build_config or not updated_build_config.get("code", {}).get("value"):
            updated_build_config = add_code_field_to_build_config(updated_build_config, effective_code)
        else:
            # Never echo client bytes back in restricted mode. A colliding
            # payload may have cleared the truncated-hash gate, but the server
            # executed its trusted copy (``effective_code``); the returned node
            # must carry that trusted code too, otherwise the attacker bytes
            # could be persisted into a saved flow and later exec'd on the
            # build path. In the default (unrestricted) mode ``effective_code``
            # is ``code_request.code``, so this is a no-op.
            updated_build_config["code"]["value"] = effective_code
        component_node["template"] = updated_build_config

        if isinstance(cc_instance, Component):
            await cc_instance.run_and_validate_update_outputs(
                frontend_node=component_node,
                field_name=code_request.field,
                field_value=code_request.field_value,
            )

    except CatalogPolicyHTTPException:
        raise
    except ModelProviderPolicyError as exc:
        raise HTTPException(status_code=404, detail="Model provider not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        reset_current_model_provider_policy_context(policy_context_token)

    locale = getattr(request.state, "locale", "en")
    if locale != "en":
        from langflow.utils.i18n import translate_component_node

        try:
            component_node = translate_component_node(component_type, component_node, locale)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to translate component node", extra={"locale": locale})

    try:
        return jsonable_encoder(component_node)
    except Exception as exc:
        raise SerializationError.from_exception(exc, data=component_node) from exc


def _blocked_component_types(snapshot) -> list[str]:
    """Return every component type the editor should treat as policy-blocked.

    The editor compares a node's ``type`` against this set, and a saved node
    carries whichever identity it was saved under -- ``Prompt`` rather than the
    registry key ``Prompt Template``. Alias resolution only runs one way, so
    reporting the administrator's key and its canonical candidates is not
    enough: blocking the canonical key would leave every node saved under an
    alias unmatched, and the palette exposes only the canonical key, so that is
    the one an administrator can find.

    ``_resolve_catalog_policy_matches`` decides the write by resolving the node
    side too and intersecting, so the same rule is applied here in reverse:
    every alias whose canonical candidates meet the blocked identities is
    reported. That keeps this answer identical to the one that decides whether
    the save succeeds, which is the whole point of sending it.
    """
    blocked_keys = getattr(snapshot, "blocked_component_keys", None)
    if not blocked_keys:
        return []

    types = set(blocked_keys)
    try:
        from lfx.utils.flow_validation import get_component_identity_index_for_validation

        identity_index = get_component_identity_index_for_validation()
    except Exception:  # noqa: BLE001
        identity_index = None
    if identity_index is not None:
        blocked_identities = frozenset(identity_index.resolve_many(blocked_keys))
        types |= blocked_identities
        types |= {
            alias
            for alias, candidates in identity_index.aliases.items()
            # Any overlap blocks the node server side, including an alias that
            # is ambiguous across components.
            if not blocked_identities.isdisjoint(candidates)
        }
    return sorted(types)


@router.get("/config")
async def get_config(
    user: Annotated[User | None, Depends(get_optional_user)] = None,
) -> ConfigResponse | PublicConfigResponse:
    """Retrieve application configuration settings.

    Returns different configuration based on authentication status:
    - Authenticated users: Full ConfigResponse with all settings
    - Unauthenticated users: PublicConfigResponse with limited, safe-to-expose settings

    Args:
        user: The authenticated user, or None if unauthenticated.

    Returns:
        ConfigResponse | PublicConfigResponse: Configuration settings appropriate for the user's auth status.

    Raises:
        HTTPException: If an error occurs while retrieving the configuration.
    """
    try:
        settings_service: SettingsService = get_settings_service()
        blocked_component_types: list[str] = []
        try:
            catalog_policy_service = get_catalog_policy_service()
            catalog_governance_enabled = catalog_policy_service.enabled
            # A custom policy service need not expose a snapshot. Reporting no
            # identities then simply leaves the editor unable to name a cause,
            # which is the safe direction.
            blocked_component_types = _blocked_component_types(getattr(catalog_policy_service, "snapshot", None))
        except Exception as exc:  # noqa: BLE001
            # Catalog governance is explicitly fail-open. A broken custom
            # policy implementation must not break the public config endpoint
            # or expose its internal exception text.
            await logger.aexception("Catalog policy status unavailable; reporting governance disabled", exception=exc)
            catalog_governance_enabled = False
            blocked_component_types = []

        if user is None:
            return PublicConfigResponse.from_settings(
                settings_service.settings,
                settings_service.auth_settings,
                catalog_governance_enabled=catalog_governance_enabled,
            )

        return ConfigResponse.from_settings(
            settings_service.settings,
            settings_service.auth_settings,
            catalog_governance_enabled=catalog_governance_enabled,
            blocked_component_types=blocked_component_types,
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
