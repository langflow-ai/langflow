"""Base component for Agentics components."""

from __future__ import annotations

from typing import ClassVar

from lfx.base.models.unified_models import handle_model_input_update
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
        return handle_model_input_update(self, build_config, field_value, field_name)
