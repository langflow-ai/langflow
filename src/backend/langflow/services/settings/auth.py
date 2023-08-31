from pathlib import Path
from typing import Optional
import secrets
from langflow.services.settings.utils import read_secret_from_file, write_secret_to_file

from pydantic import BaseSettings, Field, validator
from passlib.context import CryptContext
from langflow.utils.logger import logger


class AuthSettings(BaseSettings):
    # Login settings
    CONFIG_DIR: str
    SECRET_KEY: str = Field(
        default="",
        description="Secret key for JWT. If not provided, a random one will be generated.",
        env="LANGFLOW_SECRET_KEY",
        allow_mutation=False,
    )
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
    AUTO_LOGIN: bool = False
    FIRST_SUPERUSER: str = "langflow"
    FIRST_SUPERUSER_PASSWORD: str = "langflow"

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    class Config:
        validate_assignment = True
        extra = "ignore"
        env_prefix = "LANGFLOW_"

    @validator("SECRET_KEY", pre=True)
    def get_secret_key(cls, value, values):
        config_dir = values.get("CONFIG_DIR")

        if not config_dir:
            logger.debug("No CONFIG_DIR provided, not saving secret key")
            return value or secrets.token_urlsafe(32)

        secret_key_path = Path(config_dir) / "secret_key"

        if value:
            logger.debug("Secret key provided")
            write_secret_to_file(secret_key_path, value)
        else:
            logger.debug("No secret key provided, generating a random one")

            if secret_key_path.exists():
                value = read_secret_from_file(secret_key_path)
                logger.debug("Loaded secret key")
                if not value:
                    value = secrets.token_urlsafe(32)
                    write_secret_to_file(secret_key_path, value)
                    logger.debug("Saved secret key")
            else:
                value = secrets.token_urlsafe(32)
                write_secret_to_file(secret_key_path, value)
                logger.debug("Saved secret key")

        return value
