"""Composed ``Settings`` class for Langflow.

Fields live in per-group mixins under :mod:`lfx.services.settings.groups`.
This module wires them together, configures env-var loading, and exposes the
YAML helpers and a few model-level utilities (``update_settings``,
``voice_mode_available``).

Group order in the inheritance list matters: Pydantic collects fields from the
rightmost base first, so cross-group validators see their dependencies in
``info.data``. Specifically:

- :class:`PathSettings` is rightmost so ``config_dir`` is validated before
  ``database_url``.
- :class:`ServerSettings` precedes :class:`RuntimeSettings` so ``workers`` is
  validated before ``event_delivery``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles
import orjson
import yaml
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict
from typing_extensions import override

from lfx.constants import BASE_COMPONENTS_PATH as BASE_COMPONENTS_PATH  # noqa: PLC0414  # re-export for back-compat
from lfx.services.settings.groups import (
    CacheSettings,
    ComponentsSettings,
    DatabaseSettings,
    McpSettings,
    ObservabilitySettings,
    PathSettings,
    RuntimeSettings,
    SecuritySettings,
    ServerSettings,
    StorageSettings,
    TelemetrySettings,
    UiSettings,
    VariablesSettings,
)

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def is_list_of_any(field: FieldInfo) -> bool:
    """Check if the given field is a list or an optional list of any type.

    Args:
        field (FieldInfo): The field to be checked.

    Returns:
        bool: True if the field is a list or a list of any type, False otherwise.
    """
    if field.annotation is None:
        return False
    try:
        union_args = field.annotation.__args__ if hasattr(field.annotation, "__args__") else []

        return field.annotation.__origin__ is list or any(
            arg.__origin__ is list for arg in union_args if hasattr(arg, "__origin__")
        )
    except AttributeError:
        return False


class CustomSource(EnvSettingsSource):
    @override
    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:  # type: ignore[misc]
        # allow comma-separated list parsing

        # fieldInfo contains the annotation of the field
        if is_list_of_any(field):
            if isinstance(value, str):
                value = value.split(",")
            if isinstance(value, list):
                return value

        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(
    VariablesSettings,
    UiSettings,
    ComponentsSettings,
    SecuritySettings,
    ObservabilitySettings,
    TelemetrySettings,
    StorageSettings,
    CacheSettings,
    McpSettings,
    DatabaseSettings,
    RuntimeSettings,
    ServerSettings,
    PathSettings,
    BaseSettings,
):
    """Top-level Langflow settings.

    Composed from per-group mixins. See module docstring for the inheritance
    order rationale.
    """

    model_config = SettingsConfigDict(validate_assignment=True, extra="ignore", env_prefix="LANGFLOW_")

    async def update_from_yaml(self, file_path: str, *, dev: bool = False) -> None:
        new_settings = await load_settings_from_yaml(file_path)
        self.components_path = new_settings.components_path or []
        self.dev = dev

    def update_settings(self, **kwargs) -> None:
        for key, value in kwargs.items():
            # value may contain sensitive information, so we don't want to log it
            if not hasattr(self, key):
                continue
            if isinstance(getattr(self, key), list):
                # value might be a '[something]' string
                value_ = value
                with contextlib.suppress(json.decoder.JSONDecodeError):
                    value_ = orjson.loads(str(value))
                if isinstance(value_, list):
                    for item in value_:
                        item_ = str(item) if isinstance(item, Path) else item
                        if item_ not in getattr(self, key):
                            getattr(self, key).append(item_)
                else:
                    value_ = str(value_) if isinstance(value_, Path) else value_
                    if value_ not in getattr(self, key):
                        getattr(self, key).append(value_)
            else:
                setattr(self, key, value)

    @property
    def voice_mode_available(self) -> bool:
        """Check if voice mode is available by testing webrtcvad import."""
        try:
            import webrtcvad  # noqa: F401
        except ImportError:
            return False
        else:
            return True

    @classmethod
    @override
    def settings_customise_sources(  # type: ignore[misc]
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (CustomSource(settings_cls),)


def save_settings_to_yaml(settings: Settings, file_path: str) -> None:
    with Path(file_path).open("w", encoding="utf-8") as f:
        settings_dict = settings.model_dump()
        yaml.dump(settings_dict, f)


async def load_settings_from_yaml(file_path: str) -> Settings:
    from lfx.log.logger import logger

    # Check if a string is a valid path or a file name
    if "/" not in file_path:
        # Get current path
        current_path = Path(__file__).resolve().parent
        file_path_ = Path(current_path) / file_path
    else:
        file_path_ = Path(file_path)

    async with aiofiles.open(file_path_.name, encoding="utf-8") as f:
        content = await f.read()
        settings_dict = yaml.safe_load(content)
        settings_dict = {k.upper(): v for k, v in settings_dict.items()}

        for key in settings_dict:
            if key not in Settings.model_fields:
                msg = f"Key {key} not found in settings"
                raise KeyError(msg)
            await logger.adebug(f"Loading {len(settings_dict[key])} {key} from {file_path}")

    return await asyncio.to_thread(Settings, **settings_dict)
