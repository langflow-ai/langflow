from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langflow.services.variable.constants import CREDENTIAL_TYPE
from langflow.services.variable.kubernetes import KubernetesSecretService
from lfx.services.variable import VariableNotFoundError
from lfx.services.variable.exceptions import RuntimeVariableError


def _service_with_secret(secret: dict[str, str] | None) -> KubernetesSecretService:
    service = KubernetesSecretService.__new__(KubernetesSecretService)
    service.kubernetes_secrets = MagicMock()
    service.kubernetes_secrets.get_secret.return_value = secret
    return service


def test_resolve_variable_rejects_empty_secret() -> None:
    service = _service_with_secret({})

    with pytest.raises(VariableNotFoundError, match="variable not found"):
        service.resolve_variable("user-secret", "user-1", "API_KEY")


def test_resolve_variable_rejects_missing_name() -> None:
    service = _service_with_secret({"OTHER_KEY": "other-value"})

    with pytest.raises(VariableNotFoundError, match="variable name API_KEY not found"):
        service.resolve_variable("user-secret", "user-1", "API_KEY")


def test_resolve_variable_returns_plain_variable() -> None:
    service = _service_with_secret({"API_KEY": "plain-value"})

    assert service.resolve_variable("user-secret", "user-1", "API_KEY") == ("API_KEY", "plain-value")


def test_resolve_variable_returns_credential_variable() -> None:
    credential_name = f"{CREDENTIAL_TYPE}_API_KEY"
    service = _service_with_secret({credential_name: "credential-value"})

    assert service.resolve_variable("user-secret", "user-1", "API_KEY") == (
        credential_name,
        "credential-value",
    )


@pytest.mark.asyncio
async def test_bound_account_refusal_precedes_kubernetes_secret_lookup(monkeypatch):
    from langflow.services.variable import runtime_policy

    service = _service_with_secret({"Credential_API_KEY": "alternate-store-value"})
    service.settings_service = object()

    async def refused(**_):
        msg = "Account denied"
        raise RuntimeVariableError(msg, reason="variable_not_approved")

    monkeypatch.setattr(runtime_policy, "_resolver", refused)
    with pytest.raises(RuntimeVariableError, match="Account denied"):
        await service.get_variable(user_id=uuid4(), name="API_KEY", field="", session=None)
    service.kubernetes_secrets.get_secret.assert_not_called()
