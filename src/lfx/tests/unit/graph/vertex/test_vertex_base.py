"""Test module for the ParameterHandler class.

This module contains tests for verifying the functionality of the ParameterHandler class,
which is responsible for processing and managing parameters in vertices.
"""

import copy
import pickle
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from ag_ui.core import StepFinishedEvent, StepStartedEvent
from lfx.components.input_output import ChatInput
from lfx.graph import Graph
from lfx.graph.edge.base import Edge
from lfx.graph.vertex import base as vertex_base_module
from lfx.graph.vertex import vertex_types as vertex_types_module
from lfx.graph.vertex.base import ParameterHandler, Vertex
from lfx.interface.components import component_cache
from lfx.services.storage.local import LocalStorageService
from lfx.services.storage.service import StorageService
from lfx.utils.file_path_security import LocalFileAccessError
from lfx.utils.util import unescape_string


def test_vertex_getstate_drops_custom_component_runtime_state():
    """Graph cache serialization should rebuild component instances instead of pickling live runtime state."""

    class UnpickleableComponent:
        """Component stand-in that fails if live runtime state is serialized."""

        def __getstate__(self):
            """Raise when pickle tries to serialize the component instance."""
            msg = "cannot pickle component runtime state"
            raise TypeError(msg)

    vertex = object.__new__(Vertex)
    vertex._lock = Mock()
    vertex.custom_component = UnpickleableComponent()
    vertex._upstream_secret_values = {"do-not-persist"}
    vertex.built_object = object()
    vertex.built_result = object()

    state = vertex.__getstate__()

    assert state["custom_component"] is None
    assert state["_upstream_secret_values"] == set()
    pickle.dumps(state)


def test_graph_source_flow_provenance_survives_pickle_and_legacy_state():
    """Cached public graphs retain provenance while older cache entries remain readable."""
    graph = Graph(flow_id="visitor-virtual-flow-id")
    graph.source_flow_id = "public-source-flow-id"

    restored = pickle.loads(pickle.dumps(graph))  # noqa: S301 - round-tripping trusted in-memory test data
    assert restored.source_flow_id == "public-source-flow-id"

    legacy_state = graph.__getstate__()
    legacy_state.pop("source_flow_id")
    legacy_graph = object.__new__(Graph)
    legacy_graph.__setstate__(legacy_state)
    assert legacy_graph.source_flow_id is None


def test_graph_deepcopy_sets_source_flow_provenance_before_rebuild(monkeypatch):
    """Deep-copy reconstruction exposes the trusted source scope before rebuilding FileInputs."""
    graph = Graph(flow_id="visitor-virtual-flow-id")
    graph.source_flow_id = "public-source-flow-id"
    original_add_nodes_and_edges = Graph.add_nodes_and_edges
    rebuild_observed = False

    def checked_add_nodes_and_edges(copied_graph, nodes, edges):
        nonlocal rebuild_observed
        rebuild_observed = True
        assert copied_graph.source_flow_id == "public-source-flow-id"
        return original_add_nodes_and_edges(copied_graph, nodes, edges)

    monkeypatch.setattr(Graph, "add_nodes_and_edges", checked_add_nodes_and_edges)

    cloned = copy.deepcopy(graph)

    assert rebuild_observed is True
    assert cloned.source_flow_id == "public-source-flow-id"


@pytest.fixture
def mock_storage_service() -> Mock:
    """Create a mock storage service for testing."""
    storage = Mock(spec=StorageService)
    storage.build_full_path = Mock(return_value="/mocked/full/path")
    storage.resolve_component_path = Mock(return_value="/mocked/full/path")
    return storage


@pytest.fixture
def mock_vertex() -> Mock:
    """Create a mock vertex for testing."""
    vertex = Mock(spec=Vertex)
    # Create a mock graph
    mock_graph = Mock()
    mock_graph.get_vertex = Mock(return_value="source_vertex")
    mock_graph.user_id = "test-user-id"
    mock_graph.flow_id = "test-flow-id"
    mock_graph.source_flow_id = None

    # Set the graph attribute on the vertex
    vertex.graph = mock_graph

    vertex.data = {
        "node": {
            "template": {
                "test_field": {"type": "str", "value": "test_value", "show": True},
                "file_field": {"type": "file", "value": None, "file_path": "/test/path"},
                "_type": {"type": "str", "value": "test_type"},
            }
        }
    }
    vertex.id = "test-vertex-id"
    vertex.display_name = "Test Vertex"
    # Default: no incoming edges for any field
    vertex.get_incoming_edge_by_target_param = Mock(return_value=None)
    return vertex


@pytest.fixture
def mock_edge() -> Mock:
    """Create a mock edge for testing."""
    edge = Mock(spec=Edge)
    edge.target_param = "test_param"
    edge.target_id = "test-vertex-id"
    edge.source_id = "source-vertex-id"
    return edge


@pytest.fixture
def parameter_handler(mock_vertex, mock_storage_service) -> ParameterHandler:
    """Create a parameter handler instance for testing."""
    return ParameterHandler(mock_vertex, mock_storage_service)


def test_process_edge_parameters(parameter_handler, mock_edge):
    """Test processing edge parameters."""
    # Add test_param to template_dict to simulate a valid edge
    parameter_handler.template_dict["test_param"] = {"list": False, "value": {}}

    # Test
    params = parameter_handler.process_edge_parameters([mock_edge])

    # Verify
    assert isinstance(params, dict)
    assert "test_param" in params
    assert params["test_param"] == "source_vertex"


def test_process_file_field(parameter_handler):
    """Test processing file fields."""
    # Test with file path
    params = parameter_handler.process_file_field(
        "file_field",
        {"type": "file", "file_path": "/test/path/file.txt"},
        {},
    )
    assert params["file_field"] == "/mocked/full/path"

    # Test with required field but no file path
    params = parameter_handler.process_file_field(
        "file_field",
        {"type": "file", "required": True, "display_name": "Test Field"},
        {},
    )
    assert params["file_field"] is None

    # Test with list field
    params = parameter_handler.process_file_field(
        "file_field",
        {"type": "file", "list": True},
        {},
    )
    assert params["file_field"] == []


@pytest.fixture
def restricted_file_access(tmp_path):
    """Enable local-file restriction with a temporary upload storage root."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    settings_service = Mock()
    settings_service.settings.restrict_local_file_access = True
    settings_service.settings.config_dir = config_dir
    settings_service.settings.database_url = ""
    with patch("lfx.utils.file_path_security.get_settings_service", return_value=settings_service):
        yield config_dir


TRUSTED_FILE_COMPONENT_CODE = """
from lfx.io import FileInput

class TrustedFileComponent:
    inputs = [FileInput(name="file_field")]
"""


@pytest.fixture
def trusted_file_component_registry(monkeypatch):
    """Install minimal server-owned metadata for canonical FileInput classification."""
    monkeypatch.setattr(
        component_cache,
        "all_types_dict",
        {
            "trusted_bundle": {
                "TrustedFileComponent": {
                    "template": {
                        "code": {"type": "code", "value": TRUSTED_FILE_COMPONENT_CODE},
                        "file_field": {
                            "_input_type": "FileInput",
                            "type": "file",
                            "list": False,
                            "required": False,
                            "show": True,
                        },
                    }
                }
            }
        },
    )
    monkeypatch.setattr(component_cache, "code_by_hash", None)


def _relabel_file_input_as_string(vertex, *, include_field: bool = True) -> None:
    template = {
        "code": {"type": "code", "value": TRUSTED_FILE_COMPONENT_CODE, "show": True},
        "text_field": {"type": "str", "value": "original", "show": True},
    }
    if include_field:
        template["file_field"] = {
            "type": "str",
            "value": "test-flow-id/../../server-secret.txt",
            "show": True,
        }
    vertex.data["node"]["template"] = template


@pytest.mark.usefixtures("restricted_file_access")
def test_process_file_field_rejects_path_outside_graph_scopes(
    parameter_handler,
    mock_storage_service,
    tmp_path,
):
    """FileInput paths cannot escape user/flow storage before a bundle receives them."""
    outside_path = tmp_path / "server-secret.txt"
    mock_storage_service.resolve_component_path.return_value = str(outside_path)

    with pytest.raises(LocalFileAccessError, match="outside the authenticated user's storage scope"):
        parameter_handler.process_file_field(
            "file_field",
            {"type": "file", "file_path": "test-flow-id/../../server-secret.txt"},
            {},
        )


@pytest.mark.usefixtures("restricted_file_access", "trusted_file_component_registry")
def test_process_field_parameters_rejects_relabelled_canonical_file_input(
    mock_vertex,
    mock_storage_service,
    tmp_path,
):
    """Request metadata cannot disguise a trusted bundle FileInput as a string."""
    _relabel_file_input_as_string(mock_vertex)
    outside_path = tmp_path / "server-secret.txt"
    mock_storage_service.resolve_component_path.return_value = str(outside_path)

    with pytest.raises(LocalFileAccessError, match="outside the authenticated user's storage scope"):
        ParameterHandler(mock_vertex, mock_storage_service).process_field_parameters()


@pytest.mark.usefixtures("restricted_file_access")
def test_process_field_parameters_uses_ast_file_input_fallback_while_registry_is_unavailable(
    monkeypatch,
    mock_vertex,
    mock_storage_service,
    tmp_path,
):
    """Direct trusted FileInput declarations remain protected while metadata warms."""
    monkeypatch.setattr(component_cache, "all_types_dict", None)
    monkeypatch.setattr(component_cache, "code_by_hash", {})
    _relabel_file_input_as_string(mock_vertex)
    outside_path = tmp_path / "server-secret.txt"
    mock_storage_service.resolve_component_path.return_value = str(outside_path)

    with pytest.raises(LocalFileAccessError, match="outside the authenticated user's storage scope"):
        ParameterHandler(mock_vertex, mock_storage_service).process_field_parameters()


@pytest.mark.usefixtures("trusted_file_component_registry")
def test_process_field_parameters_uses_canonical_file_list_semantics(
    mock_vertex,
    mock_storage_service,
    restricted_file_access,
    tmp_path,
):
    """Request list metadata cannot prevent containment from checking every canonical FileInput item."""
    component_cache.all_types_dict["trusted_bundle"]["TrustedFileComponent"]["template"]["file_field"]["list"] = True
    _relabel_file_input_as_string(mock_vertex)
    mock_vertex.data["node"]["template"]["file_field"]["value"] = ["test-flow-id/safe.txt", "/etc/passwd"]
    mock_vertex.data["node"]["template"]["file_field"]["list"] = False
    safe_path = restricted_file_access / "test-flow-id" / "safe.txt"
    safe_path.parent.mkdir()
    safe_path.write_text("safe", encoding="utf-8")
    outside_path = tmp_path / "server-secret.txt"
    mock_storage_service.resolve_component_path.side_effect = [str(safe_path), str(outside_path)]

    with pytest.raises(LocalFileAccessError, match="outside the authenticated user's storage scope"):
        ParameterHandler(mock_vertex, mock_storage_service).process_field_parameters()


@pytest.mark.usefixtures("restricted_file_access")
def test_process_file_field_rejects_legacy_absolute_path_fallback(
    parameter_handler,
    mock_storage_service,
    tmp_path,
):
    """The legacy path-parser compatibility fallback cannot bypass containment."""
    outside_path = tmp_path / "server-secret.txt"
    mock_storage_service.resolve_component_path.side_effect = ValueError("too many values to unpack")

    with pytest.raises(LocalFileAccessError, match="outside the authenticated user's storage scope"):
        parameter_handler.process_file_field(
            "file_field",
            {"type": "file", "file_path": str(outside_path)},
            {},
        )


@pytest.mark.parametrize("namespace", ["test-user-id", "test-flow-id"])
def test_process_file_field_allows_uploaded_files_in_graph_scopes(
    parameter_handler,
    mock_storage_service,
    restricted_file_access,
    namespace,
):
    """Regular and temporary uploads remain usable from user and flow namespaces."""
    uploaded_path = restricted_file_access / namespace / "uploaded.txt"
    uploaded_path.parent.mkdir()
    uploaded_path.write_text("uploaded", encoding="utf-8")
    mock_storage_service.resolve_component_path.return_value = str(uploaded_path)

    params = parameter_handler.process_file_field(
        "file_field",
        {"type": "file", "file_path": f"{namespace}/uploaded.txt", "temp_file": True},
        {},
    )

    assert params["file_field"] == str(uploaded_path.resolve())


def test_process_file_field_checks_every_list_item(
    parameter_handler,
    mock_storage_service,
    restricted_file_access,
    tmp_path,
):
    """List-valued FileInputs reject the whole input when any path escapes."""
    uploaded_path = restricted_file_access / "test-flow-id" / "uploaded.txt"
    uploaded_path.parent.mkdir()
    uploaded_path.write_text("uploaded", encoding="utf-8")
    outside_path = tmp_path / "server-secret.txt"
    mock_storage_service.resolve_component_path.side_effect = [str(uploaded_path), str(outside_path)]

    with pytest.raises(LocalFileAccessError, match="outside the authenticated user's storage scope"):
        parameter_handler.process_file_field(
            "file_field",
            {
                "type": "file",
                "file_path": ["test-flow-id/uploaded.txt", "test-flow-id/../../server-secret.txt"],
                "list": True,
            },
            {},
        )


def test_process_file_field_preserves_unrestricted_local_path_compatibility(
    parameter_handler,
    mock_storage_service,
    tmp_path,
):
    """Single-tenant installs retain arbitrary local FileInput support by default."""
    settings_service = Mock()
    settings_service.settings.restrict_local_file_access = False
    outside_path = tmp_path / "local-file.txt"
    mock_storage_service.resolve_component_path.return_value = str(outside_path)

    with patch("lfx.utils.file_path_security.get_settings_service", return_value=settings_service):
        params = parameter_handler.process_file_field(
            "file_field",
            {"type": "file", "file_path": str(outside_path)},
            {},
        )

    assert params["file_field"] == str(outside_path)


@pytest.mark.usefixtures("restricted_file_access")
def test_process_file_field_preserves_s3_references(
    parameter_handler,
    mock_storage_service,
):
    """Non-local storage keys remain logical references for storage-aware consumers."""
    mock_storage_service.settings_service = Mock()
    mock_storage_service.settings_service.settings.storage_type = "s3"
    mock_storage_service.resolve_component_path.return_value = "test-flow-id/uploaded.txt"

    params = parameter_handler.process_file_field(
        "file_field",
        {"type": "file", "file_path": "test-flow-id/uploaded.txt"},
        {},
    )

    assert params["file_field"] == "test-flow-id/uploaded.txt"


@pytest.mark.parametrize(
    "malicious_path",
    [
        "/etc/passwd",
        "test-flow-id/../../etc/passwd",
        "test-flow-id\\..\\..\\windows\\win.ini",
        "test-flow-id/secret\x00.txt",
        "other-flow-id/uploaded.txt",
    ],
)
@pytest.mark.usefixtures("restricted_file_access")
def test_process_file_field_rejects_unsafe_s3_keys_before_bundle_file_open(
    parameter_handler,
    mock_storage_service,
    malicious_path,
):
    """JigsawStack-style Path.open consumers never receive an unsafe S3 logical key."""
    mock_storage_service.settings_service = Mock()
    mock_storage_service.settings_service.settings.storage_type = "s3"
    mock_storage_service.resolve_component_path.side_effect = lambda path: path

    with pytest.raises(LocalFileAccessError, match="must stay within"):
        parameter_handler.process_file_field(
            "file_field",
            {"type": "file", "file_path": malicious_path},
            {},
        )


def test_process_file_field_allows_server_provenanced_public_flow_namespace(
    parameter_handler,
    mock_storage_service,
    restricted_file_access,
):
    """Public flows retain source-flow attachments after switching to a virtual flow ID."""
    source_flow_id = "public-source-flow-id"
    parameter_handler.vertex.graph.flow_id = "visitor-virtual-flow-id"
    parameter_handler.vertex.graph.source_flow_id = source_flow_id
    uploaded_path = restricted_file_access / source_flow_id / "uploaded.txt"
    uploaded_path.parent.mkdir()
    uploaded_path.write_text("uploaded", encoding="utf-8")
    mock_storage_service.resolve_component_path.return_value = str(uploaded_path)

    params = parameter_handler.process_file_field(
        "file_field",
        {"type": "file", "file_path": f"{source_flow_id}/uploaded.txt"},
        {},
    )

    assert params["file_field"] == str(uploaded_path.resolve())


def _runtime_file_vertex(*, source_flow_id: str | None = None) -> Vertex:
    vertex = object.__new__(Vertex)
    vertex.data = {
        "node": {
            "template": {
                "file_field": {"type": "file", "file_path": "test-flow-id/original.txt", "show": True},
                "text_field": {"type": "str", "value": "original", "show": True},
            }
        }
    }
    vertex.graph = Mock(
        user_id="test-user-id",
        flow_id="visitor-virtual-flow-id" if source_flow_id else "test-flow-id",
        source_flow_id=source_flow_id,
    )
    vertex.raw_params = {"file_field": "original-file", "text_field": "original"}
    vertex.params = vertex.raw_params.copy()
    vertex.updated_raw_params = False
    return vertex


@pytest.mark.usefixtures("restricted_file_access")
def test_update_raw_params_rejects_run_flow_file_tweak_escape(mock_storage_service, tmp_path):
    """Run Flow node tweaks cannot bypass FileInput resolution and containment."""
    vertex = _runtime_file_vertex()
    outside_path = tmp_path / "server-secret.txt"
    mock_storage_service.resolve_component_path.return_value = str(outside_path)

    with (
        patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=mock_storage_service),
        pytest.raises(LocalFileAccessError, match="outside the authenticated user's storage scope"),
    ):
        vertex.update_raw_params({"file_field": "test-flow-id/../../server-secret.txt"}, overwrite=True)

    assert vertex.raw_params["file_field"] == "original-file"


@pytest.mark.usefixtures("restricted_file_access", "trusted_file_component_registry")
def test_update_raw_params_rejects_relabelled_canonical_file_input(
    mock_storage_service,
    tmp_path,
):
    """Run Flow tweaks cannot bypass containment by relabeling trusted FileInput metadata."""
    vertex = _runtime_file_vertex()
    _relabel_file_input_as_string(vertex)
    outside_path = tmp_path / "server-secret.txt"
    mock_storage_service.resolve_component_path.return_value = str(outside_path)

    with (
        patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=mock_storage_service),
        pytest.raises(LocalFileAccessError, match="outside the authenticated user's storage scope"),
    ):
        vertex.update_raw_params({"file_field": "/etc/passwd"}, overwrite=True)

    assert vertex.raw_params["file_field"] == "original-file"


@pytest.mark.usefixtures("restricted_file_access", "trusted_file_component_registry")
def test_update_raw_params_rejects_canonical_file_input_omitted_from_request_template(
    mock_storage_service,
    tmp_path,
):
    """Canonical field identity survives removal of its request-side metadata."""
    vertex = _runtime_file_vertex()
    _relabel_file_input_as_string(vertex, include_field=False)
    outside_path = tmp_path / "server-secret.txt"
    mock_storage_service.resolve_component_path.return_value = str(outside_path)

    with (
        patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=mock_storage_service),
        pytest.raises(LocalFileAccessError, match="outside the authenticated user's storage scope"),
    ):
        vertex.update_raw_params({"file_field": "/etc/passwd"}, overwrite=True)

    assert vertex.raw_params["file_field"] == "original-file"


def test_update_raw_params_preserves_unrestricted_absolute_path_with_real_local_storage(tmp_path):
    """Disabling containment retains the legacy pass-through behavior for runtime tweaks."""
    vertex = _runtime_file_vertex()
    settings_service = Mock()
    settings_service.settings.config_dir = tmp_path / "config"
    settings_service.settings.restrict_local_file_access = False
    storage_service = LocalStorageService(Mock(), settings_service)
    absolute_path = str(tmp_path / "example.txt")

    with (
        patch("lfx.utils.file_path_security.get_settings_service", return_value=settings_service),
        patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=storage_service),
    ):
        vertex.update_raw_params({"file_field": absolute_path}, overwrite=True)

    assert vertex.raw_params["file_field"] == absolute_path


@pytest.mark.usefixtures("restricted_file_access")
def test_update_raw_params_rejects_s3_file_tweak_before_jigsawstack_file_open(mock_storage_service):
    """Bundle consumers cannot receive absolute paths from Run Flow S3 tweaks."""
    vertex = _runtime_file_vertex()
    mock_storage_service.settings_service = Mock()
    mock_storage_service.settings_service.settings.storage_type = "s3"
    mock_storage_service.resolve_component_path.side_effect = lambda path: path

    with (
        patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=mock_storage_service),
        pytest.raises(LocalFileAccessError, match="must stay within"),
    ):
        vertex.update_raw_params({"file_field": "/etc/passwd"}, overwrite=True)

    assert vertex.raw_params["file_field"] == "original-file"


def test_update_raw_params_resolves_v2_public_flow_file_input(
    mock_storage_service,
    restricted_file_access,
):
    """V2/public execution inputs resolve against trusted source-flow provenance."""
    source_flow_id = "public-source-flow-id"
    vertex = _runtime_file_vertex(source_flow_id=source_flow_id)
    uploaded_path = restricted_file_access / source_flow_id / "uploaded.txt"
    uploaded_path.parent.mkdir()
    uploaded_path.write_text("uploaded", encoding="utf-8")
    mock_storage_service.resolve_component_path.return_value = str(uploaded_path)

    with patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=mock_storage_service):
        vertex.update_raw_params({"file_field": f"{source_flow_id}/uploaded.txt"}, overwrite=True)

    assert vertex.raw_params["file_field"] == str(uploaded_path.resolve())
    assert vertex.params["file_field"] == str(uploaded_path.resolve())
    assert vertex.updated_raw_params is True


def test_update_raw_params_resolves_wrapped_v2_file_tweak(mock_storage_service, restricted_file_access):
    """Template-shaped V2 FileInput tweaks use the same resolver as scalar tweaks."""
    vertex = _runtime_file_vertex()
    uploaded_path = restricted_file_access / "test-flow-id" / "uploaded.txt"
    uploaded_path.parent.mkdir()
    uploaded_path.write_text("uploaded", encoding="utf-8")
    mock_storage_service.resolve_component_path.return_value = str(uploaded_path)

    with patch("lfx.graph.vertex.param_handler.get_storage_service", return_value=mock_storage_service):
        vertex.update_raw_params({"file_field": {"file_path": "test-flow-id/uploaded.txt"}}, overwrite=True)

    assert vertex.raw_params["file_field"] == str(uploaded_path.resolve())


def test_should_skip_field(parameter_handler):
    """Test field skipping logic."""
    # Test with field in params
    params = {"test_field": "value"}
    assert parameter_handler.should_skip_field("test_field", {}, params) is True

    # Test with _type field
    assert parameter_handler.should_skip_field("_type", {}, {}) is True

    # Test with hidden field
    assert parameter_handler.should_skip_field("hidden_field", {"show": False}, {}) is True

    # Test with visible field
    assert parameter_handler.should_skip_field("visible_field", {"show": True}, {}) is False


def test_process_non_list_edge_param(parameter_handler, mock_edge):
    """Test processing non-list edge parameters."""
    # Test with empty dict value
    field = {"value": {}}
    result = parameter_handler.process_non_list_edge_param(field, mock_edge)
    assert result == "source_vertex"

    # Test with single key dict value
    field = {"value": {"key": "value"}}
    result = parameter_handler.process_non_list_edge_param(field, mock_edge)
    assert isinstance(result, dict)
    assert next(iter(result.values())) == "source_vertex"

    # Test with non-dict value
    field = {"value": "string"}
    result = parameter_handler.process_non_list_edge_param(field, mock_edge)
    assert result == "source_vertex"


def test_handle_optional_field(parameter_handler):
    """Test handling optional fields."""
    # Test with default value
    params = {}
    field = {"required": False, "default": "default_value"}
    parameter_handler.handle_optional_field("test_field", field, params)
    assert params["test_field"] == "default_value"

    # Test without default value
    params = {"test_field": None}
    field = {"required": False}
    parameter_handler.handle_optional_field("test_field", field, params)
    assert "test_field" not in params

    # Test with required field
    params = {"test_field": "value"}
    field = {"required": True}
    parameter_handler.handle_optional_field("test_field", field, params)
    assert params["test_field"] == "value"


def test_process_field_parameters_valid(parameter_handler, mock_vertex):
    """Test processing field parameters with a valid mix of field types."""
    new_template = {
        "str_field": {"type": "str", "value": "test", "show": True},
        "int_field": {"type": "int", "value": "123", "show": True, "load_from_db": True},
        "float_field": {"type": "float", "value": "456.78", "show": True},
        "code_field": {"type": "code", "value": "['a', 'b']", "show": True},
        "dict_field": {"type": "dict", "value": {"key": "value"}, "show": True},
        "bool_field": {"type": "bool", "value": True, "show": True},
        "file_field": {"type": "file", "value": None, "file_path": "/flowid/file.txt", "show": True},
        "hidden_field": {"type": "str", "value": "hidden", "show": False},
        "str_list_field": {"type": "str", "value": ["a", "b"], "show": True},
    }
    # Override the vertex template for this test
    mock_vertex.data["node"]["template"] = new_template
    parameter_handler.template_dict = {key: value for key, value in new_template.items() if isinstance(value, dict)}

    params, load_from_db_fields = parameter_handler.process_field_parameters()

    # Validate string field (unescape_string likely returns the same string)
    assert params["str_field"] == unescape_string("test")
    # Validate int_field becomes integer 123 and appears in load_from_db_fields
    assert params["int_field"] == 123
    assert "int_field" in load_from_db_fields
    # Validate float_field becomes float 456.78
    assert params["float_field"] == 456.78
    # Validate code_field becomes evaluated list ['a', 'b']
    assert params["code_field"] == ["a", "b"]
    # Validate dict_field is as provided
    assert params["dict_field"] == {"key": "value"}
    # Validate bool_field remains True
    assert params["bool_field"] is True
    # Validate file_field uses the storage service (mock returns "/mocked/full/path")
    assert params["file_field"] == "/mocked/full/path"
    # Validate hidden field is skipped
    assert "hidden_field" not in params
    # Validate str_list_field has been processed correctly
    assert params["str_list_field"] == [unescape_string("a"), unescape_string("b")]


def test_process_field_parameters_invalid(parameter_handler, mock_vertex):
    """Test that an invalid field type raises a ValueError."""
    new_template = {"invalid_field": {"type": "unknown", "value": "something", "show": True}}
    mock_vertex.data["node"]["template"] = new_template
    parameter_handler.template_dict = new_template

    with pytest.raises(ValueError, match="is not a valid field type"):
        parameter_handler.process_field_parameters()


def test_process_field_parameters_code_error(parameter_handler, mock_vertex):
    """Test that a faulty code field gracefully returns the original value on evaluation error."""
    new_template = {"faulty_code": {"type": "code", "value": "illegal_code", "show": True}}
    mock_vertex.data["node"]["template"] = new_template
    parameter_handler.template_dict = new_template

    params, _ = parameter_handler.process_field_parameters()
    # Since ast.literal_eval fails, it should log the error and fallback to the original value.
    assert params["faulty_code"] == "illegal_code"


def test_process_field_parameters_dict_field_list(parameter_handler, mock_vertex):
    """Test processing a dict field when the value is a list of dictionaries."""
    new_template = {"list_dict_field": {"type": "dict", "value": [{"a": 1}, {"b": 2}], "show": True}}
    mock_vertex.data["node"]["template"] = new_template
    parameter_handler.template_dict = new_template

    params, _ = parameter_handler.process_field_parameters()
    # The dict field should combine the list of dictionaries into one.
    assert params["list_dict_field"] == {"a": 1, "b": 2}


def test_process_field_parameters_bool_field(parameter_handler, mock_vertex):
    """Test processing for a bool field."""
    new_template = {"bool_field": {"type": "bool", "value": True, "show": True}}
    mock_vertex.data["node"]["template"] = new_template
    parameter_handler.template_dict = new_template

    params, _ = parameter_handler.process_field_parameters()
    assert params["bool_field"] is True


def test_process_field_parameters_table_field(parameter_handler, mock_vertex):
    """Test processing for a valid table field."""
    sample_data = [{"col1": 1, "col2": 2}, {"col1": 3, "col2": 4}]
    new_template = {"table_field": {"type": "table", "value": sample_data, "show": True}}
    mock_vertex.data["node"]["template"] = new_template
    parameter_handler.template_dict = new_template

    params, _ = parameter_handler.process_field_parameters()

    # The function returns the original list, not a DataFrame
    assert params["table_field"] == sample_data


def test_process_field_parameters_table_field_invalid(parameter_handler, mock_vertex):
    """Test that an invalid value for a table field raises a ValueError."""
    new_template = {"table_field": {"type": "table", "value": "not a list", "show": True}}
    mock_vertex.data["node"]["template"] = new_template
    parameter_handler.template_dict = new_template

    with pytest.raises(ValueError, match="Invalid value type"):
        parameter_handler.process_field_parameters()


def test_vertex_before_callback_event():
    """Test that Vertex.before_callback_event generates the correct StepStartedEvent payload."""
    # Create a graph with a ChatInput component, which creates a vertex
    from lfx.graph import Graph

    chat_input = ChatInput(_id="test_vertex_id")
    chat_output = ChatInput(_id="output_id")  # Need two components for Graph
    graph = Graph(chat_input, chat_output, flow_id="test_flow")

    # Get the vertex from the graph
    vertex = graph.vertices[0]  # First vertex should be chat_input
    assert vertex.id == "test_vertex_id"

    # Call before_callback_event
    event = vertex.before_callback_event()

    # Assert the event is a StepStartedEvent
    assert isinstance(event, StepStartedEvent)

    # Assert the event has the correct step_name
    assert event.step_name == vertex.display_name

    # Assert the raw_event contains the langflow metrics
    assert event.raw_event is not None
    assert isinstance(event.raw_event, dict)
    assert "langflow" in event.raw_event

    # Assert the langflow metrics contain expected fields
    langflow_metrics = event.raw_event["langflow"]
    assert isinstance(langflow_metrics, dict)
    assert "timestamp" in langflow_metrics
    assert isinstance(langflow_metrics["timestamp"], float)
    assert "component_id" in langflow_metrics
    assert langflow_metrics["component_id"] == vertex.id
    assert langflow_metrics["component_id"] == "test_vertex_id"


def test_vertex_after_callback_event():
    """Test that Vertex.after_callback_event generates the correct StepFinishedEvent payload."""
    # Create a graph with a ChatInput component, which creates a vertex
    from lfx.graph import Graph

    chat_input = ChatInput(_id="test_vertex_id")
    chat_output = ChatInput(_id="output_id")  # Need two components for Graph
    graph = Graph(chat_input, chat_output, flow_id="test_flow")

    # Get the vertex from the graph
    vertex = graph.vertices[0]  # First vertex should be chat_input
    assert vertex.id == "test_vertex_id"

    # Call after_callback_event with a result
    test_result = "test_result_value"
    event = vertex.after_callback_event(result=test_result)

    # Assert the event is a StepFinishedEvent
    assert isinstance(event, StepFinishedEvent)

    # Assert the event has the correct step_name
    assert event.step_name == vertex.display_name

    # Assert the raw_event contains the langflow metrics
    assert event.raw_event is not None
    assert isinstance(event.raw_event, dict)
    assert "langflow" in event.raw_event

    # Assert the langflow metrics contain expected fields
    langflow_metrics = event.raw_event["langflow"]
    assert isinstance(langflow_metrics, dict)
    assert "timestamp" in langflow_metrics
    assert isinstance(langflow_metrics["timestamp"], float)
    assert "component_id" in langflow_metrics
    assert langflow_metrics["component_id"] == vertex.id
    assert langflow_metrics["component_id"] == "test_vertex_id"


def test_vertex_raw_event_metrics():
    """Test that Vertex.raw_event_metrics generates the correct metrics dictionary."""
    # Create a graph with a ChatInput component, which creates a vertex
    from lfx.graph import Graph

    chat_input = ChatInput(_id="test_vertex_id")
    chat_output = ChatInput(_id="output_id")  # Need two components for Graph
    graph = Graph(chat_input, chat_output, flow_id="test_flow")

    # Get the vertex from the graph
    vertex = graph.vertices[0]  # First vertex should be chat_input
    assert vertex.id == "test_vertex_id"

    # Call raw_event_metrics with optional fields
    metrics = vertex.raw_event_metrics({"custom_field": "custom_value"})

    # Assert metrics is a dictionary
    assert isinstance(metrics, dict)

    # Assert timestamp is present and is a float
    assert "timestamp" in metrics
    assert isinstance(metrics["timestamp"], float)

    # Assert custom field is present
    assert "custom_field" in metrics
    assert metrics["custom_field"] == "custom_value"


def test_vertex_raw_event_metrics_no_optional_fields():
    """Test that Vertex.raw_event_metrics works without optional fields."""
    # Create a graph with a ChatInput component, which creates a vertex
    from lfx.graph import Graph

    chat_input = ChatInput(_id="test_vertex_id")
    chat_output = ChatInput(_id="output_id")  # Need two components for Graph
    graph = Graph(chat_input, chat_output, flow_id="test_flow")

    # Get the vertex from the graph
    vertex = graph.vertices[0]  # First vertex should be chat_input
    assert vertex.id == "test_vertex_id"

    # Call raw_event_metrics without optional fields (pass None)
    metrics = vertex.raw_event_metrics(None)

    # Assert metrics is a dictionary
    assert isinstance(metrics, dict)

    # Assert timestamp is present and is a float
    assert "timestamp" in metrics
    assert isinstance(metrics["timestamp"], float)

    # The metrics should contain only timestamp when no optional fields are provided
    assert len(metrics) == 1


def test_component_vertex_extract_messages_coerces_uuid_session_id():
    """Model-level coercion should string-cast UUID in extracted messages."""
    session_id = uuid4()
    vertex = object.__new__(vertex_types_module.ComponentVertex)
    vertex.id = "vertex-1"
    vertex.artifacts_type = {"message": "chat"}
    artifacts = {
        "message": {
            "text": "hi",
            "sender": "Machine",
            "sender_name": "AI",
            "session_id": session_id,
            "stream_url": None,
            "files": [],
        }
    }

    messages = vertex_types_module.ComponentVertex.extract_messages_from_artifacts(vertex, artifacts)
    assert messages[0]["session_id"] == str(session_id)


def test_vertex_base_extract_messages_coerces_uuid_session_id():
    """Model-level coercion should string-cast UUID in base vertex messages."""
    session_id = uuid4()
    vertex = object.__new__(vertex_base_module.Vertex)
    vertex.id = "vertex-2"
    vertex.artifacts_type = "chat"
    artifacts = {
        "text": "hello",
        "sender": "Machine",
        "sender_name": "AI",
        "session_id": session_id,
        "stream_url": None,
        "files": [],
    }

    messages = vertex_base_module.Vertex.extract_messages_from_artifacts(vertex, artifacts)
    assert messages[0]["session_id"] == str(session_id)


class TestStrFieldWithNonStringListElements:
    """Regression: str field containing a list of Message dicts must not crash.

    Bug: On subsequent agent calls, ChatInput's input_value field receives
    a list of Message dicts from chat history. The param_handler's str case
    matched `list()` and called `unescape_string(v)` on each element, but
    v was a dict, causing 'dict' object has no attribute 'replace'.
    """

    def test_str_field_with_list_of_dicts_extracts_text(self, parameter_handler, mock_vertex):
        """A str field with list of Message dicts must extract text, not crash."""
        message_dict = {
            "text_key": "text",
            "text": "hello from user",
            "data": {"text": "hello from user", "sender": "User"},
            "default_value": "",
        }
        new_template = {
            "input_value": {
                "type": "str",
                "value": [message_dict],
                "show": True,
            }
        }
        mock_vertex.data["node"]["template"] = new_template
        parameter_handler.template_dict = new_template

        params, _ = parameter_handler.process_field_parameters()
        assert params["input_value"] == ["hello from user"]

    def test_str_field_with_dict_nested_text(self, parameter_handler, mock_vertex):
        """A Message dict without top-level text should fall back to data.text."""
        message_dict = {
            "text_key": "text",
            "data": {"text": "nested hello", "sender": "User"},
            "default_value": "",
        }
        new_template = {
            "input_value": {
                "type": "str",
                "value": [message_dict],
                "show": True,
            }
        }
        mock_vertex.data["node"]["template"] = new_template
        parameter_handler.template_dict = new_template

        params, _ = parameter_handler.process_field_parameters()
        assert params["input_value"] == ["nested hello"]

    def test_str_field_with_list_of_strings_still_unescapes(self, parameter_handler, mock_vertex):
        """A str field with list of strings must still unescape."""
        new_template = {
            "input_value": {
                "type": "str",
                "value": ["hello\\nworld", "foo\\nbar"],
                "show": True,
            }
        }
        mock_vertex.data["node"]["template"] = new_template
        parameter_handler.template_dict = new_template

        params, _ = parameter_handler.process_field_parameters()
        assert params["input_value"] == ["hello\nworld", "foo\nbar"]

    def test_str_field_with_mixed_list(self, parameter_handler, mock_vertex):
        """A str field with mixed string and dict elements extracts text from dicts."""
        message_dict = {"text_key": "text", "data": {"text": "msg"}}
        new_template = {
            "input_value": {
                "type": "str",
                "value": ["hello\\nworld", message_dict],
                "show": True,
            }
        }
        mock_vertex.data["node"]["template"] = new_template
        parameter_handler.template_dict = new_template

        params, _ = parameter_handler.process_field_parameters()
        assert params["input_value"] == ["hello\nworld", "msg"]
