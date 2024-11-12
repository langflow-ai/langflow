from typing import Any

import pytest
from typing_extensions import TypedDict

from tests.constants import SUPPORTED_VERSIONS
from tests.integration.utils import build_component_instance_for_tests


class VersionComponentMapping(TypedDict):
    version: str
    module: str
    file_name: str


# Sentinel value to mark undefined test cases
DID_NOT_EXIST = object()


class ComponentTestBase:
    component_class = None
    DEFAULT_KWARGS: dict[str, Any] = {}
    FILE_NAMES_MAPPING: list[VersionComponentMapping] = []

    def test_all_versions_have_a_file_name_defined(self):
        if not self.FILE_NAMES_MAPPING:
            msg = (
                f"FILE_NAMES_MAPPING is empty for {self.__class__.__name__}. "
                "Please define the version mappings for your component."
            )
            raise AssertionError(msg)

        version_mappings = {mapping["version"]: mapping for mapping in self.FILE_NAMES_MAPPING}

        for version in SUPPORTED_VERSIONS:
            if version not in version_mappings:
                supported_versions = ", ".join(sorted(m["version"] for m in self.FILE_NAMES_MAPPING))
                msg = (
                    f"Version {version} not found in FILE_NAMES_MAPPING for {self.__class__.__name__}.\n"
                    f"Currently defined versions: {supported_versions}\n"
                    "Please add this version to your component's FILE_NAMES_MAPPING."
                )
                raise AssertionError(msg)

            mapping = version_mappings[version]
            if mapping["file_name"] is None:
                msg = (
                    f"file_name is None for version {version} in {self.__class__.__name__}.\n"
                    "Please provide a valid file_name in FILE_NAMES_MAPPING or set it to DID_NOT_EXIST."
                )
                raise AssertionError(msg)

            if mapping["module"] is None:
                msg = (
                    f"module is None for version {version} in {self.__class__.__name__}.\n"
                    "Please provide a valid module name in FILE_NAMES_MAPPING or set it to DID_NOT_EXIST."
                )
                raise AssertionError(msg)

    def test_component_versions(self):
        """Test if the component works across different versions."""
        if self.component_class is None:
            msg = (
                f"component_class is not defined for {self.__class__.__name__}.\n"
                "Please set the component_class attribute in your test class."
            )
            raise AssertionError(msg)

        version_mappings = {mapping["version"]: mapping for mapping in self.FILE_NAMES_MAPPING}

        for version in SUPPORTED_VERSIONS:
            mapping = version_mappings[version]
            if mapping["file_name"] is DID_NOT_EXIST:
                continue

            try:
                instance = build_component_instance_for_tests(
                    version, file_name=mapping["file_name"], module=mapping["module"], **self.DEFAULT_KWARGS
                )
            except Exception as e:
                msg = (
                    f"Failed to build component instance for {self.__class__.__name__} "
                    f"version {version}:\n"
                    f"Module: {mapping['module']}\n"
                    f"File: {mapping['file_name']}\n"
                    f"Error: {e!s}"
                )
                raise AssertionError(msg) from e

            try:
                result = instance()
            except Exception as e:
                msg = (
                    f"Failed to execute component {self.__class__.__name__} "
                    f"for version {version}:\n"
                    f"Module: {mapping['module']}\n"
                    f"File: {mapping['file_name']}\n"
                    f"Error: {e!s}"
                )
                raise AssertionError(msg) from e

            if result is None:
                msg = (
                    f"Component {self.__class__.__name__} returned None "
                    f"for version {version}.\n"
                    f"Module: {mapping['module']}\n"
                    f"File: {mapping['file_name']}"
                )
                raise AssertionError(msg)


@pytest.mark.usefixtures("client")
class ComponentTestBaseWithClient(ComponentTestBase):
    pass


class ComponentTestBaseWithoutClient(ComponentTestBase):
    pass
