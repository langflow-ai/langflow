import os
from pathlib import Path

from pydantic import BaseModel, field_validator

from lfx.constants import BASE_COMPONENTS_PATH
from lfx.log.logger import logger


class ComponentsSettings(BaseModel):
    """Component discovery, indexing, and startup-load behavior."""

    components_path: list[str] = []
    """List of paths to custom components.

    Security: This setting defines an allow-list of custom components
    permitted to execute, even when LANGFLOW_ALLOW_CUSTOM_COMPONENTS is False.
    """
    components_index_path: str | None = None
    """Path or URL to a prebuilt component index JSON file.

    If None, uses the built-in index at lfx/_assets/component_index.json.
    Set to a file path (e.g., '/path/to/index.json') or URL (e.g., 'https://example.com/index.json')
    to use a custom index.
    """

    load_flows_path: str | None = None
    bundle_urls: list[str] = []

    lazy_load_components: bool = False
    """If set to True, Langflow will only partially load components at startup and fully load them on demand.
    This significantly reduces startup time but may cause a slight delay when a component is first used."""

    # Starter Projects
    create_starter_projects: bool = True
    """If set to True, Langflow will create starter projects. If False, skips all starter project setup.
    Note that this doesn't check if the starter projects are already loaded in the db;
    this is intended to be used to skip all startup project logic."""
    update_starter_projects: bool = True
    """If set to True, Langflow will update starter projects."""

    @field_validator("components_path", mode="before")
    @classmethod
    def set_components_path(cls, value):
        """Processes and updates the components path list, incorporating environment variable overrides.

        If the `LANGFLOW_COMPONENTS_PATH` environment variable is set and points to an existing path, it is
        appended to the provided list if not already present. If the input list is empty or missing, it is
        set to an empty list.
        """
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
        elif isinstance(value, Path):
            value = [str(value)]
        elif isinstance(value, list):
            value = [str(p) if isinstance(p, Path) else p for p in value]
        return value
