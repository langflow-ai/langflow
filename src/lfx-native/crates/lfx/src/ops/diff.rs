//! Deriving operations from two whole flow graphs.
//!
//! A whole-flow save hands the server the graph it wants stored.
//! [`diff_flow_data`] expresses the change from the stored graph as the
//! operations a client would have sent for it, and
//! [`derive_flow_operations`] proves they are right by replaying them and
//! requiring the canonical result to equal the target exactly. The diff
//! never falls back to replacing the whole graph: operations can express
//! every valid change, so a mismatch is a bug and the save fails.
//!
//! Shape of the result, so whole-flow saves and future operation submissions
//! record the same history:
//!
//! - at most one operation of each type, in the order `delete_edges`,
//!   `delete_nodes`, `add_nodes`, `update_nodes`, `add_edges`, each listing
//!   every item it applies to: deletions in the order the stored graph lists
//!   them, everything else in the order the target lists it. Nothing is
//!   sorted;
//! - nodes, edges and table rows are matched by id, and array order is never
//!   a change;
//! - inside a node, the diff follows `node_schema.json`: it splits only the
//!   paths the schema lists under `whole_values.recursed` into their keys.
//!   Every other value is written whole when it changes;
//! - a template field is written in units: its value (`value` with the keys
//!   that qualify it), its definition (every other key), and each toggle.
//!   When any key of a unit changes, the whole unit is written. A new field
//!   is one write, a removed field one delete;
//! - keyed lists (outputs, tool actions, table rows) are written per item, at
//!   the item's key, and per key inside an item. A natural-key list whose order
//!   changed, and a table that is not keyed by row ids on both sides, is
//!   written whole;
//! - an edge that changed in any way is deleted and added again;
//! - view state is never recorded, and two spellings of one handle are not a
//!   change. Every top-level key other than `nodes` and `edges` is view
//!   state.

use std::collections::HashSet;

use indexmap::IndexMap;
use serde_json::{Map, Value};

use crate::ops::apply::{ApplyOptions, apply_flow_operations};
use crate::ops::canonical::{graphs_equal, is_row_position, values_equal};
use crate::ops::edges::edge_changed;
use crate::ops::error::{Error, Result};
use crate::ops::ops::{AsKey, FieldUpdate, Operation, Path, PathExt, Segment};
use crate::ops::schema::{KeyedList, ListKind, NODE_SCHEMA, OUTPUTS_PATH, TEMPLATE_PATH};
use crate::ops::validate::{Numbers, validate_flow_data};

/// Operations that turn one graph into another, verified by replay.
#[derive(Debug, Clone, PartialEq)]
pub struct Derived {
    /// The operations, as the engine records them.
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
    validate_flow_data(base, Numbers::Skip, "flow.data", None)?;
    validate_flow_data(target, Numbers::Check, "target flow.data", None)?;

    let base_nodes = by_id(base, "nodes");
    let target_nodes = by_id(target, "nodes");
    let base_edges = by_id(base, "edges");
    let target_edges = by_id(target, "edges");

    let mut changed_edges = HashSet::new();
    for (id, edge) in &target_edges {
        if let Some(before) = base_edges.get(id)
            && edge_changed(before, edge)?
        {
            changed_edges.insert(*id);
        }
    }
    let deleted_edges: Vec<String> = base_edges
        .keys()
        .filter(|id| !target_edges.contains_key(*id) || changed_edges.contains(*id))
        .map(|id| (*id).to_owned())
        .collect();
    let added_edges: Vec<Map<String, Value>> = target_edges
        .iter()
        .filter(|(id, _)| !base_edges.contains_key(*id) || changed_edges.contains(*id))
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
            NodeDiff {
                id,
                updates: &mut node_updates,
            }
            .object(before, node, &mut Vec::new())?;
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
    if !added_edges.is_empty() {
        operations.push(Operation::AddEdges(added_edges));
    }
    Ok(operations)
}

/// Diff two graphs and prove the result replays exactly.
///
/// Returns the operations, as the engine records them, together with the
/// replayed graph.
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

// --- Nodes ---------------------------------------------------------------------------

/// The writes that turn one node into another.
#[derive(Debug)]
struct NodeDiff<'a> {
    id: &'a str,
    updates: &'a mut Vec<FieldUpdate>,
}

impl NodeDiff<'_> {
    /// Record a `set_field`. The walk shares one path, so a caller passes
    /// its own copy: the one copy the write needs.
    fn set(&mut self, path: Path, value: &Value) {
        self.updates
            .push(FieldUpdate::set(self.id, path, value.clone()));
    }

    /// Record a `delete_field`, with its own copy of the path like [`Self::set`].
    fn delete(&mut self, path: Path) {
        self.updates.push(FieldUpdate::delete(self.id, path));
    }

    /// The keys never written at a path the diff splits, besides a node's identity.
    fn skipped(path: &[Segment], key: &str) -> bool {
        if path.is_empty() {
            key == "id" || NODE_SCHEMA.node_view_state.contains(key)
        } else if path.equals(&["data", "node"]) {
            NODE_SCHEMA.node_data_view_state.contains(key)
        } else if path.equals(&TEMPLATE_PATH) {
            NODE_SCHEMA.template_view_state.contains(key)
        } else {
            false
        }
    }

    /// Diff an object the schema splits: split its children where the schema does, write the others whole.
    ///
    /// The walk shares one `path`: each step pushes its segment and pops it
    /// when done. An error ends the whole diff, so it leaves the path as it is.
    fn object(
        &mut self,
        base: &Map<String, Value>,
        target: &Map<String, Value>,
        path: &mut Path,
    ) -> Result<()> {
        for (key, value) in target {
            if Self::skipped(path, key) {
                continue;
            }
            path.push(Segment::Key(key.clone()));
            match base.get(key) {
                None => self.set(path.clone(), value),
                Some(previous) => {
                    if !self.split(previous, value, path)? && !values_equal(previous, value)? {
                        self.set(path.clone(), value);
                    }
                }
            }
            path.pop();
        }
        for key in base.keys() {
            if !target.contains_key(key) && !Self::skipped(path, key) {
                path.push(Segment::Key(key.clone()));
                self.delete(path.clone());
                path.pop();
            }
        }
        Ok(())
    }

    /// Diff a value the schema splits further. Returns false when it is written whole.
    fn split(&mut self, base: &Value, target: &Value, path: &mut Path) -> Result<bool> {
        let recursed = NODE_SCHEMA
            .recursed_paths
            .iter()
            .any(|recursed| path.equals(recursed));
        if recursed {
            // Validation keeps the node's data, data.node and template objects.
            if let (Value::Object(base), Value::Object(target)) = (base, target) {
                self.object(base, target, path)?;
                return Ok(true);
            }
            return Ok(false);
        }
        if path.len() == TEMPLATE_PATH.len() + 1 && path.has_start(&TEMPLATE_PATH) {
            return self.field(base, target, path);
        }
        if path.equals(&OUTPUTS_PATH) {
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
                Write::Set { path, value } => self.set(path, value),
                Write::Delete { path } => self.delete(path),
            }
        }
    }

    /// Diff a template field unit by unit. Returns false for a key that is not a field.
    fn field(&mut self, base: &Value, target: &Value, path: &mut Path) -> Result<bool> {
        let (Value::Object(base_field), Value::Object(target_field)) = (base, target) else {
            return Ok(false);
        };
        let base = visible_field_keys(base_field);
        let target = visible_field_keys(target_field);
        let all_keys: Vec<&str> = base
            .keys()
            .chain(target.keys().filter(|key| !base.contains_key(*key)))
            .copied()
            .collect();
        let in_value = |key: &str| NODE_SCHEMA.value_unit.iter().any(|unit| unit == key);
        let is_toggle = |key: &str| NODE_SCHEMA.toggles.iter().any(|toggle| toggle == key);
        let mut written: HashSet<&str> = HashSet::new();

        // The definition is every key outside the value and the toggles, written together.
        let definition: Vec<&str> = all_keys
            .iter()
            .copied()
            .filter(|key| !in_value(key) && !is_toggle(key))
            .collect();
        if any_changed(&base, &target, &definition)? {
            written.extend(&definition);
        }
        // Each toggle is a unit of its own.
        for &key in all_keys.iter().filter(|key| is_toggle(key)) {
            if key_changed(&base, &target, key)? {
                written.insert(key);
            }
        }
        // The value is `value` with the keys that qualify it. A keyed list
        // value is written item by item instead, when both sides allow it.
        let field_name = path[TEMPLATE_PATH.len()].as_key().unwrap_or_default();
        let keyed = NODE_SCHEMA.field_value_list(field_name, target_field);
        let mut item_writes = Vec::new();
        let per_item = match (keyed, base.get("value"), target.get("value")) {
            (Some(keyed), Some(base_value), Some(target_value)) => {
                path.push(Segment::Key("value".to_owned()));
                let per_item = keyed_list(keyed, base_value, target_value, path, &mut item_writes)?;
                path.pop();
                per_item
            }
            _ => false,
        };
        let value_keys: Vec<&str> = all_keys
            .iter()
            .copied()
            .filter(|key| in_value(key) && !(per_item && *key == "value"))
            .collect();
        if any_changed(&base, &target, &value_keys)? {
            written.extend(&value_keys);
        }

        // Write in the target's key order, the item writes where `value` stands.
        let mut item_writes = Some(item_writes);
        for (key, value) in &target {
            if *key == "value" && per_item {
                if let Some(writes) = item_writes.take() {
                    self.write_all(writes);
                }
            } else if written.contains(key) {
                path.push(Segment::Key((*key).to_owned()));
                self.set(path.clone(), value);
                path.pop();
            }
        }
        for key in base.keys() {
            if !target.contains_key(key) && written.contains(key) {
                path.push(Segment::Key((*key).to_owned()));
                self.delete(path.clone());
                path.pop();
            }
        }
        Ok(true)
    }
}

/// A template field's keys and values, without its display-only keys.
fn visible_field_keys(field: &Map<String, Value>) -> IndexMap<&str, &Value> {
    field
        .iter()
        .filter(|(key, _)| !NODE_SCHEMA.field_view_state.contains(key.as_str()))
        .map(|(key, value)| (key.as_str(), value))
        .collect()
}

/// Whether `key` is added, removed or changed between two fields.
fn key_changed(
    base: &IndexMap<&str, &Value>,
    target: &IndexMap<&str, &Value>,
    key: &str,
) -> Result<bool> {
    Ok(match (base.get(key), target.get(key)) {
        (Some(before), Some(after)) => !values_equal(before, after)?,
        (None, None) => false,
        _ => true,
    })
}

/// Whether any of `keys` is added, removed or changed between two fields.
fn any_changed(
    base: &IndexMap<&str, &Value>,
    target: &IndexMap<&str, &Value>,
    keys: &[&str],
) -> Result<bool> {
    for key in keys {
        if key_changed(base, target, key)? {
            return Ok(true);
        }
    }
    Ok(false)
}

/// One write the keyed-list diff found, before the node diff records it.
#[derive(Debug)]
enum Write<'v> {
    Set { path: Path, value: &'v Value },
    Delete { path: Path },
}

/// Diff a keyed list item by item. Returns false when it has to be written whole.
///
/// `path` names the list. Like the node walk, it pushes and pops each step,
/// and copies the path only into a write it records.
fn keyed_list<'v>(
    keyed: &KeyedList,
    base: &'v Value,
    target: &'v Value,
    path: &mut Path,
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
    for (key, item) in &target_items {
        path.push(Segment::Item((*key).to_owned()));
        match base_items.get(key) {
            None => writes.push(Write::Set {
                path: path.clone(),
                value: item,
            }),
            Some(previous) => {
                if let (Some(item_map), Some(previous)) = (item.as_object(), previous.as_object()) {
                    item_writes(item_map, previous, path, writes)?;
                }
            }
        }
        path.pop();
    }
    for key in base_items.keys() {
        if !target_items.contains_key(key) {
            path.push(Segment::Item((*key).to_owned()));
            writes.push(Write::Delete { path: path.clone() });
            path.pop();
        }
    }
    Ok(true)
}

/// The writes that turn one keyed-list item into another, key by key.
/// `path` names the item.
fn item_writes<'v>(
    target: &'v Map<String, Value>,
    base: &'v Map<String, Value>,
    path: &mut Path,
    writes: &mut Vec<Write<'v>>,
) -> Result<()> {
    for (key, value) in target {
        let before = base.get(key);
        let unchanged = match before {
            Some(before) => values_equal(before, value)?,
            None => false,
        };
        if !unchanged {
            path.push(Segment::Key(key.clone()));
            writes.push(Write::Set {
                path: path.clone(),
                value,
            });
            path.pop();
        }
    }
    for key in base.keys() {
        if !target.contains_key(key) {
            path.push(Segment::Key(key.clone()));
            writes.push(Write::Delete { path: path.clone() });
            path.pop();
        }
    }
    Ok(())
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
        if let Some(position) = keyed.position.as_deref()
            && !map.get(position).is_some_and(is_row_position)
        {
            return None;
        }
        by_key.insert(key, item);
    }
    Some(by_key)
}
