from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class KeycloakSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KEYCLOAK_", env_file=".env", extra="ignore")

    ENABLED: bool = False

    # Keycloak connection (backend → Keycloak, e.g. token exchange, JWKS)
    SERVER_URL: str = ""
    REALM: str = ""
    CLIENT_ID: str = ""
    CLIENT_SECRET: str = ""

    # Browser-facing Keycloak URL for the authorization redirect.
    # Set this when SERVER_URL is an internal Docker/k8s hostname that the
    # browser cannot reach (e.g. SERVER_URL=http://keycloak:8080 but browser
    # must use http://keycloak.company.com).
    # Falls back to SERVER_URL when not set.
    EXTERNAL_SERVER_URL: str = ""

    # Redirect URI that Keycloak calls back (must be registered in Keycloak client)
    REDIRECT_URI: str = ""

    # The single shared Langflow username everyone on this instance logs into.
    # Authorization (who is allowed) is enforced by Keycloak; anyone who
    # successfully passes Keycloak lands on this account.
    SHARED_USERNAME: str = "langflow-shared"

    # Text shown on the login button
    BUTTON_TEXT: str = "Login with Keycloak"

    # Secret for signing the OAuth2 state parameter JWT.
    # Falls back to LANGFLOW_SECRET_KEY at runtime if not set.
    STATE_SECRET: str = Field(default="")

    # Removed: GROUPS_CLAIM — group-based mapping is no longer used.
    # Authorization is fully delegated to Keycloak (client-level access control).

    @property
    def token_endpoint(self) -> str:
        return f"{self.SERVER_URL}/realms/{self.REALM}/protocol/openid-connect/token"

    @property
    def authorization_endpoint(self) -> str:
        base = self.EXTERNAL_SERVER_URL or self.SERVER_URL
        return f"{base}/realms/{self.REALM}/protocol/openid-connect/auth"

    @property
    def jwks_uri(self) -> str:
        return f"{self.SERVER_URL}/realms/{self.REALM}/protocol/openid-connect/certs"

    @property
    def userinfo_endpoint(self) -> str:
        return f"{self.SERVER_URL}/realms/{self.REALM}/protocol/openid-connect/userinfo"


@lru_cache(maxsize=1)
def get_keycloak_settings() -> KeycloakSettings:
    return KeycloakSettings()
