from typing import Dict, Optional
from jwt import decode, get_unverified_header, ExpiredSignatureError, InvalidSignatureError, DecodeError
from jwt.algorithms import RSAAlgorithm
import requests
from langflow.base.auth.model import AuthComponent
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message

class JWTValidatorComponent(AuthComponent):
    display_name = "JWT Validator"
    description = "Validates JWT tokens and extracts user ID using JWKs"
    documentation: str = "https://python-jose.readthedocs.io/en/latest/jwt/"
    icon = "jwt"
    name = "JWTValidator"

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

    def build_config(self) -> Dict:
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

    def _fetch_jwks(self) -> Dict:
        """Fetch JWKs from the configured URL."""
        try:
            response = requests.get(self.jwks_url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch JWKS: {str(e)}")

    def _get_key(self, kid: str) -> Optional[str]:
        """Get the public key for a given key ID."""
        for key in self.jwks.get('keys', []):
            if key.get('kid') == kid:
                try:
                    return RSAAlgorithm.from_jwk(key)
                except Exception as e:
                    raise ValueError(f"Invalid key format in JWKS: {str(e)}")
        return None

    def process_token(self) -> Message:
        """
        Validate the JWT and extract the user ID.
        
        Returns:
            Message: A Message object containing the user ID
        """
        try:
            if not self.jwt_token:
                raise ValueError("Token is empty")

            try:
                header = get_unverified_header(self.jwt_token)
            except Exception:
                raise ValueError("Malformed token header")

            kid = header.get('kid')
            if not kid:
                raise ValueError("Missing key ID (kid) in token header")
            
            public_key = self._get_key(kid)
            if not public_key:
                raise ValueError(f"No matching key found for kid: {kid}")
            
            try:
                decoded = decode(
                    self.jwt_token,
                    key=public_key,
                    algorithms=['RS256']
                )
            except ExpiredSignatureError:
                raise ValueError("Token has expired")
            except InvalidSignatureError:
                raise ValueError("Invalid token signature")
            except DecodeError:
                raise ValueError("Malformed token payload")
            except Exception as e:
                raise ValueError(f"Token validation failed: {str(e)}")
            
            user_id = decoded.get('sub')
            if not user_id:
                raise ValueError("No user ID (sub) claim in token")
                
            self.status = user_id
            return Message(text=user_id)
            
        except ValueError as e:
            return Message(text=f"Error: {str(e)}")
        except Exception as e:
            return Message(text=f"Unexpected error: {str(e)}")
