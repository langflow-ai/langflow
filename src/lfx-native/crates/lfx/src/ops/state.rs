//! [`GraphState`]: the indexed graph that apply works on, kept between batches.
//!
//! Nodes and edges are indexed by id, and edges by the nodes they touch.
//! Indexes that only some writes need are built the first time a write asks
//! for them and kept up to date afterwards: keyed lists by item key, each
//! edge's handles, and each node's connections by the input or output they
//! use.
//!
//! A batch is all or nothing. Every change records how to undo it, so a batch
//! that fails puts the graph back as it was, in time proportional to what it
//! changed rather than to the size of the graph.

use std::collections::{HashMap, HashSet};
use std::fmt;
use std::str::FromStr;

use indexmap::{IndexMap, IndexSet};
use serde_json::{Map, Value};

use crate::ops::edges::{EdgeIndex, GraphRead, endpoint};
use crate::ops::entry::EntryExt;
use crate::ops::error::{Error, Result};
use crate::ops::keyed::{ListIndex, Removal};
use crate::ops::ops::PathExt;
use crate::ops::schema::KeyedList;
use crate::ops::validate::{Numbers, PathPart, validate_flow_data};

/// Whether a removal returns copies of what it removed, which inverses need.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Copies {
    Keep,
    Discard,
}

/// How to undo one change inside a node.
#[derive(Debug)]
pub(crate) enum FieldUndo {
    /// A key was set; put back the value it held, or remove it if it was new.
    KeySet { key: String, old: Option<Value> },
    /// A key was deleted from `index`.
    KeyDeleted {
        key: String,
        index: usize,
        old: Value,
    },
    /// An item was appended.
    ItemAdded,
    /// The item at `slot` was replaced.
    ItemReplaced { slot: usize, old: Value },
    /// An item was removed.
    ItemRemoved { removal: Removal, old: Value },
}

/// How to undo one change.
#[derive(Debug)]
enum Undo {
    NodeAdded(String),
    NodeRemoved {
        index: usize,
        id: String,
        node: Value,
    },
    EdgeAdded(String),
    EdgeRemoved {
        index: usize,
        id: String,
        edge: Value,
    },
    Field {
        node_id: String,
        container: Vec<PathPart>,
        undo: FieldUndo,
    },
}

/// Nodes and edges by id, and edges by the nodes they touch.
#[derive(Debug, Default)]
pub(crate) struct Graph {
    pub nodes: IndexMap<String, Value>,
    pub edges: IndexMap<String, Value>,
    edges_at: HashMap<String, IndexSet<String>>,
}

impl Graph {
    fn attach(&mut self, id: &str, edge: &Value) {
        for end in ends(edge) {
            self.edges_at
                .entry(end.to_owned())
                .or_default()
                .insert(id.to_owned());
        }
    }

    fn detach(&mut self, id: &str, edge: &Value) {
        for end in ends(edge) {
            if let Some(ids) = self.edges_at.get_mut(end) {
                ids.swap_remove(id);
                if ids.is_empty() {
                    self.edges_at.remove(end);
                }
            }
        }
    }

    /// The ids of the edges at a node.
    pub fn edges_at(&self, node_id: &str) -> impl Iterator<Item = &String> {
        self.edges_at.get(node_id).into_iter().flatten()
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
#[derive(Debug, Default)]
pub(crate) struct Lists {
    by_node: HashMap<String, Vec<(Vec<String>, ListIndex)>>,
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

    /// Forget the indexes of the lists at or under `path`, which a write replaced or removed.
    pub fn forget_under(&mut self, node_id: &str, path: &[&str]) {
        if let Some(lists) = self.by_node.get_mut(node_id) {
            lists.retain(|(list_path, _)| !list_path.has_start(path));
        }
    }

    fn forget_node(&mut self, node_id: &str) {
        self.by_node.remove(node_id);
    }
}

/// What one batch did, so it can be undone and reported.
#[derive(Debug, Default)]
pub(crate) struct Batch {
    undos: Vec<Undo>,
    added_nodes: HashSet<String>,
    removed_base_nodes: HashSet<String>,
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
        let mut graph = Graph::default();
        for node in take_list(&mut root, "nodes") {
            let id = node.id().to_owned();
            graph.nodes.insert(id, node);
        }
        for edge in take_list(&mut root, "edges") {
            let id = edge.id().to_owned();
            graph.attach(&id, &edge);
            graph.edges.insert(id, edge);
        }
        Ok(Self {
            root,
            graph,
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

    /// Start a batch: forget what the previous one did.
    pub(crate) fn begin(&mut self) {
        self.batch = Batch::default();
    }

    /// Undo everything the current batch changed, and drop the indexes it touched.
    pub(crate) fn rollback(&mut self) {
        while let Some(undo) = self.batch.undos.pop() {
            self.undo(undo);
        }
        self.edge_index.clear();
        self.lists = Lists::default();
        self.batch = Batch::default();
    }

    fn undo(&mut self, undo: Undo) {
        match undo {
            Undo::NodeAdded(id) => {
                self.graph.nodes.shift_remove(&id);
            }
            Undo::NodeRemoved { index, id, node } => {
                self.graph.nodes.shift_insert(index, id, node);
            }
            Undo::EdgeAdded(id) => {
                if let Some(edge) = self.graph.edges.shift_remove(&id) {
                    self.graph.detach(&id, &edge);
                }
            }
            Undo::EdgeRemoved { index, id, edge } => {
                self.graph.attach(&id, &edge);
                self.graph.edges.shift_insert(index, id, edge);
            }
            Undo::Field {
                node_id,
                container,
                undo,
            } => {
                let container = self
                    .graph
                    .nodes
                    .get_mut(&node_id)
                    .and_then(|node| resolve_mut(node, &container));
                if let Some(container) = container {
                    undo_field(container, undo);
                }
            }
        }
    }

    /// Whether the node existed when the batch started.
    pub(crate) fn is_base_node(&self, id: &str) -> bool {
        if self.batch.added_nodes.contains(id) {
            self.batch.removed_base_nodes.contains(id)
        } else {
            self.graph.nodes.contains_key(id) || self.batch.removed_base_nodes.contains(id)
        }
    }

    // --- Changes that record their undo ---------------------------------------------------

    pub(crate) fn insert_node(&mut self, id: String, node: Value) {
        self.batch.added_nodes.insert(id.clone());
        self.batch.changed_nodes.insert(id.clone());
        self.batch.undos.push(Undo::NodeAdded(id.clone()));
        self.graph.nodes.insert(id, node);
    }

    /// Remove a node, if it exists, and with [`Copies::Keep`] return a copy of
    /// it. Its edges stay; the caller removes them.
    pub(crate) fn remove_node(&mut self, id: &str, copies: Copies) -> Option<Map<String, Value>> {
        let base = self.is_base_node(id);
        let (index, id, node) = self.graph.nodes.shift_remove_full(id)?;
        self.edge_index.forget_node(&id);
        self.lists.forget_node(&id);
        if base {
            self.batch.removed_base_nodes.insert(id.clone());
        }
        self.batch.changed_nodes.insert(id.clone());
        let kept = match copies {
            Copies::Keep => node.as_object().cloned(),
            Copies::Discard => None,
        };
        self.batch.undos.push(Undo::NodeRemoved { index, id, node });
        kept
    }

    pub(crate) fn insert_edge(&mut self, id: String, edge: Value) {
        self.graph.attach(&id, &edge);
        if let Some(map) = edge.as_object() {
            self.edge_index.insert(map);
        }
        self.batch.changed_edges.insert(id.clone());
        self.batch.undos.push(Undo::EdgeAdded(id.clone()));
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
            let Some((index, id, edge)) = self.graph.edges.shift_remove_full(id) else {
                continue;
            };
            if let Some(map) = edge.as_object() {
                self.edge_index.forget(map);
                if copies == Copies::Keep {
                    kept.push(map.clone());
                }
            }
            self.graph.detach(&id, &edge);
            self.batch.changed_edges.insert(id.clone());
            removed.push(id.clone());
            self.batch.undos.push(Undo::EdgeRemoved { index, id, edge });
        }
        (removed, kept)
    }

    /// Record how to undo a change made inside a node.
    pub(crate) fn record_field(
        &mut self,
        node_id: &str,
        container: Vec<PathPart>,
        undo: FieldUndo,
    ) {
        self.batch.changed_nodes.insert(node_id.to_owned());
        self.batch.undos.push(Undo::Field {
            node_id: node_id.to_owned(),
            container,
            undo,
        });
    }

    /// The value the last recorded field change replaced or removed.
    pub(crate) fn last_replaced(&self) -> Option<&Value> {
        match self.batch.undos.last()? {
            Undo::Field { undo, .. } => match undo {
                FieldUndo::KeySet { old, .. } => old.as_ref(),
                FieldUndo::KeyDeleted { old, .. }
                | FieldUndo::ItemReplaced { old, .. }
                | FieldUndo::ItemRemoved { old, .. } => Some(old),
                FieldUndo::ItemAdded => None,
            },
            _ => None,
        }
    }
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

fn undo_field(container: &mut Value, undo: FieldUndo) {
    match (container, undo) {
        (Value::Object(map), FieldUndo::KeySet { key, old }) => match old {
            Some(old) => {
                map.insert(key, old);
            }
            None => {
                map.shift_remove(&key);
            }
        },
        (Value::Object(map), FieldUndo::KeyDeleted { key, index, old }) => {
            map.shift_insert(index, key, old);
        }
        (Value::Array(items), FieldUndo::ItemAdded) => {
            items.pop();
        }
        (Value::Array(items), FieldUndo::ItemReplaced { slot, old }) => {
            items[slot] = old;
        }
        (Value::Array(items), FieldUndo::ItemRemoved { removal, old }) => match removal {
            Removal::Shifted { slot } => items.insert(slot, old),
            Removal::Swapped { slot } => {
                items.push(old);
                let last = items.len() - 1;
                items.swap(slot, last);
            }
        },
        _ => {}
    }
}
