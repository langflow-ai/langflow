import asyncio
import inspect
import ipaddress
import socket
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from lfx.custom.custom_component.component import Component
from lfx.schema.dotdict import dotdict
from typing_extensions import TypedDict

from tests.constants import SUPPORTED_VERSIONS
from tests.integration.utils import build_component_instance_for_tests


class VersionComponentMapping(TypedDict):
    version: str
    module: str
    file_name: str


# Sentinel value to mark undefined test cases
DID_NOT_EXIST = object()


def _is_local_address(address: Any) -> bool:
    """Whether a socket address is a Unix socket path or a loopback host."""
    if isinstance(address, str | bytes):
        return True
    try:
        host = str(address[0])
        if host == "localhost":
            return True
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except (ValueError, TypeError, IndexError, KeyError):
        # An address shape this helper does not know; treat it as outbound.
        return False


@contextmanager
def _refuse_outbound_connections(current_output: Callable[[], str]) -> Iterator[list[str]]:
    """Refuse every non-loopback socket connect in the block and record who tried.

    Components often catch the connection error and return a fallback value, so the
    record, not the exception, is what shows that an output needed the network.
    """
    attempts: list[str] = []
    connect = socket.socket.connect

    def guarded_connect(sock: socket.socket, address: Any) -> None:
        if not _is_local_address(address):
            attempts.append(f"{current_output()} -> {address!r}")
            msg = f"test_latest_version runs offline and refused a connection to {address!r}"
            raise ConnectionRefusedError(msg)
        connect(sock, address)

    with patch.object(socket.socket, "connect", guarded_connect):
        yield attempts


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

    @pytest.fixture
    def skipped_outputs(self) -> dict[str, str]:
        """Outputs test_latest_version leaves unrun, each mapped to the reason.

        Only for an output the harness cannot run offline with default_kwargs: it calls a live
        service, needs real credentials, or needs state the unit suite does not set up. Every
        other output still has to run and return a value, so prefer mocks or default_kwargs.
        """
        return {}

    async def component_setup(self, component_class: type[Any], default_kwargs: dict[str, Any]) -> Component:
        mock_vertex = Mock()
        mock_vertex.id = str(uuid4())
        # An unconnected vertex. With no outgoing edges Component._should_process_output selects
        # every output, as it does for a vertex with nothing downstream in a real graph. Left as
        # bare Mocks, these edge lists are truthy and cannot be indexed or searched.
        mock_vertex.incoming_edges = []
        mock_vertex.outgoing_edges = []
        mock_vertex.edges_source_names = set()
        mock_vertex._accumulate_upstream_token_usage = Mock(return_value=None)
        mock_vertex.graph = Mock()
        mock_vertex.graph.id = str(uuid4())
        mock_vertex.graph.session_id = str(uuid4())
        mock_vertex.graph.flow_id = str(uuid4())
        mock_vertex.graph.run_id = str(uuid4())
        mock_vertex.graph.context = dotdict()
        mock_vertex.graph.vertices = []
        mock_vertex.is_output = Mock(return_value=False)
        source_code = await asyncio.to_thread(inspect.getsource, component_class)
        component_instance = component_class(_code=source_code, **default_kwargs)
        component_instance._vertex = mock_vertex
        # Mock the log method to avoid tracing service context issues
        component_instance.log = Mock()
        return component_instance

    @staticmethod
    async def map_frontend_outputs(component: Component, field_name: str, field_value: Any) -> None:
        """Give a component with dynamic outputs the ones its saved node would carry.

        The frontend builds them with update_outputs when field_name changes, and the engine
        maps a saved node's outputs onto its component from the vertex. This does both.
        """
        node = await component.run_and_validate_update_outputs({"outputs": []}, field_name, field_value)
        component._vertex.outputs = node["outputs"]
        component.map_outputs()

    async def test_latest_version(
        self,
        component_class: type[Any],
        default_kwargs: dict[str, Any],
        skipped_outputs: dict[str, str],
    ) -> None:
        """Run every output of the latest version offline and check that each returned a value."""
        name = component_class.__name__
        component_instance = await self.component_setup(component_class, default_kwargs)
        if skipped_outputs:
            # Leave the skipped outputs unconnected, as if nothing downstream used them.
            component_instance._should_process_output = lambda output: output.name not in skipped_outputs

        offline_hint = "Mock the call, or list the output in skipped_outputs with the reason."
        with _refuse_outbound_connections(lambda: getattr(component_instance, "_current_output", "?")) as attempts:
            try:
                results, _artifacts = await component_instance.run()
            except Exception as exc:
                if attempts:
                    msg = f"{name} outputs tried to reach the network: {attempts}. {offline_hint}"
                    raise AssertionError(msg) from exc
                raise
        assert not attempts, f"{name} outputs tried to reach the network: {attempts}. {offline_hint}"

        outputs = set(component_instance.list_outputs())
        unknown = sorted(skipped_outputs.keys() - outputs)
        assert not unknown, f"skipped_outputs names outputs {name} does not have: {unknown}"
        if not results and skipped_outputs:
            pytest.skip(f"Every output of {name} is in skipped_outputs: {skipped_outputs}")
        assert results, f"{name} has no outputs to run; set default_kwargs so that it exposes some"
        not_run = sorted(outputs - skipped_outputs.keys() - results.keys())
        assert not not_run, f"{name}.run() never ran these outputs: {not_run}"
        returned_none = sorted(output for output, value in results.items() if value is None)
        assert not returned_none, f"{name} outputs returned None: {returned_none}"

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
