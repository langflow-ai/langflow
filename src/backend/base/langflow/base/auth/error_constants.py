"""Constants for authentication error messages."""


class AuthValidationError:
    """Custom exception class for authentication validation errors."""

    def __init__(self, message: str):
        self.message = message


class AuthErrors:
    """Constants for authentication error messages."""

    # Initialization errors
    PERMIT_NOT_INITIALIZED = AuthValidationError("Permit client not initialized. Please provide API key and PDP URL.")
    JWKS_NOT_INITIALIZED = AuthValidationError("JWKS not initialized. Please provide JWKS URL.")

    # Validation errors
    AUTH_REQUIRED = AuthValidationError("Authorization required")
    INVALID_FORMAT = AuthValidationError("Invalid authorization format")
    MISSING_IDENTIFIER = AuthValidationError("Missing authorization identifier")
    NOT_FOUND = AuthValidationError("Authorization not found")

    # Status errors
    AUTH_INVALID = AuthValidationError("Authorization invalid")
    AUTH_EXPIRED = AuthValidationError("Authorization expired")
    MALFORMED = AuthValidationError("Invalid structure")
    MISSING_USER = AuthValidationError("Missing user identifier")

    @staticmethod
    def auth_not_found(identifier: str) -> AuthValidationError:
        """Generate error for missing authorization."""
        return AuthValidationError(f"Authorization not found: {identifier}")

    @staticmethod
    def validation_failed(error: Exception) -> AuthValidationError:
        """Generate error for validation failure."""
        return AuthValidationError(str(error))
