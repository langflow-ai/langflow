use crate::flow_value;
use crate::json::FlowValue;

use super::*;
use crate::flow::edge_handle::escape_handle;
use crate::flow::model::OUTPUTS_PATH;
use crate::op::ReplayOptions;

fn target_handle(field: &str) -> FlowValue {
    flow_value!({"fieldName": field, "id": "T", "inputTypes": ["Message"], "type": "str"})
}

fn edge(id: &str, field: &str) -> FlowValue {
    let source =
        flow_value!({"dataType": "X", "id": "S", "name": "out", "output_types": ["Message"]});
    flow_value!({
        "id": id, "source": "S", "target": "T",
        "sourceHandle": escape_handle(&source),
        "targetHandle": escape_handle(&target_handle(field)),
        "data": {"sourceHandle": source, "targetHandle": target_handle(field)},
    })
}

fn operations(value: FlowValue) -> Vec<Operation> {
    Operation::list_from_value(value).unwrap()
}

#[test]
fn deletion_options_preserve_cascade_order_duplicates_and_rollback() {
    let field = flow_value!({"type": "str", "value": ""});
    let graph = flow_value!({
        "nodes": [
            {"id": "S", "data": {"node": {"template": {}, "outputs": [{"name": "out"}]}}},
            {"id": "T", "data": {"node": {"template": {"A": &field, "B": &field}}}},
        ],
        "edges": [edge("e1", "A"), edge("e2", "B")],
    });
    for forward in [false, true] {
        for backward in [false, true] {
            let options = ApplyOptions { forward, backward };
            let mut state = GraphState::new(graph.clone()).unwrap();
            let before = state.to_json();
            let applied = state
                .apply(
                    operations(flow_value!([
                        {"type": "delete_nodes", "ids": ["T", "S", "T"]},
                        {"type": "delete_edges", "ids": ["e1", "e1", "absent"]},
                    ])),
                    options,
                )
                .unwrap();
            assert_eq!(state.to_value()["nodes"], flow_value!([]));
            assert_eq!(state.to_value()["edges"], flow_value!([]));
            if forward {
                assert_eq!(
                    applied.forward,
                    operations(flow_value!([
                        {"type": "delete_nodes", "ids": ["T", "S"]},
                        {"type": "delete_edges", "ids": ["e1", "e2"]},
                    ]))
                );
            } else {
                assert_eq!(applied.forward, Vec::<Operation>::new());
            }
            if backward {
                assert_eq!(applied.backward.len(), 2);
                assert_eq!(applied.backward[1], Vec::<Operation>::new());
                for batch in applied.backward.into_iter().rev() {
                    state.replay(batch, ReplayOptions::default()).unwrap();
                }
                assert_eq!(
                    state.graph_hash().unwrap(),
                    GraphState::new(graph.clone())
                        .unwrap()
                        .graph_hash()
                        .unwrap()
                );
            } else {
                assert_eq!(applied.backward, Vec::<Vec<Operation>>::new());
            }
            let mut state = GraphState::new(graph.clone()).unwrap();
            let refused = operations(flow_value!([
                {"type": "delete_edges", "ids": ["e1", "e1"]},
                {"type": "delete_nodes", "ids": ["T", "absent", "S"]},
            ]));
            let error = state.apply(refused, options).unwrap_err();
            assert!(error.to_string().contains("absent"));
            assert_eq!(state.to_json(), before);
            assert!(!state.is_staged());
        }
    }
}

#[test]
fn an_update_error_names_the_update_and_the_segment() {
    let graph = flow_value!({
        "nodes": [{"id": "a", "data": {"node": {"template": {"f": {"value": 1}}}}}],
        "edges": [],
    });
    let mut state = GraphState::new(graph).unwrap();
    let write = flow_value!([{"type": "update_nodes", "updates": [
        {"id": "a", "op": "set_field", "path": ["position"], "value": {}},
        {"id": "a", "op": "set_field", "path": ["data", "node", "template", "f", "value", {"key": "r"}], "value": {"__id__": "r", "__pos__": 1}},
    ]}]);
    let error = state
        .apply(operations(write), ApplyOptions::default())
        .unwrap_err();
    assert!(
        error.message.starts_with("update_nodes[1].path[5]: "),
        "{}",
        error.message
    );
}

#[test]
fn a_kept_state_swaps_two_edges_by_deleting_and_adding_them() {
    let field = flow_value!({"type": "str", "value": ""});
    let graph = flow_value!({
        "nodes": [
            {"id": "S", "data": {"node": {"template": {}, "outputs": [{"name": "out"}]}}},
            {"id": "T", "data": {"node": {"template": {"A": &field, "B": &field, "C": &field}}}},
        ],
        "edges": [edge("e1", "B"), edge("e2", "A")],
    });
    let mut state = GraphState::new(graph).unwrap();
    // This batch indexes the connections of T, which the next batch reuses.
    let add = flow_value!([{"type": "add_edges", "edges": [edge("e3", "C")]}]);
    state
        .apply(operations(add), ApplyOptions::default())
        .unwrap();
    let swap = flow_value!([
        {"type": "delete_edges", "ids": ["e1", "e2"]},
        {"type": "add_edges", "edges": [edge("e1", "A"), edge("e2", "B")]},
    ]);
    state
        .apply(operations(swap), ApplyOptions::default())
        .unwrap();
}

#[test]
fn a_refused_batch_keeps_the_indexes_earlier_batches_built() {
    let field = flow_value!({"type": "str", "value": ""});
    let graph = flow_value!({
        "nodes": [
            {"id": "S", "data": {"node": {"template": {}, "outputs": [{"name": "out"}]}}},
            {"id": "T", "data": {"node": {"template": {"A": &field, "B": &field}}}},
        ],
        "edges": [edge("e1", "A")],
    });
    let mut state = GraphState::new(graph).unwrap();
    let add = flow_value!([{"type": "add_edges", "edges": [edge("e2", "B")]}]);
    state
        .apply(operations(add), ApplyOptions::default())
        .unwrap();
    assert!(state.edge_index.has_connections("T"));
    // A writes T, then the second edge into A is refused: the batch changes nothing.
    let refused = flow_value!([
        {"type": "update_nodes", "updates": [
            {"id": "T", "op": "set_field", "path": ["data", "node", "template", "A", "value"], "value": "x"},
        ]},
        {"type": "add_edges", "edges": [edge("e3", "A")]},
    ]);
    let before = state.to_value();
    state
        .apply(operations(refused), ApplyOptions::default())
        .unwrap_err();
    assert_eq!(state.to_value(), before);
    assert!(state.edge_index.has_connections("T"));
}

fn set(id: &str, path: FlowValue, value: FlowValue) -> FlowValue {
    let mut update = flow_value!({"id": id, "op": "set_field"});
    update["path"] = path;
    update["value"] = value;
    update
}

fn delete(id: &str, path: FlowValue) -> FlowValue {
    let mut update = flow_value!({"id": id, "op": "delete_field"});
    update["path"] = path;
    update
}

fn updates(updates: Vec<FlowValue>) -> Vec<Operation> {
    let mut operation = flow_value!({"type": "update_nodes"});
    operation["updates"] = FlowValue::Array(updates);
    operations(FlowValue::Array(vec![operation]))
}

fn table_node() -> FlowValue {
    let row = |id: &str, pos: u32| flow_value!({"__id__": id, "__pos__": pos, "v": "x"});
    flow_value!({"id": "t", "data": {"node": {"template": {
        "rows": {"type": "table", "value": [row("r1", 1), row("r2", 2), row("r3", 3)]},
        "text": {"type": "str", "value": ""},
    }}}})
}

fn rows_path(key: Option<&str>) -> FlowValue {
    let mut path = flow_value!(["data", "node", "template", "rows", "value"]);
    if let Some(key) = key {
        path.as_vec_mut().unwrap().push(flow_value!({"key": key}));
    }
    path
}

fn cell_path(key: &str) -> FlowValue {
    let mut path = rows_path(Some(key));
    path.as_vec_mut().unwrap().push(flow_value!("v"));
    path
}

/// A batch on a kept graph state gives what it gives on a fresh one.
fn same_as_fresh(state: &mut GraphState, batch: Vec<Operation>) -> Result<()> {
    let fresh = apply_flow_operations(state.to_value(), batch.clone(), ApplyOptions::default());
    let kept = state.apply(batch, ApplyOptions::default());
    match (fresh, kept) {
        (Ok((graph, _)), Ok(_)) => {
            assert!(crate::compare::graphs_equal(&state.to_value(), &graph).unwrap());
            Ok(())
        }
        (Err(_), Err(error)) => Err(error),
        (fresh, kept) => panic!("fresh {fresh:?}, kept {kept:?}"),
    }
}

#[test]
fn a_kept_table_keeps_its_index_through_writes_and_refused_batches() {
    let mut state = GraphState::new(flow_value!({"nodes": [table_node()], "edges": []})).unwrap();
    let row = |id: &str, pos: f64| flow_value!({"__id__": id, "__pos__": pos, "v": "n"});
    same_as_fresh(
        &mut state,
        updates(vec![set("t", cell_path("r2"), flow_value!("y"))]),
    )
    .unwrap();
    same_as_fresh(
        &mut state,
        updates(vec![delete("t", rows_path(Some("r1")))]),
    )
    .unwrap();
    // Refused after a row is added and a cell written: nothing changes.
    let before = state.to_value();
    let refused = updates(vec![
        set("t", rows_path(Some("r4")), row("r4", 4.0)),
        set("t", cell_path("r3"), flow_value!("z")),
        set("t", cell_path("gone"), flow_value!("z")),
    ]);
    same_as_fresh(&mut state, refused).unwrap_err();
    assert_eq!(state.to_value(), before);
    same_as_fresh(
        &mut state,
        updates(vec![
            set("t", rows_path(Some("r5")), row("r5", 0.5)),
            set("t", cell_path("r5"), flow_value!("w")),
            delete("t", rows_path(Some("r2"))),
            set("t", cell_path("r3"), flow_value!("v3")),
        ]),
    )
    .unwrap();
    same_as_fresh(
        &mut state,
        updates(vec![set("t", cell_path("r5"), flow_value!("again"))]),
    )
    .unwrap();
    let rows = &state.to_value()["nodes"][0]["data"]["node"]["template"]["rows"]["value"];
    let mut cells: Vec<(String, String)> = rows
        .as_array()
        .unwrap()
        .iter()
        .map(|row| {
            (
                row["__id__"].as_str().unwrap().into(),
                row["v"].as_str().unwrap().into(),
            )
        })
        .collect();
    cells.sort();
    assert_eq!(
        cells,
        [("r3".into(), "v3".into()), ("r5".into(), "again".into())]
    );
}

#[test]
fn a_field_type_written_in_the_batch_decides_whether_its_value_is_a_table() {
    let node = flow_value!({"id": "t", "data": {"node": {"template": {
        "rows": {"type": "str", "value": [{"__id__": "r1", "__pos__": 1}]},
    }}}});
    let graph = flow_value!({"nodes": [node], "edges": []});
    let row = flow_value!({"__id__": "r2", "__pos__": 2});
    let refused = updates(vec![set("t", rows_path(Some("r2")), row.clone())]);
    let error = apply_flow_operations(graph.clone(), refused, ApplyOptions::default()).unwrap_err();
    assert!(
        error.message.contains("does not declare keyed"),
        "{}",
        error.message
    );
    let typed = updates(vec![
        set(
            "t",
            flow_value!(["data", "node", "template", "rows", "type"]),
            flow_value!("table"),
        ),
        set("t", rows_path(Some("r2")), row),
    ]);
    let (graph, _) = apply_flow_operations(graph, typed, ApplyOptions::default()).unwrap();
    assert_eq!(
        graph["nodes"][0]["data"]["node"]["template"]["rows"]["value"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
}

#[test]
fn a_list_written_in_the_batch_is_checked_when_a_write_reads_its_items() {
    let graph = flow_value!({"nodes": [table_node()], "edges": []});
    let update = |update: FlowValue| flow_value!({"type": "update_nodes", "updates": [update]});
    let batch = operations(flow_value!([
        update(set("t", rows_path(None), flow_value!([1, 2]))),
        update(delete("t", rows_path(Some("r1")))),
    ]));
    let error = apply_flow_operations(graph, batch, ApplyOptions::default()).unwrap_err();
    assert!(
        error.message.contains("non-empty string key"),
        "{}",
        error.message
    );
}

#[test]
fn an_output_deleted_and_added_again_in_one_batch_takes_its_new_position() {
    let output = |name: &str, position: u32| flow_value!({"name": name, "__pos__": position});
    let node = flow_value!({"id": "n", "data": {"node": {"template": {},
        "outputs": [output("a", 1), output("b", 2), output("c", 3)]}}});
    let outputs = |key: &str| flow_value!(["data", "node", "outputs", {"key": key}]);
    let update = |update: FlowValue| flow_value!({"type": "update_nodes", "updates": [update]});
    let batch = operations(flow_value!([
        update(delete("n", outputs("a"))),
        update(set("n", outputs("d"), output("d", 4))),
        update(set("n", outputs("a"), output("a", 5))),
    ]));
    let mut state = GraphState::new(flow_value!({"nodes": [node], "edges": []})).unwrap();
    state.apply(batch, ApplyOptions::default()).unwrap();
    let outputs = state.graph.node_value("n", &OUTPUTS_PATH).unwrap();
    let mut order: Vec<(u64, &str)> = outputs
        .as_array()
        .unwrap()
        .iter()
        .map(|output| {
            (
                output["__pos__"].as_u64().unwrap(),
                output["name"].as_str().unwrap(),
            )
        })
        .collect();
    order.sort_unstable();
    let names: Vec<&str> = order.into_iter().map(|(_, name)| name).collect();
    assert_eq!(names, ["b", "c", "d", "a"]);
}

#[test]
fn a_node_deleted_and_added_again_takes_the_writes_after_it() {
    let node = flow_value!({"id": "n", "data": {"node": {"template": {"f": {"value": 1}}}}});
    let batch = flow_value!([
        {"type": "delete_nodes", "ids": ["n"]},
        {"type": "add_nodes", "nodes": [{"id": "n", "data": {"node": {"template": {"g": {"value": 2}}}}}]},
        {"type": "update_nodes", "updates": [set("n", flow_value!(["data", "node", "template", "g", "value"]), flow_value!(3))]},
    ]);
    let (graph, _) = apply_flow_operations(
        flow_value!({"nodes": [node], "edges": []}),
        operations(batch),
        ApplyOptions::default(),
    )
    .unwrap();
    assert_eq!(
        graph["nodes"][0]["data"]["node"]["template"],
        flow_value!({"g": {"value": 3}})
    );
}

#[test]
fn an_edge_rule_reads_a_field_written_in_the_batch() {
    let field = flow_value!({"type": "str", "value": ""});
    let graph = flow_value!({
        "nodes": [
            {"id": "S", "data": {"node": {"template": {}, "outputs": [{"name": "out"}]}}},
            {"id": "T", "data": {"node": {"template": {"A": field}}}},
        ],
        "edges": [edge("e1", "A")],
    });
    let second = flow_value!({"type": "add_edges", "edges": [edge("e2", "A")]});
    let error = apply_flow_operations(
        graph.clone(),
        operations(flow_value!([&second])),
        ApplyOptions::default(),
    )
    .unwrap_err();
    assert_eq!(
        error.code,
        crate::violation::error::ErrorCode::Violation(
            crate::validate::ViolationCode::EdgeTargetOccupied
        ),
        "{error}"
    );
    let list = set(
        "T",
        flow_value!(["data", "node", "template", "A", "list"]),
        flow_value!(true),
    );
    let batch = flow_value!([{"type": "update_nodes", "updates": [list]}, second]);
    apply_flow_operations(graph, operations(batch), ApplyOptions::default()).unwrap();
}

#[test]
fn a_write_over_earlier_writes_undoes_to_the_graph_before_the_batch() {
    let graph = flow_value!({"nodes": [table_node()], "edges": []});
    let field = flow_value!(["data", "node", "template", "rows"]);
    let batch = updates(vec![
        set("t", cell_path("r1"), flow_value!("y")),
        delete("t", rows_path(Some("r2"))),
        set("t", field, flow_value!({"type": "str", "value": "flat"})),
    ]);
    let mut state = GraphState::new(graph.clone()).unwrap();
    let options = ApplyOptions {
        backward: true,
        ..ApplyOptions::default()
    };
    let applied = state.apply(batch, options).unwrap();
    for list in applied.backward.into_iter().rev() {
        state.replay(list, ReplayOptions::default()).unwrap();
    }
    assert!(crate::compare::graphs_equal(&state.to_value(), &graph).unwrap());
}

#[test]
fn a_staged_batch_is_not_read_until_it_is_kept() {
    let mut state = GraphState::new(flow_value!({"nodes": [table_node()], "edges": []})).unwrap();
    let before = state.to_value();
    let batch = updates(vec![
        set("t", cell_path("r2"), flow_value!("y")),
        delete("t", rows_path(Some("r1"))),
    ]);
    let options = ApplyOptions {
        forward: true,
        backward: true,
    };
    let (expected_graph, expected) =
        apply_flow_operations(before.clone(), batch.clone(), options).unwrap();
    assert!(state.staged_to_json().is_none(), "nothing is staged yet");
    let staged = state.stage(batch, options).unwrap();
    assert_eq!(staged, expected);
    assert!(state.is_staged());
    assert_eq!(state.to_value(), before);
    assert_eq!(
        serde_json::from_str::<FlowValue>(&state.to_json()).unwrap(),
        before
    );
    // The staged graph is the graph that keep makes, while the committed graph stays.
    let staged_text = state.staged_to_json().unwrap();
    assert!(
        crate::compare::graphs_equal(
            &serde_json::from_str(&staged_text).unwrap(),
            &expected_graph
        )
        .unwrap()
    );
    assert!(state.keep());
    assert!(!state.is_staged());
    assert_eq!(state.to_json(), staged_text);
    assert!(crate::compare::graphs_equal(&state.to_value(), &expected_graph).unwrap());
    assert!(!state.keep(), "nothing is staged after keep");
    assert!(
        state.staged_to_json().is_none(),
        "nothing is staged after keep"
    );
}

#[test]
fn a_dropped_batch_leaves_the_graph_and_its_indexes() {
    let field = flow_value!({"type": "str", "value": ""});
    let graph = flow_value!({
        "nodes": [
            {"id": "S", "data": {"node": {"template": {}, "outputs": [{"name": "out"}]}}},
            {"id": "T", "data": {"node": {"template": {"A": &field, "B": &field}}}},
        ],
        "edges": [edge("e1", "A")],
    });
    let mut state = GraphState::new(graph).unwrap();
    let add = flow_value!([{"type": "add_edges", "edges": [edge("e2", "B")]}]);
    state
        .apply(operations(add), ApplyOptions::default())
        .unwrap();
    let before = state.to_value();
    let batch = flow_value!([
        {"type": "delete_edges", "ids": ["e1"]},
        {"type": "update_nodes", "updates": [
            set("T", flow_value!(["data", "node", "template", "A", "value"]), flow_value!("x")),
        ]},
        {"type": "add_edges", "edges": [edge("e3", "A")]},
    ]);
    state
        .stage(operations(batch.clone()), ApplyOptions::default())
        .unwrap();
    assert!(state.drop_staged());
    assert!(!state.is_staged());
    assert_eq!(state.to_value(), before);
    assert!(state.edge_index.has_connections("T"));
    // The indexes still hold e1 in A: a second edge into A is refused.
    let second = flow_value!([{"type": "add_edges", "edges": [edge("e3", "A")]}]);
    state
        .apply(operations(second), ApplyOptions::default())
        .unwrap_err();
    // The dropped batch applies as it would have.
    state
        .apply(operations(batch), ApplyOptions::default())
        .unwrap();
    assert!(!state.drop_staged(), "nothing is staged after apply");
}

#[test]
fn a_refused_batch_is_not_staged() {
    let mut state = GraphState::new(flow_value!({"nodes": [table_node()], "edges": []})).unwrap();
    let before = state.to_value();
    let refused = updates(vec![
        set("t", cell_path("r2"), flow_value!("y")),
        set("t", cell_path("gone"), flow_value!("z")),
    ]);
    state.stage(refused, ApplyOptions::default()).unwrap_err();
    assert!(!state.is_staged());
    assert!(!state.keep());
    assert_eq!(state.to_value(), before);
}

#[test]
fn a_group_sub_flow_node_is_not_selected_by_key() {
    let inner =
        flow_value!({"id": "lm", "data": {"node": {"template": {"api_key": {"value": ""}}}}});
    let graph = flow_value!({
        "nodes": [{"id": "g", "data": {"node": {
            "template": {},
            "flow": {"data": {"nodes": [inner], "edges": []}},
        }}}],
        "edges": [],
    });
    let path = flow_value!([
        "data", "node", "flow", "data", "nodes", {"key": "lm"},
        "data", "node", "template", "api_key", "value",
    ]);
    let write = flow_value!([{"type": "update_nodes", "updates": [
        {"id": "g", "op": "set_field", "path": path, "value": "x"},
    ]}]);
    let error =
        apply_flow_operations(graph, operations(write), ApplyOptions::default()).unwrap_err();
    assert!(
        error.to_string().contains("does not declare keyed"),
        "{error}"
    );
}
