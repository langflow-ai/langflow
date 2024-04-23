import contextlib
import json
import os
from pathlib import Path
from shutil import copy2
from typing import Any, List, Optional, Tuple, Type

import orjson
import yaml
from loguru import logger
from pydantic import field_validator, validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict

from langflow.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT

# BASE_COMPONENTS_PATH = str(Path(__file__).parent / "components")
BASE_COMPONENTS_PATH = str(Path(__file__).parent.parent.parent / "components")


def is_list_of_any(field: FieldInfo) -> bool:
    """
    Check if the given field is a list or an optional list of any type.

    Args:
        field (FieldInfo): The field to be checked.

    Returns:
        bool: True if the field is a list or a list of any type, False otherwise.
    """
    if field.annotation is None:
        return False
    try:
        if hasattr(field.annotation, "__args__"):
            union_args = field.annotation.__args__
        else:
            union_args = []

        return field.annotation.__origin__ == list or any(
            arg.__origin__ == list for arg in union_args if hasattr(arg, "__origin__")
        )
    except AttributeError:
        return False


class MyCustomSource(EnvSettingsSource):
    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        # allow comma-separated list parsing

        # fieldInfo contains the annotation of the field
        if is_list_of_any(field):
            if isinstance(value, str):
                value = value.split(",")
            if isinstance(value, list):
                return value

        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    CHAINS: dict = {}
    AGENTS: dict = {}
    PROMPTS: dict = {}
    LLMS: dict = {}
    TOOLS: dict = {}
    MEMORIES: dict = {}
    EMBEDDINGS: dict = {}
    VECTORSTORES: dict = {}
    DOCUMENTLOADERS: dict = {}
    WRAPPERS: dict = {}
    RETRIEVERS: dict = {}
    TOOLKITS: dict = {}
    TEXTSPLITTERS: dict = {}
    UTILITIES: dict = {}
    OUTPUT_PARSERS: dict = {}
    CUSTOM_COMPONENTS: dict = {}

    # Define the default LANGFLOW_DIR
    CONFIG_DIR: Optional[str] = None

    DEV: bool = False
    DATABASE_URL: Optional[str] = None
    CACHE_TYPE: str = "async"
    REMOVE_API_KEYS: bool = False
    COMPONENTS_PATH: List[str] = []
    LANGCHAIN_CACHE: str = "InMemoryCache"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: Optional[str] = None
    REDIS_CACHE_EXPIRE: int = 3600

    # PLUGIN_DIR: Optional[str] = None

    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_HOST: Optional[str] = None

    STORE: Optional[bool] = True
    STORE_URL: Optional[str] = "https://api.langflow.store"
    DOWNLOAD_WEBHOOK_URL: Optional[str] = (
        "https://api.langflow.store/flows/trigger/ec611a61-8460-4438-b187-a4f65e5559d4"
    )
    LIKE_WEBHOOK_URL: Optional[str] = "https://api.langflow.store/flows/trigger/64275852-ec00-45c1-984e-3bff814732da"

    STORAGE_TYPE: str = "local"

    CELERY_ENABLED: bool = False

    store_environment_variables: bool = True
    """Whether to store environment variables as Global Variables in the database."""
    variables_to_get_from_environment: list[str] = VARIABLES_TO_GET_FROM_ENVIRONMENT
    """List of environment variables to get from the environment and store in the database."""

    @validator("CONFIG_DIR", pre=True, allow_reuse=True)
    def set_langflow_dir(cls, value):
        if not value:
            from platformdirs import user_cache_dir

            # Define the app name and author
            app_name = "langflow"
            app_author = "langflow"

            # Get the cache directory for the application
            cache_dir = user_cache_dir(app_name, app_author)

            # Create a .langflow directory inside the cache directory
            value = Path(cache_dir)
            value.mkdir(parents=True, exist_ok=True)

        if isinstance(value, str):
            value = Path(value)
        if not value.exists():
            value.mkdir(parents=True, exist_ok=True)

        return str(value)

    @validator("DATABASE_URL", pre=True)
    def set_database_url(cls, value, values):
        if not value:
            logger.debug("No database_url provided, trying LANGFLOW_DATABASE_URL env variable")
            if langflow_database_url := os.getenv("LANGFLOW_DATABASE_URL"):
                value = langflow_database_url
                logger.debug("Using LANGFLOW_DATABASE_URL env variable.")
            else:
                logger.debug("No DATABASE_URL env variable, using sqlite database")
                # Originally, we used sqlite:///./langflow.db
                # so we need to migrate to the new format
                # if there is a database in that location
                if not values["CONFIG_DIR"]:
                    raise ValueError("CONFIG_DIR not set, please set it or provide a DATABASE_URL")
                from langflow.version import is_pre_release  # type: ignore

                pre_db_file_name = "langflow-pre.db"
                db_file_name = "langflow.db"
                new_pre_path = f"{values['CONFIG_DIR']}/{pre_db_file_name}"
                new_path = f"{values['CONFIG_DIR']}/{db_file_name}"
                final_path = None
                if is_pre_release:
                    if Path(new_pre_path).exists():
                        final_path = new_pre_path
                    elif Path(new_path).exists():
                        # We need to copy the current db to the new location
                        logger.debug("Copying existing database to new location")
                        copy2(new_path, new_pre_path)
                        logger.debug(f"Copied existing database to {new_pre_path}")
                    elif Path(f"./{db_file_name}").exists():
                        logger.debug("Copying existing database to new location")
                        copy2(f"./{db_file_name}", new_pre_path)
                        logger.debug(f"Copied existing database to {new_pre_path}")
                    else:
                        logger.debug(f"Database already exists at {new_pre_path}, using it")
                        final_path = new_pre_path
                else:
                    if Path(new_path).exists():
                        logger.debug(f"Database already exists at {new_path}, using it")
                        final_path = new_path
                    elif Path("./{db_file_name}").exists():
                        try:
                            logger.debug("Copying existing database to new location")
                            copy2("./{db_file_name}", new_path)
                            logger.debug(f"Copied existing database to {new_path}")
                        except Exception:
                            logger.error("Failed to copy database, using default path")
                            new_path = "./{db_file_name}"
                    else:
                        final_path = new_path

                if final_path is None:
                    if is_pre_release:
                        final_path = new_pre_path
                    else:
                        final_path = new_path

                value = f"sqlite:///{final_path}"

        return value

    @field_validator("COMPONENTS_PATH", mode="before")
    def set_components_path(cls, value):
        if os.getenv("LANGFLOW_COMPONENTS_PATH"):
            logger.debug("Adding LANGFLOW_COMPONENTS_PATH to components_path")
            langflow_component_path = os.getenv("LANGFLOW_COMPONENTS_PATH")
            if Path(langflow_component_path).exists() and langflow_component_path not in value:
                if isinstance(langflow_component_path, list):
                    for path in langflow_component_path:
                        if path not in value:
                            value.append(path)
                    logger.debug(f"Extending {langflow_component_path} to components_path")
                elif langflow_component_path not in value:
                    value.append(langflow_component_path)
                    logger.debug(f"Appending {langflow_component_path} to components_path")

        if not value:
            value = [BASE_COMPONENTS_PATH]
            logger.debug("Setting default components path to components_path")
        elif BASE_COMPONENTS_PATH not in value:
            value.append(BASE_COMPONENTS_PATH)
            logger.debug("Adding default components path to components_path")

        logger.debug(f"Components path: {value}")
        return value

    model_config = SettingsConfigDict(validate_assignment=True, extra="ignore", env_prefix="LANGFLOW_")

    def update_from_yaml(self, file_path: str, dev: bool = False):
        new_settings = load_settings_from_yaml(file_path)
        self.CHAINS = new_settings.CHAINS or {}
        self.AGENTS = new_settings.AGENTS or {}
        self.PROMPTS = new_settings.PROMPTS or {}
        self.LLMS = new_settings.LLMS or {}
        self.TOOLS = new_settings.TOOLS or {}
        self.MEMORIES = new_settings.MEMORIES or {}
        self.WRAPPERS = new_settings.WRAPPERS or {}
        self.TOOLKITS = new_settings.TOOLKITS or {}
        self.TEXTSPLITTERS = new_settings.TEXTSPLITTERS or {}
        self.UTILITIES = new_settings.UTILITIES or {}
        self.EMBEDDINGS = new_settings.EMBEDDINGS or {}
        self.VECTORSTORES = new_settings.VECTORSTORES or {}
        self.DOCUMENTLOADERS = new_settings.DOCUMENTLOADERS or {}
        self.RETRIEVERS = new_settings.RETRIEVERS or {}
        self.OUTPUT_PARSERS = new_settings.OUTPUT_PARSERS or {}
        self.CUSTOM_COMPONENTS = new_settings.CUSTOM_COMPONENTS or {}
        self.COMPONENTS_PATH = new_settings.COMPONENTS_PATH or []
        self.DEV = dev

    def update_settings(self, **kwargs):
        logger.debug("Updating settings")
        for key, value in kwargs.items():
            # value may contain sensitive information, so we don't want to log it
            if not hasattr(self, key):
                logger.debug(f"Key {key} not found in settings")
                continue
            logger.debug(f"Updating {key}")
            if isinstance(getattr(self, key), list):
                # value might be a '[something]' string
                with contextlib.suppress(json.decoder.JSONDecodeError):
                    value = orjson.loads(str(value))
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, Path):
                            item = str(item)
                        if item not in getattr(self, key):
                            getattr(self, key).append(item)
                    logger.debug(f"Extended {key}")
                else:
                    if isinstance(value, Path):
                        value = str(value)
                    if value not in getattr(self, key):
                        getattr(self, key).append(value)
                        logger.debug(f"Appended {key}")

            else:
                setattr(self, key, value)
                logger.debug(f"Updated {key}")
            logger.debug(f"{key}: {getattr(self, key)}")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (MyCustomSource(settings_cls),)


def save_settings_to_yaml(settings: Settings, file_path: str):
    with open(file_path, "w") as f:
        settings_dict = settings.model_dump()
        yaml.dump(settings_dict, f)


def load_settings_from_yaml(file_path: str) -> Settings:
    # Check if a string is a valid path or a file name
    if "/" not in file_path:
        # Get current path
        current_path = os.path.dirname(os.path.abspath(__file__))

        file_path = os.path.join(current_path, file_path)

    with open(file_path, "r") as f:
        settings_dict = yaml.safe_load(f)
        settings_dict = {k.upper(): v for k, v in settings_dict.items()}

        for key in settings_dict:
            if key not in Settings.model_fields.keys():
                raise KeyError(f"Key {key} not found in settings")
            logger.debug(f"Loading {len(settings_dict[key])} {key} from {file_path}")

    return Settings(**settings_dict)
