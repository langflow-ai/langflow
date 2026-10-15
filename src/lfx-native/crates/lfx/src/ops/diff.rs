//! Deriving operations from two whole flow graphs.
//!
//! A whole-flow save hands the server the graph it wants stored.
//! [`diff_flow_data`] expresses the change from the stored graph as the
//! operations a client would have sent for it, and
//! [`derive_flow_operations`] proves they are right by replaying them and
//! requiring the canonical result to equal the target exactly. There is no
//! whole-graph replacement fallback: every valid transition is expressible in
//! the vocabulary, so a mismatch is a bug and the save must fail.
//!
//! Shape of the result, so whole-flow saves and future operation submissions
//! record the same history:
//!
//! - at most one operation of each type, in the order `delete_edges`,
//!   `delete_nodes`, `add_nodes`, `update_nodes`, `update_edges`, `add_edges`,
//!   `update_metadata`, each listing every item it applies to: deletions in
//!   the order the stored graph lists them, everything else in the order the
//!   target lists it. Nothing is sorted;
//! - nodes, edges and table rows are matched by id, and array order is never
//!   a change;
//! - inside a node, the diff follows `node_schema.json`: it splits only the
//!   paths the schema lists under `whole_values.recursed` into their keys.
//!   Every other value is written whole when it changes;
//! - a template field is written in units: its value (`value` with the keys
//!   that qualify it), its definition (every other key), and each toggle.
//!   When any key of a unit changes, the whole unit is written. A new field
//!   is one write, a removed field one delete;
//! - keyed lists (outputs, tool actions, table rows) are written per item by
//!   selector, and per key inside an item. A natural-key list whose order
//!   changed, and a table that is not keyed by row ids on both sides, is
//!   written whole;
//! - an edge that still connects the same two nodes is updated in place, key
//!   by key; one whose source or target changed is deleted and added again;
//! - view state is never recorded, and two spellings of one handle are not a
//!   change.

use std::collections::HashSet;

use indexmap::IndexMap;
use serde_json::{Map, Value};

use crate::ops::apply::{ApplyOptions, apply_flow_operations};
use crate::ops::canonical::{
    HANDLE_KEYS, graphs_equal, is_row_position, json_type, parse_handle, values_equal,
};
use crate::ops::error::{Error, Result};
use crate::ops::ops::{Change, FieldUpdate, Operation, Path, Segment};
use crate::ops::schema::{KeyedList, ListKind, NODE_SCHEMA};
use crate::ops::validate::validate_flow_data;

/// The keys of a template field that decide whether its value is a secret,
/// recorded with every write inside the field.
pub const TEMPLATE_FIELD_METADATA_KEYS: [&str; 6] = [
    "name",
    "type",
    "password",
    "load_from_db",
    "_input_type",
    "table_schema",
];

const TEMPLATE_PATH: [&str; 3] = ["data", "node", "template"];
const OUTPUTS_PATH: [&str; 3] = ["data", "node", "outputs"];
const EDGE_IDENTITY_KEYS: [&str; 3] = ["id", "source", "target"];

/// Operations that turn one graph into another, verified by replay.
#[derive(Debug, Clone, PartialEq)]
pub struct Derived {
    /// The operations as the engine normalized them, which is what gets recorded.
    pub operations: Vec<Operation>,
    /// The graph the operations replay to.
    pub flow_data: Value,
}

/// The ordered operations that turn `base` into `target`.
///
/// Both graphs must follow the engine's rules. `base` is stored data and is
/// checked structurally; `target` comes from outside and is checked fully, so
/// a broken target fails with the engine's own error rather than surfacing
/// later as a replay mismatch.
///
/// # Errors
///
/// A graph breaks the rules.
pub fn diff_flow_data(base: &Value, target: &Value) -> Result<Vec<Operation>> {
    validate_flow_data(base, false, "flow.data", None)?;
    validate_flow_data(target, true, "target flow.data", None)?;

    let base_nodes = by_id(base, "nodes");
    let target_nodes = by_id(target, "nodes");
    let base_edges = by_id(base, "edges");
    let target_edges = by_id(target, "edges");

    let ends =
        |edge: &Map<String, Value>| (edge.get("source").cloned(), edge.get("target").cloned());
    let reconnected: HashSet<&str> = target_edges
        .iter()
        .filter(|(id, edge)| {
            base_edges
                .get(*id)
                .is_some_and(|before| ends(before) != ends(edge))
        })
        .map(|(id, _)| *id)
        .collect();
    let deleted_edges: Vec<String> = base_edges
        .keys()
        .filter(|id| !target_edges.contains_key(*id) || reconnected.contains(*id))
        .map(|id| (*id).to_owned())
        .collect();
    let added_edges: Vec<Map<String, Value>> = target_edges
        .iter()
        .filter(|(id, _)| !base_edges.contains_key(*id) || reconnected.contains(*id))
        .map(|(_, edge)| without(edge, |key| NODE_SCHEMA.edge_view_state.contains(key)))
        .collect();
    let deleted_nodes: Vec<String> = base_nodes
        .keys()
        .filter(|id| !target_nodes.contains_key(*id))
        .map(|id| (*id).to_owned())
        .collect();
    let added_nodes: Vec<Map<String, Value>> = target_nodes
        .iter()
        .filter(|(id, _)| !base_nodes.contains_key(*id))
        .map(|(_, node)| without(node, |key| NODE_SCHEMA.node_view_state.contains(key)))
        .collect();

    let mut node_updates = Vec::new();
    for (id, node) in &target_nodes {
        if let Some(before) = base_nodes.get(id) {
            NodeDiff::new(id, node, &mut node_updates).object(before, node, &[])?;
        }
    }
    let mut edge_updates = Vec::new();
    for (id, edge) in &target_edges {
        if let Some(before) = base_edges.get(id)
            && !reconnected.contains(id)
        {
            diff_edge(id, before, edge, &mut edge_updates)?;
        }
    }

    let mut operations = Vec::new();
    if !deleted_edges.is_empty() {
        operations.push(Operation::DeleteEdges(deleted_edges));
    }
    if !deleted_nodes.is_empty() {
        operations.push(Operation::DeleteNodes(deleted_nodes));
    }
    if !added_nodes.is_empty() {
        operations.push(Operation::AddNodes(added_nodes));
    }
    if !node_updates.is_empty() {
        operations.push(Operation::UpdateNodes(node_updates));
    }
    if !edge_updates.is_empty() {
        operations.push(Operation::UpdateEdges(edge_updates));
    }
    if !added_edges.is_empty() {
        operations.push(Operation::AddEdges(added_edges));
    }
    if let Some(metadata) = diff_metadata(base, target)? {
        operations.push(metadata);
    }
    Ok(operations)
}

/// Diff two graphs and prove the result replays exactly.
///
/// Returns the operations as the engine normalized them, which is what gets
/// recorded, together with the replayed graph.
///
/// # Errors
///
/// A graph breaks the rules, or the operations do not replay to `target`,
/// which is a bug in the diff or the engine.
pub fn derive_flow_operations(base: Value, target: &Value) -> Result<Derived> {
    let operations = diff_flow_data(&base, target)?;
    let options = ApplyOptions {
        forward: true,
        ..ApplyOptions::default()
    };
    let (flow_data, applied) = apply_flow_operations(base, operations, options)?;
    if !graphs_equal(&flow_data, target)? {
        return Err(Error::replay(
            "derived operations do not replay to the target graph",
        ));
    }
    Ok(Derived {
        operations: applied.forward,
        flow_data,
    })
}

/// A validated graph's nodes or edges, by id, in the graph's order.
fn by_id<'g>(graph: &'g Value, key: &str) -> IndexMap<&'g str, &'g Map<String, Value>> {
    graph
        .get(key)
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_object)
        .filter_map(|entry| Some((entry.get("id")?.as_str()?, entry)))
        .collect()
}

fn without(map: &Map<String, Value>, hidden: impl Fn(&str) -> bool) -> Map<String, Value> {
    map.iter()
        .filter(|(key, _)| !hidden(key))
        .map(|(key, value)| (key.clone(), value.clone()))
        .collect()
}

fn key_path(path: &[Segment], key: &str) -> Path {
    path.iter()
        .cloned()
        .chain([Segment::Key(key.to_owned())])
        .collect()
}

fn is_path(path: &[Segment], expected: &[&str]) -> bool {
    path.len() == expected.len()
        && path
            .iter()
            .zip(expected)
            .all(|(segment, key)| segment.as_key() == Some(*key))
}

/// A `set_field` of `value`, declaring a type change from `previous`.
fn set(
    id: &str,
    path: Path,
    value: &Value,
    previous: Option<&Value>,
    template_field: Option<Map<String, Value>>,
) -> FieldUpdate {
    let from_type = previous
        .filter(|previous| json_type(previous) != json_type(value))
        .map(json_type);
    FieldUpdate {
        id: id.to_owned(),
        path,
        expect: None,
        change: Change::Set {
            value: value.clone(),
            from_type,
            template_field,
        },
    }
}

// --- Edges ---------------------------------------------------------------------------

fn diff_edge(
    id: &str,
    base: &Map<String, Value>,
    target: &Map<String, Value>,
    updates: &mut Vec<FieldUpdate>,
) -> Result<()> {
    let skip =
        |key: &str| EDGE_IDENTITY_KEYS.contains(&key) || NODE_SCHEMA.edge_view_state.contains(key);
    for (key, value) in target {
        if skip(key) {
            continue;
        }
        let Some(previous) = base.get(key) else {
            updates.push(set(id, vec![Segment::Key(key.clone())], value, None, None));
            continue;
        };
        let unchanged = if HANDLE_KEYS.contains(&key.as_str()) {
            values_equal(&handle_value(previous), &handle_value(value))?
        } else {
            values_equal(previous, value)?
        };
        if !unchanged {
            updates.push(set(
                id,
                vec![Segment::Key(key.clone())],
                value,
                Some(previous),
                None,
            ));
        }
    }
    for key in base.keys() {
        if !target.contains_key(key) && !skip(key) {
            updates.push(FieldUpdate::delete(id, vec![Segment::Key(key.clone())]));
        }
    }
    Ok(())
}

/// A handle string compares by the object it encodes, so two spellings of one handle are the same value.
fn handle_value(handle: &Value) -> Value {
    parse_handle(handle).map_or_else(|| handle.clone(), Value::Object)
}

// --- Nodes ---------------------------------------------------------------------------

/// The writes that turn one node into another.
struct NodeDiff<'a> {
    id: &'a str,
    /// The target node's template, whose fields' metadata writes inside a field record.
    template: Option<&'a Map<String, Value>>,
    updates: &'a mut Vec<FieldUpdate>,
}

impl<'a> NodeDiff<'a> {
    fn new(id: &'a str, target: &'a Map<String, Value>, updates: &'a mut Vec<FieldUpdate>) -> Self {
        let template = target
            .get("data")
            .and_then(|data| data.get("node"))
            .and_then(|node| node.get("template"))
            .and_then(Value::as_object);
        Self {
            id,
            template,
            updates,
        }
    }

    /// The metadata of the template field a path writes inside of.
    ///
    /// A path that sets a whole template field carries its metadata in the
    /// value already, and a path outside the template writes no field value,
    /// so only writes strictly inside one field need it recorded.
    fn field_metadata(&self, path: &[Segment]) -> Option<Map<String, Value>> {
        let depth = TEMPLATE_PATH.len();
        if path.len() <= depth + 1 || !is_path(&path[..depth], &TEMPLATE_PATH) {
            return None;
        }
        let field = self.template?.get(path[depth].as_key()?)?.as_object()?;
        let metadata: Map<String, Value> = TEMPLATE_FIELD_METADATA_KEYS
            .iter()
            .filter_map(|key| Some(((*key).to_owned(), field.get(*key)?.clone())))
            .collect();
        (!metadata.is_empty()).then_some(metadata)
    }

    fn set(&mut self, path: Path, value: &Value, previous: Option<&Value>) {
        let metadata = self.field_metadata(&path);
        self.updates
            .push(set(self.id, path, value, previous, metadata));
    }

    fn delete(&mut self, path: Path) {
        self.updates.push(FieldUpdate::delete(self.id, path));
    }

    /// The keys never written at a path the diff splits, besides a node's identity.
    fn skipped(path: &[Segment], key: &str) -> bool {
        if path.is_empty() {
            key == "id" || NODE_SCHEMA.node_view_state.contains(key)
        } else if is_path(path, &["data", "node"]) {
            NODE_SCHEMA.node_data_view_state.contains(key)
        } else if is_path(path, &TEMPLATE_PATH) {
            NODE_SCHEMA.template_view_state.contains(key)
        } else {
            false
        }
    }

    /// Diff an object the schema splits: split its children where the schema does, write the others whole.
    fn object(
        &mut self,
        base: &Map<String, Value>,
        target: &Map<String, Value>,
        path: &[Segment],
    ) -> Result<()> {
        for (key, value) in target {
            if Self::skipped(path, key) {
                continue;
            }
            let child_path = key_path(path, key);
            let Some(previous) = base.get(key) else {
                self.set(child_path, value, None);
                continue;
            };
            if self.child(previous, value, &child_path)? {
                continue;
            }
            if !values_equal(previous, value)? {
                self.set(child_path, value, Some(previous));
            }
        }
        for key in base.keys() {
            if !target.contains_key(key) && !Self::skipped(path, key) {
                self.delete(key_path(path, key));
            }
        }
        Ok(())
    }

    /// Diff a value the schema splits further. Returns false when it is written whole.
    fn child(&mut self, base: &Value, target: &Value, path: &[Segment]) -> Result<bool> {
        let recursed = NODE_SCHEMA.recursed_paths.iter().any(|recursed| {
            path.len() == recursed.len()
                && path
                    .iter()
                    .zip(recursed)
                    .all(|(a, b)| a.as_key() == Some(b))
        });
        if recursed {
            // Validation keeps the node's data, data.node and template objects.
            if let (Value::Object(base), Value::Object(target)) = (base, target) {
                self.object(base, target, path)?;
                return Ok(true);
            }
            return Ok(false);
        }
        if path.len() == TEMPLATE_PATH.len() + 1
            && is_path(&path[..TEMPLATE_PATH.len()], &TEMPLATE_PATH)
        {
            return self.field(base, target, path);
        }
        if is_path(path, &OUTPUTS_PATH) {
            let keyed = NODE_SCHEMA
                .keyed_list_at(&Value::Null, &OUTPUTS_PATH)
                .ok_or_else(|| Error::invalid("node_schema.json declares no outputs list"))?;
            let mut items = Vec::new();
            if keyed_list(keyed, base, target, path, &mut items)? {
                self.write_all(items);
                return Ok(true);
            }
        }
        Ok(false)
    }

    fn write_all(&mut self, writes: Vec<Write<'_>>) {
        for write in writes {
            match write {
                Write::Set {
                    path,
                    value,
                    previous,
                } => self.set(path, value, previous),
                Write::Delete { path } => self.delete(path),
            }
        }
    }

    /// Diff a template field unit by unit. Returns false for a key that is not a field.
    fn field(&mut self, base: &Value, target: &Value, path: &[Segment]) -> Result<bool> {
        let (Value::Object(base), Value::Object(target_field)) = (base, target) else {
            return Ok(false);
        };
        let hidden = |key: &str| NODE_SCHEMA.field_view_state.contains(key);
        let base: IndexMap<&str, &Value> = base
            .iter()
            .filter(|(key, _)| !hidden(key))
            .map(|(k, v)| (k.as_str(), v))
            .collect();
        let target: IndexMap<&str, &Value> = target_field
            .iter()
            .filter(|(key, _)| !hidden(key))
            .map(|(k, v)| (k.as_str(), v))
            .collect();
        let changed = |key: &str| -> Result<bool> {
            Ok(match (base.get(key), target.get(key)) {
                (Some(a), Some(b)) => !values_equal(a, b)?,
                (None, None) => false,
                _ => true,
            })
        };
        let any_changed = |keys: &mut dyn Iterator<Item = &str>| -> Result<bool> {
            for key in keys {
                if changed(key)? {
                    return Ok(true);
                }
            }
            Ok(false)
        };
        let all_keys: Vec<&str> = base
            .keys()
            .chain(target.keys().filter(|key| !base.contains_key(*key)))
            .copied()
            .collect();
        let in_value = |key: &str| NODE_SCHEMA.value_unit.iter().any(|unit| unit == key);
        let is_toggle = |key: &str| NODE_SCHEMA.toggles.iter().any(|toggle| toggle == key);

        let mut written: HashSet<&str> = HashSet::new();
        let definition: Vec<&str> = all_keys
            .iter()
            .copied()
            .filter(|key| !in_value(key) && !is_toggle(key))
            .collect();
        if any_changed(&mut definition.iter().copied())? {
            written.extend(&definition);
        }
        for key in all_keys.iter().copied().filter(|key| is_toggle(key)) {
            if changed(key)? {
                written.insert(key);
            }
        }

        let field_name = path[TEMPLATE_PATH.len()].as_key().unwrap_or_default();
        let value_path = key_path(path, "value");
        let keyed = NODE_SCHEMA.field_value_list(field_name, target_field);
        let mut item_writes = Vec::new();
        let per_item = match (keyed, base.get("value"), target.get("value")) {
            (Some(keyed), Some(base_value), Some(target_value)) => keyed_list(
                keyed,
                base_value,
                target_value,
                &value_path,
                &mut item_writes,
            )?,
            _ => false,
        };
        let value_keys: Vec<&str> = all_keys
            .iter()
            .copied()
            .filter(|key| in_value(key) && !(per_item && *key == "value"))
            .collect();
        if any_changed(&mut value_keys.iter().copied())? {
            written.extend(&value_keys);
        }

        let mut item_writes = Some(item_writes);
        for (key, value) in &target {
            if *key == "value" && per_item {
                if let Some(writes) = item_writes.take() {
                    self.write_all(writes);
                }
            } else if written.contains(key) {
                self.set(key_path(path, key), value, base.get(key).copied());
            }
        }
        for key in base.keys() {
            if !target.contains_key(key) && written.contains(key) {
                self.delete(key_path(path, key));
            }
        }
        Ok(true)
    }
}

/// One write the keyed-list diff found, before the node diff records it.
enum Write<'v> {
    Set {
        path: Path,
        value: &'v Value,
        previous: Option<&'v Value>,
    },
    Delete {
        path: Path,
    },
}

/// Diff a keyed list item by item. Returns false when it has to be written whole.
fn keyed_list<'v>(
    keyed: &KeyedList,
    base: &'v Value,
    target: &'v Value,
    path: &[Segment],
    writes: &mut Vec<Write<'v>>,
) -> Result<bool> {
    let (Some(base_items), Some(target_items)) =
        (items_by_key(keyed, base), items_by_key(keyed, target))
    else {
        return Ok(false);
    };
    if keyed.kind == ListKind::Natural {
        // A natural list's order is state; a table's order is its rows' positions.
        let kept = base_items
            .keys()
            .filter(|key| target_items.contains_key(*key));
        let added = target_items
            .keys()
            .filter(|key| !base_items.contains_key(*key));
        if !target_items.keys().eq(kept.chain(added)) {
            return Ok(false);
        }
    }
    let selector = |key: &str| match keyed.kind {
        ListKind::Table => Segment::ById(key.to_owned()),
        ListKind::Natural => Segment::ByKey(key.to_owned()),
    };
    let item_path = |key: &str| -> Path { path.iter().cloned().chain([selector(key)]).collect() };
    for (key, item) in &target_items {
        let Some(previous) = base_items.get(key) else {
            writes.push(Write::Set {
                path: item_path(key),
                value: item,
                previous: None,
            });
            continue;
        };
        let (Some(item_map), Some(previous)) = (item.as_object(), previous.as_object()) else {
            continue;
        };
        for (item_key, value) in item_map {
            let before = previous.get(item_key);
            let unchanged = match before {
                Some(before) => values_equal(before, value)?,
                None => false,
            };
            if !unchanged {
                writes.push(Write::Set {
                    path: key_path(&item_path(key), item_key),
                    value,
                    previous: before,
                });
            }
        }
        for item_key in previous.keys() {
            if !item_map.contains_key(item_key) {
                writes.push(Write::Delete {
                    path: key_path(&item_path(key), item_key),
                });
            }
        }
    }
    for key in base_items.keys() {
        if !target_items.contains_key(key) {
            writes.push(Write::Delete {
                path: item_path(key),
            });
        }
    }
    Ok(true)
}

/// A list by item key, or `None` when it cannot be written item by item.
///
/// That is a list whose items do not all carry a unique key, or a table whose
/// rows do not all carry a numeric position: such a list (a legacy table) is
/// written whole, which brings it within the rules.
fn items_by_key<'v>(keyed: &KeyedList, items: &'v Value) -> Option<IndexMap<&'v str, &'v Value>> {
    let Value::Array(items) = items else {
        return None;
    };
    let mut by_key = IndexMap::with_capacity(items.len());
    for item in items {
        let key = keyed.key_of(item).filter(|key| !key.is_empty())?;
        let map = item.as_object()?;
        if by_key.contains_key(key) {
            return None;
        }
        if keyed.kind == ListKind::Table
            && !map
                .get(keyed.position.as_deref()?)
                .is_some_and(is_row_position)
        {
            return None;
        }
        by_key.insert(key, item);
    }
    Some(by_key)
}

// --- Metadata ------------------------------------------------------------------------

fn diff_metadata(base: &Value, target: &Value) -> Result<Option<Operation>> {
    let empty = Map::new();
    let base = base.as_object().unwrap_or(&empty);
    let target = target.as_object().unwrap_or(&empty);
    let skip =
        |key: &str| key == "nodes" || key == "edges" || NODE_SCHEMA.flow_view_state.contains(key);
    let mut fields = Map::new();
    for (key, value) in target {
        if skip(key) {
            continue;
        }
        let unchanged = match base.get(key) {
            Some(previous) => values_equal(previous, value)?,
            None => false,
        };
        if !unchanged {
            fields.insert(key.clone(), value.clone());
        }
    }
    let delete_keys: Vec<String> = base
        .keys()
        .filter(|key| !skip(key) && !target.contains_key(*key))
        .cloned()
        .collect();
    if fields.is_empty() && delete_keys.is_empty() {
        return Ok(None);
    }
    Ok(Some(Operation::UpdateMetadata {
        fields,
        delete_keys,
    }))
}
