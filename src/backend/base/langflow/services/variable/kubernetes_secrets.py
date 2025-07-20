from base64 import b64decode, b64encode
from http import HTTPStatus
from uuid import UUID

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from loguru import logger


class KubernetesSecretManager:
    """A class for managing Kubernetes secrets."""

    def __init__(self, namespace: str = "langflow"):
        """Initialize the KubernetesSecretManager class.

        Args:
            namespace (str): The namespace in which to perform secret operations.
        """
        config.load_kube_config()
        self.namespace = namespace

        # initialize the Kubernetes API client
        self.core_api = client.CoreV1Api()

    def create_secret(
        self,
        name: str,
        data: dict,
        secret_type: str = "Opaque",  # noqa: S107
    ):
        """Create a new secret in the specified namespace.

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
            api_version="v1", kind="Secret", metadata=secret_metadata, type=secret_type, data=encoded_data
        )

        return self.core_api.create_namespaced_secret(self.namespace, secret)

    def upsert_secret(self, secret_name: str, data: dict):
        """Upsert a secret in the specified namespace.

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
            if e.status == HTTPStatus.NOT_FOUND:
                # Secret doesn't exist, create a new one
                return self.create_secret(secret_name, data)
            logger.exception(f"Error upserting secret {secret_name}")
            raise

    def get_secret(self, name: str) -> dict | None:
        """Read a secret from the specified namespace.

        Args:
            name (str): The name of the secret to read.

        Returns:
            V1Secret: The secret object.
        """
        try:
            secret = self.core_api.read_namespaced_secret(name, self.namespace)
            return {k: b64decode(v).decode() for k, v in secret.data.items()}
        except ApiException as e:
            if e.status == HTTPStatus.NOT_FOUND:
                return None
            raise

    def update_secret(self, name: str, data: dict):
        """Update an existing secret in the specified namespace.

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
        """Delete a key from the specified secret in the namespace.

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
        """Delete a secret from the specified namespace.

        Args:
            name (str): The name of the secret to delete.

        Returns:
            V1Status: The status object indicating the success or failure of the operation.
        """
        return self.core_api.delete_namespaced_secret(name, self.namespace)


# utility function to encode user_id to base64 lower case and numbers only
# this is required by kubernetes secret name restrictions
def encode_user_id(user_id: UUID | str) -> str:
    # Handle UUID
    if isinstance(user_id, UUID):
        return f"uuid-{str(user_id).lower()}"[:253]

    # Convert string to lowercase
    user_id_ = str(user_id).lower()

    # If the user_id looks like an email, replace @ and . with allowed characters
    if "@" in user_id_ or "." in user_id_:
        user_id_ = user_id_.replace("@", "-at-").replace(".", "-dot-")

    # Encode the user_id to base64
    # encoded = base64.b64encode(user_id.encode("utf-8")).decode("utf-8")

    # Replace characters not allowed in Kubernetes names
    user_id_ = user_id_.replace("+", "-").replace("/", "_").rstrip("=")

    # Ensure the name starts with an alphanumeric character
    if not user_id_[0].isalnum():
        user_id_ = "a-" + user_id_

    # Truncate to 253 characters (Kubernetes name length limit)
    user_id_ = user_id_[:253]

    if not all(c.isalnum() or c in "-_" for c in user_id_):
        msg = f"Invalid user_id: {user_id_}"
        raise ValueError(msg)

    # Ensure the name ends with an alphanumeric character
    while not user_id_[-1].isalnum():
        user_id_ = user_id_[:-1]

    return user_id_
