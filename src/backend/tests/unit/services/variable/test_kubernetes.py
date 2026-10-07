from unittest.mock import MagicMock, patch

import pytest
from langflow.services.variable.constants import CREDENTIAL_TYPE
from langflow.services.variable.kubernetes import KubernetesSecretService
from lfx.services.variable import VariableNotFoundError


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


async def test_batch_fallback_preserves_values_and_warns_on_each_call() -> None:
    service = _service_with_secret({"VALUE": "test-value"})
    with patch("langflow.services.variable.base.logger.warning") as warning:
        assert await service.get_variables("user-1", [], "", None) == {}
        warning.assert_not_called()
        for _ in range(2):
            assert await service.get_variables("user-1", ["VALUE", "MISSING"], "", None) == {
                "VALUE": "test-value",
                "MISSING": None,
            }
    assert warning.call_count == 2
    message = warning.call_args.args[0]
    assert "KubernetesSecretService" in message
    assert "VALUE" not in message
    assert "test-value" not in message
