from typing import Any

import requests
from jwt import (
    DecodeError,
    ExpiredSignatureError,
    InvalidSignatureError,
    decode,
    get_unverified_header,
)
from jwt.algorithms import RSAAlgorithm

from langflow.base.auth.error_constants import AuthErrors
from langflow.base.auth.model import AuthComponent
from langflow.io import MessageTextInput, Output, StrInput


class JWTValidatorComponent(AuthComponent):
    """Component for validating JWT tokens and extracting user IDs."""

    display_name = "JWT Validator"
    description = "Validates JWT tokens and extracts user ID using JWKs"
    documentation = "https://docs.langflow.org/components-auth"
    icon = "key"

    outputs = [Output(display_name="User ID", name="auth_result", method="validate_auth")]

    inputs = [
        StrInput(
            name="jwks_url",
            display_name="JWKS URL",
            required=True,
            info="URL to fetch the JSON Web Key Sets",
        ),
        MessageTextInput(
            name="jwt_token",
            display_name="JWT Token",
            required=True,
            placeholder="Enter JWT token",
            info="JWT token to validate",
        ),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.jwks: dict[str, Any] | None = None

    def build(self, **kwargs: Any) -> None:
        """Initialize the component with JWKS URL."""
        super().build(**kwargs)

        jwks_url = kwargs.get("jwks_url") or getattr(self, "jwks_url", None)
        if jwks_url:
            self.jwks_url = jwks_url
            self.jwks = self._fetch_jwks()

    def _fetch_jwks(self) -> dict[str, Any]:
        """Fetch JWKs from the configured URL."""
        try:
            response = requests.get(self.jwks_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            error = AuthErrors.validation_failed(e)
            raise ValueError(error.message) from e

    def _get_key(self, kid: str) -> str | None:
        """Get the public key for a given key ID."""
        if not self.jwks:
            return None

        for key in self.jwks.get("keys", []):
            if key.get("kid") == kid:
                try:
                    return RSAAlgorithm.from_jwk(key)
                except (ValueError, TypeError) as e:
                    error = AuthErrors.validation_failed(e)
                    raise ValueError(error.message) from e
        return None

    def _validate_token_header(self) -> str:
        """Validate token header and extract key ID."""
        if not self.jwt_token:
            error = AuthErrors.AUTH_REQUIRED
            raise ValueError(error.message)

        try:
            header = get_unverified_header(self.jwt_token)
        except Exception as e:
            error = AuthErrors.INVALID_FORMAT
            raise ValueError(error.message) from e

        kid = header.get("kid")
        if not kid:
            error = AuthErrors.MISSING_IDENTIFIER
            raise ValueError(error.message)

        return kid

    def _decode_token(self, public_key: str) -> dict[str, Any]:
        """Decode and validate the JWT token."""
        try:
            return decode(self.jwt_token, key=public_key, algorithms=["RS256"])
        except ExpiredSignatureError as e:
            error = AuthErrors.AUTH_EXPIRED
            raise ValueError(error.message) from e
        except InvalidSignatureError as e:
            error = AuthErrors.AUTH_INVALID
            raise ValueError(error.message) from e
        except DecodeError as e:
            error = AuthErrors.MALFORMED
            raise ValueError(error.message) from e
        except Exception as e:
            error = AuthErrors.validation_failed(e)
            raise ValueError(error.message) from e

    def validate_auth(self) -> str:
        """Validate the JWT and extract the user ID."""
        if not self.jwks:
            self.build(jwks_url=getattr(self, "jwks_url", None))
            if not self.jwks:
                error = AuthErrors.JWKS_NOT_INITIALIZED
                raise ValueError(error.message)

        try:
            # Validate token header and get key ID
            kid = self._validate_token_header()

            # Get public key
            public_key = self._get_key(kid)
            if not public_key:
                error = AuthErrors.auth_not_found(kid)
                raise ValueError(error.message)

            # Decode and validate token
            decoded = self._decode_token(public_key)

            # Extract and validate user ID
            user_id = decoded.get("sub")
            if user_id:
                self.status = user_id
                return user_id
            error = AuthErrors.MISSING_USER
            raise ValueError(error.message)

        except ValueError as e:
            raise ValueError(str(e)) from e
