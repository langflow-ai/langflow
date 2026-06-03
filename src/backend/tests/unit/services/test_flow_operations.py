"""Unit tests for the pure flow operation apply engine."""

from __future__ import annotations

import copy

import pytest
from lfx.services.flow_operations import (
    AddNodesOp,
    DeleteEdgesOp,
    DeleteNodesOp,
    FlowDataValidationError,
    FlowOperationsApplyResult,
    FlowOperationValidationError,
    PythonFlowOperationService,
    UpdateMetadataOp,
    UpdateNodesOp,
    coalesce_delete_ids,
    normalize_requested_ops,
    parse_flow_operations,
)
from lfx.services.flow_operations import (
    apply_flow_operations as _apply_flow_operations,
)
from lfx.services.flow_operations.factory import FlowOperationServiceFactory

NODE_A = {"id": "a", "type": "generic", "position": {"x": 0, "y": 0}, "data": {}}
NODE_B = {"id": "b", "type": "generic", "position": {"x": 100, "y": 0}, "data": {}}
EDGE_AB = {
    "id": "e-ab",
    "source": "a",
    "target": "b",
    "sourceHandle": "out",
    "targetHandle": "in",
}


def _base_flow_data() -> dict:
    return {
        "nodes": [copy.deepcopy(NODE_A), copy.deepcopy(NODE_B)],
        "edges": [copy.deepcopy(EDGE_AB)],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


def apply_flow_operations(base_flow: dict, operations: list[dict]) -> FlowOperationsApplyResult:
    return _apply_flow_operations(base_flow, parse_flow_operations(operations))


class TestCoalesceDeleteIds:
    def test_preserves_first_seen_order(self):
        assert coalesce_delete_ids(["e1", "e2", "e1", "e3", "e2"]) == ["e1", "e2", "e3"]


class TestNormalizeRequestedOps:
    def test_parse_flow_operations_parses_dict_operations(self):
        ops = parse_flow_operations([{"type": "delete_nodes", "ids": ["a"]}])
        assert len(ops) == 1
        assert isinstance(ops[0], DeleteNodesOp)

    def test_parse_flow_operations_rejects_unknown_operation_type(self):
        with pytest.raises(FlowOperationValidationError, match="Unsupported operation type"):
            parse_flow_operations([{"type": "replace_graph", "data": {}}])

    def test_normalize_requested_ops_preserves_parsed_models(self):
        ops = parse_flow_operations([{"type": "delete_nodes", "ids": ["a"]}])

        assert normalize_requested_ops(ops) == ops


class TestFlowOperationService:
    def test_default_service_applies_operations(self):
        service = PythonFlowOperationService()
        new_node = {"id": "c", "type": "generic", "position": {"x": 200, "y": 0}, "data": {}}

        result = service.apply(_base_flow_data(), parse_flow_operations([{"type": "add_nodes", "nodes": [new_node]}]))

        assert any(node["id"] == "c" for node in result.flow_data["nodes"])
        assert result.forward_ops == [AddNodesOp(type="add_nodes", nodes=[new_node])]

    def test_factory_creates_default_service(self):
        service = FlowOperationServiceFactory().create()

        assert isinstance(service, PythonFlowOperationService)


class TestApplyFlowOperations:
    def test_does_not_mutate_input_on_success(self):
        flow_data = _base_flow_data()
        original = copy.deepcopy(flow_data)
        apply_flow_operations(
            flow_data,
            [
                {
                    "type": "update_nodes",
                    "updates": [{"id": "a", "op": "set_field", "path": ["position", "x"], "value": 5}],
                }
            ],
        )
        assert flow_data == original

    def test_does_not_mutate_input_on_failure(self):
        flow_data = _base_flow_data()
        original = copy.deepcopy(flow_data)
        with pytest.raises(FlowOperationValidationError):
            apply_flow_operations(flow_data, [{"type": "add_nodes", "nodes": [copy.deepcopy(NODE_A)]}])
        assert flow_data == original

    def test_add_nodes(self):
        flow_data = _base_flow_data()
        new_node = {"id": "c", "type": "generic", "position": {"x": 200, "y": 0}, "data": {}}
        result = apply_flow_operations(flow_data, [{"type": "add_nodes", "nodes": [new_node]}])

        assert len(result.flow_data["nodes"]) == 3
        assert any(node["id"] == "c" for node in result.flow_data["nodes"])
        assert len(result.forward_ops) == 1
        assert isinstance(result.forward_ops[0], AddNodesOp)
        assert result.forward_ops[0].nodes == [new_node]

    def test_update_nodes_sets_scalar_null_list_and_object_values(self):
        flow_data = _base_flow_data()
        operations = [
            {
                "type": "update_nodes",
                "updates": [
                    {"id": "a", "op": "set_field", "path": ["position", "x"], "value": 50},
                    {"id": "a", "op": "set_field", "path": ["data", "label"], "value": None},
                    {"id": "a", "op": "set_field", "path": ["data", "items"], "value": [1, 2, 3]},
                    {"id": "a", "op": "set_field", "path": ["data", "config"], "value": {"enabled": True}},
                ],
            }
        ]
        result = apply_flow_operations(flow_data, operations)

        stored = next(node for node in result.flow_data["nodes"] if node["id"] == "a")
        assert stored["position"]["x"] == 50
        assert stored["data"]["label"] is None
        assert stored["data"]["items"] == [1, 2, 3]
        assert stored["data"]["config"] == {"enabled": True}
        assert result.forward_ops == [UpdateNodesOp(type="update_nodes", updates=operations[0]["updates"])]

    def test_update_nodes_can_create_optional_final_object_key(self):
        flow_data = _base_flow_data()
        result = apply_flow_operations(
            flow_data,
            [
                {
                    "type": "update_nodes",
                    "updates": [{"id": "a", "op": "set_field", "path": ["data", "selected_output"], "value": "result"}],
                }
            ],
        )

        stored = next(node for node in result.flow_data["nodes"] if node["id"] == "a")
        assert stored["data"]["selected_output"] == "result"

    def test_update_nodes_deletes_optional_object_key(self):
        flow_data = _base_flow_data()
        flow_data["nodes"][0]["data"]["customColor"] = "#fff"
        result = apply_flow_operations(
            flow_data,
            [
                {
                    "type": "update_nodes",
                    "updates": [{"id": "a", "op": "delete_field", "path": ["data", "customColor"]}],
                }
            ],
        )

        stored = next(node for node in result.flow_data["nodes"] if node["id"] == "a")
        assert "customColor" not in stored["data"]
        assert result.forward_ops == [
            UpdateNodesOp(
                type="update_nodes",
                updates=[{"id": "a", "op": "delete_field", "path": ["data", "customColor"]}],
            )
        ]

    def test_update_nodes_delete_missing_optional_key_is_noop(self):
        flow_data = _base_flow_data()
        result = apply_flow_operations(
            flow_data,
            [
                {
                    "type": "update_nodes",
                    "updates": [{"id": "a", "op": "delete_field", "path": ["data", "customColor"]}],
                }
            ],
        )

        assert result.flow_data == flow_data
        assert result.forward_ops == [
            UpdateNodesOp(
                type="update_nodes",
                updates=[{"id": "a", "op": "delete_field", "path": ["data", "customColor"]}],
            )
        ]

    def test_update_nodes_applies_array_index_replacement(self):
        flow_data = _base_flow_data()
        flow_data["nodes"][0]["data"]["node"] = {"outputs": [{"selected": "a"}, {"selected": "b"}]}
        result = apply_flow_operations(
            flow_data,
            [
                {
                    "type": "update_nodes",
                    "updates": [
                        {
                            "id": "a",
                            "op": "set_field",
                            "path": ["data", "node", "outputs", 1, "selected"],
                            "value": None,
                        }
                    ],
                }
            ],
        )

        stored = next(node for node in result.flow_data["nodes"] if node["id"] == "a")
        assert stored["data"]["node"]["outputs"][1]["selected"] is None

    def test_update_nodes_forward_ops_snapshot_does_not_drift_after_nested_field_update(self):
        flow_data = _base_flow_data()
        result = apply_flow_operations(
            flow_data,
            [
                {
                    "type": "update_nodes",
                    "updates": [
                        {
                            "id": "a",
                            "op": "set_field",
                            "path": ["data", "config"],
                            "value": {"enabled": True},
                        },
                        {
                            "id": "a",
                            "op": "set_field",
                            "path": ["data", "config", "retries"],
                            "value": 3,
                        },
                    ],
                }
            ],
        )

        stored = next(node for node in result.flow_data["nodes"] if node["id"] == "a")
        assert stored["data"]["config"] == {"enabled": True, "retries": 3}
        update_op = result.forward_ops[0]
        assert isinstance(update_op, UpdateNodesOp)
        assert update_op.updates[0].value == {"enabled": True}

    @pytest.mark.parametrize(
        "updates",
        [
            [
                {"id": "a", "op": "set_field", "path": ["data", "customColor"], "value": "#fff"},
                {"id": "a", "op": "set_field", "path": ["data", "customColor"], "value": "#000"},
            ],
            [
                {"id": "a", "op": "delete_field", "path": ["data", "customColor"]},
                {"id": "a", "op": "delete_field", "path": ["data", "customColor"]},
            ],
            [
                {"id": "a", "op": "set_field", "path": ["data", "customColor"], "value": "#fff"},
                {"id": "a", "op": "delete_field", "path": ["data", "customColor"]},
            ],
            [
                {"id": "a", "op": "delete_field", "path": ["data", "customColor"]},
                {"id": "a", "op": "set_field", "path": ["data", "customColor"], "value": "#fff"},
            ],
        ],
    )
    def test_update_nodes_rejects_duplicate_field_path_updates(self, updates):
        flow_data = _base_flow_data()
        with pytest.raises(FlowOperationValidationError, match="multiple field updates"):
            apply_flow_operations(flow_data, [{"type": "update_nodes", "updates": updates}])

    def test_update_nodes_replaces_full_payload(self):
        flow_data = _base_flow_data()
        updated = copy.deepcopy(NODE_A)
        updated["position"] = {"x": 50, "y": 50}
        result = apply_flow_operations(
            flow_data, [{"type": "update_nodes", "updates": [{"id": "a", "op": "overwrite_node", "node": updated}]}]
        )

        stored = next(node for node in result.flow_data["nodes"] if node["id"] == "a")
        assert stored["position"] == {"x": 50, "y": 50}
        assert result.forward_ops == [
            UpdateNodesOp(type="update_nodes", updates=[{"id": "a", "op": "overwrite_node", "node": updated}])
        ]

    def test_delete_nodes_removes_incident_edges(self):
        flow_data = _base_flow_data()
        result = apply_flow_operations(flow_data, [{"type": "delete_nodes", "ids": ["a"]}])

        assert [node["id"] for node in result.flow_data["nodes"]] == ["b"]
        assert result.flow_data["edges"] == []
        assert result.forward_ops[0] == DeleteNodesOp(type="delete_nodes", ids=["a"])
        assert result.forward_ops[1] == DeleteEdgesOp(type="delete_edges", ids=["e-ab"])
        assert result.deleted_edges == ("e-ab",)

    def test_delete_edges_ignores_missing_ids(self):
        flow_data = _base_flow_data()
        result = apply_flow_operations(
            flow_data,
            [{"type": "delete_edges", "ids": ["missing", "e-ab", "e-ab"]}],
        )

        assert result.flow_data["edges"] == []
        assert result.forward_ops == [DeleteEdgesOp(type="delete_edges", ids=["e-ab"])]

    def test_add_edges_requires_existing_endpoints(self):
        flow_data = _base_flow_data()
        with pytest.raises(FlowOperationValidationError, match="source node does not exist"):
            apply_flow_operations(
                flow_data,
                [
                    {
                        "type": "add_edges",
                        "edges": [{"id": "e-new", "source": "missing", "target": "b"}],
                    }
                ],
            )

    def test_add_edges_after_add_nodes_in_same_batch(self):
        flow_data = _base_flow_data()
        new_node = {"id": "c", "type": "generic", "position": {"x": 0, "y": 0}, "data": {}}
        new_edge = {"id": "e-bc", "source": "b", "target": "c"}
        result = apply_flow_operations(
            flow_data,
            [
                {"type": "add_nodes", "nodes": [new_node]},
                {"type": "add_edges", "edges": [new_edge]},
            ],
        )

        assert len(result.flow_data["nodes"]) == 3
        assert any(edge["id"] == "e-bc" for edge in result.flow_data["edges"])

    def test_rejects_duplicate_node_id_in_add_nodes(self):
        flow_data = _base_flow_data()
        with pytest.raises(FlowOperationValidationError, match="already exists"):
            apply_flow_operations(flow_data, [{"type": "add_nodes", "nodes": [copy.deepcopy(NODE_A)]}])

    def test_rejects_duplicate_node_id_within_request(self):
        flow_data = _base_flow_data()
        node = {"id": "c", "type": "generic", "position": {"x": 0, "y": 0}, "data": {}}
        with pytest.raises(FlowOperationValidationError, match="duplicate node id"):
            apply_flow_operations(flow_data, [{"type": "add_nodes", "nodes": [node, copy.deepcopy(node)]}])

    def test_rejects_multiple_overwrite_node_updates_for_same_node(self):
        flow_data = _base_flow_data()
        first_update = copy.deepcopy(NODE_A)
        first_update["position"] = {"x": 10, "y": 10}
        second_update = copy.deepcopy(NODE_A)
        second_update["position"] = {"x": 20, "y": 20}

        with pytest.raises(FlowOperationValidationError, match="multiple overwrite_node entries"):
            apply_flow_operations(
                flow_data,
                [
                    {
                        "type": "update_nodes",
                        "updates": [
                            {"id": "a", "op": "overwrite_node", "node": first_update},
                            {"id": "a", "op": "overwrite_node", "node": second_update},
                        ],
                    }
                ],
            )

    def test_rejects_missing_node_on_update(self):
        flow_data = _base_flow_data()
        with pytest.raises(FlowOperationValidationError, match="does not exist"):
            apply_flow_operations(
                flow_data,
                [
                    {
                        "type": "update_nodes",
                        "updates": [{"id": "missing", "op": "set_field", "path": ["position", "x"], "value": 1}],
                    }
                ],
            )

    def test_rejects_old_update_nodes_nodes_payload(self):
        flow_data = _base_flow_data()
        with pytest.raises(FlowOperationValidationError, match="updates"):
            apply_flow_operations(flow_data, [{"type": "update_nodes", "nodes": [copy.deepcopy(NODE_A)]}])

    def test_rejects_overwrite_node_id_mismatch(self):
        flow_data = _base_flow_data()
        updated = copy.deepcopy(NODE_A)
        updated["id"] = "different"
        with pytest.raises(FlowOperationValidationError, match="overwrite_node node id must match"):
            apply_flow_operations(
                flow_data,
                [{"type": "update_nodes", "updates": [{"id": "a", "op": "overwrite_node", "node": updated}]}],
            )

    def test_rejects_mixing_overwrite_node_and_field_updates(self):
        flow_data = _base_flow_data()
        with pytest.raises(FlowOperationValidationError, match="cannot mix overwrite_node"):
            apply_flow_operations(
                flow_data,
                [
                    {
                        "type": "update_nodes",
                        "updates": [
                            {"id": "a", "op": "set_field", "path": ["position", "x"], "value": 1},
                            {"id": "a", "op": "overwrite_node", "node": copy.deepcopy(NODE_A)},
                        ],
                    }
                ],
            )

    @pytest.mark.parametrize(
        ("path", "message"),
        [
            (["id"], "cannot modify node identity"),
            (["data", "missing", "value"], "object path part must be an existing string key: 'missing'"),
        ],
    )
    def test_rejects_invalid_update_node_paths(self, path, message):
        flow_data = _base_flow_data()
        with pytest.raises(FlowOperationValidationError, match=message):
            apply_flow_operations(
                flow_data,
                [{"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": path, "value": 1}]}],
            )

    def test_rejects_array_delete(self):
        flow_data = _base_flow_data()
        flow_data["nodes"][0]["data"]["items"] = ["a", "b"]
        with pytest.raises(FlowOperationValidationError, match="delete only supports object properties"):
            apply_flow_operations(
                flow_data,
                [
                    {
                        "type": "update_nodes",
                        "updates": [{"id": "a", "op": "delete_field", "path": ["data", "items", 0]}],
                    }
                ],
            )

    def test_rejects_malformed_node_payload(self):
        flow_data = _base_flow_data()
        with pytest.raises(FlowOperationValidationError, match="must have a non-empty string id"):
            apply_flow_operations(flow_data, [{"type": "add_nodes", "nodes": [{"type": "generic"}]}])

    def test_rejects_malformed_edge_payload(self):
        flow_data = _base_flow_data()
        with pytest.raises(FlowOperationValidationError, match="must have a non-empty string source"):
            apply_flow_operations(
                flow_data,
                [{"type": "add_edges", "edges": [{"id": "e-x", "target": "b"}]}],
            )

    def test_rejects_duplicate_edge_id_in_add_edges(self):
        flow_data = _base_flow_data()
        duplicate_current_edge = {"id": "e-ab", "source": "a", "target": "b"}
        new_edge = {"id": "e-new", "source": "a", "target": "b"}

        with pytest.raises(FlowOperationValidationError, match="edge id already exists"):
            apply_flow_operations(flow_data, [{"type": "add_edges", "edges": [duplicate_current_edge]}])

        with pytest.raises(FlowOperationValidationError, match="duplicate edge id"):
            apply_flow_operations(flow_data, [{"type": "add_edges", "edges": [new_edge, copy.deepcopy(new_edge)]}])

    def test_rejects_duplicate_ids_in_base_flow_data(self):
        flow_data = _base_flow_data()
        flow_data["nodes"].append(copy.deepcopy(NODE_A))
        with pytest.raises(FlowDataValidationError, match=r"flow\.data\.nodes: duplicate node id"):
            apply_flow_operations(flow_data, [])

        flow_data = _base_flow_data()
        flow_data["edges"].append(copy.deepcopy(EDGE_AB))
        with pytest.raises(FlowDataValidationError, match=r"flow\.data\.edges: duplicate edge id"):
            apply_flow_operations(flow_data, [])

    def test_update_metadata_shallow_updates_and_deletes(self):
        flow_data = _base_flow_data()
        flow_data["description"] = "old"
        flow_data["custom_flag"] = True
        result = apply_flow_operations(
            flow_data,
            [
                {
                    "type": "update_metadata",
                    "fields": {"description": "new", "notes": {"k": "v"}},
                    "delete_keys": ["custom_flag", "custom_flag"],
                }
            ],
        )

        assert result.flow_data["description"] == "new"
        assert result.flow_data["notes"] == {"k": "v"}
        assert "custom_flag" not in result.flow_data
        assert result.flow_data["viewport"] == {"x": 0, "y": 0, "zoom": 1}
        metadata_op = result.forward_ops[0]
        assert isinstance(metadata_op, UpdateMetadataOp)
        assert metadata_op.fields == {"description": "new", "notes": {"k": "v"}}
        assert metadata_op.delete_keys == ["custom_flag"]

    def test_update_metadata_rejects_graph_collection_keys(self):
        flow_data = _base_flow_data()
        with pytest.raises(FlowOperationValidationError, match="cannot set graph collection key"):
            apply_flow_operations(
                flow_data,
                [{"type": "update_metadata", "fields": {"nodes": []}, "delete_keys": []}],
            )
        with pytest.raises(FlowOperationValidationError, match="cannot delete graph collection key"):
            apply_flow_operations(
                flow_data,
                [{"type": "update_metadata", "fields": {}, "delete_keys": ["edges"]}],
            )

    def test_preserves_operation_order_in_forward_ops(self):
        flow_data = _base_flow_data()
        updated = copy.deepcopy(NODE_B)
        updated["position"] = {"x": 10, "y": 10}
        result = apply_flow_operations(
            flow_data,
            [
                {"type": "update_nodes", "updates": [{"id": "b", "op": "overwrite_node", "node": updated}]},
                {"type": "delete_edges", "ids": ["e-ab"]},
            ],
        )

        assert isinstance(result.forward_ops[0], UpdateNodesOp)
        assert isinstance(result.forward_ops[1], DeleteEdgesOp)

    def test_viewport_unchanged_by_graph_ops(self):
        flow_data = _base_flow_data()
        result = apply_flow_operations(flow_data, [{"type": "delete_edges", "ids": ["e-ab"]}])
        assert result.flow_data["viewport"] == flow_data["viewport"]
