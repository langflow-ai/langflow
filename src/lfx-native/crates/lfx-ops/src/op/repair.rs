//! Repair: fix each rule violation that has exactly one fix.
//!
//! Repair does not touch a violation with more than one fix, such as two edges
//! into an input that accepts only one edge. The client chooses that fix.
//! Repair runs only when a request asks for it.

use crate::map::hash::{HashMap, HashSet};
use crate::flow_value;
use crate::json::{FlowObj, FlowValue};
use sha2::{Digest, Sha256};

use crate::compare::canonical_json;
use crate::flow::edge_handle::derive_missing_handle_forms;
use crate::flow::id::{new_edge_id, unused_id};
use crate::flow::list::{Renumber, fill_missing_positions};
use crate::flow::model::EntryExt;
use crate::flow::model::{FLOW_MODEL, KeyedList, NODE_OBJECT_PATHS};
use crate::json::pointer::resolve_mut;
use crate::json::pointer::{GraphPath, PathPart, Step, owned_path};
use crate::json::{is_finite_number, is_row_position};
use crate::node_input::table_input::match_row_ids;
use crate::rule::edge::find_edge_violations;
use crate::rule::list::{changed_keyed_lists, changed_tables};
use crate::state::plain::GraphPlain;
use crate::validate::{Numbers, Resolution, ViolationCode, validate_flow_data};
use crate::violation::error::Result;

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
    pub fn to_value(&self) -> FlowValue {
        let mut object = FlowObj::new();
        object.insert("code".into(), FlowValue::from(self.code.as_str()));
        object.insert(
            "path".into(),
            FlowValue::Array(self.path.iter().map(PathPart::to_value).collect()),
        );
        object.insert("action".into(), FlowValue::from(self.action));
        FlowValue::Object(object)
    }
}

/// A repaired graph and the fixes that made it.
#[derive(Debug, Clone, PartialEq)]
pub struct Repaired {
    /// The repaired graph.
    pub flow_data: FlowValue,
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

/// A copy of `flow` with each violation that has one fix fixed, and the fixes.
///
/// A new node id comes from the node's content, so a second repair gives the
/// same id. With `base`, repair also fixes the tables, lists and edges that
/// `flow` adds or changes. A row without an id takes the id of an identical
/// stored row.
///
/// # Errors
///
/// The graph also breaks a rule that only the client can fix.
pub fn repair_flow_data(flow: &FlowValue, base: Option<&FlowValue>) -> Result<Repaired> {
    let mut fixes = Fixes::default();
    let FlowValue::Object(flow) = flow else {
        fixes.add(ViolationCode::FlowDataNotObject, Vec::new());
        let empty = flow_value!({
            "nodes": FlowValue::Array(Vec::new()),
            "edges": FlowValue::Array(Vec::new()),
        });
        return Ok(Repaired {
            flow_data: empty,
            fixes: fixes.0,
        });
    };
    let mut repaired = FlowValue::Object(flow.clone());
    replace_non_finite(&mut repaired, &mut fixes);
    let FlowValue::Object(graph) = &mut repaired else {
        unreachable!("the repaired graph is an object");
    };
    for key in ["nodes", "edges"] {
        if !graph.get(key).is_some_and(FlowValue::is_array) {
            fixes.add(ViolationCode::CollectionNotList, path([key.into()]));
            graph.insert(key.to_owned(), FlowValue::Array(Vec::new()));
        }
    }
    let nodes = take_array(graph, "nodes");
    let nodes = repair_nodes(nodes, &mut fixes)?;
    let node_ids: HashSet<String> = nodes
        .iter()
        .filter_map(|node| node.non_empty_str("id").map(str::to_owned))
        .collect();
    graph.insert("nodes".into(), FlowValue::Array(nodes));
    let edges = take_array(graph, "edges");
    graph.insert(
        "edges".into(),
        FlowValue::Array(repair_edges(edges, &node_ids, &mut fixes)),
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

fn take_array(graph: &mut FlowObj, key: &str) -> Vec<FlowValue> {
    match graph.get_mut(key).map(std::mem::take) {
        Some(FlowValue::Array(items)) => items,
        _ => Vec::new(),
    }
}

/// Replace each number that is not finite with `null`.
/// It finds the paths first, so that it writes only where a number is invalid.
fn replace_non_finite(value: &mut FlowValue, fixes: &mut Fixes) {
    let mut paths = Vec::new();
    non_finite_paths(value, &mut Vec::new(), &mut paths);
    for path in paths {
        if let Some(value) = resolve_mut(value, &path) {
            *value = FlowValue::Null;
            fixes.add(ViolationCode::NonFiniteNumber, path);
        }
    }
}

fn non_finite_paths<'a>(value: &'a FlowValue, at: &mut Vec<Step<'a>>, paths: &mut Vec<GraphPath>) {
    let mut number = |step, value: &FlowValue| {
        if let FlowValue::Number(number) = value
            && !is_finite_number(number)
        {
            at.push(step);
            paths.push(owned_path(at));
            at.pop();
        }
    };
    match value {
        FlowValue::Object(map) => {
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
        FlowValue::Array(items) => {
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

fn repair_nodes(nodes: Vec<FlowValue>, fixes: &mut Fixes) -> Result<Vec<FlowValue>> {
    let mut kept: Vec<(usize, FlowObj)> = Vec::new();
    for (index, node) in nodes.into_iter().enumerate() {
        let FlowValue::Object(mut node) = node else {
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
    let mut seen = HashSet::default();
    for (index, node) in &mut kept {
        let Some(code) = id_fault(node, "id", &mut seen, NODE_ID_FAULTS) else {
            continue;
        };
        let old_id = node.get("id").cloned();
        fixes.add(code, path(["nodes".into(), (*index).into(), "id".into()]));
        let new_id = generate_node_id(node, *index, &used)?;
        used.insert(new_id.clone());
        seen.insert(new_id.clone());
        node.insert("id".into(), FlowValue::from(new_id.clone()));
        // The editor keeps a node's own id in data.id; follow a rename there.
        if let Some(FlowValue::Object(data)) = node.get_mut("data") {
            let follows = match data.get("id") {
                None | Some(FlowValue::Null) => true,
                Some(data_id) => Some(data_id) == old_id.as_ref(),
            };
            if follows {
                data.insert("id".into(), FlowValue::from(new_id));
            }
        }
    }
    Ok(kept
        .into_iter()
        .map(|(_, node)| FlowValue::Object(node))
        .collect())
}

/// The id faults of nodes, edges and table rows: missing, then duplicate.
const NODE_ID_FAULTS: [ViolationCode; 2] =
    [ViolationCode::NodeIdMissing, ViolationCode::NodeIdDuplicate];
const EDGE_ID_FAULTS: [ViolationCode; 2] =
    [ViolationCode::EdgeIdMissing, ViolationCode::EdgeIdDuplicate];
const ROW_ID_FAULTS: [ViolationCode; 2] = [
    ViolationCode::TableRowIdMissing,
    ViolationCode::TableRowIdDuplicate,
];

/// What is wrong with the id at `key`: missing, or already in `seen`.
/// A good id goes into `seen`.
fn id_fault(
    entry: &impl EntryExt,
    key: &str,
    seen: &mut HashSet<String>,
    [missing, duplicate]: [ViolationCode; 2],
) -> Option<ViolationCode> {
    match entry.non_empty_str(key) {
        Some(id) if seen.insert(id.to_owned()) => None,
        Some(_) => Some(duplicate),
        None => Some(missing),
    }
}

fn repair_node_objects(node: &mut FlowObj, index: usize, fixes: &mut Fixes) {
    // A valid node stays shared. Do not detach its objects just to inspect them.
    if NODE_OBJECT_PATHS.iter().all(|path| {
        let mut value = node.get(path[0]);
        for key in &path[1..] {
            value = value.and_then(|value| value.get(*key));
        }
        value.is_some_and(FlowValue::is_object)
    }) {
        return;
    }
    let mut parent = node;
    for object_path in NODE_OBJECT_PATHS {
        let key = object_path[object_path.len() - 1];
        if !parent.get(key).is_some_and(FlowValue::is_object) {
            let parts = ["nodes".into(), index.into()]
                .into_iter()
                .chain(object_path.iter().map(|part| PathPart::from(*part)));
            fixes.add(ViolationCode::NodeDataNotObject, path(parts));
            parent.insert(key.to_owned(), FlowValue::Object(FlowObj::new()));
        }
        let Some(FlowValue::Object(child)) = parent.get_mut(key) else {
            return;
        };
        parent = child;
    }
}

fn repair_edges(
    edges: Vec<FlowValue>,
    node_ids: &HashSet<String>,
    fixes: &mut Fixes,
) -> Vec<FlowValue> {
    let mut kept: Vec<(usize, FlowObj)> = Vec::new();
    for (index, edge) in edges.into_iter().enumerate() {
        let FlowValue::Object(edge) = edge else {
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
                .and_then(FlowValue::as_str)
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
    let mut seen = HashSet::default();
    for (index, edge) in &mut kept {
        let Some(code) = id_fault(edge, "id", &mut seen, EDGE_ID_FAULTS) else {
            continue;
        };
        fixes.add(code, path(["edges".into(), (*index).into(), "id".into()]));
        // A random id, like the editor's newEdgeId().
        let new_id = unused_id(&used, new_edge_id);
        used.insert(new_id.clone());
        seen.insert(new_id.clone());
        edge.insert("id".into(), FlowValue::from(new_id));
    }
    kept.into_iter()
        .map(|(_, edge)| FlowValue::Object(edge))
        .collect()
}

/// Fix the edge violations that have one fix, in the edges `graph` adds to `base`.
fn repair_added_edges(graph: &mut FlowValue, base: &FlowValue, fixes: &mut Fixes) -> Result<()> {
    let mut dropped = HashSet::default();
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
        } else if let Some(FlowValue::Object(edge)) = graph
            .get_mut("edges")
            .and_then(|edges| edges.get_mut(index))
        {
            derive_missing_handle_forms(edge);
        }
    }
    if !dropped.is_empty()
        && let Some(FlowValue::Array(edges)) = graph.get_mut("edges")
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
fn repair_tables(graph: &mut FlowValue, base: &FlowValue, fixes: &mut Fixes) -> Result<()> {
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
    for (table_input_path, node_id, field) in tables {
        let previous = stored.get(&(node_id.as_str(), field.as_str())).copied();
        if let Some(FlowValue::Array(rows)) = resolve_mut(graph, &table_input_path) {
            repair_table(rows, &table_input_path, previous, fixes)?;
        }
    }
    Ok(())
}

/// Give a position to each list item without one, in the lists that `graph`
/// changes relative to `base`. Example: an item between positions 1 and 2 gets 1.5.
fn repair_list_positions(graph: &mut FlowValue, base: &FlowValue, fixes: &mut Fixes) -> Result<()> {
    let lists: Vec<(GraphPath, &'static KeyedList)> = changed_keyed_lists(base, graph)?
        .into_iter()
        .map(|changed| (changed.path, changed.keyed))
        .collect();
    for (list_path, keyed) in lists {
        let Some(FlowValue::Array(items)) = resolve_mut(graph, &list_path) else {
            continue;
        };
        for index in fill_missing_positions(keyed, items, Renumber::Never) {
            let item_path = list_path
                .iter()
                .cloned()
                .chain([index.into(), keyed.position.as_str().into()]);
            fixes.add(ViolationCode::ListItemMissingPos, path(item_path));
        }
    }
    Ok(())
}

/// Each list value `base` stores in a template field, by node id and field name.
fn stored_tables(base: &FlowValue) -> HashMap<(&str, &str), &FlowValue> {
    let mut stored = HashMap::default();
    for node in base
        .get("nodes")
        .and_then(FlowValue::as_array)
        .into_iter()
        .flatten()
    {
        let (Some(id), Some(template)) =
            (node.get("id").and_then(FlowValue::as_str), node.template())
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

/// Fix one table in place, so that each row is an object with a unique id and a position.
fn repair_table(
    rows: &mut Vec<FlowValue>,
    table_input_path: &[PathPart],
    previous: Option<&FlowValue>,
    fixes: &mut Fixes,
) -> Result<()> {
    let id_key = &FLOW_MODEL.table_input_keys.id;
    let position_key = &FLOW_MODEL.table_input_keys.position;
    let row_path = |index: usize, key: Option<&str>| {
        path(
            table_input_path
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
    rows.retain(FlowValue::is_object);

    let missing: Vec<usize> = (0..rows.len())
        .filter(|index| !rows[*index].get(position_key).is_some_and(is_row_position))
        .collect();
    let mut seen = HashSet::default();
    for (index, row) in rows.iter_mut().enumerate() {
        let Some(code) = id_fault(row, id_key, &mut seen, ROW_ID_FAULTS) else {
            continue;
        };
        fixes.add(code, row_path(index, Some(id_key)));
        // match_row_ids gives this row the id of an identical stored row, or a new id.
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
    fill_missing_positions(&FLOW_MODEL.table_input, rows, Renumber::Never);
    Ok(())
}

/// A node id from the node's `data.type`, content and index. Example: `Text-a1B2c`.
fn generate_node_id(node: &FlowObj, index: usize, used: &HashSet<String>) -> Result<String> {
    let prefix = node
        .get("data")
        .and_then(|data| data.get("type"))
        .and_then(FlowValue::as_str)
        .filter(|kind| !kind.is_empty())
        .unwrap_or("node");
    let seed = format!(
        "{index}:{}",
        canonical_json(&FlowValue::Object(node.clone()))?
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

impl GraphPlain {
    /// A fixed copy and its fixes, as [`repair_flow_data`] returns them.
    ///
    /// # Errors
    ///
    /// What [`repair_flow_data`] fails with.
    pub fn repair(&self, base: Option<&Self>) -> Result<(Self, Vec<Fix>)> {
        if self.passed_against(base) {
            return Ok((self.checked_copy(base), Vec::new()));
        }
        let repaired = repair_flow_data(self.as_value(), base.map(Self::as_value))?;
        // Repair checks every rule on what it returns.
        Ok((Self::checked_new(repaired.flow_data, base), repaired.fixes))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::flow_value;

    #[test]
    fn repair_keeps_valid_node_objects_shared() {
        let source = flow_value!({"nodes":[{"id":"a","data":{"node":{"template":{"t":{"value":"unchanged"}}}}}],"edges":[]});
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
        let source: FlowValue = serde_json::from_str(
            r#"{"nodes":[],"edges":[],"first":{"bad":1e400},"second":{"keep":"text"}}"#,
        )
        .unwrap();
        let repaired = repair_flow_data(&source, None).unwrap();
        assert_eq!(repaired.flow_data["first"]["bad"], FlowValue::Null);
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
