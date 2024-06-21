import pytest
from unittest.mock import MagicMock, patch
from kubernetes.client.rest import ApiException
from kubernetes.client import V1ObjectMeta, V1Secret
from base64 import b64encode

from langflow.services.variable.kubernetes_secrets import KubernetesSecretManager

@pytest.fixture
def secret_manager():
    return KubernetesSecretManager(namespace='test-namespace')

def test_create_secret(secret_manager, mocker):
    mocker.patch.object(secret_manager.core_api, 'create_namespaced_secret', return_value=V1Secret(metadata=V1ObjectMeta(name='test-secret')))
    
    secret_manager.create_secret(name='test-secret', data={'key': 'value'})
    secret_manager.core_api.create_namespaced_secret.assert_called_once_with(
        'test-namespace',
        V1Secret(
            api_version='v1',
            kind='Secret',
            metadata=V1ObjectMeta(name='test-secret'),
            type='Opaque',
            data={'key': b64encode('value'.encode()).decode()}
        )
    )

def test_get_secret(secret_manager, mocker):
    mock_secret = V1Secret(data={'key': b64encode('value'.encode()).decode()})
    mocker.patch.object(secret_manager.core_api, 'read_namespaced_secret', return_value=mock_secret)
    
    secret_data = secret_manager.get_secret(name='test-secret')
    secret_manager.core_api.read_namespaced_secret.assert_called_once_with('test-secret', 'test-namespace')
    assert secret_data == {'key': 'value'}

def test_update_secret(secret_manager, mocker):
    mocker.patch.object(secret_manager.core_api, 'replace_namespaced_secret', return_value=V1Secret(metadata=V1ObjectMeta(name='test-secret')))
    
    secret_manager.update_secret(name='test-secret', data={'key': 'new-value'})
    secret_manager.core_api.replace_namespaced_secret.assert_called_once_with(
        'test-secret',
        'test-namespace',
        V1Secret(metadata=V1ObjectMeta(name='test-secret'), data={'key': 'new-value'})
    )

def test_delete_secret(secret_manager, mocker):
    mocker.patch.object(secret_manager.core_api, 'delete_namespaced_secret', return_value=MagicMock(status='Success'))
    
    secret_manager.delete_secret(name='test-secret')
    secret_manager.core_api.delete_namespaced_secret.assert_called_once_with('test-secret', 'test-namespace')
