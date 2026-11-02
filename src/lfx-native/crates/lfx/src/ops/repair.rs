//! Bringing a graph that breaks the engine's rules back within them.
//!
//! Flows stored before the engine enforced its rules, imported flows, and
//! flows edited directly in the database can break them, and such a flow
//! cannot take any edit until it is repaired. [`repair_flow_data`] fixes every
//! violation that has exactly one fix, and lists what it changed. It never
//! touches a violation that has more than one correct way to fix it (an
//! edge that names an output that does not exist, or a second edge into a
//! single input): fixing one means choosing what the person meant, so the
//! client does.
//!
//! Repair is never implicit: callers invoke it only when a request asks for
//! it, and they keep the original first, so even a fix that discards a value
//! loses nothing permanently. Replay and ordinary saves never repair.
//!
//! Given the stored graph a write replaces (`base`), repair also fixes what
//! the write adds or changes:
//!
//! - the rows of every table: it assigns missing row ids, regenerates
//!   duplicate ids, and gives rows without a position one that keeps them
//!   where they are stored;
//! - every edge it adds: it derives a handle's missing form from
//!   the one present, and drops an edge that touches a note.

use std::collections::{HashMap, HashSet};

use crate::value::{AnyMap, AnyValue};
use sha2::{Digest, Sha256};

use crate::ops::canonical::{canonical_json, is_finite_number, is_row_position};
use crate::ops::edges::derive_missing_handle_forms;
use crate::ops::entry::EntryExt;
use crate::ops::error::Result;
use crate::ops::ids::{new_edge_id, unused_id};
use crate::ops::keyed::{Renumber, fill_missing_positions, match_row_ids};
use crate::ops::schema::{NODE_OBJECT_PATHS, NODE_SCHEMA};
use crate::ops::state::resolve_mut;
use crate::ops::validate::{
    GraphPath, Numbers, PathPart, Resolution, Step, ViolationCode, changed_keyed_lists,
    changed_tables, find_edge_violations, owned_path, validate_flow_data,
};

const GENERATED_ID_LENGTH: usize = 5;
const ID_ALPHABET: &[u8; 62] = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

/// One change repair made, at the path the violation was found.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Fix {
    /// The rule the change fixes.
    pub code: ViolationCode,
    /// Where the violation was.
    pub path: GraphPath,
    /// What repair did.
    pub action: &'static str,
}

impl Fix {
    /// The fix as the API reports it.
    #[must_use]
    pub fn to_value(&self) -> AnyValue {
        let mut object = AnyMap::new();
        object.insert("code".into(), AnyValue::from(self.code.as_str()));
        object.insert(
            "path".into(),
            AnyValue::Array(self.path.iter().map(PathPart::to_value).collect()),
        );
        object.insert("action".into(), AnyValue::from(self.action));
        AnyValue::Object(object)
    }
}

/// A repaired graph and the fixes that made it.
#[derive(Debug, Clone, PartialEq)]
pub struct Repaired {
    /// The repaired graph.
    pub flow_data: AnyValue,
    /// Every fix, in the order repair made them.
    pub fixes: Vec<Fix>,
}

#[derive(Debug, Default)]
struct Fixes(Vec<Fix>);

impl Fixes {
    fn add(&mut self, code: ViolationCode, path: GraphPath) {
        let action = code
            .repair_action()
            .expect("repair records only violations it has a fix for");
        self.0.push(Fix { code, path, action });
    }
}

fn path(parts: impl IntoIterator<Item = PathPart>) -> GraphPath {
    parts.into_iter().collect()
}

/// A copy of `flow` with every violation that has one fix fixed, and the fixes applied.
///
/// Generated node ids are derived from the node's content and position, so
/// repairing the same graph twice gives the same nodes. Generated edge ids
/// are random, like the editor's. With `base`, the table rows the
/// write adds or changes are repaired too: a row without an id takes the id
/// of an identical stored row, so a table written back without ids keeps the
/// rows it already held, and only new rows get new random ids.
///
/// # Errors
///
/// The graph also breaks a rule only the client can fix: the error lists
/// what is left, so a repaired save writes nothing.
pub fn repair_flow_data(flow: &AnyValue, base: Option<&AnyValue>) -> Result<Repaired> {
    let mut fixes = Fixes::default();
    let AnyValue::Object(flow) = flow else {
        fixes.add(ViolationCode::FlowDataNotObject, Vec::new());
        let empty = crate::json!({"nodes": [], "edges": []});
        return Ok(Repaired {
            flow_data: empty,
            fixes: fixes.0,
        });
    };
    let mut repaired = AnyValue::Object(flow.clone());
    replace_non_finite(&mut repaired, &mut fixes);
    let AnyValue::Object(graph) = &mut repaired else {
        unreachable!("the repaired graph is an object");
    };
    for key in ["nodes", "edges"] {
        if !graph.get(key).is_some_and(AnyValue::is_array) {
            fixes.add(ViolationCode::CollectionNotList, path([key.into()]));
            graph.insert(key.to_owned(), AnyValue::Array(Vec::new()));
        }
    }
    let nodes = take_array(graph, "nodes");
    let nodes = repair_nodes(nodes, &mut fixes)?;
    let node_ids: HashSet<String> = nodes
        .iter()
        .filter_map(|node| node.non_empty_str("id").map(str::to_owned))
        .collect();
    graph.insert("nodes".into(), AnyValue::Array(nodes));
    let edges = take_array(graph, "edges");
    graph.insert(
        "edges".into(),
        AnyValue::Array(repair_edges(edges, &node_ids, &mut fixes)),
    );

    if let Some(base) = base {
        repair_tables(&mut repaired, base, &mut fixes)?;
        repair_list_positions(&mut repaired, base, &mut fixes)?;
        repair_added_edges(&mut repaired, base, &mut fixes)?;
    }

    // Repair must never return a graph that the normal checks would refuse.
    validate_flow_data(&repaired, Numbers::Check, "repaired flow.data", base)?;
    Ok(Repaired {
        flow_data: repaired,
        fixes: fixes.0,
    })
}

fn take_array(graph: &mut AnyMap, key: &str) -> Vec<AnyValue> {
    match graph.get_mut(key).map(std::mem::take) {
        Some(AnyValue::Array(items)) => items,
        _ => Vec::new(),
    }
}

/// Read first. Only paths that hold an invalid number need mutable access.
/// Direct members precede nested containers, last container first, as before.
fn replace_non_finite(value: &mut AnyValue, fixes: &mut Fixes) {
    let mut paths = Vec::new();
    non_finite_paths(value, &mut Vec::new(), &mut paths);
    for path in paths {
        if let Some(value) = resolve_mut(value, &path) {
            *value = AnyValue::Null;
            fixes.add(ViolationCode::NonFiniteNumber, path);
        }
    }
}

fn non_finite_paths<'a>(value: &'a AnyValue, at: &mut Vec<Step<'a>>, paths: &mut Vec<GraphPath>) {
    let mut number = |step, value: &AnyValue| {
        if let AnyValue::Number(number) = value
            && !is_finite_number(number)
        {
            at.push(step);
            paths.push(owned_path(at));
            at.pop();
        }
    };
    match value {
        AnyValue::Object(map) => {
            for (key, value) in map {
                number(Step::Key(key), value);
            }
            for (key, value) in map.iter().rev() {
                if value.is_object() || value.is_array() {
                    at.push(Step::Key(key));
                    non_finite_paths(value, at, paths);
                    at.pop();
                }
            }
        }
        AnyValue::Array(items) => {
            for (index, value) in items.iter().enumerate() {
                number(Step::Index(index), value);
            }
            for (index, value) in items.iter().enumerate().rev() {
                if value.is_object() || value.is_array() {
                    at.push(Step::Index(index));
                    non_finite_paths(value, at, paths);
                    at.pop();
                }
            }
        }
        _ => {}
    }
}

fn repair_nodes(nodes: Vec<AnyValue>, fixes: &mut Fixes) -> Result<Vec<AnyValue>> {
    let mut kept: Vec<(usize, AnyMap)> = Vec::new();
    for (index, node) in nodes.into_iter().enumerate() {
        let AnyValue::Object(mut node) = node else {
            fixes.add(
                ViolationCode::NodeNotObject,
                path(["nodes".into(), index.into()]),
            );
            continue;
        };
        repair_node_objects(&mut node, index, fixes);
        kept.push((index, node));
    }
    let mut used: HashSet<String> = kept
        .iter()
        .filter_map(|(_, node)| node.non_empty_str("id").map(str::to_owned))
        .collect();
    let mut seen = HashSet::new();
    for (index, node) in &mut kept {
        let old_id = node.get("id").cloned();
        let valid = node.non_empty_str("id").map(str::to_owned);
        if let Some(id) = &valid
            && seen.insert(id.clone())
        {
            continue;
        }
        let code = if valid.is_some() {
            ViolationCode::NodeIdDuplicate
        } else {
            ViolationCode::NodeIdMissing
        };
        fixes.add(code, path(["nodes".into(), (*index).into(), "id".into()]));
        let new_id = generate_node_id(node, *index, &used)?;
        used.insert(new_id.clone());
        seen.insert(new_id.clone());
        node.insert("id".into(), AnyValue::from(new_id.clone()));
        // The editor keeps a node's own id in data.id; follow a rename there.
        if let Some(AnyValue::Object(data)) = node.get_mut("data") {
            let follows = match data.get("id") {
                None | Some(AnyValue::Null) => true,
                Some(data_id) => Some(data_id) == old_id.as_ref(),
            };
            if follows {
                data.insert("id".into(), AnyValue::from(new_id));
            }
        }
    }
    Ok(kept
        .into_iter()
        .map(|(_, node)| AnyValue::Object(node))
        .collect())
}

fn repair_node_objects(node: &mut AnyMap, index: usize, fixes: &mut Fixes) {
    // A valid node stays shared. Do not detach its objects just to inspect them.
    if NODE_OBJECT_PATHS.iter().all(|path| {
        let mut value = node.get(path[0]);
        for key in &path[1..] {
            value = value.and_then(|value| value.get(*key));
        }
        value.is_some_and(AnyValue::is_object)
    }) {
        return;
    }
    let mut parent = node;
    for object_path in NODE_OBJECT_PATHS {
        let key = object_path[object_path.len() - 1];
        if !parent.get(key).is_some_and(AnyValue::is_object) {
            let parts = ["nodes".into(), index.into()]
                .into_iter()
                .chain(object_path.iter().map(|part| PathPart::from(*part)));
            fixes.add(ViolationCode::NodeDataNotObject, path(parts));
            parent.insert(key.to_owned(), AnyValue::Object(AnyMap::new()));
        }
        let Some(AnyValue::Object(child)) = parent.get_mut(key) else {
            return;
        };
        parent = child;
    }
}

fn repair_edges(
    edges: Vec<AnyValue>,
    node_ids: &HashSet<String>,
    fixes: &mut Fixes,
) -> Vec<AnyValue> {
    let mut kept: Vec<(usize, AnyMap)> = Vec::new();
    for (index, edge) in edges.into_iter().enumerate() {
        let AnyValue::Object(edge) = edge else {
            fixes.add(
                ViolationCode::EdgeNotObject,
                path(["edges".into(), index.into()]),
            );
            continue;
        };
        // The editor drops these on every load (cleanEdges); nothing can draw them.
        let invalid = ["source", "target"].into_iter().find(|end| {
            !edge
                .get(end)
                .and_then(AnyValue::as_str)
                .is_some_and(|id| node_ids.contains(id))
        });
        if let Some(end) = invalid {
            fixes.add(
                ViolationCode::EdgeEndpointInvalid,
                path(["edges".into(), index.into(), end.into()]),
            );
            continue;
        }
        kept.push((index, edge));
    }
    let mut used: HashSet<String> = kept
        .iter()
        .filter_map(|(_, edge)| edge.non_empty_str("id").map(str::to_owned))
        .collect();
    let mut seen = HashSet::new();
    for (index, edge) in &mut kept {
        let valid = edge.non_empty_str("id").map(str::to_owned);
        if let Some(id) = &valid
            && seen.insert(id.clone())
        {
            continue;
        }
        let code = if valid.is_some() {
            ViolationCode::EdgeIdDuplicate
        } else {
            ViolationCode::EdgeIdMissing
        };
        fixes.add(code, path(["edges".into(), (*index).into(), "id".into()]));
        // A random id like the editor's newEdgeId(), never derived from the handles.
        let new_id = unused_id(&used, new_edge_id);
        used.insert(new_id.clone());
        seen.insert(new_id.clone());
        edge.insert("id".into(), AnyValue::from(new_id));
    }
    kept.into_iter()
        .map(|(_, edge)| AnyValue::Object(edge))
        .collect()
}

/// Fix the edge rule violations that have one fix, in the edges `graph` adds relative to `base`.
fn repair_added_edges(graph: &mut AnyValue, base: &AnyValue, fixes: &mut Fixes) -> Result<()> {
    let mut dropped = HashSet::new();
    for violation in find_edge_violations(base, graph)? {
        if violation.code.resolution() == Resolution::Manual {
            continue;
        }
        let Some(PathPart::Index(index)) = violation.path.get(1).cloned() else {
            continue;
        };
        fixes.add(violation.code, violation.path);
        if violation.code == ViolationCode::EdgeTouchesNote {
            dropped.insert(index);
        } else if let Some(AnyValue::Object(edge)) = graph
            .get_mut("edges")
            .and_then(|edges| edges.get_mut(index))
        {
            derive_missing_handle_forms(edge);
        }
    }
    if !dropped.is_empty()
        && let Some(AnyValue::Array(edges)) = graph.get_mut("edges")
    {
        let mut index = 0;
        edges.retain(|_| {
            let keep = !dropped.contains(&index);
            index += 1;
            keep
        });
    }
    Ok(())
}

/// Fix the rows of every table value `graph` adds or changes relative to `base`.
fn repair_tables(graph: &mut AnyValue, base: &AnyValue, fixes: &mut Fixes) -> Result<()> {
    let stored = stored_tables(base);
    let tables: Vec<(GraphPath, String, String)> = changed_tables(base, graph)?
        .into_iter()
        .map(|table| {
            (
                table.path,
                table.node_id.unwrap_or_default().to_owned(),
                table.field.to_owned(),
            )
        })
        .collect();
    for (table_path, node_id, field) in tables {
        let previous = stored.get(&(node_id.as_str(), field.as_str())).copied();
        if let Some(AnyValue::Array(rows)) = resolve_mut(graph, &table_path) {
            repair_table(rows, &table_path, previous, fixes)?;
        }
    }
    Ok(())
}

/// Give a position to every item without one in the outputs and tool action
/// lists that `graph` adds or changes relative to `base`: the midpoint of
/// its array neighbours' positions, as for an insert.
fn repair_list_positions(graph: &mut AnyValue, base: &AnyValue, fixes: &mut Fixes) -> Result<()> {
    let lists: Vec<GraphPath> = changed_keyed_lists(base, graph)?
        .into_iter()
        .map(|changed| changed.path)
        .collect();
    for list_path in lists {
        let Some(AnyValue::Array(items)) = resolve_mut(graph, &list_path) else {
            continue;
        };
        for index in fill_missing_positions(items, Renumber::Never) {
            let item_path = list_path.iter().cloned().chain([
                index.into(),
                NODE_SCHEMA.table_keys.position.as_str().into(),
            ]);
            fixes.add(ViolationCode::ListItemMissingPos, path(item_path));
        }
    }
    Ok(())
}

/// Each list value `base` stores in a template field, by node id and field name.
fn stored_tables(base: &AnyValue) -> HashMap<(&str, &str), &AnyValue> {
    let mut stored = HashMap::new();
    for node in base
        .get("nodes")
        .and_then(AnyValue::as_array)
        .into_iter()
        .flatten()
    {
        let (Some(id), Some(template)) =
            (node.get("id").and_then(AnyValue::as_str), node.template())
        else {
            continue;
        };
        for (name, field) in template {
            if let Some(value) = field.get("value").filter(|value| value.is_array()) {
                stored.entry((id, name.as_str())).or_insert(value);
            }
        }
    }
    stored
}

/// Fix one table value in place: rows are objects with unique ids and numeric positions.
fn repair_table(
    rows: &mut Vec<AnyValue>,
    table_path: &[PathPart],
    previous: Option<&AnyValue>,
    fixes: &mut Fixes,
) -> Result<()> {
    let (id_key, position_key) = (&NODE_SCHEMA.table_keys.id, &NODE_SCHEMA.table_keys.position);
    let row_path = |index: usize, key: Option<&str>| {
        path(
            table_path
                .iter()
                .cloned()
                .chain([index.into()])
                .chain(key.map(PathPart::from)),
        )
    };
    for (index, row) in rows.iter().enumerate() {
        if !row.is_object() {
            fixes.add(ViolationCode::TableRowNotObject, row_path(index, None));
        }
    }
    rows.retain(AnyValue::is_object);

    let missing: Vec<usize> = (0..rows.len())
        .filter(|index| !rows[*index].get(position_key).is_some_and(is_row_position))
        .collect();
    let mut seen = HashSet::new();
    for (index, row) in rows.iter_mut().enumerate() {
        let valid = row.non_empty_str(id_key).map(str::to_owned);
        if let Some(id) = &valid
            && seen.insert(id.clone())
        {
            continue;
        }
        let code = if valid.is_some() {
            ViolationCode::TableRowIdDuplicate
        } else {
            ViolationCode::TableRowIdMissing
        };
        fixes.add(code, row_path(index, Some(id_key)));
        // A duplicate gives up its id; match_row_ids gives every row without one
        // the id (and position) of an identical stored row, or a new random id.
        if let Some(row) = row.as_object_mut() {
            row.shift_remove(id_key);
        }
    }
    match_row_ids(rows, previous)?;
    for index in missing {
        fixes.add(
            ViolationCode::TableRowPosInvalid,
            row_path(index, Some(position_key)),
        );
    }
    fill_missing_positions(rows, Renumber::Never);
    Ok(())
}

/// A node id in the editor's shape, `<component type>-<5 characters>`, derived
/// from the node's content and position.
fn generate_node_id(node: &AnyMap, index: usize, used: &HashSet<String>) -> Result<String> {
    let prefix = node
        .get("data")
        .and_then(|data| data.get("type"))
        .and_then(AnyValue::as_str)
        .filter(|kind| !kind.is_empty())
        .unwrap_or("node");
    let seed = format!(
        "{index}:{}",
        canonical_json(&AnyValue::Object(node.clone()))?
    );
    let mut attempt = 0u64;
    loop {
        let candidate = format!("{prefix}-{}", short_digest(&format!("{seed}:{attempt}")));
        if !used.contains(&candidate) {
            return Ok(candidate);
        }
        attempt += 1;
    }
}

fn short_digest(seed: &str) -> String {
    let digest = Sha256::digest(seed.as_bytes());
    let mut number = digest[..8]
        .iter()
        .fold(0u64, |number, byte| (number << 8) | u64::from(*byte));
    let mut characters = String::with_capacity(GENERATED_ID_LENGTH);
    for _ in 0..GENERATED_ID_LENGTH {
        let remainder = usize::try_from(number % 62).unwrap_or_default();
        number /= 62;
        characters.push(char::from(ID_ALPHABET[remainder]));
    }
    characters
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::json;

    #[test]
    fn repair_keeps_valid_node_objects_shared() {
        let source = json!({"nodes":[{"id":"a","data":{"node":{"template":{"t":{"value":"unchanged"}}}}}],"edges":[]});
        let repaired = repair_flow_data(&source, None).unwrap();
        assert_eq!(repaired.fixes, []);
        assert!(std::ptr::eq(
            source["nodes"][0]["data"]
                .as_object()
                .unwrap()
                .get("node")
                .unwrap(),
            repaired.flow_data["nodes"][0]["data"]
                .as_object()
                .unwrap()
                .get("node")
                .unwrap()
        ));
    }

    #[test]
    fn replacing_invalid_numbers_leaves_other_branches_shared() {
        let source: AnyValue = serde_json::from_str(
            r#"{"nodes":[],"edges":[],"first":{"bad":1e400},"second":{"keep":"text"}}"#,
        )
        .unwrap();
        let repaired = repair_flow_data(&source, None).unwrap();
        assert_eq!(repaired.flow_data["first"]["bad"], AnyValue::Null);
        assert!(source["first"]["bad"].as_f64().unwrap().is_infinite());
        assert!(std::ptr::eq(
            source["second"].as_object().unwrap().get("keep").unwrap(),
            repaired.flow_data["second"]
                .as_object()
                .unwrap()
                .get("keep")
                .unwrap()
        ));
        assert_eq!(repaired.fixes.len(), 1);
    }
}
