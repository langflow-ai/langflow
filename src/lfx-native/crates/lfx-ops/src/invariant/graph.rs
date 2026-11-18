//! The graph structure every stored flow has: the flow, its nodes and its edges.

use crate::map::hash::HashSet;
use crate::json::{FlowObj, FlowValue};

use crate::flow::model::EntryExt;
use crate::flow::model::NODE_OBJECT_PATHS;
use crate::violation::{PathPart, Violation, ViolationCode, path_of};

pub(crate) fn not_an_object() -> Violation {
    Violation::new(
        ViolationCode::FlowDataNotObject,
        Vec::new(),
        "flow data must be an object",
    )
}

/// The structural rules `graph` breaks, in the order the graph lists them.
pub(crate) fn structure_violations(graph: &FlowObj) -> Vec<Violation> {
    let mut violations = Vec::new();
    let nodes = graph.get("nodes").and_then(FlowValue::as_array);
    let edges = graph.get("edges").and_then(FlowValue::as_array);
    for (key, collection) in [("nodes", nodes), ("edges", edges)] {
        if collection.is_none() {
            violations.push(Violation::new(
                ViolationCode::CollectionNotList,
                vec![key.into()],
                format!("flow data {key} must be a list"),
            ));
        }
    }

    let mut node_ids = HashSet::default();
    if let Some(nodes) = nodes {
        for (index, node) in nodes.iter().enumerate() {
            node_violations(
                node,
                &["nodes".into(), index.into()],
                &mut node_ids,
                &mut violations,
            );
        }
    }
    if let Some(edges) = edges {
        let mut edge_ids = HashSet::default();
        for (index, edge) in edges.iter().enumerate() {
            edge_violations(
                edge,
                &["edges".into(), index.into()],
                &mut edge_ids,
                &node_ids,
                &mut violations,
            );
        }
    }
    violations
}

fn node_violations<'a>(
    node: &'a FlowValue,
    path: &[PathPart],
    node_ids: &mut HashSet<&'a str>,
    violations: &mut Vec<Violation>,
) {
    let FlowValue::Object(node) = node else {
        violations.push(Violation::new(
            ViolationCode::NodeNotObject,
            path.to_vec(),
            "node must be an object",
        ));
        return;
    };
    match node.non_empty_str("id") {
        None => violations.push(Violation::new(
            ViolationCode::NodeIdMissing,
            path_of(path, &["id"]),
            "node must have a non-empty string id",
        )),
        Some(id) if !node_ids.insert(id) => violations.push(Violation::new(
            ViolationCode::NodeIdDuplicate,
            path_of(path, &["id"]),
            "duplicate node id",
        )),
        Some(_) => {}
    }
    if let Some(object_path) = missing_node_object(node) {
        violations.push(Violation::new(
            ViolationCode::NodeDataNotObject,
            path_of(path, object_path),
            format!("{} must be an object", object_path.join(".")),
        ));
    }
}

/// The first of `data`, `data.node` and `data.node.template` that is not an object.
fn missing_node_object(node: &FlowObj) -> Option<&'static [&'static str]> {
    let mut value = node;
    for object_path in NODE_OBJECT_PATHS {
        let key = object_path[object_path.len() - 1];
        match value.get(key) {
            Some(FlowValue::Object(object)) => value = object,
            _ => return Some(object_path),
        }
    }
    None
}

fn edge_violations<'a>(
    edge: &'a FlowValue,
    path: &[PathPart],
    edge_ids: &mut HashSet<&'a str>,
    node_ids: &HashSet<&str>,
    violations: &mut Vec<Violation>,
) {
    let FlowValue::Object(edge) = edge else {
        violations.push(Violation::new(
            ViolationCode::EdgeNotObject,
            path.to_vec(),
            "edge must be an object",
        ));
        return;
    };
    match edge.non_empty_str("id") {
        None => violations.push(Violation::new(
            ViolationCode::EdgeIdMissing,
            path_of(path, &["id"]),
            "edge must have a non-empty string id",
        )),
        Some(id) if !edge_ids.insert(id) => violations.push(Violation::new(
            ViolationCode::EdgeIdDuplicate,
            path_of(path, &["id"]),
            "duplicate edge id",
        )),
        Some(_) => {}
    }
    for end in ["source", "target"] {
        let message = match edge.non_empty_str(end) {
            None => format!("edge must have a non-empty string {end}"),
            Some(node_id) if !node_ids.contains(node_id) => {
                format!("edge {end} node does not exist")
            }
            Some(_) => continue,
        };
        violations.push(Violation::new(
            ViolationCode::EdgeEndpointInvalid,
            path_of(path, &[end]),
            message,
        ));
    }
}
