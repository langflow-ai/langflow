//! [`GraphState`]: the indexed graph that apply works on, kept between batches.
//!
//! Nodes and edges are indexed by id, and edges by the nodes they touch.
//! Indexes that only some writes need are built the first time a write asks
//! for them and kept up to date afterwards: keyed lists by item key, each
//! edge's handles, and each node's connections by the input or output they
//! use.
//!
//! A batch is all or nothing, and it never writes to the graph it starts
//! from. The first write to a node, an edge or an index entry copies it into
//! the batch's layer, and later reads and writes in the batch use the copy.
//! A batch that succeeds folds its layer into the graph; a batch that fails
//! drops it. So nothing is ever undone, and a failed batch keeps the indexes
//! that earlier batches built.

use std::collections::HashSet;
use std::fmt;
use std::str::FromStr;

use indexmap::{IndexMap, IndexSet};
use serde_json::{Map, Value};

use crate::ops::edges::{EdgeIndex, GraphRead, endpoint};
use crate::ops::entry::EntryExt;
use crate::ops::error::{Error, Result};
use crate::ops::keyed::ListIndex;
use crate::ops::ops::PathExt;
use crate::ops::schema::KeyedList;
use crate::ops::validate::{Numbers, PathPart, validate_flow_data};

/// Whether a removal returns copies of what it removed, which inverses need.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Copies {
    Keep,
    Discard,
}

// --- Layers --------------------------------------------------------------------------------

/// Whether removing an entry keeps the order of the others.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Order {
    /// Nodes and edges keep their order, as callers read the graph back.
    Kept,
    /// An index has no order, so a removal can move the last entry into the gap.
    Free,
}

/// What a batch did to one entry of a [`Layered`] map.
#[derive(Debug)]
enum Staged<V> {
    /// A stored entry the batch updated. The batch writes to its own copy,
    /// and the copy replaces the stored entry in place.
    Updated(V),
    /// An entry the batch added, which goes after the stored ones.
    Added(V),
    /// A stored entry the batch removed.
    Removed,
}

/// A map that a batch changes through a layer of its own.
///
/// Reads look in the layer first, then in the stored map. The first write to
/// a stored entry copies it into the layer. [`Layered::fold`] makes the layer
/// part of the stored map, and [`Layered::discard`] drops it.
#[derive(Debug)]
pub(crate) struct Layered<V> {
    stored: IndexMap<String, V>,
    layer: IndexMap<String, Staged<V>>,
    order: Order,
}

impl<V: Clone> Layered<V> {
    /// An empty map.
    pub fn new(order: Order) -> Self {
        Self::with_stored(IndexMap::new(), order)
    }

    fn with_stored(stored: IndexMap<String, V>, order: Order) -> Self {
        Self {
            stored,
            layer: IndexMap::new(),
            order,
        }
    }

    /// The entry with `key`.
    pub fn get(&self, key: &str) -> Option<&V> {
        match self.layer.get(key) {
            Some(Staged::Updated(value) | Staged::Added(value)) => Some(value),
            Some(Staged::Removed) => None,
            None => self.stored.get(key),
        }
    }

    /// Whether there is an entry with `key`.
    pub fn contains(&self, key: &str) -> bool {
        self.get(key).is_some()
    }

    /// Whether the entry existed when the batch started.
    pub fn in_base(&self, key: &str) -> bool {
        self.stored.contains_key(key)
    }

    /// The entry with `key`, to change it. The first call in a batch copies a stored entry.
    pub fn get_mut(&mut self, key: &str) -> Option<&mut V> {
        if !self.layer.contains_key(key) {
            let copy = self.stored.get(key)?.clone();
            self.layer.insert(key.to_owned(), Staged::Updated(copy));
        }
        match self.layer.get_mut(key)? {
            Staged::Updated(value) | Staged::Added(value) => Some(value),
            Staged::Removed => None,
        }
    }

    /// The entry with `key`, to change it, added by `new` when there is none.
    pub fn get_or_insert_with(&mut self, key: &str, new: impl FnOnce() -> V) -> &mut V {
        if !self.contains(key) {
            self.insert(key.to_owned(), new());
        }
        self.get_mut(key)
            .expect("the entry exists or was just added")
    }

    /// Add an entry, or replace the one with the same key.
    pub fn insert(&mut self, key: String, value: V) {
        match self.layer.get_mut(&key) {
            Some(Staged::Updated(old) | Staged::Added(old)) => *old = value,
            Some(Staged::Removed) => {
                // An entry removed and added again goes after the stored ones, as any addition.
                self.layer.shift_remove(&key);
                self.layer.insert(key, Staged::Added(value));
            }
            None if self.stored.contains_key(&key) => {
                self.layer.insert(key, Staged::Updated(value));
            }
            None => {
                self.layer.insert(key, Staged::Added(value));
            }
        }
    }

    /// Remove the entry with `key`. Returns whether there was one.
    pub fn remove(&mut self, key: &str) -> bool {
        match self.layer.get(key) {
            Some(Staged::Removed) => false,
            Some(Staged::Added(_)) if !self.stored.contains_key(key) => {
                self.layer.shift_remove(key);
                true
            }
            Some(_) => {
                self.layer.insert(key.to_owned(), Staged::Removed);
                true
            }
            None if self.stored.contains_key(key) => {
                self.layer.insert(key.to_owned(), Staged::Removed);
                true
            }
            None => false,
        }
    }

    /// Make the batch's changes part of the stored map, in time proportional to them.
    pub fn fold(&mut self) {
        for (key, staged) in std::mem::take(&mut self.layer) {
            match staged {
                Staged::Updated(value) => {
                    if let Some(stored) = self.stored.get_mut(&key) {
                        *stored = value;
                    }
                }
                Staged::Added(value) => {
                    self.remove_stored(&key);
                    self.stored.insert(key, value);
                }
                Staged::Removed => self.remove_stored(&key),
            }
        }
    }

    /// Drop the batch's changes.
    pub fn discard(&mut self) {
        self.layer.clear();
    }

    fn remove_stored(&mut self, key: &str) {
        match self.order {
            Order::Kept => self.stored.shift_remove(key),
            Order::Free => self.stored.swap_remove(key),
        };
    }

    /// The entries in order. Only between batches, when the layer is empty.
    fn values(&self) -> impl Iterator<Item = &V> {
        debug_assert!(self.layer.is_empty(), "read between batches only");
        self.stored.values()
    }

    /// The entries in order, without copying them. Only between batches.
    fn into_values(self) -> impl Iterator<Item = V> {
        debug_assert!(self.layer.is_empty(), "read between batches only");
        self.stored.into_values()
    }
}

// --- The graph -----------------------------------------------------------------------------

/// The ids of the edges at each node.
#[derive(Debug)]
pub(crate) struct EdgesAt(Layered<IndexSet<String>>);

impl EdgesAt {
    fn attach(&mut self, id: &str, edge: &Value) {
        for end in ends(edge) {
            self.0
                .get_or_insert_with(end, IndexSet::new)
                .insert(id.to_owned());
        }
    }

    fn detach(&mut self, id: &str, edge: &Value) {
        for end in ends(edge) {
            if let Some(ids) = self.0.get_mut(end) {
                ids.swap_remove(id);
                if ids.is_empty() {
                    self.0.remove(end);
                }
            }
        }
    }
}

fn ends(edge: &Value) -> Vec<&str> {
    let Some(edge) = edge.as_object() else {
        return Vec::new();
    };
    let (source, target) = (endpoint(edge, "source"), endpoint(edge, "target"));
    if source == target {
        vec![source]
    } else {
        vec![source, target]
    }
}

/// Nodes and edges by id, and edges by the nodes they touch.
#[derive(Debug)]
pub(crate) struct Graph {
    pub nodes: Layered<Value>,
    pub edges: Layered<Value>,
    edges_at: EdgesAt,
}

impl Graph {
    /// The ids of the edges at a node.
    pub fn edges_at(&self, node_id: &str) -> impl Iterator<Item = &String> {
        self.edges_at.0.get(node_id).into_iter().flatten()
    }

    fn fold(&mut self) {
        self.nodes.fold();
        self.edges.fold();
        self.edges_at.0.fold();
    }

    fn discard(&mut self) {
        self.nodes.discard();
        self.edges.discard();
        self.edges_at.0.discard();
    }
}

impl GraphRead for Graph {
    fn node(&self, id: &str) -> Option<&Map<String, Value>> {
        self.nodes.get(id).and_then(Value::as_object)
    }

    fn edge(&self, id: &str) -> Option<&Map<String, Value>> {
        self.edges.get(id).and_then(Value::as_object)
    }

    fn edge_ids_at(&self, node_id: &str) -> impl Iterator<Item = &str> {
        self.edges_at(node_id).map(String::as_str)
    }
}

/// The keyed lists indexed so far, by node and by the path of the list.
#[derive(Debug)]
pub(crate) struct Lists {
    by_node: Layered<Vec<(Vec<String>, ListIndex)>>,
}

impl Default for Lists {
    fn default() -> Self {
        Self {
            by_node: Layered::new(Order::Free),
        }
    }
}

impl Lists {
    /// The index of the list `items` at `path` of a node, built the first time a write reaches it.
    pub fn index(
        &mut self,
        node_id: &str,
        path: &[&str],
        keyed: &'static KeyedList,
        items: &[Value],
        context: &str,
    ) -> Result<&mut ListIndex> {
        let lists = self.by_node.get_or_insert_with(node_id, Vec::new);
        let position = if let Some(position) = lists
            .iter()
            .position(|(list_path, _)| list_path.equals(path))
        {
            position
        } else {
            let owned = path.iter().map(|key| (*key).to_owned()).collect();
            lists.push((owned, ListIndex::build(keyed, items, context)?));
            lists.len() - 1
        };
        Ok(&mut lists[position].1)
    }

    /// Forget the indexes of the lists at or under `path`, which a write replaced or removed.
    pub fn forget_under(&mut self, node_id: &str, path: &[&str]) {
        let under = |(list_path, _): &(Vec<String>, ListIndex)| list_path.has_start(path);
        let indexed = self
            .by_node
            .get(node_id)
            .is_some_and(|lists| lists.iter().any(under));
        if indexed && let Some(lists) = self.by_node.get_mut(node_id) {
            lists.retain(|list| !under(list));
        }
    }

    fn forget_node(&mut self, node_id: &str) {
        self.by_node.remove(node_id);
    }

    fn fold(&mut self) {
        self.by_node.fold();
    }

    fn discard(&mut self) {
        self.by_node.discard();
    }
}

/// The nodes and edges one batch changed, to report them.
#[derive(Debug, Default)]
pub(crate) struct Batch {
    pub changed_nodes: IndexSet<String>,
    pub changed_edges: IndexSet<String>,
}

/// A flow graph, indexed for applying operations.
///
/// It keeps the graph and its indexes between batches, so the graph is
/// indexed once, and each batch costs only what it changes.
#[derive(Debug)]
pub struct GraphState {
    /// The flow's top-level object; `nodes` and `edges` hold placeholders.
    /// No operation writes its other keys, which are view state.
    root: Map<String, Value>,
    pub(crate) graph: Graph,
    pub(crate) edge_index: EdgeIndex,
    pub(crate) lists: Lists,
    pub(crate) batch: Batch,
}

impl GraphState {
    /// Load a flow graph and build its indexes, after checking its structure.
    ///
    /// Values are not walked for numbers that are not finite: that check
    /// belongs to whoever accepts a graph from outside, and skipping it keeps
    /// indexing proportional to the number of nodes and edges.
    ///
    /// # Errors
    ///
    /// The graph breaks a structural rule.
    pub fn new(flow: Value) -> Result<Self> {
        validate_flow_data(&flow, Numbers::Skip, "flow.data", None)?;
        let Value::Object(mut root) = flow else {
            return Err(Error::graph_message("flow data must be an object"));
        };
        let nodes = by_id(take_list(&mut root, "nodes"));
        let edges = by_id(take_list(&mut root, "edges"));
        let mut edges_at = EdgesAt(Layered::new(Order::Free));
        for (id, edge) in &edges {
            edges_at.attach(id, edge);
        }
        edges_at.0.fold();
        Ok(Self {
            root,
            graph: Graph {
                nodes: Layered::with_stored(nodes, Order::Kept),
                edges: Layered::with_stored(edges, Order::Kept),
                edges_at,
            },
            edge_index: EdgeIndex::default(),
            lists: Lists::default(),
            batch: Batch::default(),
        })
    }

    /// The graph as a JSON value.
    #[must_use]
    pub fn to_value(&self) -> Value {
        let mut out = Map::with_capacity(self.root.len());
        for (key, value) in &self.root {
            let value = match key.as_str() {
                "nodes" => Value::Array(self.graph.nodes.values().cloned().collect()),
                "edges" => Value::Array(self.graph.edges.values().cloned().collect()),
                _ => value.clone(),
            };
            out.insert(key.clone(), value);
        }
        Value::Object(out)
    }

    /// The graph as a JSON value, without copying it.
    #[must_use]
    pub fn into_value(self) -> Value {
        let Self {
            mut root, graph, ..
        } = self;
        root.insert(
            "nodes".into(),
            Value::Array(graph.nodes.into_values().collect()),
        );
        root.insert(
            "edges".into(),
            Value::Array(graph.edges.into_values().collect()),
        );
        Value::Object(root)
    }

    // --- Batches ---------------------------------------------------------------------

    /// Start a batch: forget what the previous one changed.
    pub(crate) fn begin(&mut self) {
        self.batch = Batch::default();
    }

    /// End a batch that succeeded: its copies and index changes become the graph.
    pub(crate) fn commit(&mut self) {
        self.graph.fold();
        self.edge_index.fold();
        self.lists.fold();
    }

    /// End a batch that failed: drop its copies and index changes.
    pub(crate) fn discard(&mut self) {
        self.graph.discard();
        self.edge_index.discard();
        self.lists.discard();
        self.batch = Batch::default();
    }

    /// Whether the node existed when the batch started.
    pub(crate) fn is_base_node(&self, id: &str) -> bool {
        self.graph.nodes.in_base(id)
    }

    // --- Changes -----------------------------------------------------------------------

    pub(crate) fn insert_node(&mut self, id: String, node: Value) {
        self.batch.changed_nodes.insert(id.clone());
        self.graph.nodes.insert(id, node);
    }

    /// Remove a node, if it exists, and with [`Copies::Keep`] return a copy of
    /// it. Its edges stay; the caller removes them.
    pub(crate) fn remove_node(&mut self, id: &str, copies: Copies) -> Option<Map<String, Value>> {
        let node = self.graph.nodes.get(id)?;
        let kept = match copies {
            Copies::Keep => node.as_object().cloned(),
            Copies::Discard => None,
        };
        self.graph.nodes.remove(id);
        self.edge_index.forget_node(id);
        self.lists.forget_node(id);
        self.batch.changed_nodes.insert(id.to_owned());
        kept
    }

    pub(crate) fn insert_edge(&mut self, id: String, edge: Value) {
        self.graph.edges_at.attach(&id, &edge);
        if let Some(map) = edge.as_object() {
            self.edge_index.insert(map);
        }
        self.batch.changed_edges.insert(id.clone());
        self.graph.edges.insert(id, edge);
    }

    /// Remove the edges that exist among `ids`, each once. Return their ids,
    /// and with [`Copies::Keep`], copies of the edges.
    pub(crate) fn remove_edges<'i>(
        &mut self,
        ids: impl IntoIterator<Item = &'i str>,
        copies: Copies,
    ) -> (Vec<String>, Vec<Map<String, Value>>) {
        let mut removed = Vec::new();
        let mut kept = Vec::new();
        let mut seen = HashSet::new();
        for id in ids {
            if !seen.insert(id) {
                continue;
            }
            let Some(edge) = self.graph.edges.get(id) else {
                continue;
            };
            if let Some(map) = edge.as_object() {
                self.edge_index.forget(map);
                if copies == Copies::Keep {
                    kept.push(map.clone());
                }
            }
            self.graph.edges_at.detach(id, edge);
            self.graph.edges.remove(id);
            self.batch.changed_edges.insert(id.to_owned());
            removed.push(id.to_owned());
        }
        (removed, kept)
    }

    /// Note that a write changed a node.
    pub(crate) fn changed_node(&mut self, node_id: &str) {
        self.batch.changed_nodes.insert(node_id.to_owned());
    }
}

/// Nodes or edges by id, in their order.
fn by_id(items: Vec<Value>) -> IndexMap<String, Value> {
    items
        .into_iter()
        .map(|item| (item.id().to_owned(), item))
        .collect()
}

/// Parse a flow graph given as JSON text, and load it into a [`GraphState`].
impl FromStr for GraphState {
    type Err = Error;

    fn from_str(text: &str) -> Result<Self> {
        Self::new(parse_json(text)?)
    }
}

/// The graph as JSON text.
impl fmt::Display for GraphState {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.to_value())
    }
}

fn take_list(root: &mut Map<String, Value>, key: &str) -> Vec<Value> {
    match root.get_mut(key) {
        Some(value) => match std::mem::take(value) {
            Value::Array(items) => items,
            _ => Vec::new(),
        },
        None => Vec::new(),
    }
}

/// Parse JSON text, reporting a parse failure as an invalid graph.
pub(crate) fn parse_json(text: &str) -> Result<Value> {
    serde_json::from_str(text)
        .map_err(|error| Error::graph_message(format!("flow data is not valid JSON: {error}")))
}

/// The value at a path of object keys and array indexes.
pub(crate) fn resolve<'v>(root: &'v Value, steps: &[PathPart]) -> Option<&'v Value> {
    steps.iter().try_fold(root, |value, step| match step {
        PathPart::Key(key) => value.as_object()?.get(key),
        PathPart::Index(index) => value.as_array()?.get(*index),
    })
}

/// The value at a path of object keys and array indexes, to change it.
pub(crate) fn resolve_mut<'v>(root: &'v mut Value, steps: &[PathPart]) -> Option<&'v mut Value> {
    steps.iter().try_fold(root, |value, step| match step {
        PathPart::Key(key) => value.as_object_mut()?.get_mut(key),
        PathPart::Index(index) => value.as_array_mut()?.get_mut(*index),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn stored(keys: &[&str]) -> Layered<u32> {
        let map = keys
            .iter()
            .zip(1..)
            .map(|(key, value)| ((*key).to_owned(), value))
            .collect();
        Layered::with_stored(map, Order::Kept)
    }

    fn keys(map: &Layered<u32>) -> Vec<&str> {
        map.stored.keys().map(String::as_str).collect()
    }

    #[test]
    fn a_batch_reads_its_own_writes_and_leaves_the_stored_map_alone() {
        let mut map = stored(&["a", "b"]);
        *map.get_mut("a").unwrap() = 10;
        map.remove("b");
        map.insert("c".into(), 3);
        assert_eq!(map.get("a"), Some(&10));
        assert_eq!(map.get("b"), None);
        assert_eq!(map.get("c"), Some(&3));
        assert_eq!(map.stored.get("a"), Some(&1));
        assert!(map.in_base("b") && !map.in_base("c"));
    }

    #[test]
    fn a_dropped_batch_leaves_nothing_behind() {
        let mut map = stored(&["a", "b"]);
        *map.get_mut("a").unwrap() = 10;
        map.remove("b");
        map.insert("c".into(), 3);
        map.discard();
        assert_eq!(keys(&map), ["a", "b"]);
        assert_eq!(map.get("a"), Some(&1));
        assert_eq!(map.get("c"), None);
    }

    #[test]
    fn a_folded_batch_keeps_copies_in_place_and_adds_last() {
        let mut map = stored(&["a", "b", "c"]);
        map.insert("x".into(), 24);
        *map.get_mut("a").unwrap() = 10;
        // Removed and added again: it goes last, after the other additions.
        map.remove("b");
        map.insert("b".into(), 20);
        map.remove("c");
        map.fold();
        assert_eq!(keys(&map), ["a", "x", "b"]);
        assert_eq!(map.values().copied().collect::<Vec<_>>(), [10, 24, 20]);
    }

    #[test]
    fn an_entry_added_and_removed_in_one_batch_leaves_no_trace() {
        let mut map = stored(&["a"]);
        map.insert("x".into(), 24);
        assert!(map.remove("x"));
        assert!(!map.remove("x"));
        map.fold();
        assert_eq!(keys(&map), ["a"]);
    }
}
