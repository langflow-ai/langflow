from typing import Annotated, Literal

from pydantic import AfterValidator, TypeAdapter

ProjectAuthType = Literal["none", "apikey", "oauth"]
_AUTH_TYPE = TypeAdapter(ProjectAuthType)


def _validate_project_auth_settings(settings: dict) -> dict:
    _AUTH_TYPE.validate_python(settings.get("auth_type"))
    return settings


# Project requests preserve all provider-specific fields when storing the settings.
ProjectAuthSettings = Annotated[dict, AfterValidator(_validate_project_auth_settings)]


def stored_project_auth_type(settings: dict | None) -> str | None:
    """Keep deployment defaults for unset settings and protect incomplete legacy records."""
    if settings is None:
        return None
    mode = settings.get("auth_type", "apikey")
    return mode if isinstance(mode, str) else "invalid"
