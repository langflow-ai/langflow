from typing import Optional
import secrets

from pydantic import BaseSettings
from passlib.context import CryptContext


class AuthSettings(BaseSettings):
    # Login settings
    SECRET_KEY: str = secrets.token_hex(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 70

    # API Key to execute /process endpoint
    API_KEY_SECRET_KEY: Optional[
        str
    ] = "b82818e0ad4ff76615c5721ee21004b07d84cd9b87ba4d9cb42374da134b841a"
    API_KEY_ALGORITHM: str = "HS256"
    API_V1_STR: str = "/api/v1"

    # If AUTO_LOGIN = True
    # > The application does not request login and logs in automatically as a super user.
    AUTO_LOGIN: bool = True
    FIRST_SUPERUSER: str = "langflow"
    FIRST_SUPERUSER_PASSWORD: str = "langflow"

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    class Config:
        validate_assignment = True
        extra = "ignore"
        env_prefix = "LANGFLOW_"
