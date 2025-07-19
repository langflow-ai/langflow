import asyncio
import inspect
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest
from langflow.custom.custom_component.component import Component
from typing_extensions import TypedDict

from lfx.graph.graph.base import Graph
from lfx.graph.vertex.base import Vertex
from tests.constants import SUPPORTED_VERSIONS
from tests.integration.utils import build_component_instance_for_tests


class VersionComponentMapping(TypedDict):
    version: str
    module: str
    file_name: str


# Sentinel value to mark undefined test cases
DID_NOT_EXIST = object()


class ComponentTestBase:
    @pytest.fixture(autouse=True)
    def _validate_required_fixtures(
        self,
        component_class: type[Any],
        default_kwargs: dict[str, Any],
        file_names_mapping: list[VersionComponentMapping],
    ) -> None:
        """Validate that all required fixtures are implemented."""
        # If we get here, all fixtures exist

    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        msg = f"{self.__class__.__name__} must implement the component_class fixture"
        raise NotImplementedError(msg)

    @pytest.fixture
    def default_kwargs(self) -> dict[str, Any]:
        """Return the default kwargs for the component."""
        return {}

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        msg = f"{self.__class__.__name__} must implement the file_names_mapping fixture"
        raise NotImplementedError(msg)

    async def component_setup(self, component_class: type[Any], default_kwargs: dict[str, Any]) -> Component:
        mock_vertex = Mock(spec=Vertex)
        mock_vertex.graph = Mock(spec=Graph)
        mock_vertex.graph.session_id = str(uuid4())
        mock_vertex.graph.flow_id = str(uuid4())
        source_code = await asyncio.to_thread(inspect.getsource, component_class)
        component_instance = component_class(_code=source_code, **default_kwargs)
        component_instance._should_process_output = Mock(return_value=False)
        component_instance._vertex = mock_vertex
        return component_instance

    async def test_latest_version(self, component_class: type[Any], default_kwargs: dict[str, Any]) -> None:
        """Test that the component works with the latest version."""
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."

    def test_all_versions_have_a_file_name_defined(self, file_names_mapping: list[VersionComponentMapping]) -> None:
        """Ensure all supported versions have a file name defined."""
        if not file_names_mapping:
            msg = f"file_names_mapping is empty for {self.__class__.__name__}. Skipping versions test."
            pytest.skip(msg)

        version_mappings = {mapping["version"]: mapping for mapping in file_names_mapping}

        for version in SUPPORTED_VERSIONS:
            if version not in version_mappings:
                supported_versions = ", ".join(sorted(m["version"] for m in file_names_mapping))
                msg = (
                    f"Version {version} not found in file_names_mapping for {self.__class__.__name__}.\n"
                    f"Currently defined versions: {supported_versions}\n"
                    "Please add this version to your component's file_names_mapping."
                )
                raise AssertionError(msg)

            mapping = version_mappings[version]
            if mapping["file_name"] is None:
                msg = (
                    f"file_name is None for version {version} in {self.__class__.__name__}.\n"
                    "Please provide a valid file_name in file_names_mapping or set it to DID_NOT_EXIST."
                )
                raise AssertionError(msg)

            if mapping["module"] is None:
                msg = (
                    f"module is None for version {version} in {self.__class__.__name__}.\n"
                    "Please provide a valid module name in file_names_mapping or set it to DID_NOT_EXIST."
                )
                raise AssertionError(msg)

    @pytest.mark.parametrize("version", SUPPORTED_VERSIONS)
    def test_component_versions(
        self,
        version: str,
        default_kwargs: dict[str, Any],
        file_names_mapping: list[VersionComponentMapping],
    ) -> None:
        """Test if the component works across different versions."""
        if not file_names_mapping:
            pytest.skip("No file names mapping defined for this component.")
        version_mappings = {mapping["version"]: mapping for mapping in file_names_mapping}

        mapping = version_mappings[version]
        if mapping["file_name"] is DID_NOT_EXIST:
            pytest.skip(f"Skipping version {version} as it does not have a file name defined.")

        try:
            instance, component_code = build_component_instance_for_tests(
                version, file_name=mapping["file_name"], module=mapping["module"], **default_kwargs
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
                f"Error: {e!s}\n"
                f"Component Code: {component_code}"
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
