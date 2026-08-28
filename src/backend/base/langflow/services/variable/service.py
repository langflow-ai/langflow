from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from lfx.log.logger import logger
from lfx.services.authorization.base import ResourceVisibilityScope
from lfx.services.settings.constants import AGENTIC_VARIABLES
from lfx.services.variable import VariableNotFoundError
from sqlmodel import col, select

from langflow.services.auth import utils as auth_utils
from langflow.services.base import Service
from langflow.services.database.models.variable.model import Variable, VariableCreate, VariableRead, VariableUpdate
from langflow.services.variable.base import VariableService
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lfx.services.settings.service import SettingsService
    from pydantic import SecretStr
    from sqlmodel.ext.asyncio.session import AsyncSession


def has_variable_value(variable: Variable) -> bool:
    """Return whether a variable has a usable value without exposing credentials."""
    if not variable.value:
        return False
    if variable.type != CREDENTIAL_TYPE:
        return bool(variable.value.strip())
    try:
        decrypted_value = auth_utils.decrypt_api_key(variable.value)
    except Exception:  # noqa: BLE001
        return False
    return bool(decrypted_value and decrypted_value.strip())


class DatabaseVariableService(VariableService, Service):
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

    async def get_default_field_bindings(
        self,
        user_id: UUID | str,
        session: AsyncSession,
    ) -> list[tuple[str, list[str] | None]]:
        """Read only names and default fields; never materialize variable values."""
        stmt = (
            select(Variable.name, Variable.default_fields)
            .where(Variable.user_id == user_id)
            .order_by(col(Variable.name), col(Variable.id))
        )
        return [(name, default_fields) for name, default_fields in (await session.exec(stmt)).all() if name]

    async def initialize_user_variables(self, user_id: UUID | str, session: AsyncSession) -> None:
        if not self.settings_service.settings.store_environment_variables:
            await logger.adebug("Skipping environment variable storage.")
            return

        # Import provider metadata to identify placeholder API-key values and
        # enforce provider-governance policy for environment imports.
        try:
            from lfx.base.models.unified_models import get_model_provider_metadata
            from lfx.services.model_provider_policy import ModelProviderPolicyPurpose, resolve_model_provider_policy

            from langflow.services.database.models.user.model import User

            var_to_provider = {}
            provider_variables = {}
            metadata = get_model_provider_metadata()
            principal = await session.get(User, UUID(str(user_id)))
            for provider, meta in metadata.items():
                for var in meta.get("variables", []):
                    var_key = var.get("variable_key")
                    if var_key:
                        var_to_provider[var_key] = provider
                        provider_variables[var_key] = var
            provider_policy = resolve_model_provider_policy(
                user_id=user_id,
                providers=metadata,
                purpose=ModelProviderPolicyPurpose.CONFIGURE,
                attributes={"is_superuser": bool(principal and principal.is_superuser)},
            )
        except Exception:  # noqa: BLE001
            await logger.aexception("Could not resolve model-provider metadata; skipping environment variable import")
            return

        for var_name in self.settings_service.settings.variables_to_get_from_environment:
            # Check if session is still usable before processing each variable
            if not session.is_active:
                await logger.awarning(
                    "Session is no longer active during variable initialization. "
                    "Some environment variables may not have been processed."
                )
                break

            provider_name = var_to_provider.get(var_name)
            if provider_name is not None and not provider_policy.allows(provider_name):
                continue

            if var_name in os.environ and os.environ[var_name].strip():
                value = os.environ[var_name].strip()

                # Skip placeholder/test values like "dummy" for API key variables only
                # This prevents test environments from overwriting user-configured model provider keys
                var_info = provider_variables.get(var_name, {})
                is_provider_variable = bool(var_info)
                is_secret_variable = var_info.get("is_secret", False)

                if is_provider_variable and is_secret_variable and value.lower() == "dummy":
                    await logger.adebug(
                        f"Skipping API key variable {var_name} with placeholder value 'dummy' "
                        "to preserve user configuration"
                    )
                    continue

                query = select(Variable).where(Variable.user_id == user_id, Variable.name == var_name)
                try:
                    existing = (await session.exec(query)).first()
                except Exception as e:  # noqa: BLE001
                    await logger.aexception(f"Error querying {var_name} variable: {e!s}")
                    # If session got rolled back during query, stop processing
                    if not session.is_active:
                        await logger.awarning(
                            f"Session rolled back during {var_name} query. Stopping variable initialization."
                        )
                        break
                    continue

                try:
                    if existing:
                        # Check if the variable has been user-modified (updated_at != created_at)
                        # If so, don't overwrite with environment variable
                        is_user_modified = (
                            existing.updated_at is not None
                            and existing.created_at is not None
                            and existing.updated_at > existing.created_at
                        )

                        if is_user_modified:
                            await logger.adebug(
                                f"Skipping update of user-modified variable {var_name} with environment value"
                            )
                        else:
                            await self.update_variable(user_id, var_name, value, session=session)
                    else:
                        await self.create_variable(
                            user_id=user_id,
                            name=var_name,
                            value=value,
                            # Model Providers resolve these at runtime; Apply To Fields is user-owned.
                            default_fields=[],
                            type_=CREDENTIAL_TYPE,
                            session=session,
                        )
                    await logger.adebug(f"Processed {var_name} variable from environment.")
                except Exception as e:  # noqa: BLE001
                    await logger.aexception(f"Error processing {var_name} variable: {e!s}")
                    # If session got rolled back due to error, stop processing
                    if not session.is_active:
                        await logger.awarning(
                            f"Session rolled back after error processing {var_name}. Stopping variable initialization."
                        )
                        break

    async def get_variable_object(
        self,
        user_id: UUID | str,
        name: str,
        session: AsyncSession,
    ) -> Variable:
        # we get the credential from the database
        stmt = select(Variable).where(Variable.user_id == user_id, Variable.name == name)
        variable = (await session.exec(stmt)).first()

        if not variable or not variable.value:
            msg = f"{name} variable not found."
            raise VariableNotFoundError(msg)

        return variable

    async def get_variable(
        self,
        user_id: UUID | str,
        name: str,
        field: str,
        session: AsyncSession,
    ) -> str | SecretStr:
        # we get the credential from the database
        # credential = session.query(Variable).filter(Variable.user_id == user_id, Variable.name == name).first()
        try:
            variable = await self.get_variable_object(user_id, name, session)
        except VariableNotFoundError as owned_lookup_error:
            # Runtime resolution may use an explicitly shared variable, but it
            # must never broaden administrative get/update/delete lookups. An
            # owned variable wins on name collisions; otherwise require one
            # unambiguous READ-visible row from the authorization plugin.
            from langflow.services.deps import get_authorization_service

            authz = get_authorization_service()
            if not await authz.is_enabled() or not await authz.supports_cross_user_fetch():
                raise
            get_visibility = getattr(authz, "get_resource_visibility", None)
            if get_visibility is None:
                # Compatibility for duck-typed authorization services that
                # predate ResourceVisibilityScope.
                visible_ids = await authz.list_visible_resource_ids(
                    user_id=UUID(str(user_id)),
                    resource_type="variable",
                    domain="*",
                    act="read",
                )
                visibility = None if visible_ids is None else ResourceVisibilityScope(resource_ids=tuple(visible_ids))
            else:
                visibility = await get_visibility(
                    user_id=UUID(str(user_id)),
                    resource_type="variable",
                    domain="*",
                    act="read",
                )
            if visibility is None or not (visibility.all_resources or visibility.resource_ids):
                raise

            shared_clauses = [
                Variable.name == name,
                Variable.user_id != user_id,
            ]
            if not visibility.all_resources:
                shared_clauses.append(col(Variable.id).in_(visibility.resource_ids))
            shared_variables = list((await session.exec(select(Variable).where(*shared_clauses))).all())
            if not shared_variables:
                raise
            if len(shared_variables) > 1:
                msg = f"Multiple shared variables named '{name}' are visible; use an owned variable with that name."
                raise ValueError(msg) from owned_lookup_error
            variable = shared_variables[0]

        if variable.type == CREDENTIAL_TYPE and field == "session_id":
            msg = (
                f"variable {name} of type 'Credential' cannot be used in a Session ID field "
                "because its purpose is to prevent the exposure of values."
            )
            raise TypeError(msg)

        # Only decrypt CREDENTIAL type variables; GENERIC variables are stored as plain text.
        # CREDENTIAL values are wrapped in pydantic.SecretStr so that any consumer that echoes
        # the value through a stringification path (Message.text, status, traces, logs) gets
        # "**********" instead of the raw secret. Consumers that genuinely need the raw value
        # call .get_secret_value() at the boundary (e.g. provider client construction).
        if variable.type == CREDENTIAL_TYPE:
            from pydantic import SecretStr

            decrypted = auth_utils.decrypt_api_key(variable.value)
            if not decrypted:
                msg = (
                    f"Could not decrypt credential variable '{name}'. The stored value cannot be "
                    "decrypted with the current LANGFLOW_SECRET_KEY — it may have been encrypted "
                    "with a different key."
                )
                raise ValueError(msg)
            return SecretStr(decrypted)
        # GENERIC type - return as-is
        return variable.value

    async def get_all(
        self,
        user_id: UUID | str,
        session: AsyncSession,
        *,
        visibility: ResourceVisibilityScope | None = None,
        include_empty_names: set[str] | None = None,
    ) -> list[VariableRead]:
        stmt = select(Variable).order_by(col(Variable.name), col(Variable.id))
        if visibility is None:
            stmt = stmt.where(Variable.user_id == user_id)
        else:
            from langflow.services.authorization.listing import restrict_to_owned_or_visible_scope

            # Variable has no canonical workspace/project columns, so
            # domain-only grants intentionally remain owner-scoped.
            stmt = restrict_to_owned_or_visible_scope(
                stmt,
                id_column=Variable.id,
                owner_clause=Variable.user_id == user_id,
                visibility=visibility,
            )
        variables = list((await session.exec(stmt)).all())
        include_empty_names = include_empty_names or set()
        variables_read = []
        for variable in variables:
            is_owner = str(variable.user_id) == str(user_id)
            value = None
            if variable.type == GENERIC_TYPE and is_owner:
                if not variable.value and variable.name not in include_empty_names:
                    if variable.name in AGENTIC_VARIABLES:
                        await logger.adebug(
                            "Agentic placeholder variable '%s' has no stored value — skipping.", variable.name
                        )
                    else:
                        await logger.awarning("Variable '%s' has no stored value — skipping.", variable.name)
                    continue
                if variable.value:
                    # Security defense-in-depth: a GENERIC variable is stored as plain text, so its
                    # value must never be a Fernet token. If it is (e.g. a CREDENTIAL row that was
                    # relabeled GENERIC), do NOT decrypt-and-return it — that would leak the secret.
                    if isinstance(variable.value, str) and variable.value.startswith("gAAAAA"):
                        await logger.awarning(
                            "Skipping variable '%s': a GENERIC variable holds ciphertext "
                            "(likely a CREDENTIAL row relabeled GENERIC); not decrypting or returning it.",
                            variable.name,
                        )
                        continue
                    value = auth_utils.decrypt_api_key(variable.value)
                    if not value:
                        await logger.awarning(
                            "Variable '%s' could not be decrypted — likely encrypted with a different "
                            "LANGFLOW_SECRET_KEY. Skipping.",
                            variable.name,
                        )
                        continue
                else:
                    # Optional settings use an empty value as a meaningful reset
                    # while retaining the row UUID.
                    value = ""

            # Model validate will set value to None if credential type
            variable_read = VariableRead.model_validate(variable, from_attributes=True)
            variable_read.has_value = has_variable_value(variable)
            variable_read.is_owner = is_owner
            # Deliberately conservative: resource owners can manage shares.
            # Enterprise may authorize additional administrators server-side,
            # but the list UI must not show a re-share control to recipients.
            variable_read.can_manage_shares = is_owner
            # Shared values are usable only inside runtime variable resolution;
            # API list responses expose metadata but never plaintext values.
            if variable.type == GENERIC_TYPE and is_owner:
                variable_read.value = value
            elif not is_owner:
                variable_read.value = None

            variables_read.append(variable_read)
        return variables_read

    async def get_all_decrypted_variables(
        self,
        user_id: UUID | str,
        session: AsyncSession,
    ) -> dict[str, str]:
        """Get all variables for a user with decrypted values.

        Args:
            user_id: The user ID to get variables for
            session: Database session

        Returns:
            Dictionary mapping variable names to decrypted values
        """
        # Convert string to UUID if needed for SQLAlchemy query
        user_id_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
        stmt = select(Variable).where(Variable.user_id == user_id_uuid)
        variables = (await session.exec(stmt)).all()

        result = {}
        for var in variables:
            if var.name and var.value:
                try:
                    decrypted_value = auth_utils.decrypt_api_key(var.value)
                except Exception as e:  # noqa: BLE001
                    await logger.awarning(f"Decryption failed for variable '{var.name}': {e}. Skipping")
                    continue

                if not decrypted_value:
                    await logger.awarning(f"Decryption returned empty for variable '{var.name}'. Skipping")
                    continue

                result[var.name] = decrypted_value

        return result

    async def get_variable_by_id(
        self,
        user_id: UUID | str,
        variable_id: UUID | str,
        session: AsyncSession,
    ) -> Variable:
        query = select(Variable).where(Variable.id == variable_id, Variable.user_id == user_id)
        variable = (await session.exec(query)).first()
        if not variable:
            msg = f"{variable_id} variable not found."
            raise ValueError(msg)
        return variable

    async def list_variables(self, user_id: UUID | str, session: AsyncSession) -> list[str | None]:
        variables = await self.get_all(user_id=user_id, session=session)
        return [variable.name for variable in variables if variable]

    async def update_variable(
        self,
        user_id: UUID | str,
        name: str,
        value: str,
        session: AsyncSession,
    ):
        stmt = select(Variable).where(Variable.user_id == user_id, Variable.name == name)
        variable = (await session.exec(stmt)).first()
        if not variable:
            msg = f"{name} variable not found."
            raise ValueError(msg)

        # Validate that GENERIC variables don't start with Fernet signature
        if variable.type == GENERIC_TYPE and value.startswith("gAAAAA"):
            msg = (
                f"Generic variable '{name}' cannot start with 'gAAAAA' as this is reserved "
                "for encrypted values. Please use a different value."
            )
            raise ValueError(msg)

        # Only encrypt CREDENTIAL_TYPE variables
        if variable.type == CREDENTIAL_TYPE:
            variable.value = auth_utils.encrypt_api_key(value, settings_service=self.settings_service)
        else:
            variable.value = value
        variable.updated_at = datetime.now(timezone.utc)
        session.add(variable)
        await session.flush()
        await session.refresh(variable)
        return variable

    async def update_variable_fields(
        self,
        user_id: UUID | str,
        variable_id: UUID | str,
        variable: VariableUpdate,
        session: AsyncSession,
    ):
        query = select(Variable).where(Variable.id == variable_id, Variable.user_id == user_id)
        db_variable = (await session.exec(query)).one()

        # Security: prevent a CREDENTIAL -> GENERIC type-confusion that would expose the
        # decrypted secret. Credential values are stored as Fernet ciphertext ("gAAAAA...").
        # Relabeling the row GENERIC *without* supplying a fresh value would leave that
        # ciphertext in place; get_all() then decrypts GENERIC values and returns the
        # plaintext (e.g. the server's shared provider keys). Reject that transition.
        resulting_type = variable.type if variable.type is not None else db_variable.type
        if (
            resulting_type == GENERIC_TYPE
            and variable.value is None
            and isinstance(db_variable.value, str)
            and db_variable.value.startswith("gAAAAA")
        ):
            msg = "Cannot change a credential variable to a generic variable without providing a new value."
            raise ValueError(msg)

        # Handle value encryption based on variable type (consistent with update_variable and create_variable)
        if variable.value is not None:
            variable_type = variable.type if variable.type is not None else db_variable.type

            # Validate that GENERIC variables don't start with Fernet signature
            if variable_type == GENERIC_TYPE and variable.value.startswith("gAAAAA"):
                msg = (
                    f"Generic variable '{db_variable.name}' cannot start with 'gAAAAA' as this is reserved "
                    "for encrypted values. Please use a different value."
                )
                raise ValueError(msg)

            # Only encrypt CREDENTIAL_TYPE variables (consistent with update_variable and create_variable)
            if variable_type == CREDENTIAL_TYPE:
                variable.value = auth_utils.encrypt_api_key(variable.value, settings_service=self.settings_service)
            # GENERIC_TYPE variables are stored as plain text

        db_variable.updated_at = datetime.now(timezone.utc)
        variable_data = variable.model_dump(exclude_unset=True)
        for key, value in variable_data.items():
            setattr(db_variable, key, value)

        session.add(db_variable)
        await session.flush()
        await session.refresh(db_variable)
        return db_variable

    async def delete_variable(
        self,
        user_id: UUID | str,
        name: str,
        session: AsyncSession,
    ) -> None:
        stmt = select(Variable).where(Variable.user_id == user_id).where(Variable.name == name)
        variable = (await session.exec(stmt)).first()
        if not variable:
            msg = f"{name} variable not found."
            raise ValueError(msg)
        await session.delete(variable)

    async def delete_variable_by_id(self, user_id: UUID | str, variable_id: UUID, session: AsyncSession) -> None:
        stmt = select(Variable).where(Variable.user_id == user_id, Variable.id == variable_id)
        variable = (await session.exec(stmt)).first()
        if not variable:
            msg = f"{variable_id} variable not found."
            raise ValueError(msg)
        await session.delete(variable)

    async def create_variable(
        self,
        user_id: UUID | str,
        name: str,
        value: str,
        *,
        default_fields: Sequence[str] = (),
        type_: str = CREDENTIAL_TYPE,
        session: AsyncSession,
    ):
        # Validate that GENERIC variables don't start with Fernet signature
        if type_ == GENERIC_TYPE and value.startswith("gAAAAA"):
            msg = (
                f"Generic variable '{name}' cannot start with 'gAAAAA' as this is reserved "
                "for encrypted values. Please use a different value."
            )
            raise ValueError(msg)

        # Only encrypt CREDENTIAL_TYPE variables
        encrypted_value = auth_utils.encrypt_api_key(value) if type_ == CREDENTIAL_TYPE else value
        variable_base = VariableCreate(
            name=name,
            type=type_,
            value=encrypted_value,
            default_fields=list(default_fields),
        )
        variable = Variable.model_validate(variable_base, from_attributes=True, update={"user_id": user_id})
        session.add(variable)
        await session.flush()
        await session.refresh(variable)
        return variable
