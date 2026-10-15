//! Bringing a graph that breaks the engine's rules back within them.
//!
//! Flows stored before the engine enforced its rules, imported flows, and
//! flows edited directly in the database can break them, and such a flow
//! cannot take any edit until it is repaired. [`repair_flow_data`] fixes every
//! direct violation, the ones with exactly one fix, and lists what it
//! changed. It never touches an intent-dependent violation (an edge that
//! names an output that does not exist, or a second edge into a single
//! input): fixing one means choosing what the person meant, so the client
//! does.
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
//! - every edge it adds or rewires: it derives a handle's missing form from
//!   the one present, and drops an edge that touches a note.

use std::collections::{HashMap, HashSet};

use serde_json::{Map, Value};
use sha2::{Digest, Sha256};

use crate::ops::canonical::{canonical_json, is_finite_number, is_row_position};
use crate::ops::edges::derive_missing_handle_forms;
use crate::ops::error::Result;
use crate::ops::ids::new_edge_id;
use crate::ops::keyed::{Renumber, fill_missing_positions, match_row_ids};
use crate::ops::schema::NODE_SCHEMA;
use crate::ops::validate::{
    GraphPath, NODE_OBJECT_PATHS, PathPart, Resolution, ViolationCode, changed_tables,
    find_edge_violations, validate_flow_data,
};

const GENERATED_ID_LENGTH: usize = 5;
const ID_ALPHABET: &[u8; 62] = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

/// The fix for a direct violation, or `None` for one the client fixes.
///
/// A direct rule without a fix would leave a flow that can neither be saved
/// nor repaired, so every code is either fixed here or left to the client.
#[must_use]
pub fn repair_action(code: ViolationCode) -> Option<&'static str> {
    use ViolationCode as Code;
    Some(match code {
        Code::FlowDataNotObject => "replaced with an empty flow",
        Code::CollectionNotList => "replaced with an empty list",
        Code::NodeNotObject | Code::EdgeNotObject => "dropped the entry",
        Code::NodeIdMissing | Code::EdgeIdMissing | Code::EdgeIdDuplicate => {
            "assigned a generated id"
        }
        Code::NodeIdDuplicate => {
            "assigned a generated id; the first node keeps the id and its edges"
        }
        Code::EdgeEndpointInvalid | Code::EdgeTouchesNote => "dropped the edge",
        Code::NodeDataNotObject => "replaced with an empty object",
        Code::NonFiniteNumber => "replaced with null",
        Code::TableRowNotObject => "dropped the row",
        Code::TableRowIdMissing => "assigned a generated row id",
        Code::TableRowIdDuplicate => "assigned a generated row id; the first row keeps the id",
        Code::TableRowPosInvalid => "assigned a position that keeps the row where it is stored",
        Code::EdgeHandleFormMissing => {
            "derived the missing form of the handle from the one present"
        }
        Code::EdgeHandleInvalid | Code::EdgeHandleNotFound | Code::EdgeTargetOccupied => {
            return None;
        }
    })
}

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
    pub fn to_json(&self) -> Value {
        let mut object = Map::new();
        object.insert("code".into(), Value::from(self.code.as_str()));
        object.insert(
            "path".into(),
            Value::Array(
                self.path
                    .iter()
                    .map(|part| match part {
                        PathPart::Key(key) => Value::from(key.as_str()),
                        PathPart::Index(index) => Value::from(*index),
                    })
                    .collect(),
            ),
        );
        object.insert("action".into(), Value::from(self.action));
        Value::Object(object)
    }
}

/// A repaired graph and the fixes that made it.
#[derive(Debug, Clone, PartialEq)]
pub struct Repaired {
    /// The repaired graph.
    pub flow_data: Value,
    /// Every fix, in the order repair made them.
    pub fixes: Vec<Fix>,
}

#[derive(Default)]
struct Fixes(Vec<Fix>);

impl Fixes {
    fn add(&mut self, code: ViolationCode, path: GraphPath) {
        let action = repair_action(code).unwrap_or_default();
        self.0.push(Fix { code, path, action });
    }
}

fn path(parts: impl IntoIterator<Item = PathPart>) -> GraphPath {
    parts.into_iter().collect()
}

fn valid_id(value: Option<&Value>) -> Option<&str> {
    value.and_then(Value::as_str).filter(|id| !id.is_empty())
}

/// A copy of `flow` with every direct violation fixed, and the fixes applied.
///
/// Generated node ids are derived from the node's content and position, so
/// repairing the same graph twice gives the same nodes. Generated edge ids
/// are opaque and random, like the editor's. With `base`, the table rows the
/// write adds or changes are repaired too: a row without an id takes the id
/// of an identical stored row, so a table written back without ids keeps the
/// rows it already held, and only new rows get new random ids.
///
/// # Errors
///
/// The graph also breaks a rule only the client can fix: the error lists
/// what is left, so a repaired save writes nothing.
pub fn repair_flow_data(flow: &Value, base: Option<&Value>) -> Result<Repaired> {
    let mut fixes = Fixes::default();
    let Value::Object(flow) = flow else {
        fixes.add(ViolationCode::FlowDataNotObject, Vec::new());
        let empty = serde_json::json!({"nodes": [], "edges": []});
        return Ok(Repaired {
            flow_data: empty,
            fixes: fixes.0,
        });
    };
    let mut repaired = Value::Object(flow.clone());
    replace_non_finite(&mut repaired, &mut fixes);
    let Value::Object(graph) = &mut repaired else {
        unreachable!("the repaired graph is an object");
    };
    for key in ["nodes", "edges"] {
        if !graph.get(key).is_some_and(Value::is_array) {
            fixes.add(ViolationCode::CollectionNotList, path([key.into()]));
            graph.insert(key.to_owned(), Value::Array(Vec::new()));
        }
    }
    let nodes = take_array(graph, "nodes");
    let nodes = repair_nodes(nodes, &mut fixes)?;
    let node_ids: HashSet<String> = nodes
        .iter()
        .filter_map(|node| valid_id(node.get("id")).map(str::to_owned))
        .collect();
    graph.insert("nodes".into(), Value::Array(nodes));
    let edges = take_array(graph, "edges");
    graph.insert(
        "edges".into(),
        Value::Array(repair_edges(edges, &node_ids, &mut fixes)),
    );

    if let Some(base) = base {
        repair_tables(&mut repaired, base, &mut fixes)?;
        repair_changed_edges(&mut repaired, base, &mut fixes)?;
    }

    // Repair must never return a graph the strict path would refuse.
    validate_flow_data(&repaired, true, "repaired flow.data", base)?;
    Ok(Repaired {
        flow_data: repaired,
        fixes: fixes.0,
    })
}

fn take_array(graph: &mut Map<String, Value>, key: &str) -> Vec<Value> {
    match graph.get_mut(key).map(std::mem::take) {
        Some(Value::Array(items)) => items,
        _ => Vec::new(),
    }
}

/// Replace every number that is not finite with null, containers last found first.
fn replace_non_finite(value: &mut Value, fixes: &mut Fixes) {
    let mut stack: Vec<GraphPath> = vec![Vec::new()];
    while let Some(container_path) = stack.pop() {
        let Some(container) = resolve_mut(value, &container_path) else {
            continue;
        };
        let children: Vec<(PathPart, &mut Value)> = match container {
            Value::Object(map) => map
                .iter_mut()
                .map(|(key, item)| (PathPart::Key(key.clone()), item))
                .collect(),
            Value::Array(items) => items
                .iter_mut()
                .enumerate()
                .map(|(index, item)| (index.into(), item))
                .collect(),
            _ => Vec::new(),
        };
        for (part, item) in children {
            let child_path = || {
                container_path
                    .iter()
                    .cloned()
                    .chain([part.clone()])
                    .collect::<GraphPath>()
            };
            match item {
                Value::Number(number) if !is_finite_number(number) => {
                    fixes.add(ViolationCode::NonFiniteNumber, child_path());
                    *item = Value::Null;
                }
                Value::Object(_) | Value::Array(_) => stack.push(child_path()),
                _ => {}
            }
        }
    }
}

fn resolve_mut<'v>(value: &'v mut Value, parts: &[PathPart]) -> Option<&'v mut Value> {
    parts.iter().try_fold(value, |value, part| match part {
        PathPart::Key(key) => value.as_object_mut()?.get_mut(key),
        PathPart::Index(index) => value.as_array_mut()?.get_mut(*index),
    })
}

fn repair_nodes(nodes: Vec<Value>, fixes: &mut Fixes) -> Result<Vec<Value>> {
    let mut kept: Vec<(usize, Map<String, Value>)> = Vec::new();
    for (index, node) in nodes.into_iter().enumerate() {
        let Value::Object(mut node) = node else {
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
        .filter_map(|(_, node)| valid_id(node.get("id")).map(str::to_owned))
        .collect();
    let mut seen = HashSet::new();
    for (index, node) in &mut kept {
        let old_id = node.get("id").cloned();
        let valid = valid_id(old_id.as_ref());
        if let Some(id) = valid
            && seen.insert(id.to_owned())
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
        node.insert("id".into(), Value::String(new_id.clone()));
        // The editor keeps a node's own id in data.id; follow a rename there.
        if let Some(Value::Object(data)) = node.get_mut("data") {
            let follows = match data.get("id") {
                None | Some(Value::Null) => true,
                Some(data_id) => Some(data_id) == old_id.as_ref(),
            };
            if follows {
                data.insert("id".into(), Value::String(new_id));
            }
        }
    }
    Ok(kept
        .into_iter()
        .map(|(_, node)| Value::Object(node))
        .collect())
}

fn repair_node_objects(node: &mut Map<String, Value>, index: usize, fixes: &mut Fixes) {
    let mut parent = node;
    for object_path in NODE_OBJECT_PATHS {
        let key = object_path[object_path.len() - 1];
        if !parent.get(key).is_some_and(Value::is_object) {
            let parts = ["nodes".into(), index.into()]
                .into_iter()
                .chain(object_path.iter().map(|part| PathPart::from(*part)));
            fixes.add(ViolationCode::NodeDataNotObject, path(parts));
            parent.insert(key.to_owned(), Value::Object(Map::new()));
        }
        let Some(Value::Object(child)) = parent.get_mut(key) else {
            return;
        };
        parent = child;
    }
}

fn repair_edges(edges: Vec<Value>, node_ids: &HashSet<String>, fixes: &mut Fixes) -> Vec<Value> {
    let mut kept: Vec<(usize, Map<String, Value>)> = Vec::new();
    for (index, edge) in edges.into_iter().enumerate() {
        let Value::Object(edge) = edge else {
            fixes.add(
                ViolationCode::EdgeNotObject,
                path(["edges".into(), index.into()]),
            );
            continue;
        };
        // The editor drops these on every load (cleanEdges); nothing can draw them.
        let invalid = ["source", "target"].into_iter().find(|end| {
            !edge
                .get(*end)
                .and_then(Value::as_str)
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
        .filter_map(|(_, edge)| valid_id(edge.get("id")).map(str::to_owned))
        .collect();
    let mut seen = HashSet::new();
    for (index, edge) in &mut kept {
        let valid = valid_id(edge.get("id")).map(str::to_owned);
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
        // An opaque id like the editor's newEdgeId(), never derived from the handles.
        let mut new_id = new_edge_id();
        while used.contains(&new_id) {
            new_id = new_edge_id();
        }
        used.insert(new_id.clone());
        seen.insert(new_id.clone());
        edge.insert("id".into(), Value::String(new_id));
    }
    kept.into_iter()
        .map(|(_, edge)| Value::Object(edge))
        .collect()
}

/// Fix the direct edge rules broken by the edges `graph` adds or rewires relative to `base`.
fn repair_changed_edges(graph: &mut Value, base: &Value, fixes: &mut Fixes) -> Result<()> {
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
        } else if let Some(Value::Object(edge)) = graph
            .get_mut("edges")
            .and_then(|edges| edges.get_mut(index))
        {
            derive_missing_handle_forms(edge);
        }
    }
    if !dropped.is_empty()
        && let Some(Value::Array(edges)) = graph.get_mut("edges")
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
fn repair_tables(graph: &mut Value, base: &Value, fixes: &mut Fixes) -> Result<()> {
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
        if let Some(Value::Array(rows)) = resolve_mut(graph, &table_path) {
            repair_table(rows, &table_path, previous, fixes)?;
        }
    }
    Ok(())
}

/// Each list value `base` stores in a template field, by node id and field name.
fn stored_tables(base: &Value) -> HashMap<(&str, &str), &Value> {
    let mut stored = HashMap::new();
    for node in base
        .get("nodes")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        let (Some(id), Some(template)) = (
            node.get("id").and_then(Value::as_str),
            node.pointer("/data/node/template")
                .and_then(Value::as_object),
        ) else {
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
    rows: &mut Vec<Value>,
    table_path: &[PathPart],
    previous: Option<&Value>,
    fixes: &mut Fixes,
) -> Result<()> {
    let id_key = NODE_SCHEMA.table.id_key().unwrap_or("_id");
    let position_key = NODE_SCHEMA.table.position.as_deref().unwrap_or("_pos");
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
    rows.retain(Value::is_object);

    let missing: Vec<usize> = (0..rows.len())
        .filter(|index| !rows[*index].get(position_key).is_some_and(is_row_position))
        .collect();
    let mut seen = HashSet::new();
    for (index, row) in rows.iter_mut().enumerate() {
        let valid = valid_id(row.get(id_key)).map(str::to_owned);
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
fn generate_node_id(
    node: &Map<String, Value>,
    index: usize,
    used: &HashSet<String>,
) -> Result<String> {
    let prefix = node
        .get("data")
        .and_then(|data| data.get("type"))
        .and_then(Value::as_str)
        .filter(|kind| !kind.is_empty())
        .unwrap_or("node");
    let seed = format!("{index}:{}", canonical_json(&Value::Object(node.clone()))?);
    for attempt in 0.. {
        let candidate = format!("{prefix}-{}", short_digest(&format!("{seed}:{attempt}")));
        if !used.contains(&candidate) {
            return Ok(candidate);
        }
    }
    unreachable!("some attempt yields an unused id")
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
