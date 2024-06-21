from kubernetes import client, config  # type: ignore
from kubernetes.client.rest import ApiException
from base64 import b64encode, b64decode

from loguru import logger

class KubernetesSecretManager:
    """
    A class for managing Kubernetes secrets.
    """

    def __init__(self, namespace: str = "langflow"):
        """
        Initialize the KubernetesSecretManager class.

        Args:
            namespace (str): The namespace in which to perform secret operations.
        """
        config.load_kube_config()
        self.namespace = namespace

        # initialize the Kubernetes API client
        self.core_api = client.CoreV1Api()

    def create_secret(self, name: str, data: dict, secret_type: str = "Opaque"):
        """
        Create a new secret in the specified namespace.

        Args:
            name (str): The name of the secret to create.
            data (dict): A dictionary containing the key-value pairs for the secret data.
            secret_type (str, optional): The type of secret to create. Defaults to 'Opaque'.

        Returns:
            V1Secret: The created secret object.
        """
        encoded_data = {k: b64encode(v.encode()).decode() for k, v in data.items()}

        secret_metadata = client.V1ObjectMeta(name=name)
        secret = client.V1Secret(
            api_version="v1",
            kind="Secret",
            metadata=secret_metadata, 
            type=secret_type,
            data=encoded_data
        )

        return self.core_api.create_namespaced_secret(self.namespace, secret)
    
    def upsert_secret(self, secret_name: str, data: dict, secret_type: str = "Opaque"):
        """
        Upsert a secret in the specified namespace.
        If the secret doesn't exist, it will be created.
        If it exists, it will be updated with new data while preserving existing keys.

        :param secret_name: Name of the secret
        :param new_data: Dictionary containing new key-value pairs for the secret
        :return: Created or updated secret object
        """
        try:
            # Try to read the existing secret
            existing_secret = self.core_api.read_namespaced_secret(secret_name, self.namespace)
            
            # If secret exists, update it
            existing_data = {k: b64decode(v).decode() for k, v in existing_secret.data.items()}
            existing_data.update(data)
            
            # Encode all data to base64
            encoded_data = {k: b64encode(v.encode()).decode() for k, v in existing_data.items()}
            
            # Update the existing secret
            existing_secret.data = encoded_data
            return self.core_api.replace_namespaced_secret(secret_name, self.namespace, existing_secret)
        
        except ApiException as e:
            if e.status == 404:
                # Secret doesn't exist, create a new one
                return self.create_secret(secret_name, data)
            else:
                logger.error(f"Error upserting secret {secret_name}: {e}")
                raise

    def get_secret(self, name: str) -> dict | None:
        """
        Read a secret from the specified namespace.

        Args:
            name (str): The name of the secret to read.

        Returns:
            V1Secret: The secret object.
        """
        try:
            secret = self.core_api.read_namespaced_secret(name, self.namespace)
            return {k: b64decode(v).decode() for k, v in secret.data.items()}
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    def update_secret(self, name: str, data: dict):
        """
        Update an existing secret in the specified namespace.

        Args:
            name (str): The name of the secret to update.
            data (dict): A dictionary containing the key-value pairs for the updated secret data.

        Returns:
            V1Secret: The updated secret object.
        """
        # Get the existing secret
        secret = self.core_api.read_namespaced_secret(name, self.namespace)
        if secret is None:
            raise ApiException(status=404, reason="Not Found", msg="Secret not found")
        
        # Update the secret data
        encoded_data = {k: b64encode(v.encode()).decode() for k, v in data.items()}
        secret.data.update(encoded_data)
        
        # Update the secret in Kubernetes
        return self.core_api.replace_namespaced_secret(name, self.namespace, secret)
    
    def delete_secret_key(self, name: str, key: str):
        """
        Delete a key from the specified secret in the namespace.

        Args:
            name (str): The name of the secret.
            key (str): The key to delete from the secret.

        Returns:
            V1Secret: The updated secret object.
        """
        # Get the existing secret
        secret = self.core_api.read_namespaced_secret(name, self.namespace)
        if secret is None:
            raise ApiException(status=404, reason="Not Found", msg="Secret not found")
        
        # Delete the key from the secret data
        if key in secret.data:
            del secret.data[key]
        else:
            raise ApiException(status=404, reason="Not Found", msg="Key not found in the secret")
        
        # Update the secret in Kubernetes
        return self.core_api.replace_namespaced_secret(name, self.namespace, secret)
      
    def delete_secret(self, name: str):
        """
        Delete a secret from the specified namespace.

        Args:
            name (str): The name of the secret to delete.

        Returns:
            V1Status: The status object indicating the success or failure of the operation.
        """
        return self.core_api.delete_namespaced_secret(name, self.namespace)

# utility function to encode user_id to base64 lower case and numbers only
# this is required by kubernetes secret name restrictions
def encode_user_id(user_id: str) -> str:
    return b64encode(user_id.encode()).decode().lower().replace("=", "").replace("+", "-").replace("/", "_")
