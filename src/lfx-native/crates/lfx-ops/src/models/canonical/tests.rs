//! Tests of the canonical form, its text and its hash.

use std::fmt::Write as _;

use crate::data::value::AnyValue;
use sha2::{Digest, Sha256};

use crate::json;
use crate::models::canonical::equal::{
    Canon, View, canon_equal, canonical_edge, canonical_graph, canonical_node,
};
use crate::models::canonical::text::{Sink, flow_part, write_part};
use crate::models::error::{Error, Result};
use crate::models::schema::NODE_SCHEMA;

use super::*;

/// Flow data in canonical graph form, as RFC 8785 text.
fn canonical_graph_json(flow: &AnyValue) -> Result<String> {
    let mut out = Sink::text();
    write_part(flow_part(flow), &mut out)?;
    Ok(out.into_text())
}

#[test]
fn graphs_compare_their_canonical_forms() {
    let left = json!({
        "viewport": {"x": 1},
        "description": "every top-level key but nodes and edges is view state",
        "nodes": [
            {"id": "b", "selected": true, "data": {"node": {"template": {}}}},
            {"id": "a", "data": {"node": {"last_updated": "x", "template": {
                "rows": {"type": "table", "value": [{"__id__": "r2", "__pos__": 2}, {"__id__": "r1", "__pos__": 1.0}]}
            }}}},
        ],
        "edges": [{"id": "e", "sourceHandle": "{œnameœ: œoutœ}", "animated": true}],
    });
    let right = json!({
        "nodes": [
            {"id": "a", "data": {"node": {"template": {
                "rows": {"type": "table", "value": [{"__id__": "r1", "__pos__": 1}, {"__id__": "r2", "__pos__": 2}]}
            }}}},
            {"id": "b", "data": {"node": {"template": {}}}},
        ],
        "edges": [{"id": "e", "sourceHandle": "{œnameœ:œoutœ}"}],
    });
    assert!(graphs_equal(&left, &right).unwrap());
    assert_eq!(graph_hash(&left).unwrap(), graph_hash(&right).unwrap());

    let mut changed = right.clone();
    changed["nodes"][1]["data"]["node"]["template"]["x"] = json!(1);
    assert!(!graphs_equal(&left, &changed).unwrap());
    assert_ne!(graph_hash(&left).unwrap(), graph_hash(&changed).unwrap());
}

#[rustfmt::skip]
    const FIXTURES: [&str; 12] = [
        include_str!("../../../../../fixtures/apply_cases.json"),
        include_str!("../../../../../fixtures/backward_cases.json"),
        include_str!("../../../../../fixtures/canonical_cases.json"),
        include_str!("../../../../../fixtures/diff_cases.json"),
        include_str!("../../../../../fixtures/editor_cases.json"),
        include_str!("../../../../../fixtures/limit_cases.json"),
        include_str!("../../../../../fixtures/merge_cases.json"),
        include_str!("../../../../../fixtures/property_cases.json"),
        include_str!("../../../../../fixtures/repair_cases.json"),
        include_str!("../../../../../fixtures/restore_cases.json"),
        include_str!("../../../../../fixtures/table_cases.json"),
        include_str!("../../../../../fixtures/validation_cases.json"),
    ];

/// Every graph in every fixture case.
fn fixture_graphs() -> Vec<AnyValue> {
    let mut out = Vec::new();
    for text in FIXTURES {
        let file: AnyValue = serde_json::from_str(text).unwrap();
        let mut found = Vec::new();
        graphs(&file, &mut found);
        out.extend(found.into_iter().cloned());
    }
    out
}

#[test]
fn graph_hash_streams_the_canonical_text() {
    let all = fixture_graphs();
    assert!(all.len() > 500, "only {} graphs", all.len());
    for graph in &all {
        let Ok(text) = canonical_graph_json(graph) else {
            assert!(graph_hash(graph).is_err());
            continue;
        };
        let digest = Sha256::digest(text.as_bytes());
        let hex = digest.iter().fold(String::new(), |mut hex, byte| {
            write!(hex, "{byte:02x}").ok();
            hex
        });
        assert_eq!(graph_hash(graph).unwrap(), hex, "{graph}");
    }
}

#[test]
fn a_loaded_graph_hashes_as_its_value_does() {
    let mut loaded = 0;
    for graph in fixture_graphs() {
        let Ok(state) = crate::GraphState::new(graph) else {
            continue;
        };
        assert_eq!(state.graph_hash(), graph_hash(&state.to_value()));
        loaded += 1;
    }
    assert!(loaded > 300, "only {loaded} graphs loaded");
}

/// A comparison that makes every node canonical before it compares.
fn graphs_equal_eager(left: &AnyValue, right: &AnyValue) -> Result<bool> {
    fn eager(canon: Canon<'_>) -> Canon<'_> {
        match canon {
            Canon::Node(node) => canonical_node(node),
            Canon::Edge(edge) => canonical_edge(edge).unwrap(),
            Canon::Object(map) => Canon::Object(
                map.into_iter()
                    .map(|(key, value)| (key, eager(value)))
                    .collect(),
            ),
            Canon::Array(items) => Canon::Array(items.into_iter().map(eager).collect()),
            other => other,
        }
    }
    let left = eager(canonical_graph(left));
    let right = eager(canonical_graph(right));
    canon_equal(View::of(&left), View::of(&right), None)
}

/// Every graph in a fixture case, nested ones included.
fn graphs<'v>(value: &'v AnyValue, out: &mut Vec<&'v AnyValue>) {
    match value {
        AnyValue::Object(map) => {
            if map.get("nodes").is_some_and(AnyValue::is_array) {
                out.push(value);
            }
            map.values().for_each(|value| graphs(value, out));
        }
        AnyValue::Array(items) => items.iter().for_each(|value| graphs(value, out)),
        _ => {}
    }
}

/// The graph with its nodes in reverse order, and `number` under `key`
/// on each node.
fn reshuffled(graph: &AnyValue, key: &str, number: &str) -> AnyValue {
    let mut graph = graph.clone();
    if let Some(AnyValue::Array(nodes)) = graph.get_mut("nodes") {
        nodes.reverse();
        for node in nodes.iter_mut().filter_map(AnyValue::as_object_mut) {
            node.insert(key.to_owned(), serde_json::from_str(number).unwrap());
        }
    }
    graph
}

#[test]
fn graphs_equal_answers_as_the_eager_comparison() {
    let hidden = NODE_SCHEMA
        .node_view_state
        .iter()
        .min()
        .expect("a node view-state key");
    assert!(!NODE_SCHEMA.node_view_state.contains("compared"));
    let mut pairs = 0;
    for text in FIXTURES {
        let file: AnyValue = serde_json::from_str(text).unwrap();
        let cases = file
            .as_object()
            .into_iter()
            .flat_map(crate::data::value::AnyMap::values)
            .filter_map(AnyValue::as_array)
            .flatten();
        for case in cases {
            let mut found = Vec::new();
            graphs(case, &mut found);
            // A display-only key with a finite or an infinite number, and an
            // infinite number where the comparison reads it.
            let shuffled: Vec<AnyValue> = found
                .iter()
                .flat_map(|graph| {
                    [
                        reshuffled(graph, hidden, "1"),
                        reshuffled(graph, hidden, "1e400"),
                        reshuffled(graph, "compared", "1e400"),
                    ]
                })
                .collect();
            let all: Vec<(&AnyValue, bool)> = found
                .into_iter()
                .chain(&shuffled)
                .map(|graph| (graph, graph_hash(graph).is_err()))
                .collect();
            for &(left, left_refused) in &all {
                for &(right, right_refused) in &all {
                    // A refused graph is refused against any graph. The
                    // eager comparison may stop early and answer not equal.
                    let (new, old) = (graphs_equal(left, right), graphs_equal_eager(left, right));
                    if left_refused || right_refused {
                        assert_eq!(new, Err(Error::non_finite()), "{left}\n{right}");
                        assert!(!matches!(old, Ok(true)), "{left}\n{right}");
                    } else {
                        assert_eq!(new, old, "{left}\n{right}");
                    }
                    pairs += 1;
                }
            }
        }
    }
    assert!(pairs > 10_000, "only {pairs} pairs");
}
