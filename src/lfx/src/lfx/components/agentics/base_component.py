"""Base component for Agentics components."""

from __future__ import annotations

from lfx.base.models.unified_models import (
    get_language_model_options,
    update_model_options_in_build_config,
)
from lfx.components.agentics.helpers import update_provider_fields_visibility
from lfx.custom.custom_component.component import Component


class BaseAgenticComponent(Component):
    """Base class for Agentics components with common configuration logic."""

    def update_build_config(
        self,
        build_config: dict,
        field_value: str,
        field_name: str | None = None,
    ) -> dict:
        """Dynamically update build config with user-filtered model options."""
        build_config = update_model_options_in_build_config(
            component=self,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=get_language_model_options,
            field_name=field_name,
            field_value=field_value,
        )
        return update_provider_fields_visibility(build_config, field_value, field_name)
