import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from lfx.base.models.unified_models import (
    get_all_variables_for_provider,
    get_model_provider_variable_mapping,
    validate_model_provider_key,
)
from lfx.services.model_provider_policy import ModelProviderPolicyPurpose
from sqlalchemy.exc import NoResultFound

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.models import (
    DISABLED_MODELS_VAR,
    ENABLED_MODELS_VAR,
    _require_provider,
    _resolve_policy,
    build_model_providers_by_name,
    get_provider_from_variable_name,
    normalize_model_status_entries,
)
from langflow.api.v1.schemas.deployments import DetectVarsRequest, DetectVarsResponse
from langflow.services.authorization import VariableAction, ensure_variable_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.authorization.listing import visible_scope_prefilter
from langflow.services.database.models.flow_version.crud import get_flow_version_entries_by_ids
from langflow.services.database.models.variable.model import Variable, VariableCreate, VariableRead, VariableUpdate
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE
from langflow.services.variable.service import DatabaseVariableService

router = APIRouter(prefix="/variables", tags=["Variables"])
logger = logging.getLogger(__name__)


async def _cleanup_model_list_variable(
    variable_service: DatabaseVariableService,
    user_id: UUID,
    variable_name: str,
    provider: str,
    providers_by_name: dict[str, set[str]],
    session: DbSession,
) -> None:
    """Remove one provider's models from a persisted model-status variable.

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
        parsed_value = json.loads(model_list_var.value)
        current_models = (
            {str(item) for item in parsed_value if isinstance(item, str)} if isinstance(parsed_value, list) else set()
        )
    except (json.JSONDecodeError, TypeError):
        current_models = set()

    # Migrate known legacy bare names first so shared aliases retain the other
    # provider identities, then remove only the deleted provider's qualified
    # entries (including live/custom deployment names absent from the catalog).
    normalized_models = normalize_model_status_entries(current_models, providers_by_name)
    provider_prefix = f"{provider}::"
    filtered_models = {model for model in normalized_models if not model.startswith(provider_prefix)}

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
        providers_by_name = build_model_providers_by_name()
    except ValueError:
        logger.exception("Provider model retrieval failed")
        return

    # Clean up disabled and enabled models
    await _cleanup_model_list_variable(
        variable_service,
        user_id,
        DISABLED_MODELS_VAR,
        provider,
        providers_by_name,
        session,
    )
    await _cleanup_model_list_variable(
        variable_service,
        user_id,
        ENABLED_MODELS_VAR,
        provider,
        providers_by_name,
        session,
    )


@router.post("/", response_model=VariableRead, status_code=201, include_in_schema=False)
async def create_variable(
    *,
    session: DbSession,
    variable: VariableCreate,
    current_user: CurrentActiveUser,
):
    """Create a new variable."""
    await ensure_variable_permission(
        current_user,
        VariableAction.CREATE,
        variable_user_id=current_user.id,
    )
    variable_service = get_variable_service()
    if not variable.name and not variable.value:
        raise HTTPException(status_code=400, detail="Variable name and value cannot be empty")

    if not variable.name:
        raise HTTPException(status_code=400, detail="Variable name cannot be empty")

    if not variable.value:
        raise HTTPException(status_code=400, detail="Variable value cannot be empty")

    # Provider variables contributed by core or extensions are policy-gated
    # before credential lookup, SDK import, validation, or persistence.
    provider = get_provider_from_variable_name(variable.name)
    if provider is not None:
        _require_provider(current_user, provider, ModelProviderPolicyPurpose.CONFIGURE)

    if variable.name in await variable_service.list_variables(user_id=current_user.id, session=session):
        raise HTTPException(status_code=400, detail="Variable name already exists")

    if provider is not None and variable.name == get_model_provider_variable_mapping().get(provider):
        provider_vars = await asyncio.to_thread(get_all_variables_for_provider, current_user.id, provider)
        try:
            await asyncio.to_thread(
                validate_model_provider_key,
                provider,
                {**provider_vars, variable.name: variable.value},
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        created_variable = await variable_service.create_variable(
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
    else:
        response = VariableRead.model_validate(created_variable, from_attributes=True)
        response.is_owner = True
        response.can_manage_shares = True
        return response


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
    await ensure_variable_permission(
        current_user,
        VariableAction.READ,
        variable_user_id=current_user.id,
    )
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        msg = "Variable service is not an instance of DatabaseVariableService"
        raise TypeError(msg)
    try:
        visibility = await visible_scope_prefilter(
            current_user,
            resource_type="variable",
            act=VariableAction.READ,
        )
        all_variables = await variable_service.get_all(
            user_id=current_user.id,
            session=session,
            visibility=visibility,
        )

        # Filter out internal variables (those starting and ending with __)
        provider_policy = _resolve_policy(current_user, ModelProviderPolicyPurpose.CONFIGURE)
        filtered_variables = []
        for var in all_variables:
            if var.name and var.name.startswith("__") and var.name.endswith("__"):
                continue
            provider = get_provider_from_variable_name(var.name) if var.name else None
            if provider is not None and not provider_policy.allows(provider):
                continue
            filtered_variables.append(var)

        # Mark model provider credentials - validation status is based on existence
        # (actual validation happens on create/update)
        primary_provider_variables = set(get_model_provider_variable_mapping().values())
        for var in filtered_variables:
            if var.name and var.name in primary_provider_variables and var.type == CREDENTIAL_TYPE:
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
        # Share-aware fetch: load by id when a plugin enables cross-user fetch,
        # otherwise scope to the owner (OSS default — behavior unchanged).
        existing_variable = await authorized_or_owner_scoped(
            session,
            Variable,
            id_column=Variable.id,
            resource_id=variable_id,
            owner_column=Variable.user_id,
            owner_id=current_user.id,
        )
        if existing_variable is None:
            raise HTTPException(status_code=404, detail="Variable not found")
        # Pass the *resource* owner so the owner-override only fast-paths the real
        # owner; a non-owner falls through to the plugin's enforce(). Plugin deny
        # → 404 (UUID privacy), matching the flow/deployment routes.
        owner_id = existing_variable.user_id
        try:
            await ensure_variable_permission(
                current_user,
                VariableAction.WRITE,
                variable_id=variable_id,
                variable_user_id=owner_id,
            )
        except HTTPException as exc:
            raise deny_to_404(exc, detail="Variable not found") from exc

        # Validate provider variables using their effective post-update name.
        # This closes the rename path from a generic variable into a hidden
        # provider credential while still allowing rename/delete cleanup.
        effective_name = variable.name or existing_variable.name
        provider = get_provider_from_variable_name(effective_name)
        if provider is not None:
            _require_provider(current_user, provider, ModelProviderPolicyPurpose.CONFIGURE)
            if variable.value and effective_name == get_model_provider_variable_mapping().get(provider):
                # Run validation off the event loop; owner context (not caller) for share-aware updates.
                provider_vars = await asyncio.to_thread(get_all_variables_for_provider, owner_id, provider)
                try:
                    await asyncio.to_thread(
                        validate_model_provider_key,
                        provider,
                        {**provider_vars, effective_name: variable.value},
                    )
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e)) from e

        # Mutate against the resolved owner so the owner-scoped service query
        # matches the row a share-aware fetch resolved.
        updated_variable = await variable_service.update_variable_fields(
            user_id=owner_id,
            variable_id=variable_id,
            variable=variable,
            session=session,
        )
        is_owner = str(owner_id) == str(current_user.id)
        response = VariableRead.model_validate(updated_variable, from_attributes=True)
        response.is_owner = is_owner
        response.can_manage_shares = is_owner
        # A shared variable may be used by runtime resolution, but mutation
        # responses must never disclose the owner's existing stored value when
        # a recipient patches metadata or omits ``value`` entirely.
        if not is_owner:
            response.value = None
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail="Variable not found") from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Variable not found") from e
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return response


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
        # Share-aware fetch (see update_variable): load by id when a plugin
        # enables cross-user fetch, else owner-scoped (OSS default).
        variable_to_delete = await authorized_or_owner_scoped(
            session,
            Variable,
            id_column=Variable.id,
            resource_id=variable_id,
            owner_column=Variable.user_id,
            owner_id=current_user.id,
        )
        if variable_to_delete is None:
            raise HTTPException(status_code=404, detail="Variable not found")
        owner_id = variable_to_delete.user_id
        try:
            await ensure_variable_permission(
                current_user,
                VariableAction.DELETE,
                variable_id=variable_id,
                variable_user_id=owner_id,
            )
        except HTTPException as exc:
            raise deny_to_404(exc, detail="Variable not found") from exc

        # Check if this variable is a model provider credential
        provider = get_provider_from_variable_name(variable_to_delete.name)

        # Delete the variable, scoped to the resolved owner so a shared delete
        # removes the owner's row.
        await variable_service.delete_variable_by_id(user_id=owner_id, variable_id=variable_id, session=session)

        # If this was a provider credential, clean up the *owner's* disabled and
        # enabled model lists for that provider.
        if provider and isinstance(variable_service, DatabaseVariableService):
            await _cleanup_provider_models(variable_service, owner_id, provider, session)

    except Exception as e:
        # Preserve 404 / deny_to_404 (and any other HTTPException) instead of
        # masking it as a 500.
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e


def _collect_candidate_variable_keys_from_flow_data(data: dict) -> set[str]:
    """Collect explicit global-variable keys from flow data."""
    candidate_keys: set[str] = set()

    for node in data.get("nodes", []):
        template = node.get("data", {}).get("node", {}).get("template", {})
        if not isinstance(template, dict):
            continue
        for field in template.values():
            if not isinstance(field, dict):
                continue
            if field.get("load_from_db") is True:
                var_name = field.get("value")
                normalized_var_name = var_name.strip() if isinstance(var_name, str) else None
                if normalized_var_name:
                    candidate_keys.add(normalized_var_name)

    return candidate_keys


def _validate_flow_or_422(*, version_id: UUID, data: object) -> dict:
    """Validate flow version data structure and raise HTTP 422 on malformed input."""
    if not (isinstance(data, dict) and "nodes" in data and isinstance(data["nodes"], list)):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Flow version {version_id} data must be a JSON object with a 'nodes' list containing node templates."
            ),
        )
    return data


@router.post("/detections", response_model=DetectVarsResponse, include_in_schema=False)
async def detect_env_vars(
    payload: DetectVarsRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Detect global variable references used by the given flow version IDs.

    Candidates are inferred only from ``load_from_db=True`` fields, where
    the field value is interpreted as the referenced global variable name.

    Returned values are cross-checked against the user's existing global
    variable names. This is a security guardrail: it prevents echoing arbitrary
    template values (including accidental secrets) and ensures results are
    actual stored global variables.
    """
    await ensure_variable_permission(
        current_user,
        VariableAction.READ,
        variable_user_id=current_user.id,
    )
    variable_service = get_variable_service()
    existing_variable_names = {
        name
        for name in await variable_service.list_variables(user_id=current_user.id, session=session)
        if isinstance(name, str) and name
    }

    candidate_keys: set[str] = set()
    versions_by_id = await get_flow_version_entries_by_ids(
        session,
        version_ids=payload.flow_version_ids,
        user_id=current_user.id,
    )

    for version_id in payload.flow_version_ids:
        version = versions_by_id.get(version_id)
        if version is None:
            raise HTTPException(status_code=404, detail=f"Flow version {version_id} not found")

        data = _validate_flow_or_422(version_id=version_id, data=version.data)
        candidate_keys.update(_collect_candidate_variable_keys_from_flow_data(data))

    provider_policy = _resolve_policy(current_user, ModelProviderPolicyPurpose.CONFIGURE)
    visible_candidate_keys = {
        variable_key
        for variable_key in candidate_keys
        if (provider := get_provider_from_variable_name(variable_key)) is None or provider_policy.allows(provider)
    }

    return DetectVarsResponse(variables=sorted(existing_variable_names.intersection(visible_candidate_keys)))
