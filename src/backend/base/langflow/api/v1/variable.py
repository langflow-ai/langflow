import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from lfx.base.models.unified_models import get_model_provider_variable_mapping, validate_model_provider_key
from sqlalchemy.exc import NoResultFound

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.models import (
    DISABLED_MODELS_VAR,
    ENABLED_MODELS_VAR,
    get_model_names_for_provider,
    get_provider_from_variable_name,
)
from langflow.api.v1.schemas.deployments import DetectedEnvVar, DetectVarsRequest, DetectVarsResponse
from langflow.services.database.models.flow_version.crud import get_flow_version_entry_or_raise
from langflow.services.database.models.flow_version.exceptions import FlowVersionNotFoundError
from langflow.services.database.models.variable.model import VariableCreate, VariableRead, VariableUpdate
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE
from langflow.services.variable.service import DatabaseVariableService

router = APIRouter(prefix="/variables", tags=["Variables"])
model_provider_variable_mapping = get_model_provider_variable_mapping()
logger = logging.getLogger(__name__)


async def _cleanup_model_list_variable(
    variable_service: DatabaseVariableService,
    user_id: UUID,
    variable_name: str,
    models_to_remove: set[str],
    session: DbSession,
) -> None:
    """Remove specified models from a model list variable (disabled or enabled models).

    If all models are removed, the variable is deleted entirely.
    If the variable doesn't exist, this is a no-op.
    """
    try:
        model_list_var = await variable_service.get_variable_object(
            user_id=user_id, name=variable_name, session=session
        )
    except ValueError:
        # Variable doesn't exist, nothing to clean up
        return

    if not model_list_var or not model_list_var.value:
        return

    # Parse current models
    try:
        current_models = set(json.loads(model_list_var.value))
    except (json.JSONDecodeError, TypeError):
        current_models = set()

    # Filter out the provider's models
    filtered_models = current_models - models_to_remove

    # Nothing changed, no update needed
    if filtered_models == current_models:
        return

    if filtered_models:
        # Update with filtered list
        if model_list_var.id is not None:
            await variable_service.update_variable_fields(
                user_id=user_id,
                variable_id=model_list_var.id,
                variable=VariableUpdate(
                    id=model_list_var.id,
                    name=variable_name,
                    value=json.dumps(list(filtered_models)),
                    type=GENERIC_TYPE,
                ),
                session=session,
            )
    else:
        # No models left, delete the variable
        await variable_service.delete_variable(user_id=user_id, name=variable_name, session=session)


async def _cleanup_provider_models(
    variable_service: DatabaseVariableService,
    user_id: UUID,
    provider: str,
    session: DbSession,
) -> None:
    """Clean up disabled and enabled model lists for a deleted provider credential."""
    try:
        provider_models = get_model_names_for_provider(provider)
    except ValueError:
        logger.exception("Provider model retrieval failed")
        return

    # Clean up disabled and enabled models
    await _cleanup_model_list_variable(variable_service, user_id, DISABLED_MODELS_VAR, provider_models, session)
    await _cleanup_model_list_variable(variable_service, user_id, ENABLED_MODELS_VAR, provider_models, session)


@router.post("/", response_model=VariableRead, status_code=201, include_in_schema=False)
async def create_variable(
    *,
    session: DbSession,
    variable: VariableCreate,
    current_user: CurrentActiveUser,
):
    """Create a new variable."""
    variable_service = get_variable_service()
    if not variable.name and not variable.value:
        raise HTTPException(status_code=400, detail="Variable name and value cannot be empty")

    if not variable.name:
        raise HTTPException(status_code=400, detail="Variable name cannot be empty")

    if not variable.value:
        raise HTTPException(status_code=400, detail="Variable value cannot be empty")

    if variable.name in await variable_service.list_variables(user_id=current_user.id, session=session):
        raise HTTPException(status_code=400, detail="Variable name already exists")

    # Check if the variable is a reserved model provider variable
    if variable.name in model_provider_variable_mapping.values():
        provider = get_provider_from_variable_name(variable.name)
        if provider is not None:
            # Validate that the key actually works using the Language Model Service
            # Run validation off the event loop to avoid blocking
            try:
                await asyncio.to_thread(validate_model_provider_key, provider, {variable.name: variable.value})
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        return await variable_service.create_variable(
            user_id=current_user.id,
            name=variable.name,
            value=variable.value,
            default_fields=variable.default_fields or [],
            type_=variable.type or CREDENTIAL_TYPE,
            session=session,
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/", response_model=list[VariableRead], status_code=200, include_in_schema=False)
async def read_variables(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Read all variables.

    Model provider credentials are validated when they are created or updated,
    not on every read. This avoids latency from external API calls on read operations.

    Returns a list of variables.
    """
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        msg = "Variable service is not an instance of DatabaseVariableService"
        raise TypeError(msg)
    try:
        all_variables = await variable_service.get_all(user_id=current_user.id, session=session)

        # Filter out internal variables (those starting and ending with __)
        filtered_variables = [
            var for var in all_variables if not (var.name and var.name.startswith("__") and var.name.endswith("__"))
        ]

        # Mark model provider credentials - validation status is based on existence
        # (actual validation happens on create/update)
        for var in filtered_variables:
            if var.name and var.name in model_provider_variable_mapping.values() and var.type == CREDENTIAL_TYPE:
                # Credential exists and was validated on save
                var.is_valid = True
                var.validation_error = None
            else:
                # Not a model provider credential
                var.is_valid = None
                var.validation_error = None

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return filtered_variables


@router.patch("/{variable_id}", response_model=VariableRead, status_code=200, include_in_schema=False)
async def update_variable(
    *,
    session: DbSession,
    variable_id: UUID,
    variable: VariableUpdate,
    current_user: CurrentActiveUser,
):
    """Update a variable."""
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        msg = "Variable service is not an instance of DatabaseVariableService"
        raise TypeError(msg)
    try:
        # Get existing variable to check if it's a model provider credential
        existing_variable = await variable_service.get_variable_by_id(
            user_id=current_user.id, variable_id=variable_id, session=session
        )

        # Validate API key if updating a model provider variable
        if existing_variable.name in model_provider_variable_mapping.values() and variable.value:
            provider = get_provider_from_variable_name(existing_variable.name)
            if provider is not None:
                # Run validation off the event loop to avoid blocking
                try:
                    await asyncio.to_thread(
                        validate_model_provider_key,
                        provider,
                        {existing_variable.name: variable.value},
                    )
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e)) from e

        return await variable_service.update_variable_fields(
            user_id=current_user.id,
            variable_id=variable_id,
            variable=variable,
            session=session,
        )
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail="Variable not found") from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Variable not found") from e
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{variable_id}", status_code=204, include_in_schema=False)
async def delete_variable(
    *,
    session: DbSession,
    variable_id: UUID,
    current_user: CurrentActiveUser,
) -> None:
    """Delete a variable.

    If the deleted variable is a model provider credential (e.g., OPENAI_API_KEY),
    all disabled models for that provider are automatically cleared.
    """
    variable_service = get_variable_service()
    try:
        # Get the variable before deleting to check if it's a provider credential
        variable_to_delete = await variable_service.get_variable_by_id(
            user_id=current_user.id, variable_id=variable_id, session=session
        )

        # Check if this variable is a model provider credential
        provider = get_provider_from_variable_name(variable_to_delete.name)

        # Delete the variable
        await variable_service.delete_variable_by_id(user_id=current_user.id, variable_id=variable_id, session=session)

        # If this was a provider credential, clean up disabled and enabled models for that provider
        if provider and isinstance(variable_service, DatabaseVariableService):
            await _cleanup_provider_models(variable_service, current_user.id, provider, session)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def _derive_env_var_name(field_key: str, template: dict) -> str:
    """Derive a meaningful env var name for a password field without a global variable.

    Looks for a sibling ``model`` field whose selected value carries a ``category``
    (e.g. ``"OpenAI"``). When found, returns ``{CATEGORY}_API_KEY`` (e.g.
    ``OPENAI_API_KEY``).  Falls back to the uppercased field key (``API_KEY``).
    """
    model_field = template.get("model")
    if isinstance(model_field, dict):
        raw = model_field.get("value")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError:
                raw = None
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            category = raw[0].get("category", "")
            if category:
                prefix = category.upper().replace(" ", "_").replace("-", "_")
                return f"{prefix}_{field_key.upper()}"

    return field_key.upper()


@router.post("/detections", response_model=DetectVarsResponse, include_in_schema=False)
async def detect_env_vars(
    payload: DetectVarsRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Detect credential fields used by the given flow version IDs.

    Two tiers of detection:
    1. Fields with ``load_from_db=True``: the ``value`` is a Langflow global
       variable name — returned with ``global_variable_name`` set.
    2. Fields with ``password=True`` and no global variable link: the field
       key is uppercased and returned as a suggested env var name, with
       ``global_variable_name`` left as ``None``.

    Results are deduplicated. Global-variable refs take precedence over
    password-only suggestions when the same key appears in both tiers.
    """
    global_var_keys: dict[str, str] = {}
    password_keys: dict[str, str] = {}
    unresolved_ids: list[UUID] = []

    for version_id in payload.flow_version_ids:
        try:
            version = await get_flow_version_entry_or_raise(
                session,
                version_id=version_id,
                user_id=current_user.id,
            )
        except FlowVersionNotFoundError:
            unresolved_ids.append(version_id)
            continue

        data = version.data
        if not isinstance(data, dict):
            continue

        for node in data.get("nodes", []):
            template = node.get("data", {}).get("node", {}).get("template", {})
            if not isinstance(template, dict):
                continue
            for field_key, field in template.items():
                if not isinstance(field, dict):
                    continue
                if field.get("load_from_db") is True:
                    var_name = field.get("value")
                    if isinstance(var_name, str) and var_name.strip():
                        global_var_keys[var_name.strip()] = var_name.strip()
                elif field.get("password") is True:
                    suggested = _derive_env_var_name(field_key, template)
                    if suggested not in global_var_keys:
                        password_keys[suggested] = suggested

    merged: list[DetectedEnvVar] = [DetectedEnvVar(key=k, global_variable_name=k) for k in sorted(global_var_keys)]
    merged.extend(
        DetectedEnvVar(key=k, global_variable_name=None) for k in sorted(password_keys) if k not in global_var_keys
    )

    return DetectVarsResponse(variables=merged, unresolved_ids=unresolved_ids)
