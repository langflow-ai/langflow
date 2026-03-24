# Copyright 2025 DataStax Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

"""Test utilities for building tweaks with environment variable support.

This module provides testing-specific utilities for creating tweaks for
Langflow component testing. It handles environment variables, pytest
integration, and common test scenarios.

This is separate from the production stepflow_tweaks.py to keep the
production code lean and focused.
"""

import os
from typing import Any


class TweaksBuilder:
    """Builder utility for creating tweaks with environment variable support.

    This class makes it easy to build tweaks for testing by providing convenient
    methods to add tweaks from environment variables or direct values.

    Examples:
        >>> builder = TweaksBuilder()
        >>> builder.add_env_tweak(
        ...     "LanguageModelComponent-abc123", "api_key", "OPENAI_API_KEY"
        ... )
        >>> builder.add_tweak("LanguageModelComponent-abc123", "temperature", 0.8)
        >>> tweaks = builder.build_or_skip()  # Auto-skips test if env vars missing
    """

    def __init__(self):
        """Initialize empty tweaks builder."""
        self.tweaks: dict[str, dict[str, Any]] = {}
        self.missing_env_vars: list[str] = []

    def add_tweak(
        self, component_id: str, field_name: str, value: Any
    ) -> "TweaksBuilder":
        """Add a direct value tweak for a component field.

        Args:
            component_id: Langflow component ID (e.g., "LanguageModelComponent-abc123")
            field_name: Field name to tweak (e.g., "api_key", "temperature")
            value: Value to set for the field

        Returns:
            Self for method chaining
        """
        if component_id not in self.tweaks:
            self.tweaks[component_id] = {}

        self.tweaks[component_id][field_name] = value
        return self

    def add_env_tweak(
        self, component_id: str, field_name: str, env_var: str
    ) -> "TweaksBuilder":
        """Add a tweak from an environment variable.

        Args:
            component_id: Langflow component ID (e.g., "LanguageModelComponent-abc123")
            field_name: Field name to tweak (e.g., "api_key", "temperature")
            env_var: Environment variable name (e.g., "OPENAI_API_KEY")

        Returns:
            Self for method chaining

        Note:
            If the environment variable is not set, it will be reported later
        """
        env_value = os.environ.get(env_var)
        if env_value is not None:
            self.add_tweak(component_id, field_name, env_value)
        else:
            self.missing_env_vars.append(env_var)

        return self

    def add_astradb_tweaks(
        self,
        component_id: str,
        endpoint_env: str = "ASTRA_DB_API_ENDPOINT",
        **kwargs: Any,
    ) -> "TweaksBuilder":
        """Add common AstraDB component tweaks.

        Args:
            component_id: Langflow component ID
            token_env: Environment variable for application token
            endpoint_env: Environment variable for API endpoint
            **kwargs: Additional direct tweaks (e.g., database_name="test_db")

        Returns:
            Self for method chaining
        """
        self.add_env_tweak(component_id, "api_endpoint", endpoint_env)

        # Add default test values if not overridden
        if "database_name" not in kwargs:
            kwargs["database_name"] = "langflow-test"
        if "collection_name" not in kwargs:
            kwargs["collection_name"] = "test_collection"

        for field_name, value in kwargs.items():
            self.add_tweak(component_id, field_name, value)

        return self

    def build(self) -> dict[str, dict[str, Any]]:
        """Build the final tweaks dictionary.

        Returns:
            Dictionary ready to use with apply_stepflow_tweaks

        Raises:
            ValueError: If any required environment variables are missing
        """
        if self.missing_env_vars:
            missing_vars = ", ".join(self.missing_env_vars)
            raise ValueError(
                f"Missing required environment variables: {missing_vars}. "
                "Please set these variables or use pytest.skip() to skip the test."
            )

        return dict(self.tweaks)

    def build_or_skip(self) -> dict[str, dict[str, Any]]:
        """Build tweaks dictionary or skip test if environment variables are missing.

        This is a convenience method for use in pytest tests that automatically
        calls pytest.skip() if required environment variables are missing.

        Returns:
            Dictionary ready to use with apply_stepflow_tweaks

        Raises:
            pytest.skip: If any required environment variables are missing
        """
        if self.missing_env_vars:
            import pytest

            missing_vars = ", ".join(self.missing_env_vars)
            pytest.skip(f"Missing required environment variables: {missing_vars}")

        return dict(self.tweaks)


# Generic helper functions
def create_openai_test_tweaks(*component_ids: str) -> dict[str, dict[str, Any]]:
    """Create tweaks for multiple OpenAI components.

    Args:
        *component_ids: Langflow component IDs that use OpenAI API key

    Returns:
        Tweaks dictionary for use with stepflow workflows
    """
    builder = TweaksBuilder()
    for component_id in component_ids:
        builder.add_openai_tweaks(component_id)
    return builder.build_or_skip()


def create_astradb_test_tweaks(
    *component_ids: str, **overrides: Any
) -> dict[str, dict[str, Any]]:
    """Create tweaks for multiple AstraDB components.

    Args:
        *component_ids: Langflow component IDs that use AstraDB
        **overrides: Override default values (e.g., database_name="custom_db")

    Returns:
        Tweaks dictionary for use with stepflow workflows
    """
    builder = TweaksBuilder()
    for component_id in component_ids:
        builder.add_astradb_tweaks(component_id, **overrides)
    return builder.build_or_skip()
