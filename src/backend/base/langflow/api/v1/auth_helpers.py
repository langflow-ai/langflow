from typing import Any

from pydantic import SecretStr

from langflow.services.auth.mcp_encryption import decrypt_auth_settings, encrypt_auth_settings
from langflow.services.database.models.folder.model import Folder


def handle_auth_settings_update(
    existing_project: Folder,
    new_auth_settings: dict | Any | None,
) -> dict[str, bool]:
    """Handle auth settings update including encryption/decryption and MCP Composer logic.

    Args:
        existing_project: The project being updated (modified in-place)
        new_auth_settings: New auth settings (could be dict, Pydantic model, or None)

    Returns:
        Dict containing:
        - should_start_composer: bool
        - should_stop_composer: bool
    """
    # Get current auth type before update
    current_auth_type = None
    decrypted_current = None
    if existing_project.auth_settings:
        current_auth_type = existing_project.auth_settings.get("auth_type")
        # Only decrypt if we need access to sensitive fields (for preserving masked values)
        if current_auth_type in ["oauth", "apikey"]:
            decrypted_current = decrypt_auth_settings(existing_project.auth_settings)

    if new_auth_settings is None:
        # Explicitly set to None - clear auth settings
        existing_project.auth_settings = None
        # If we were using OAuth, stop the composer
        return {"should_start_composer": False, "should_stop_composer": current_auth_type == "oauth"}

    # Handle different input types (dict vs Pydantic model)
    if isinstance(new_auth_settings, dict):
        auth_dict = new_auth_settings.copy()
    else:
        # Pydantic model - use python mode to get raw values without SecretStr masking
        auth_dict = new_auth_settings.model_dump(mode="python", exclude_none=True)

        # Handle SecretStr fields
        secret_fields = ["api_key", "oauth_client_secret"]
        for field in secret_fields:
            field_val = getattr(new_auth_settings, field, None)
            if isinstance(field_val, SecretStr):
                auth_dict[field] = field_val.get_secret_value()

    new_auth_type = auth_dict.get("auth_type")

    # Handle masked secret fields from frontend
    # If frontend sends back "*******" for a secret field, preserve the existing value
    if decrypted_current:
        secret_fields = ["oauth_client_secret", "api_key"]
        for field in secret_fields:
            if field in auth_dict and auth_dict[field] == "*******" and field in decrypted_current:
                auth_dict[field] = decrypted_current[field]

    # Encrypt and store the auth settings
    existing_project.auth_settings = encrypt_auth_settings(auth_dict)

    # Determine MCP Composer actions
    should_start_composer = new_auth_type == "oauth"
    should_stop_composer = current_auth_type == "oauth" and new_auth_type != "oauth"
    should_handle_composer = current_auth_type == "oauth" or new_auth_type == "oauth"

    return {
        "should_start_composer": should_start_composer,
        "should_stop_composer": should_stop_composer,
        "should_handle_composer": should_handle_composer,
    }
