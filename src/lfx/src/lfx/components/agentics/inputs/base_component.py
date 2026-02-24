"""Base component for Agentics components."""

from __future__ import annotations

from typing import ClassVar

from lfx.base.models.unified_models import (
    get_language_model_options,
    update_model_options_in_build_config,
)
from lfx.components.agentics.helpers import update_provider_fields_visibility
from lfx.custom.custom_component.component import Component


class BaseAgenticComponent(Component):
    """Base class for Agentics components with shared configuration and model management.

    Provides common functionality for:
    - Dynamic model option updates based on user selection
    - Provider-specific field visibility management
    - Unified build configuration handling
    """

    display_name = False  # Hide from sidebar - not meant to be used directly
    code_class_base_inheritance: ClassVar[str | None] = None
    _code_class_base_inheritance: ClassVar[str | None] = None

    def update_build_config(
        self,
        build_config: dict,
        field_value: str,
        field_name: str | None = None,
    ) -> dict:
        """Dynamically update build configuration with user-filtered model options.

        Args:
            build_config: The current build configuration dictionary.
            field_value: The value of the field being updated.
            field_name: The name of the field being updated.

        Returns:
            Updated build configuration with filtered model options and adjusted field visibility.
        """
        build_config = update_model_options_in_build_config(
            component=self,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=get_language_model_options,
            field_name=field_name,
            field_value=field_value,
        )
        return update_provider_fields_visibility(build_config, field_value, field_name)
