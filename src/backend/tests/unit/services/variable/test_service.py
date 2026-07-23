import secrets
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from langflow.services.auth.service import AuthService
from langflow.services.auth.utils import ensure_fernet_key
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import VariableUpdate
from langflow.services.deps import get_settings_service
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE
from langflow.services.variable.service import DatabaseVariableService
from lfx.services.authorization.base import ResourceVisibilityScope
from lfx.services.model_provider_policy import (
    ModelProviderPolicyContext,
    ModelProviderPolicyPurpose,
    ModelProviderPolicySnapshot,
)
from lfx.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
def service():
    settings_service = get_settings_service()
    auth_service = AuthService(settings_service)
    with patch("langflow.services.auth.utils.get_auth_service", return_value=auth_service):
        yield DatabaseVariableService(settings_service)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


async def test_initialize_user_variables__create_and_update(service, session: AsyncSession):
    user_id = uuid4()
    field = ""
    good_vars = {k: f"value{i}" for i, k in enumerate(VARIABLES_TO_GET_FROM_ENVIRONMENT)}
    bad_vars = {"VAR1": "value1", "VAR2": "value2", "VAR3": "value3"}
    env_vars = {**good_vars, **bad_vars}

    await service.create_variable(user_id, "OPENAI_API_KEY", "outdate", session=session)
    env_vars["OPENAI_API_KEY"] = "updated_value"

    with patch.dict("os.environ", env_vars, clear=True):
        await service.initialize_user_variables(user_id=user_id, session=session)

    variables = await service.list_variables(user_id, session=session)
    for name in variables:
        value = await service.get_variable(user_id, name, field, session=session)
        assert isinstance(value, SecretStr)
        assert value.get_secret_value() == env_vars[name]

    assert all(i in variables for i in good_vars)
    assert all(i not in variables for i in bad_vars)


async def test_initialize_user_variables__not_found_variable(service, session: AsyncSession):
    with patch("langflow.services.variable.service.DatabaseVariableService.create_variable") as m:
        m.side_effect = Exception()
        await service.initialize_user_variables(uuid4(), session=session)
    assert True


async def test_initialize_user_variables__skipping_environment_variable_storage(service, session: AsyncSession):
    service.settings_service.settings.store_environment_variables = False
    await service.initialize_user_variables(uuid4(), session=session)
    assert True


async def test_initialize_user_variables_skips_policy_hidden_provider_before_validation(
    service,
    session: AsyncSession,
    monkeypatch,
):
    user_id = uuid4()
    monkeypatch.setattr(
        service.settings_service.settings,
        "variables_to_get_from_environment",
        ["ANTHROPIC_API_KEY"],
    )
    snapshot = ModelProviderPolicySnapshot(
        context=ModelProviderPolicyContext(user_id=user_id),
        purpose=ModelProviderPolicyPurpose.CONFIGURE,
        candidate_provider_ids=frozenset({"openai", "anthropic"}),
        allowed_provider_ids=frozenset({"openai"}),
    )

    with (
        patch.dict(
            "os.environ",
            {"ANTHROPIC_API_KEY": "hidden-secret"},  # pragma: allowlist secret
            clear=True,
        ),
        patch("lfx.services.model_provider_policy.resolve_model_provider_policy", return_value=snapshot),
        patch(
            "lfx.base.models.unified_models.validate_model_provider_key",
            side_effect=AssertionError("hidden provider credential must not be validated"),
        ),
    ):
        await service.initialize_user_variables(user_id=user_id, session=session)

    assert await service.list_variables(user_id, session=session) == []


async def test_initialize_user_variables_stops_when_policy_resolution_fails(
    service,
    session: AsyncSession,
    monkeypatch,
):
    user_id = uuid4()
    monkeypatch.setattr(
        service.settings_service.settings,
        "variables_to_get_from_environment",
        ["OPENAI_API_KEY"],
    )

    with (
        patch.dict("os.environ", {"OPENAI_API_KEY": "must-not-import"}, clear=True),  # pragma: allowlist secret
        patch(
            "lfx.services.model_provider_policy.resolve_model_provider_policy",
            side_effect=RuntimeError("policy unavailable"),
        ),
    ):
        await service.initialize_user_variables(user_id=user_id, session=session)

    assert await service.list_variables(user_id, session=session) == []


async def test_initialize_user_variables_passes_trusted_superuser_context(
    service,
    session: AsyncSession,
    monkeypatch,
):
    user = User(
        username=f"provider_superuser_{uuid4().hex}",
        password="test-password",  # noqa: S106 - inert test fixture credential  # pragma: allowlist secret
        is_active=True,
        is_superuser=True,
    )
    session.add(user)
    await session.flush()
    monkeypatch.setattr(service.settings_service.settings, "store_environment_variables", True)
    monkeypatch.setattr(
        service.settings_service.settings,
        "variables_to_get_from_environment",
        ["OPENAI_API_KEY"],
    )
    seen_attributes = None

    def allow_superuser(*, user_id, providers, purpose, attributes=None):
        nonlocal seen_attributes
        seen_attributes = attributes
        assert user_id == user.id
        assert purpose is ModelProviderPolicyPurpose.CONFIGURE
        assert "OpenAI" in providers
        return ModelProviderPolicySnapshot(
            context=ModelProviderPolicyContext(user_id=user_id, attributes=attributes or {}),
            purpose=purpose,
            candidate_provider_ids=frozenset({"openai"}),
            allowed_provider_ids=frozenset({"openai"}),
        )

    with (
        patch.dict(
            "os.environ",
            {"OPENAI_API_KEY": "superuser-env-key"},  # pragma: allowlist secret
            clear=True,
        ),
        patch("lfx.services.model_provider_policy.resolve_model_provider_policy", side_effect=allow_superuser),
        patch("lfx.base.models.unified_models.validate_model_provider_key"),
    ):
        await service.initialize_user_variables(user_id=user.id, session=session)

    assert seen_attributes == {"is_superuser": True}
    imported = await service.get_variable_object(user.id, "OPENAI_API_KEY", session)
    assert imported.user_id == user.id


async def test_get_variable(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    value = "value"
    field = ""
    await service.create_variable(user_id, name, value, session=session)

    result = await service.get_variable(user_id, name, field, session=session)

    assert isinstance(result, SecretStr)
    assert result.get_secret_value() == value
    assert str(result) == "**********"


async def test_get_variable__valueerror(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    field = ""

    with pytest.raises(ValueError, match=f"{name} variable not found."):
        await service.get_variable(user_id, name, field, session=session)


async def test_get_variable_resolves_one_explicitly_shared_runtime_value(service, session: AsyncSession):
    owner_id = uuid4()
    actor_id = uuid4()
    shared = await service.create_variable(
        owner_id,
        "SHARED_TOKEN",
        "shared-secret",
        type_=CREDENTIAL_TYPE,
        session=session,
    )

    authz = MagicMock()
    authz.is_enabled = AsyncMock(return_value=True)
    authz.supports_cross_user_fetch = AsyncMock(return_value=True)
    authz.get_resource_visibility = None
    authz.list_visible_resource_ids = AsyncMock(return_value=[shared.id])

    with patch("langflow.services.deps.get_authorization_service", return_value=authz):
        result = await service.get_variable(actor_id, "SHARED_TOKEN", "", session=session)

    assert isinstance(result, SecretStr)
    assert result.get_secret_value() == "shared-secret"


async def test_get_variable_resolves_scope_native_global_runtime_value(service, session: AsyncSession):
    owner_id = uuid4()
    actor_id = uuid4()
    await service.create_variable(
        owner_id,
        "GLOBAL_SHARED_TOKEN",
        "shared-secret",
        type_=CREDENTIAL_TYPE,
        session=session,
    )

    authz = MagicMock()
    authz.is_enabled = AsyncMock(return_value=True)
    authz.supports_cross_user_fetch = AsyncMock(return_value=True)
    authz.get_resource_visibility = AsyncMock(return_value=ResourceVisibilityScope(all_resources=True))
    authz.list_visible_resource_ids = AsyncMock(side_effect=AssertionError("legacy visibility hook used"))

    with patch("langflow.services.deps.get_authorization_service", return_value=authz):
        result = await service.get_variable(actor_id, "GLOBAL_SHARED_TOKEN", "", session=session)

    assert isinstance(result, SecretStr)
    assert result.get_secret_value() == "shared-secret"
    authz.get_resource_visibility.assert_awaited_once()
    authz.list_visible_resource_ids.assert_not_awaited()


async def test_get_variable_fails_closed_for_domain_only_runtime_scope(service, session: AsyncSession):
    owner_id = uuid4()
    actor_id = uuid4()
    await service.create_variable(
        owner_id,
        "DOMAIN_ONLY_TOKEN",
        "shared-secret",
        type_=CREDENTIAL_TYPE,
        session=session,
    )

    authz = MagicMock()
    authz.is_enabled = AsyncMock(return_value=True)
    authz.supports_cross_user_fetch = AsyncMock(return_value=True)
    authz.get_resource_visibility = AsyncMock(
        return_value=ResourceVisibilityScope(workspace_ids=(uuid4(),), project_ids=(uuid4(),))
    )
    authz.list_visible_resource_ids = AsyncMock(side_effect=AssertionError("legacy visibility hook used"))

    with (
        patch("langflow.services.deps.get_authorization_service", return_value=authz),
        pytest.raises(ValueError, match="DOMAIN_ONLY_TOKEN variable not found"),
    ):
        await service.get_variable(actor_id, "DOMAIN_ONLY_TOKEN", "", session=session)

    authz.get_resource_visibility.assert_awaited_once()
    authz.list_visible_resource_ids.assert_not_awaited()


async def test_get_all_redacts_shared_generic_values(service, session: AsyncSession):
    owner_id = uuid4()
    actor_id = uuid4()
    owned = await service.create_variable(
        actor_id,
        "OWNED_VALUE",
        "owned-plaintext",
        type_=GENERIC_TYPE,
        session=session,
    )
    shared = await service.create_variable(
        owner_id,
        "SHARED_VALUE",
        "shared-plaintext",
        type_=GENERIC_TYPE,
        session=session,
    )

    rows = await service.get_all(
        actor_id,
        session,
        visibility=ResourceVisibilityScope(resource_ids=(shared.id,)),
    )
    by_id = {row.id: row for row in rows}

    assert by_id[owned.id].value == "owned-plaintext"
    assert by_id[owned.id].is_owner is True
    assert by_id[owned.id].can_manage_shares is True
    assert by_id[shared.id].value is None
    assert by_id[shared.id].is_owner is False
    assert by_id[shared.id].can_manage_shares is False


async def test_get_variable__typeerror(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    value = "value"
    field = "session_id"
    type_ = CREDENTIAL_TYPE
    await service.create_variable(user_id, name, value, type_=type_, session=session)

    with pytest.raises(TypeError) as exc:
        await service.get_variable(user_id, name, field, session=session)

    assert name in str(exc.value)
    assert "purpose is to prevent the exposure of value" in str(exc.value)


async def test_get_variable__credential_decrypt_failure(service, session: AsyncSession):
    """Store credential under SECRET_KEY=A, resolve with SECRET_KEY=B → raises naming the variable.

    Uses ensure_fernet_key (the real SECRET_KEY→Fernet derivation path) so the test exercises
    the exact mismatch scenario described in the ticket: a key rotation or missing persisted key.
    The test auth service (lfx stub) is a passthrough, so we patch at the auth_utils boundary.
    """
    secret_key_a = secrets.token_urlsafe(32)
    secret_key_b = secrets.token_urlsafe(32)
    fernet_a = Fernet(ensure_fernet_key(secret_key_a))
    fernet_b = Fernet(ensure_fernet_key(secret_key_b))

    user_id = uuid4()
    name = "MY_CRED"

    # Phase 1: store credential encrypted under SECRET_KEY = secret_key_a.
    with patch(
        "langflow.services.variable.service.auth_utils.encrypt_api_key",
        side_effect=lambda v: fernet_a.encrypt(v.encode()).decode(),
    ):
        await service.create_variable(user_id, name, "secret123", type_=CREDENTIAL_TYPE, session=session)

    # Phase 2: resolve with SECRET_KEY = secret_key_b (mismatched) — Fernet raises InvalidToken → "".
    def decrypt_with_wrong_key(ciphertext: str) -> str:
        try:
            return fernet_b.decrypt(ciphertext.encode()).decode()
        except Exception:
            return ""

    with (
        patch("langflow.services.variable.service.auth_utils.decrypt_api_key", side_effect=decrypt_with_wrong_key),
        pytest.raises(ValueError, match=r"MY_CRED.*SECRET_KEY"),
    ):
        await service.get_variable(user_id, name, "", session=session)


async def test_list_variables(service, session: AsyncSession):
    user_id = uuid4()
    names = ["name1", "name2", "name3"]
    value = "value"
    for name in names:
        await service.create_variable(user_id, name, value, session=session)

    result = await service.list_variables(user_id, session=session)

    assert all(name in result for name in names)


async def test_list_variables__empty(service, session: AsyncSession):
    result = await service.list_variables(uuid4(), session=session)

    assert not result
    assert isinstance(result, list)


async def test_update_variable(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    old_value = "old_value"
    new_value = "new_value"
    field = ""
    await service.create_variable(user_id, name, old_value, session=session)

    old_recovered = await service.get_variable(user_id, name, field, session=session)
    result = await service.update_variable(user_id, name, new_value, session=session)
    new_recovered = await service.get_variable(user_id, name, field, session=session)

    assert isinstance(old_recovered, SecretStr)
    assert isinstance(new_recovered, SecretStr)
    assert old_value == old_recovered.get_secret_value()
    assert new_value == new_recovered.get_secret_value()
    assert result.user_id == user_id
    assert result.name == name
    assert result.value != old_value
    assert result.value != new_value
    assert result.default_fields == []
    assert result.type == CREDENTIAL_TYPE
    assert isinstance(result.created_at, datetime)
    assert isinstance(result.updated_at, datetime)


async def test_update_variable__valueerror(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    value = "value"

    with pytest.raises(ValueError, match=f"{name} variable not found."):
        await service.update_variable(user_id, name, value, session=session)


async def test_update_variable_fields(service, session: AsyncSession):
    user_id = uuid4()
    new_name = new_value = "donkey"
    variable = await service.create_variable(user_id, "old_name", "old_value", session=session)
    saved = variable.model_dump()
    variable = VariableUpdate(**saved)
    variable.name = new_name
    variable.value = new_value
    variable.default_fields = ["new_field"]

    result = await service.update_variable_fields(
        user_id=user_id,
        variable_id=saved.get("id"),
        variable=variable,
        session=session,
    )

    assert result.name == new_name
    assert result.value != new_value
    assert saved.get("id") == result.id
    assert saved.get("user_id") == result.user_id
    assert saved.get("name") != result.name
    assert saved.get("value") != result.value
    assert saved.get("default_fields") != result.default_fields
    assert saved.get("type") == result.type
    assert saved.get("created_at") == result.created_at
    assert saved.get("updated_at") != result.updated_at


async def test_update_variable_fields__generic_type_not_encrypted(service, session: AsyncSession):
    """Test that GENERIC_TYPE variables are NOT encrypted when using update_variable_fields."""
    user_id = uuid4()
    original_value = '["model1", "model2"]'  # JSON string like __enabled_models__
    new_value = '["model3", "model4"]'

    # Create a GENERIC_TYPE variable (like __enabled_models__)
    variable = await service.create_variable(
        user_id, "enabled_models", original_value, type_=GENERIC_TYPE, session=session
    )
    saved = variable.model_dump()

    # Verify it was stored as plain text (not encrypted)
    assert saved.get("value") == original_value

    # Update using update_variable_fields
    variable_update = VariableUpdate(**saved)
    variable_update.value = new_value

    result = await service.update_variable_fields(
        user_id=user_id,
        variable_id=saved.get("id"),
        variable=variable_update,
        session=session,
    )

    # For GENERIC_TYPE, value should be stored as plain text (not encrypted)
    assert result.value == new_value
    assert result.type == GENERIC_TYPE


async def test_delete_variable(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    value = "value"
    field = ""

    await service.create_variable(user_id, name, value, session=session)
    recovered = await service.get_variable(user_id, name, field, session=session)
    await service.delete_variable(user_id, name, session=session)
    with pytest.raises(ValueError, match=f"{name} variable not found."):
        await service.get_variable(user_id, name, field, session=session)

    assert isinstance(recovered, SecretStr)
    assert recovered.get_secret_value() == value


async def test_delete_variable__valueerror(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"

    with pytest.raises(ValueError, match=f"{name} variable not found."):
        await service.delete_variable(user_id, name, session=session)


async def test_delete_variable_by_id(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    value = "value"
    field = "field"

    saved = await service.create_variable(user_id, name, value, session=session)
    recovered = await service.get_variable(user_id, name, field, session=session)
    await service.delete_variable_by_id(user_id, saved.id, session=session)
    with pytest.raises(ValueError, match=f"{name} variable not found."):
        await service.get_variable(user_id, name, field, session=session)

    assert isinstance(recovered, SecretStr)
    assert recovered.get_secret_value() == value


async def test_delete_variable_by_id__valueerror(service, session: AsyncSession):
    user_id = uuid4()
    variable_id = uuid4()

    with pytest.raises(ValueError, match=f"{variable_id} variable not found."):
        await service.delete_variable_by_id(user_id, variable_id, session=session)


async def test_create_variable(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    value = "value"

    result = await service.create_variable(user_id, name, value, session=session)

    assert result.user_id == user_id
    assert result.name == name
    assert result.value != value
    assert result.default_fields == []
    assert result.type == CREDENTIAL_TYPE
    assert isinstance(result.created_at, datetime)
    assert result.updated_at is None  # Should be None on creation


async def test_get_all_decrypted_variables(service, session: AsyncSession):
    """Test get_all_decrypted_variables returns all variables with decrypted values."""
    user_id = uuid4()

    # Create multiple variables with different types
    await service.create_variable(user_id, "API_KEY_1", "secret_value_1", type_=CREDENTIAL_TYPE, session=session)
    await service.create_variable(user_id, "API_KEY_2", "secret_value_2", type_=CREDENTIAL_TYPE, session=session)
    await service.create_variable(user_id, "GENERIC_VAR", "plain_value", type_="GENERIC", session=session)

    # Get all decrypted variables
    result = await service.get_all_decrypted_variables(user_id, session=session)

    # Verify all variables are returned
    assert len(result) == 3
    assert "API_KEY_1" in result
    assert "API_KEY_2" in result
    assert "GENERIC_VAR" in result

    # Verify values are decrypted
    assert result["API_KEY_1"] == "secret_value_1"  # pragma: allowlist secret
    assert result["API_KEY_2"] == "secret_value_2"  # pragma: allowlist secret
    assert result["GENERIC_VAR"] == "plain_value"


async def test_get_all_decrypted_variables__empty(service, session: AsyncSession):
    """Test get_all_decrypted_variables returns empty dict when no variables exist."""
    user_id = uuid4()

    result = await service.get_all_decrypted_variables(user_id, session=session)

    assert result == {}
    assert isinstance(result, dict)


async def test_get_all_decrypted_variables__decryption_failure(service, session: AsyncSession):
    """Test get_all_decrypted_variables handles decryption failures gracefully."""
    user_id = uuid4()

    # Create a variable
    await service.create_variable(user_id, "TEST_VAR", "test_value", session=session)

    # Mock decryption to fail
    with patch("langflow.services.auth.utils.decrypt_api_key") as mock_decrypt:
        mock_decrypt.side_effect = Exception("Decryption failed")

        result = await service.get_all_decrypted_variables(user_id, session=session)

        # Should skip variables that fail decryption
        assert "TEST_VAR" not in result
        assert result == {}


async def test_create_generic_variable_with_fernet_signature_fails(service, session: AsyncSession):
    """Test that creating a GENERIC variable starting with gAAAAA fails."""
    user_id = uuid4()

    with pytest.raises(ValueError, match="cannot start with 'gAAAAA'"):
        await service.create_variable(
            user_id, "TEST_VAR", "gAAAAABthis-looks-like-encrypted-but-is-generic", type_="Generic", session=session
        )


async def test_update_generic_variable_with_fernet_signature_fails(service, session: AsyncSession):
    """Test that updating a GENERIC variable to start with gAAAAA fails."""
    user_id = uuid4()

    # Create a normal generic variable
    await service.create_variable(user_id, "TEST_VAR", "normal_value", type_="Generic", session=session)

    # Try to update it to a value starting with gAAAAA
    with pytest.raises(ValueError, match="cannot start with 'gAAAAA'"):
        await service.update_variable(user_id, "TEST_VAR", "gAAAAABthis-looks-like-encrypted", session=session)


async def test_get_all__empty_value_warns_and_skips(service, session: AsyncSession):
    """get_all warns and skips GENERIC variables whose stored value is None or empty."""
    user_id = uuid4()

    # Create a normal generic variable, then manually blank its value to simulate a bad DB row.
    var = await service.create_variable(user_id, "EMPTY_VAR", "initial", type_=GENERIC_TYPE, session=session)
    var.value = ""
    session.add(var)
    await session.flush()

    mock_logger = MagicMock()
    mock_logger.awarning = AsyncMock()
    with patch("langflow.services.variable.service.logger", mock_logger):
        result = await service.get_all(user_id, session=session)

    # Variable should be excluded from results.
    assert not any(v.name == "EMPTY_VAR" for v in result)
    # Warning must name the variable and mention empty value.
    warning_calls = [str(c) for c in mock_logger.awarning.call_args_list]
    assert any("EMPTY_VAR" in c for c in warning_calls)
    assert any("no stored value" in c for c in warning_calls)


async def test_get_all__decrypt_failure_warns_and_skips(service, session: AsyncSession):
    """get_all warns with a key-mismatch message when decrypt returns empty for a non-empty value."""
    user_id = uuid4()

    await service.create_variable(user_id, "MY_VAR", "real_value", type_=GENERIC_TYPE, session=session)

    mock_logger = MagicMock()
    mock_logger.awarning = AsyncMock()
    # Simulate decrypt returning "" (key mismatch) without touching the stored value.
    with (
        patch("langflow.services.variable.service.auth_utils.decrypt_api_key", return_value=""),
        patch("langflow.services.variable.service.logger", mock_logger),
    ):
        result = await service.get_all(user_id, session=session)

    # Variable should be excluded from results.
    assert not any(v.name == "MY_VAR" for v in result)
    # Warning must name the variable and mention SECRET_KEY.
    warning_calls = [str(c) for c in mock_logger.awarning.call_args_list]
    assert any("MY_VAR" in c for c in warning_calls)
    assert any("SECRET_KEY" in c for c in warning_calls)


async def test_get_all__healthy_generic_variable_included(service, session: AsyncSession):
    """get_all includes GENERIC variables that decrypt successfully — no warnings emitted."""
    user_id = uuid4()

    await service.create_variable(user_id, "GOOD_VAR", "good_value", type_=GENERIC_TYPE, session=session)

    mock_logger = MagicMock()
    mock_logger.awarning = AsyncMock()
    with patch("langflow.services.variable.service.logger", mock_logger):
        result = await service.get_all(user_id, session=session)

    assert any(v.name == "GOOD_VAR" for v in result)
    mock_logger.awarning.assert_not_called()


async def test_create_credential_variable_with_fernet_signature_succeeds(service, session: AsyncSession):
    """Test that CREDENTIAL variables can have values that look like Fernet tokens (they get encrypted anyway)."""
    user_id = uuid4()

    # This should succeed because CREDENTIAL types are encrypted
    variable = await service.create_variable(
        user_id,
        "TEST_CRED",
        "gAAAAABsome-value",  # This will be encrypted, so it's fine
        type_="Credential",
        session=session,
    )

    assert variable is not None
    assert variable.name == "TEST_CRED"
    # The value should be encrypted (different from input)
    assert variable.value != "gAAAAABsome-value"


# A Fernet token always starts with this prefix. We use a synthetic one so the tests are
# deterministic regardless of whether the auth service in the test env actually encrypts.
_FERNET_TOKEN = "gAAAAABthis-stands-in-for-an-encrypted-credential"  # noqa: S105  # pragma: allowlist secret


async def test_credential_to_generic_type_flip_without_value_is_rejected(service, session: AsyncSession):
    """Security: flipping a CREDENTIAL variable to GENERIC without a new value is rejected.

    Otherwise the Fernet ciphertext would remain in the row while the type says GENERIC,
    and get_all() would decrypt it and return the plaintext secret via GET /variables.
    """
    user_id = uuid4()
    variable = await service.create_variable(
        user_id, "OPENAI_API_KEY", "placeholder", type_=CREDENTIAL_TYPE, session=session
    )
    saved_id = variable.model_dump()["id"]

    # Pin the at-rest value to a Fernet token so the guard precondition holds in any env.
    db_var = await service.get_variable_by_id(user_id, saved_id, session=session)
    db_var.value = _FERNET_TOKEN
    session.add(db_var)
    await session.flush()
    assert db_var.updated_at is None

    # Attacker sends only {id, type=Generic} with no value -> must be rejected.
    flip = VariableUpdate(id=saved_id, type=GENERIC_TYPE)
    with pytest.raises(ValueError, match="without providing a new value"):
        await service.update_variable_fields(
            user_id=user_id,
            variable_id=saved_id,
            variable=flip,
            session=session,
        )

    # The row must remain CREDENTIAL-typed (transition rejected, not silently applied).
    db_var_after = await service.get_variable_by_id(user_id, saved_id, session=session)
    assert db_var_after.type == CREDENTIAL_TYPE
    assert db_var_after.updated_at is None


async def test_get_all_never_returns_decrypted_credential_as_generic(service, session: AsyncSession):
    """Security defense-in-depth: a GENERIC row holding a Fernet token is never decrypted/returned.

    Simulates a pre-existing type-confused row (e.g. from before the write-path guard) and
    verifies get_all() does not leak its value.
    """
    user_id = uuid4()
    variable = await service.create_variable(
        user_id, "AWS_SECRET_ACCESS_KEY", "placeholder", type_=CREDENTIAL_TYPE, session=session
    )
    saved_id = variable.model_dump()["id"]

    # Force the corrupt state directly in the DB (bypassing the write-path guard):
    # GENERIC type but the value is still a Fernet token.
    db_var = await service.get_variable_by_id(user_id, saved_id, session=session)
    db_var.type = GENERIC_TYPE
    db_var.value = _FERNET_TOKEN
    session.add(db_var)
    await session.flush()

    results = await service.get_all(user_id, session=session)
    # The type-confused row must be skipped, never returned with a value derived from the token.
    leaked = [v for v in results if v.value and v.value.startswith("gAAAAA")]
    assert leaked == []
    assert all(v.id != saved_id for v in results if v.value is not None)
