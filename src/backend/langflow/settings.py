import contextlib
import json
import os
from pathlib import Path
from typing import List, Optional, Dict

import yaml
from pydantic import model_validator, validator
from pydantic_settings import BaseSettings

from langflow.utils.logger import logger

# component config path
COMPONENT_CONFIG_PATH = os.getenv("COMPONENT_CONFIG_PATH", Path(__file__).parent / "component_config.yaml")


class ConfigurableComponent:
    name: str
    module_import: str
    documentation: Optional[str]


class Settings(BaseSettings):
    DEV: bool = False
    CACHE: str = "InMemoryCache"
    COMPONENTS: Dict[str, List[ConfigurableComponent]] = {}

    class Config:
        validate_assignment = True
        extra = "ignore"

    @model_validator(mode="after")
    def validate_lists(cls, values):
        for key, value in values.items():
            if key != "dev" and not value:
                values[key] = []
        return values

    def get_components_with_category(self, category: str) -> List[ConfigurableComponent]:
        return self.COMPONENTS.get(category, [])

    def get_all_components(self) -> Dict[str, ConfigurableComponent]:
        ret_map = {}
        for category, components in self.COMPONENTS.items():
            for component in components:
                ret_map[component.name] = component

        return ret_map

    def get_component_setting(self, component: str) -> Optional[ConfigurableComponent]:
        return self.get_all_components().get(component)


def load_settings_from_yaml(file_path: str) -> Settings:
    # Check if a string is a valid path or a file name
    if "/" not in file_path:
        # Get current path
        current_path = os.path.dirname(os.path.abspath(__file__))

        file_path = os.path.join(current_path, file_path)

    with open(file_path, "r") as f:
        components_dict = yaml.safe_load(f)
        components_dict = {k.upper(): v for k, v in components_dict.items()}

        components = {}

        for category, component_val in components_dict:
            for component, val in component_val.items():
                if category not in settings.COMPONENTS:
                    components[category] = []
                components[category].append(ConfigurableComponent(
                    name=component,
                    module_import_command=val.get("module_import"),
                    documentation=val.get("documentation")
                ))
                logger.debug(f"Loading {category}, {component} from {file_path}")

    return Settings(**components)


settings = load_settings_from_yaml(COMPONENT_CONFIG_PATH)
