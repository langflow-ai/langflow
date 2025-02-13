import requests
from jwt import DecodeError, ExpiredSignatureError, InvalidSignatureError, decode, get_unverified_header
from jwt.algorithms import RSAAlgorithm

from langflow.base.auth.model import AuthComponent
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


class JWTValidatorComponent(AuthComponent):
   """Component for validating JWT tokens and extracting user IDs."""

   display_name = "JWT Validator"
   description = "Validates JWT tokens and extracts user ID using JWKs"
   documentation = "https://docs.langflow.org/components-auth"
   icon = "key"

   inputs = [
       MessageTextInput(
           name="jwt_token",
           display_name="JWT Token",
           required=True,
           placeholder="Enter JWT token",
           info="JWT token to validate"
       ),
   ]

   outputs = [
       Output(display_name="User ID", name="output", method="process_token"),
   ]

   def build_config(self) -> dict:
       return {
           "jwks_url": {
               "display_name": "JWKS URL",
               "description": "URL to fetch the JSON Web Key Sets",
               "type": "str",
               "required": True,
           }
       }

   def build(self, jwks_url: str) -> None:
       self.jwks_url = jwks_url
       self.jwks = self._fetch_jwks()

   def _fetch_jwks(self) -> dict:
       """Fetch JWKs from the configured URL."""
       try:
           response = requests.get(self.jwks_url, timeout=10)  # Added timeout
           response.raise_for_status()
           return response.json()
       except requests.RequestException as e:
           error_msg = f"Failed to fetch JWKS: {e!s}"
           raise ValueError(error_msg) from e  # Added from e

   def _get_key(self, kid: str) -> str | None:
       """Get the public key for a given key ID."""
       for key in self.jwks.get("keys", []):
           if key.get("kid") == kid:
               try:
                   return RSAAlgorithm.from_jwk(key)
               except (ValueError, TypeError) as e:  # Specific exceptions
                   error_msg = f"Invalid key format in JWKS: {e!s}"
                   raise ValueError(error_msg) from e
       return None

   def process_token(self) -> Message:
       """Validate the JWT and extract the user ID.

       Returns:
           Message: A Message object containing the user ID
       """
       try:
           # Get jwt_token from component input
           jwt_token = self.jwt_token if hasattr(self, "jwt_token") else None

           if not jwt_token:
               return Message(text="Error: Token is empty")

           try:
               header = get_unverified_header(jwt_token)
           except DecodeError as e:  # Specific exception
               return Message(text=f"Error: Malformed token header - {e!s}")

           kid = header.get("kid")
           if not kid:
               return Message(text="Error: Missing key ID (kid) in token header")

           public_key = self._get_key(kid)
           if not public_key:
               error_msg = "No matching key found"
               return Message(text=f"Error: {error_msg}")

           try:
               decoded = decode(
                   jwt_token,
                   key=public_key,
                   algorithms=["RS256"]
               )
           except ExpiredSignatureError:
               return Message(text="Error: Token has expired")
           except InvalidSignatureError:
               return Message(text="Error: Invalid token signature")
           except DecodeError:
               return Message(text="Error: Malformed token payload")
           except ValueError as e:
               error_msg = f"Token validation failed: {e!s}"
               return Message(text=f"Error: {error_msg}")

           user_id = decoded.get("sub")
           if not user_id:
               error_msg = "No user ID (sub) claim in token"
               return Message(text=f"Error: {error_msg}")

           self.status = user_id
           return Message(text=user_id)

       except ValueError as e:
           return Message(text=f"Error: {e!s}")
