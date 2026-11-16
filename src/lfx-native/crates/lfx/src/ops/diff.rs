//! Deriving operations from two whole flow graphs.
//!
//! [`diff_flow_data`] gives the operations a client would send for a
//! whole-flow save. [`derive_flow_operations`] replays them and requires the
//! result to equal the target. A mismatch is a bug, and the save fails.
//!
//! The result has this shape:
//!
//! - at most one operation of each type, in the order `delete_edges`,
//!   `delete_nodes`, `add_nodes`, `update_nodes`, `add_edges`. Deletions keep
//!   the base order, and the rest keep the target order;
//! - nodes, edges and table rows match by id. Array order is never a change;
//! - inside a node, only the paths under `whole_values.recursed` in
//!   `node_schema.json` split into their keys. Other values are written whole;
//! - a template field has these units: its value, its definition and each
//!   toggle. A change to one key writes its whole unit;
//! - a keyed list is written per item and per key inside an item. A move is a
//!   write to `__pos__`. A list without a unique key and a position on every
//!   item is written whole;
//! - a changed edge is deleted and added again;
//! - view state is never recorded. Example: two spellings of one handle are
//!   not a change.

use crate::ops::maps::{HashSet, IndexMap, State};
use crate::value::{AnyMap, AnyValue};

use crate::ops::apply::ApplyOptions;
use crate::ops::canonical::{Proven, graphs_equal_given, is_row_position, values_equal};
use crate::ops::edges::edge_changed;
use crate::ops::error::{Error, Result};
use crate::ops::ops::{AsKey, FieldUpdate, NodePath, Operation, Path, PathExt, Segment};
use crate::ops::schema::{KeySet, KeyedList, NODE_SCHEMA, OUTPUTS_PATH, TEMPLATE_PATH};
use crate::ops::state::GraphState;
use crate::ops::validate::{Numbers, validate_flow_data};

/// Operations that turn one graph into another, verified by replay.
#[derive(Debug, Clone, PartialEq)]
pub struct Derived {
    /// The operations, as the engine records them.
    pub operations: Vec<Operation>,
    /// The graph the operations replay to.
    pub flow_data: AnyValue,
}

/// The ordered operations that turn `base` into `target`.
///
/// It checks `base` structurally and `target` fully, so a broken target
/// fails here and not as a replay mismatch.
///
/// # Errors
///
/// A graph breaks the rules.
pub fn diff_flow_data(base: &AnyValue, target: &AnyValue) -> Result<Vec<Operation>> {
    validate_flow_data(base, Numbers::Skip, "flow.data", None)?;
    validate_flow_data(target, Numbers::Check, "target flow.data", None)?;
    diff_proving(base, target, None)
}

/// [`diff_flow_data`] for graphs that passed its checks, recording in
/// `proven` each base node it finds equal to its target node.
fn diff_proving(
    base: &AnyValue,
    target: &AnyValue,
    mut proven: Option<&mut Proven>,
) -> Result<Vec<Operation>> {
    let base_nodes = by_id(base, "nodes");
    let target_nodes = by_id(target, "nodes");
    let base_edges = by_id(base, "edges");
    let target_edges = by_id(target, "edges");

    let mut changed_edges = HashSet::default();
    for (id, edge) in &target_edges {
        if let Some(before) = base_edges.get(id)
            && edge_changed(before, edge)?
        {
            changed_edges.insert(*id);
        }
    }
    let no_change = HashSet::default();
    let deleted_edges = gone(&base_edges, &target_edges, &changed_edges);
    let added_edges = added(
        &base_edges,
        &target_edges,
        &changed_edges,
        &NODE_SCHEMA.edge_view_state,
    )?;
    let deleted_nodes = gone(&base_nodes, &target_nodes, &no_change);
    let added_nodes = added(
        &base_nodes,
        &target_nodes,
        &no_change,
        &NODE_SCHEMA.node_view_state,
    )?;

    let mut node_updates = Vec::new();
    for (id, node) in &target_nodes {
        if let Some(before) = base_nodes.get(id) {
            // Skip the walk for an equal node: most nodes of a save are
            // unchanged. The walk cannot fail on an equal node.
            if before == node {
                if let Some(proven) = proven.as_deref_mut() {
                    proven.insert(
                        before.entries_ptr(),
                        (AnyMap::clone(before), node.entries_ptr()),
                    );
                }
                continue;
            }
            NodeDiff {
                id,
                updates: &mut node_updates,
            }
            .object(before, node, &mut Vec::new())?;
        }
    }

    Ok([
        (!deleted_edges.is_empty()).then(|| Operation::DeleteEdges(deleted_edges)),
        (!deleted_nodes.is_empty()).then(|| Operation::DeleteNodes(deleted_nodes)),
        (!added_nodes.is_empty()).then(|| Operation::AddNodes(added_nodes)),
        (!node_updates.is_empty()).then(|| Operation::UpdateNodes(node_updates)),
        (!added_edges.is_empty()).then(|| Operation::AddEdges(added_edges)),
    ]
    .into_iter()
    .flatten()
    .collect())
}

/// The ids in `base` that `target` drops or `replaced` names.
fn gone(
    base: &IndexMap<&str, &AnyMap>,
    target: &IndexMap<&str, &AnyMap>,
    replaced: &HashSet<&str>,
) -> Vec<String> {
    base.keys()
        .filter(|id| !target.contains_key(*id) || replaced.contains(*id))
        .map(|id| (*id).to_owned())
        .collect()
}

/// The entries of `target` that `base` lacks or `replaced` names, without
/// their view state.
fn added<T: TryFrom<AnyMap, Error = Error>>(
    base: &IndexMap<&str, &AnyMap>,
    target: &IndexMap<&str, &AnyMap>,
    replaced: &HashSet<&str>,
    view_state: &KeySet,
) -> Result<Vec<T>> {
    target
        .iter()
        .filter(|(id, _)| !base.contains_key(*id) || replaced.contains(*id))
        .map(|(_, entry)| T::try_from(without(entry, |key| view_state.contains(key))))
        .collect()
}

/// Diff two graphs, and return the forward operations with the replayed graph.
///
/// # Errors
///
/// A graph breaks the rules, or the operations do not replay to `target`.
pub fn derive_flow_operations(base: AnyValue, target: &AnyValue) -> Result<Derived> {
    validate_flow_data(&base, Numbers::Skip, "flow.data", None)?;
    validate_flow_data(target, Numbers::Check, "target flow.data", None)?;
    derive_checked(base, target)
}

/// [`derive_flow_operations`] for graphs that have passed its checks: `base`
/// structurally, and `target` fully.
pub(crate) fn derive_checked(base: AnyValue, target: &AnyValue) -> Result<Derived> {
    let mut proven = Proven::default();
    let operations = diff_proving(&base, target, Some(&mut proven))?;
    let options = ApplyOptions {
        forward: true,
        ..ApplyOptions::default()
    };
    let mut state = GraphState::from_checked(base)?;
    let applied = state.apply(operations, options)?;
    let flow_data = state.into_value();
    // The check skips the nodes the diff found equal.
    if !graphs_equal_given(&flow_data, target, Some(&proven))? {
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
fn by_id<'g>(graph: &'g AnyValue, key: &str) -> IndexMap<&'g str, &'g AnyMap> {
    graph
        .get(key)
        .and_then(AnyValue::as_array)
        .into_iter()
        .flatten()
        .filter_map(AnyValue::as_object)
        .filter_map(|entry| Some((entry.get("id")?.as_str()?, entry)))
        .collect()
}

fn without(map: &AnyMap, hidden: impl Fn(&str) -> bool) -> AnyMap {
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
    /// Record a `set_field`. The caller passes its own copy of the path.
    fn set(&mut self, path: Path, value: &AnyValue) -> Result<()> {
        let path = NodePath::try_from(path)?;
        self.updates
            .push(FieldUpdate::set(self.id, path, value.clone()));
        Ok(())
    }

    /// Record a `delete_field`, with its own copy of the path like [`Self::set`].
    fn delete(&mut self, path: Path) -> Result<()> {
        let path = NodePath::try_from(path)?;
        self.updates.push(FieldUpdate::delete(self.id, path));
        Ok(())
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

    /// Diff an object the schema splits. Each step pushes its segment onto
    /// `path` and pops it when done.
    fn object(&mut self, base: &AnyMap, target: &AnyMap, path: &mut Path) -> Result<()> {
        for (key, value) in target {
            if Self::skipped(path, key) {
                continue;
            }
            path.push(Segment::Key(key.to_string()));
            match base.get(key) {
                None => self.set(path.clone(), value)?,
                Some(previous) => {
                    if !self.split(previous, value, path)? && !values_equal(previous, value)? {
                        self.set(path.clone(), value)?;
                    }
                }
            }
            path.pop();
        }
        for key in base.keys() {
            if !target.contains_key(key) && !Self::skipped(path, key) {
                path.push(Segment::Key(key.to_string()));
                self.delete(path.clone())?;
                path.pop();
            }
        }
        Ok(())
    }

    /// Diff a value the schema splits further. Returns false when it is written whole.
    fn split(&mut self, base: &AnyValue, target: &AnyValue, path: &mut Path) -> Result<bool> {
        let recursed = NODE_SCHEMA
            .recursed_paths
            .iter()
            .any(|recursed| path.equals(recursed));
        if recursed {
            // Validation keeps the node's data, data.node and template objects.
            if let (AnyValue::Object(base), AnyValue::Object(target)) = (base, target) {
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
                .keyed_list_at(&AnyValue::Null, &OUTPUTS_PATH)
                .ok_or_else(|| Error::invalid("node_schema.json declares no outputs list"))?;
            let mut items = Vec::new();
            if keyed_list(keyed, base, target, path, &mut items)? {
                self.write_all(items)?;
                return Ok(true);
            }
        }
        Ok(false)
    }

    fn write_all(&mut self, writes: Vec<Write<'_>>) -> Result<()> {
        for write in writes {
            match write {
                Write::Set { path, value } => self.set(path, value)?,
                Write::Delete { path } => self.delete(path)?,
            }
        }
        Ok(())
    }

    /// Diff a template field unit by unit. Returns false for a key that is not a field.
    fn field(&mut self, base: &AnyValue, target: &AnyValue, path: &mut Path) -> Result<bool> {
        let (AnyValue::Object(base_field), AnyValue::Object(target_field)) = (base, target) else {
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
        let mut written: HashSet<&str> = HashSet::default();

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
                    self.write_all(writes)?;
                }
            } else if written.contains(key) {
                path.push(Segment::Key((*key).to_owned()));
                self.set(path.clone(), value)?;
                path.pop();
            }
        }
        for key in base.keys() {
            if !target.contains_key(key) && written.contains(key) {
                path.push(Segment::Key((*key).to_owned()));
                self.delete(path.clone())?;
                path.pop();
            }
        }
        Ok(true)
    }
}

/// A template field's keys and values, without its display-only keys.
fn visible_field_keys(field: &AnyMap) -> IndexMap<&str, &AnyValue> {
    field
        .iter()
        .filter(|(key, _)| !NODE_SCHEMA.field_view_state.contains(key.as_str()))
        .map(|(key, value)| (key.as_str(), value))
        .collect()
}

/// Whether `key` is added, removed or changed between two fields.
fn key_changed(
    base: &IndexMap<&str, &AnyValue>,
    target: &IndexMap<&str, &AnyValue>,
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
    base: &IndexMap<&str, &AnyValue>,
    target: &IndexMap<&str, &AnyValue>,
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
    Set { path: Path, value: &'v AnyValue },
    Delete { path: Path },
}

/// Diff a keyed list item by item. Returns false when it has to be written whole.
/// `path` names the list.
fn keyed_list<'v>(
    keyed: &KeyedList,
    base: &'v AnyValue,
    target: &'v AnyValue,
    path: &mut Path,
    writes: &mut Vec<Write<'v>>,
) -> Result<bool> {
    let (Some(base_items), Some(target_items)) =
        (items_by_key(keyed, base), items_by_key(keyed, target))
    else {
        return Ok(false);
    };
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
    target: &'v AnyMap,
    base: &'v AnyMap,
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
            path.push(Segment::Key(key.to_string()));
            writes.push(Write::Set {
                path: path.clone(),
                value,
            });
            path.pop();
        }
    }
    for key in base.keys() {
        if !target.contains_key(key) {
            path.push(Segment::Key(key.to_string()));
            writes.push(Write::Delete { path: path.clone() });
            path.pop();
        }
    }
    Ok(())
}

/// A list by item key, or `None` when an item has no unique key or no
/// numeric position. Writing such a legacy list whole brings it within the rules.
fn items_by_key<'v>(
    keyed: &KeyedList,
    items: &'v AnyValue,
) -> Option<IndexMap<&'v str, &'v AnyValue>> {
    let AnyValue::Array(items) = items else {
        return None;
    };
    let mut by_key = IndexMap::with_capacity_and_hasher(items.len(), State::default());
    for item in items {
        let key = keyed.key_of(item).filter(|key| !key.is_empty())?;
        let map = item.as_object()?;
        if by_key.contains_key(key) {
            return None;
        }
        if !map.get(&keyed.position).is_some_and(is_row_position) {
            return None;
        }
        by_key.insert(key, item);
    }
    Some(by_key)
}
