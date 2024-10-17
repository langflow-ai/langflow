from base64 import b64encode
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from kubernetes.client import V1ObjectMeta, V1Secret
from langflow.services.variable.kubernetes_secrets import KubernetesSecretManager, encode_user_id


@pytest.fixture
def _mock_kube_config(mocker):
    mocker.patch("kubernetes.config.load_kube_config")
    mocker.patch("kubernetes.config.load_incluster_config")


@pytest.fixture
def secret_manager(_mock_kube_config):
    return KubernetesSecretManager(namespace="test-namespace")


def test_create_secret(secret_manager, mocker):
    mocker.patch.object(
        secret_manager.core_api,
        "create_namespaced_secret",
        return_value=V1Secret(metadata=V1ObjectMeta(name="test-secret")),
    )

    secret_manager.create_secret(name="test-secret", data={"key": "value"})
    secret_manager.core_api.create_namespaced_secret.assert_called_once_with(
        "test-namespace",
        V1Secret(
            api_version="v1",
            kind="Secret",
            metadata=V1ObjectMeta(name="test-secret"),
            type="Opaque",
            data={"key": b64encode(b"value").decode()},
        ),
    )


def test_get_secret(secret_manager, mocker):
    mock_secret = V1Secret(data={"key": b64encode(b"value").decode()})
    mocker.patch.object(secret_manager.core_api, "read_namespaced_secret", return_value=mock_secret)

    secret_data = secret_manager.get_secret(name="test-secret")
    secret_manager.core_api.read_namespaced_secret.assert_called_once_with("test-secret", "test-namespace")
    assert secret_data == {"key": "value"}


def test_delete_secret(secret_manager, mocker):
    mocker.patch.object(secret_manager.core_api, "delete_namespaced_secret", return_value=MagicMock(status="Success"))

    secret_manager.delete_secret(name="test-secret")
    secret_manager.core_api.delete_namespaced_secret.assert_called_once_with("test-secret", "test-namespace")


def test_encode_uuid():
    uuid = UUID("123e4567-e89b-12d3-a456-426614174000")
    result = encode_user_id(uuid)
    assert result == "uuid-123e4567-e89b-12d3-a456-426614174000"
    assert len(result) < 253
    assert result[0].isalnum()
    assert result[-1].isalnum()


def test_encode_string():
    string_id = "user@example.com"
    result = encode_user_id(string_id)
    # assert (result.isalnum() or '-' in result or '_' in result)
    assert len(result) < 253
    assert result[0].isalnum()
    assert result[-1].isalnum()


def test_long_string():
    long_string = "a" * 300
    result = encode_user_id(long_string)
    assert len(result) <= 253


def test_starts_with_non_alphanumeric():
    non_alnum_start = "+user123"
    result = encode_user_id(non_alnum_start)
    assert result[0].isalnum()


def test_ends_with_non_alphanumeric():
    non_alnum_end = "user123+"
    result = encode_user_id(non_alnum_end)
    assert result[-1].isalnum()


def test_email_address():
    email = "User.Name@Example.com"
    result = encode_user_id(email)
    assert result.isalnum() or "-" in result or "_" in result
    assert len(result) < 253
    assert result[0].isalnum()
    assert result[-1].isalnum()


def test_uuid_case_insensitivity():
    uuid_upper = UUID("123E4567-E89B-12D3-A456-426614174000")
    uuid_lower = UUID("123e4567-e89b-12d3-a456-426614174000")
    result_upper = encode_user_id(uuid_upper)
    result_lower = encode_user_id(uuid_lower)
    assert result_upper == result_lower
