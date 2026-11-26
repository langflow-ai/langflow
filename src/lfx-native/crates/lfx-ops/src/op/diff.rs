//! Deriving operations from two whole flow graphs.
//!
//! [`diff_flow_data`] gives the operations a client would send
//! for a whole-flow save. [`derive_flow_operations`] replays
//! them and requires the result to equal the target. A mismatch
//! is a bug, and the save fails.
//!
//! The result has this shape:
//!
//! - at most one operation of each type, in the order
//!   `delete_edges`, `delete_nodes`, `add_nodes`,
//!   `update_nodes`, `add_edges`. Deletions keep the base
//!   order, and the rest keep the target order;
//! - nodes, edges and table rows match by id. Array order is
//!   never a change;
//! - inside a node, an object is diffed key by key, so a write
//!   holds only what changed. Any other value that changed is
//!   written whole;
//! - a keyed list is written per item and per key inside an
//!   item. A move is a write to `__pos__`. A list without a
//!   unique key and a position on every item is written whole;
//! - a changed edge is deleted and added again;
//! - view state is never recorded. Example: a change to a
//!   node's `selected` is not a change.

use std::borrow::Cow;

use crate::json::{FlowObj, FlowValue};
use crate::map::hash::{HashSet, IndexMap, State};

use crate::compare::{KnownEqual, graphs_equal_given, values_equal};
use crate::flow::deserialize::DeserializeError;
use crate::flow::model::{FLOW_MODEL, KeySet, KeyedList, TEMPLATE_PATH};
use crate::flow::path::{Path, PathExt, Segment};
use crate::json::is_row_position;
use crate::op::ApplyOptions;
use crate::op::operation::{FieldUpdate, NodePath, Operation};
use crate::rule::edge::edge_changed;
use crate::state::GraphState;
use crate::state::plain::GraphPlain;
use crate::validate::{Numbers, validate_flow_data};
use crate::violation::error::{Error, ErrorCode, ErrorKind, Result};

/// Operations that turn one graph into another, verified by
/// replay.
#[derive(Debug, Clone, PartialEq)]
pub struct Derived {
    /// The operations, as the engine records them.
    pub operations: Vec<Operation>,
    /// The graph the operations replay to.
    pub flow_data: FlowValue,
}

/// The ordered operations that turn `base` into `target`.
///
/// It checks `base` structurally and `target` fully, so a
/// broken target fails here and not as a replay mismatch.
///
/// # Errors
///
/// A graph breaks the rules.
pub fn diff_flow_data(base: &FlowValue, target: &FlowValue) -> Result<Vec<Operation>> {
    validate_flow_data(base, Numbers::Skip, "flow.data", None)?;
    validate_flow_data(target, Numbers::Check, "target flow.data", None)?;
    diff_proving(base, target, None)
}

/// [`diff_flow_data`] for graphs that passed its checks,
/// recording in `known_equal` each base node it finds equal to
/// its target node.
fn diff_proving(
    base: &FlowValue,
    target: &FlowValue,
    mut known_equal: Option<&mut KnownEqual>,
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
        "edge",
        &base_edges,
        &target_edges,
        &changed_edges,
        &FLOW_MODEL.edge_view_state,
    )?;
    let deleted_nodes = gone(&base_nodes, &target_nodes, &no_change);
    let added_nodes = added(
        "node",
        &base_nodes,
        &target_nodes,
        &no_change,
        &FLOW_MODEL.node_view_state,
    )?;

    let mut node_updates = Vec::new();
    for (id, node) in &target_nodes {
        if let Some(before) = base_nodes.get(id) {
            // Skip the diff of an equal node: most nodes of a
            // save are unchanged. The diff cannot fail on an
            // equal node.
            if before == node {
                if let Some(known_equal) = known_equal.as_deref_mut() {
                    known_equal.insert(
                        before.entries_ptr(),
                        (FlowObj::clone(before), node.entries_ptr()),
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
    base: &IndexMap<&str, &FlowObj>,
    target: &IndexMap<&str, &FlowObj>,
    replaced: &HashSet<&str>,
) -> Vec<String> {
    base.keys()
        .filter(|id| !target.contains_key(*id) || replaced.contains(*id))
        .map(|id| (*id).to_owned())
        .collect()
}

/// The nodes or edges of `target` that `base` lacks or
/// `replaced` names, without their view state.
fn added<T: TryFrom<FlowObj, Error = DeserializeError>>(
    root: &str,
    base: &IndexMap<&str, &FlowObj>,
    target: &IndexMap<&str, &FlowObj>,
    replaced: &HashSet<&str>,
    view_state: &KeySet,
) -> Result<Vec<T>> {
    target
        .iter()
        .filter(|(id, _)| !base.contains_key(*id) || replaced.contains(*id))
        .map(|(_, entry)| {
            T::try_from(without(entry, |key| view_state.contains(key)))
                .map_err(|error| error.into_error(root))
        })
        .collect()
}

/// Diff two graphs, and return the forward operations with the
/// replayed graph.
///
/// # Errors
///
/// A graph breaks the rules, or the operations do not replay to
/// `target`.
pub fn derive_flow_operations(base: FlowValue, target: &FlowValue) -> Result<Derived> {
    validate_flow_data(&base, Numbers::Skip, "flow.data", None)?;
    validate_flow_data(target, Numbers::Check, "target flow.data", None)?;
    derive_checked(base, target)
}

/// [`derive_flow_operations`] for graphs that have passed its
/// checks: `base` structurally, and `target` fully.
fn derive_checked(base: FlowValue, target: &FlowValue) -> Result<Derived> {
    let mut known_equal = KnownEqual::default();
    let operations = diff_proving(&base, target, Some(&mut known_equal))?;
    let options = ApplyOptions {
        forward: true,
        ..ApplyOptions::default()
    };
    let mut state = GraphState::from_checked(base)?;
    let applied = state.apply(operations, options)?;
    let flow_data = state.into_value();
    // The check skips the nodes the diff found equal.
    if !graphs_equal_given(&flow_data, target, Some(&known_equal))? {
        return Err(Error::replay(
            "derived operations do not replay to the target graph",
        ));
    }
    Ok(Derived {
        operations: applied.forward,
        flow_data,
    })
}

/// A validated graph's nodes or edges, by id, in the graph's
/// order.
fn by_id<'g>(graph: &'g FlowValue, key: &str) -> IndexMap<&'g str, &'g FlowObj> {
    graph
        .get(key)
        .and_then(FlowValue::as_array)
        .into_iter()
        .flatten()
        .filter_map(FlowValue::as_object)
        .filter_map(|entry| Some((entry.get("id")?.as_str()?, entry)))
        .collect()
}

fn without(map: &FlowObj, hidden: impl Fn(&str) -> bool) -> FlowObj {
    map.iter()
        .filter(|(key, _)| !hidden(key))
        .map(|(key, value)| (key.clone(), value.clone()))
        .collect()
}

// --- Nodes ---------------------------------------------------

/// The writes that turn one node into another.
#[derive(Debug)]
struct NodeDiff<'a> {
    id: &'a str,
    updates: &'a mut Vec<FieldUpdate>,
}

impl NodeDiff<'_> {
    /// Record a `set_field`. The caller passes its own copy of
    /// the path.
    fn set(&mut self, path: Path, value: &FlowValue) -> Result<()> {
        let path = NodePath::try_from(path)?;
        self.updates
            .push(FieldUpdate::set(self.id, path, value.clone()));
        Ok(())
    }

    /// Record a `delete_field`, with its own copy of the path
    /// like [`Self::set`].
    fn delete(&mut self, path: Path) -> Result<()> {
        let path = NodePath::try_from(path)?;
        self.updates.push(FieldUpdate::delete(self.id, path));
        Ok(())
    }

    /// The keys the diff never writes, besides a node's
    /// identity: view state.
    fn skipped(path: &[Segment], key: &str) -> bool {
        if path.is_empty() {
            key == "id" || FLOW_MODEL.node_view_state.contains(key)
        } else if path.equals(&["data", "node"]) {
            FLOW_MODEL.node_data_view_state.contains(key)
        } else if path.equals(&TEMPLATE_PATH) {
            FLOW_MODEL.template_view_state.contains(key)
        } else if path.len() == TEMPLATE_PATH.len() + 1 && path.has_start(&TEMPLATE_PATH) {
            FLOW_MODEL.field_view_state.contains(key)
        } else {
            false
        }
    }

    /// Diff two objects key by key. Each step pushes its
    /// segment onto `path` and pops it when done.
    fn object(&mut self, base: &FlowObj, target: &FlowObj, path: &mut Path) -> Result<()> {
        for (key, value) in target {
            if Self::skipped(path, key) {
                continue;
            }
            path.push(Segment::Key(key.clone()));
            match base.get(key) {
                None => self.set(path.clone(), value)?,
                Some(previous) => self.value(previous, value, target, path)?,
            }
            path.pop();
        }
        for key in base.keys() {
            if !target.contains_key(key) && !Self::skipped(path, key) {
                path.push(Segment::Key(key.clone()));
                self.delete(path.clone())?;
                path.pop();
            }
        }
        Ok(())
    }

    /// Diff the value at `path`. `parent` is the target object
    /// that holds it. An object is diffed key by key, and a
    /// keyed list item by item. Any other value that changed is
    /// written whole.
    fn value(
        &mut self,
        base: &FlowValue,
        target: &FlowValue,
        parent: &FlowObj,
        path: &mut Path,
    ) -> Result<()> {
        let keyed = FLOW_MODEL.keyed_list_by(path, |_, key| parent.get(key).map(Cow::Borrowed));
        if let Some(keyed) = keyed {
            let mut items = Vec::new();
            if keyed_list(keyed, base, target, path, &mut items)? {
                return self.write_all(items);
            }
        } else if let (FlowValue::Object(base), FlowValue::Object(target)) = (base, target) {
            return self.object(base, target, path);
        }
        if !values_equal(base, target)? {
            self.set(path.clone(), target)?;
        }
        Ok(())
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
}

/// One write the keyed-list diff found, before the node diff
/// records it.
#[derive(Debug)]
enum Write<'v> {
    Set { path: Path, value: &'v FlowValue },
    Delete { path: Path },
}

/// Diff a keyed list item by item. Returns false when it has to
/// be written whole. `path` names the list.
fn keyed_list<'v>(
    keyed: &KeyedList,
    base: &'v FlowValue,
    target: &'v FlowValue,
    path: &mut Path,
    writes: &mut Vec<Write<'v>>,
) -> Result<bool> {
    let (Some(base_items), Some(target_items)) =
        (items_by_key(keyed, base), items_by_key(keyed, target))
    else {
        return Ok(false);
    };
    for (key, item) in &target_items {
        path.push(Segment::Item((*key).into()));
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
            path.push(Segment::Item((*key).into()));
            writes.push(Write::Delete { path: path.clone() });
            path.pop();
        }
    }
    Ok(true)
}

/// The writes that turn one keyed-list item into another, key
/// by key. `path` names the item.
fn item_writes<'v>(
    target: &'v FlowObj,
    base: &'v FlowObj,
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

/// A list by item key, or `None` when an item has no unique key
/// or no numeric position. Writing such a legacy list whole
/// brings it within the rules.
fn items_by_key<'v>(
    keyed: &KeyedList,
    items: &'v FlowValue,
) -> Option<IndexMap<&'v str, &'v FlowValue>> {
    let FlowValue::Array(items) = items else {
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

impl GraphPlain {
    /// The operations that turn this graph into `target`,
    /// checked by replay. See [`derive_flow_operations`].
    ///
    /// # Errors
    ///
    /// A graph breaks the rules, or the operations do not
    /// replay to `target`.
    pub fn ops_diff(&self, target: &Self) -> Result<Derived> {
        self.require(Numbers::Skip, "flow.data")?;
        target.require(Numbers::Check, "target flow.data")?;
        derive_checked(self.as_value().clone(), target.as_value())
    }
}

impl Error {
    /// Derived operations that do not replay to their target.
    pub fn replay(message: impl Into<String>) -> Self {
        Self {
            kind: ErrorKind::ReplayMismatch,
            ..Self::invalid_with(ErrorCode::ReplayMismatch, message)
        }
    }
}
