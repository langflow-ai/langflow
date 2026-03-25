from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class KeycloakSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KEYCLOAK_", env_file=".env", extra="ignore")

    ENABLED: bool = False

    # Keycloak connection
    SERVER_URL: str = ""
    REALM: str = ""
    CLIENT_ID: str = ""
    CLIENT_SECRET: str = ""

    # Redirect URI that Keycloak calls back (must be registered in Keycloak client)
    REDIRECT_URI: str = ""

    # JWT claim that contains the list of groups (e.g. ["groups", "realm_access.roles"])
    GROUPS_CLAIM: str = "groups"

    # Text shown on the login button
    BUTTON_TEXT: str = "Login with Keycloak"

    # Secret for signing the OAuth2 state parameter JWT.
    # Falls back to LANGFLOW_SECRET_KEY at runtime if not set.
    STATE_SECRET: str = Field(default="")

    @property
    def token_endpoint(self) -> str:
        return f"{self.SERVER_URL}/realms/{self.REALM}/protocol/openid-connect/token"

    @property
    def authorization_endpoint(self) -> str:
        return f"{self.SERVER_URL}/realms/{self.REALM}/protocol/openid-connect/auth"

    @property
    def jwks_uri(self) -> str:
        return f"{self.SERVER_URL}/realms/{self.REALM}/protocol/openid-connect/certs"

    @property
    def userinfo_endpoint(self) -> str:
        return f"{self.SERVER_URL}/realms/{self.REALM}/protocol/openid-connect/userinfo"


@lru_cache(maxsize=1)
def get_keycloak_settings() -> KeycloakSettings:
    return KeycloakSettings()
