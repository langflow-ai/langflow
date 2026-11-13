//! [`GraphState`]: the indexed graph that apply works on, kept between batches.
//!
//! Nodes and edges are indexed by id, and edges by the nodes they touch.
//! Indexes that only some writes need are built the first time a write asks
//! for them and kept up to date afterwards: keyed lists by item key, each
//! edge's handles, and each node's connections by the input or output they
//! use.
//!
//! A batch is all or nothing, and it never writes to the graph it starts
//! from. A node or an edge that a batch adds or removes, and an index entry
//! it changes, goes into the batch's layer (`Layered`). A field write goes
//! into the batch's field layer (`FieldLayer`), a tree of the paths the batch
//! writes, which keeps only what it wrote. Reads in the batch look in the layers
//! first. A batch that succeeds folds its layers into the graph; a batch
//! that fails drops them. So nothing is ever undone, and a failed batch
//! keeps the indexes that earlier batches built.

use std::borrow::Cow;
use std::collections::HashMap;
use std::fmt;
use std::str::FromStr;

use indexmap::{IndexMap, IndexSet};
use serde_json::{Map, Value};

use crate::ops::edges::{EdgeIndex, GraphRead};
use crate::ops::entry::EntryExt;
use crate::ops::error::{Error, Result};
use crate::ops::fields::{self, FieldLayer};
use crate::ops::keyed::ListIndex;
use crate::ops::ops::{Edge, Node, PathExt, Segment};
use crate::ops::schema::{KeyedList, NODE_SCHEMA};
use crate::ops::validate::{Numbers, PathPart, validate_flow_data};

// --- Layers --------------------------------------------------------------------------------

/// A map that a batch changes through a layer of its own.
///
/// Reads look in the layer first, then in the stored map. The first write to
/// a stored entry copies it into the layer. [`Layered::fold`] makes the layer
/// part of the stored map, and [`Layered::discard`] drops it.
///
/// Entry order is not state, as for the nodes and edges of a flow. So a
/// removal moves the last entry into the gap, and costs the same whatever the
/// size of the map.
#[derive(Debug)]
pub(crate) struct Layered<V> {
    stored: IndexMap<String, V>,
    /// What the batch wrote, by key: the new value, or `None` for a stored
    /// entry that the batch removed.
    layer: IndexMap<String, Option<V>>,
}

impl<V: Clone> Layered<V> {
    /// An empty map.
    pub fn new() -> Self {
        Self::with_stored(IndexMap::new())
    }

    fn with_stored(stored: IndexMap<String, V>) -> Self {
        Self {
            stored,
            layer: IndexMap::new(),
        }
    }

    /// The entry with `key`.
    pub fn get(&self, key: &str) -> Option<&V> {
        match self.layer.get(key) {
            Some(written) => written.as_ref(),
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

    /// Whether the batch added, replaced or removed the entry.
    pub fn in_layer(&self, key: &str) -> bool {
        self.layer.contains_key(key)
    }

    /// The stored entry with `key`, to change it in place. Only between
    /// batches, when the layer is empty.
    pub fn stored_mut(&mut self, key: &str) -> Option<&mut V> {
        debug_assert!(self.layer.is_empty(), "write between batches only");
        self.stored.get_mut(key)
    }

    /// The entry with `key`, to change it. The first call in a batch copies a stored entry.
    pub fn get_mut(&mut self, key: &str) -> Option<&mut V> {
        if !self.layer.contains_key(key) {
            // No entry anywhere: return `None`, and leave the layer as it is.
            let copy = self.stored.get(key)?.clone();
            self.layer.insert(key.to_owned(), Some(copy));
        }
        self.layer.get_mut(key)?.as_mut()
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
        self.layer.insert(key, Some(value));
    }

    /// Remove the entry with `key`. Returns whether there was one.
    pub fn remove(&mut self, key: &str) -> bool {
        let existed = self.contains(key);
        if self.stored.contains_key(key) {
            self.layer.insert(key.to_owned(), None);
        } else {
            self.layer.swap_remove(key);
        }
        existed
    }

    /// Make the batch's changes part of the stored map, in time proportional to them.
    pub fn fold(&mut self) {
        for (key, written) in std::mem::take(&mut self.layer) {
            match written {
                Some(value) => {
                    self.stored.insert(key, value);
                }
                None => {
                    self.stored.swap_remove(&key);
                }
            }
        }
    }

    /// Drop the batch's changes.
    pub fn discard(&mut self) {
        self.layer.clear();
    }

    /// The entries. Only between batches, when the layer is empty.
    fn values(&self) -> impl Iterator<Item = &V> {
        debug_assert!(self.layer.is_empty(), "read between batches only");
        self.stored.values()
    }

    /// The entries, without copying them. Only between batches.
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
    fn attach(&mut self, id: &str, edge: &Edge) {
        for end in ends(edge) {
            self.0
                .get_or_insert_with(end, IndexSet::new)
                .insert(id.to_owned());
        }
    }

    fn detach(&mut self, id: &str, edge: &Edge) {
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

fn ends(edge: &Edge) -> Vec<&str> {
    let (source, target) = (edge.source(), edge.target());
    if source == target {
        vec![source]
    } else {
        vec![source, target]
    }
}

/// Nodes and edges by id, edges by the nodes they touch, and the batch's field writes.
///
/// Its maps are private: code outside this module reads a node only through
/// [`fields::walk`], by [`Graph::walk_field`], [`field_value`] and
/// [`GraphRead::node_value`]. So no read misses the batch's field writes.
#[derive(Debug)]
pub(crate) struct Graph {
    nodes: Layered<Node>,
    edges: Layered<Edge>,
    edges_at: EdgesAt,
    fields: FieldLayer,
}

impl Graph {
    /// The ids of the edges at a node.
    pub fn edges_at(&self, node_id: &str) -> impl Iterator<Item = &String> {
        self.edges_at.0.get(node_id).into_iter().flatten()
    }

    /// Whether the graph has an edge with `id`.
    pub fn has_edge(&self, id: &str) -> bool {
        self.edges.contains(id)
    }

    /// Whether node `id` is a stored node: the one the graph had when the
    /// batch started, not one the batch added in its place. Only a stored
    /// node's lists are indexed.
    pub fn is_stored_node(&self, id: &str) -> bool {
        self.nodes.in_base(id) && !self.nodes.in_layer(id)
    }

    /// Follow `path` in node `id` as the batch sees it ([`fields::walk`]), or
    /// `None` when there is no such node.
    ///
    /// # Errors
    ///
    /// `step` fails.
    pub fn walk_field<'g>(
        &'g self,
        id: &str,
        path: &[Segment],
        step: impl FnMut(&'g Value, usize, bool) -> Result<Option<&'g Value>>,
    ) -> Result<Option<fields::Walked<'g>>> {
        let Some(node) = self.nodes.get(id) else {
            return Ok(None);
        };
        fields::walk(node.as_value(), self.fields.node(id), path, step).map(Some)
    }

    /// The batch's writes to node `id`, to add one.
    pub fn writes_mut(&mut self, id: &str) -> &mut fields::PathWrites {
        self.fields.node_mut(id)
    }

    fn discard(&mut self) {
        self.nodes.discard();
        self.edges.discard();
        self.edges_at.0.discard();
        self.fields.discard();
    }
}

impl GraphRead for Graph {
    fn has_node(&self, id: &str) -> bool {
        self.nodes.contains(id)
    }

    fn node_value(&self, id: &str, path: &[&str]) -> Option<Cow<'_, Value>> {
        let node = self.nodes.get(id)?;
        let path: Vec<Segment> = path
            .iter()
            .map(|key| Segment::Key((*key).to_owned()))
            .collect();
        let step = |value, index: usize, _| Ok(fields::child(value, &path[..index], &path[index]));
        fields::read(node.as_value(), self.fields.node(id), &path, step)
            .expect("a read of object keys cannot fail")
    }

    fn edge(&self, id: &str) -> Option<&Map<String, Value>> {
        self.edges.get(id).map(Edge::as_map)
    }

    fn edge_ids_at(&self, node_id: &str) -> impl Iterator<Item = &str> {
        self.edges_at(node_id).map(String::as_str)
    }
}

/// The value at `path` of node `id` as the batch sees it, with the batch's
/// field writes. A list item of a stored node is found through the list's
/// index, built the first time a read reaches it. `context` names the read
/// in an index's error.
///
/// # Errors
///
/// A list that the read indexes breaks the keyed-list rules.
pub(crate) fn field_value<'g>(
    graph: &'g Graph,
    lists: &mut Lists,
    id: &str,
    path: &[Segment],
    context: &dyn fmt::Display,
) -> Result<Option<Cow<'g, Value>>> {
    let Some(node) = graph.nodes.get(id) else {
        return Ok(None);
    };
    let stored = graph.is_stored_node(id);
    let step = |value: &'g Value, index: usize, in_entry: bool| {
        let (parent, segment) = (&path[..index], &path[index]);
        let (Segment::Item(key), true, Some(list_path)) =
            (segment, stored && !in_entry, parent.to_list())
        else {
            return Ok(fields::child(value, parent, segment));
        };
        let Some(items) = value.as_array() else {
            return Ok(None);
        };
        let keyed = NODE_SCHEMA.listed_at(parent);
        let slot = lists
            .index(id, &list_path, keyed, items, context)?
            .slot(key);
        Ok(slot.map(|slot| &items[slot]))
    };
    fields::read(node.as_value(), graph.fields.node(id), path, step)
}

/// The keyed lists indexed so far, by node and by the path of the list.
///
/// They index stored nodes, never the batch's field writes, so
/// a batch that fails leaves them right. A field write forgets the indexes
/// it makes stale, and the fold keeps the others up to date.
#[derive(Debug, Default)]
pub(crate) struct Lists {
    by_node: HashMap<String, Vec<(Vec<String>, ListIndex)>>,
}

impl Lists {
    /// The index of the list `items` at `path` of a node, built the first time a read reaches it.
    pub fn index(
        &mut self,
        node_id: &str,
        path: &[&str],
        keyed: &'static KeyedList,
        items: &[Value],
        context: &dyn fmt::Display,
    ) -> Result<&mut ListIndex> {
        let lists = self.by_node.entry(node_id.to_owned()).or_default();
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

    /// The index of the list at `path` of a node, if one is built.
    pub fn built(&mut self, node_id: &str, path: &[&str]) -> Option<&mut ListIndex> {
        self.by_node
            .get_mut(node_id)?
            .iter_mut()
            .find(|(list_path, _)| list_path.equals(path))
            .map(|(_, index)| index)
    }

    /// Forget the indexes of the lists at `path` or at a descendant (desc.)
    /// path of it, which a write replaced or removed.
    pub fn forget_under(&mut self, node_id: &str, path: &[&str]) {
        if let Some(lists) = self.by_node.get_mut(node_id) {
            lists.retain(|(list_path, _)| !list_path.has_start(path));
        }
    }

    fn forget_node(&mut self, node_id: &str) {
        self.by_node.remove(node_id);
    }
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
        // Validation passed, so every node and edge has its shape.
        let nodes = by_id(take_list(&mut root, "nodes"), Node::try_from)?;
        let edges = by_id(take_list(&mut root, "edges"), Edge::try_from)?;
        let mut edges_at = EdgesAt(Layered::new());
        for (id, edge) in &edges {
            edges_at.attach(id, edge);
        }
        edges_at.0.fold();
        Ok(Self {
            root,
            graph: Graph {
                nodes: Layered::with_stored(nodes),
                edges: Layered::with_stored(edges),
                edges_at,
                fields: FieldLayer::default(),
            },
            edge_index: EdgeIndex::default(),
            lists: Lists::default(),
        })
    }

    /// The graph as a JSON value.
    #[must_use]
    pub fn to_value(&self) -> Value {
        let mut out = Map::with_capacity(self.root.len());
        for (key, value) in &self.root {
            let value = match key.as_str() {
                "nodes" => Value::Array(
                    self.graph
                        .nodes
                        .values()
                        .map(|node| node.as_value().clone())
                        .collect(),
                ),
                "edges" => Value::Array(
                    self.graph
                        .edges
                        .values()
                        .map(|edge| Value::Object(edge.as_map().clone()))
                        .collect(),
                ),
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
            Value::Array(graph.nodes.into_values().map(Node::into_value).collect()),
        );
        root.insert(
            "edges".into(),
            Value::Array(
                graph
                    .edges
                    .into_values()
                    .map(|edge| Value::Object(edge.into_map()))
                    .collect(),
            ),
        );
        Value::Object(root)
    }

    // --- Batches ---------------------------------------------------------------------

    /// End a batch that succeeded: its layers become the graph.
    ///
    /// Nodes fold first, so a field write lands in the node the batch saw:
    /// a node the batch deleted and added again is written after it is
    /// added.
    pub(crate) fn commit(&mut self) {
        let graph = &mut self.graph;
        graph.nodes.fold();
        graph.edges.fold();
        graph.edges_at.0.fold();
        for (id, writes) in graph.fields.take() {
            let node = graph
                .nodes
                .stored_mut(&id)
                .expect("a field write's node exists");
            let mut lists = fields::NodeLists {
                lists: &mut self.lists,
                id: &id,
            };
            fields::make_writes(
                node.as_value_mut(),
                writes,
                &mut Vec::new(),
                Some(&mut lists),
            );
        }
        self.edge_index.fold();
    }

    /// End a batch that failed: drop its layers.
    pub(crate) fn discard(&mut self) {
        self.graph.discard();
        self.edge_index.discard();
    }

    /// Whether the node existed when the batch started.
    pub(crate) fn is_base_node(&self, id: &str) -> bool {
        self.graph.nodes.in_base(id)
    }

    // --- Changes -----------------------------------------------------------------------

    /// Add `node`, whose id the graph does not have.
    pub(crate) fn insert_node(&mut self, node: Node) {
        debug_assert!(!self.graph.nodes.contains(node.id()), "a new node id");
        // The key is the one copy of the id that the graph needs.
        self.graph.nodes.insert(node.id().to_owned(), node);
    }

    /// A copy of the node `id` as the batch sees it, for the backward operations.
    pub(crate) fn node_copy(&self, id: &str) -> Option<Node> {
        let node = self.graph.node_value(id, &[])?.into_owned();
        let Value::Object(node) = node else {
            unreachable!("a node is a JSON object")
        };
        Some(Node::try_from(node).expect("a field write keeps the shape of a node"))
    }

    /// Remove the node `id`, if it exists. Its edges stay; the caller removes them.
    pub(crate) fn remove_node(&mut self, id: &str) {
        self.graph.nodes.remove(id);
        self.graph.fields.forget_node(id);
        self.edge_index.forget_node(id);
        self.lists.forget_node(id);
    }

    /// Add `edge`, whose id the graph does not have.
    pub(crate) fn insert_edge(&mut self, edge: Edge) {
        debug_assert!(!self.graph.edges.contains(edge.id()), "a new edge id");
        self.graph.edges_at.attach(edge.id(), &edge);
        self.edge_index.insert(edge.as_map());
        self.graph.edges.insert(edge.id().to_owned(), edge);
    }

    /// A copy of the edge `id`, for the backward operations.
    pub(crate) fn edge_copy(&self, id: &str) -> Option<Edge> {
        self.graph.edges.get(id).cloned()
    }

    /// Remove the edge `id`, if it exists.
    pub(crate) fn remove_edge(&mut self, id: &str) {
        let Some(edge) = self.graph.edges.get(id) else {
            return;
        };
        self.edge_index.forget(edge.as_map());
        self.graph.edges_at.detach(id, edge);
        self.graph.edges.remove(id);
    }
}

/// Nodes or edges by id, in their order, each made by `make`.
fn by_id<T>(
    items: Vec<Value>,
    make: fn(Map<String, Value>) -> Result<T>,
) -> Result<IndexMap<String, T>> {
    items
        .into_iter()
        .map(|item| {
            let Value::Object(item) = item else {
                return Err(Error::graph_message("nodes and edges must be objects"));
            };
            Ok((item.id().to_owned(), make(item)?))
        })
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
        Layered::with_stored(map)
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
    fn a_folded_batch_writes_its_changes_to_the_stored_map() {
        let mut map = stored(&["a", "b", "c"]);
        map.insert("x".into(), 24);
        *map.get_mut("a").unwrap() = 10;
        map.remove("b");
        map.insert("b".into(), 20);
        map.remove("c");
        map.fold();
        let mut entries: Vec<_> = map
            .stored
            .iter()
            .map(|(key, value)| (key.as_str(), *value))
            .collect();
        entries.sort_unstable();
        assert_eq!(entries, [("a", 10), ("b", 20), ("x", 24)]);
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
