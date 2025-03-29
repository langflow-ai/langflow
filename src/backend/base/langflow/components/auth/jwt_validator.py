import base64

import jwt
import requests
from jwt import PyJWK

from langflow.custom import Component
from langflow.inputs import MessageTextInput
from langflow.schema.message import Message
from langflow.template import Output


class JWTValidatorComponent(Component):
    display_name = "JWT Validator"
    description = "Validates a JWT and extracts the user ID."
    icon = "lock"

    inputs = [
        MessageTextInput(
            name="jwt_token",
            display_name="JWT Token",
            required=True,
            info="The JSON Web Token to validate",
        ),
        MessageTextInput(
            name="jwks_url",
            display_name="JWKS URL",
            required=True,
            value="https://test.com/.well-known/jwks.json",
            info="URL of the JSON Web Key Set for token validation",
        ),
    ]
    outputs = [
        Output(display_name="User ID", name="user_id", method="validate_auth"),
    ]

    def validate_auth(self) -> Message:
        response = requests.get(self.jwks_url, timeout=10)
        jwks = response.json()
        headers = jwt.get_unverified_header(self.jwt_token)

        try:
            jwk = next(k for k in jwks["keys"] if k["kid"] == headers["kid"])
            if isinstance(jwk.get("e"), int):
                jwk["e"] = self._int_to_base64url(jwk["e"])
            if isinstance(jwk.get("n"), int):
                jwk["n"] = self._int_to_base64url(jwk["n"])

            public_key = PyJWK(jwk).key
            payload = jwt.decode(self.jwt_token, public_key, algorithms=["RS256"])
            return Message(content=payload["sub"])
        except KeyError as e:
            error_message = f"Missing key in JWT or JWKS: {e!s}"
            raise KeyError(error_message) from e
        except jwt.ExpiredSignatureError:
            raise
        except jwt.PyJWTError as e:
            error_message = f"JWT validation failed: {e!s}"
            raise jwt.InvalidTokenError(error_message) from e

    def _int_to_base64url(self, value: int) -> str:
        """Convert an integer to a Base64URL-encoded string."""
        byte_length = (value.bit_length() + 7) // 8
        value_bytes = value.to_bytes(byte_length, byteorder="big")
        return base64.urlsafe_b64encode(value_bytes).rstrip(b"=").decode("ascii")
