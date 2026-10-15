//! The indexed graph that apply works on, and that a handle keeps between calls.
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

use indexmap::{IndexMap, IndexSet};
use serde_json::{Map, Value};

use crate::ops::edges::{EdgeIndex, GraphRead, endpoint};
use crate::ops::error::{Error, Result};
use crate::ops::keyed::{ListIndex, Removal};
use crate::ops::schema::KeyedList;
use crate::ops::validate::validate_flow_data;

/// One step of a resolved path: an object key or an array slot.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum Step {
    Key(String),
    Index(usize),
}

/// The node or edge a field write goes to.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Owner {
    Node,
    Edge,
}

/// How to undo one change inside a node or an edge.
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
    RootSet {
        key: String,
        old: Option<Value>,
    },
    RootDeleted {
        key: String,
        index: usize,
        old: Value,
    },
    Field {
        owner: Owner,
        id: String,
        container: Vec<Step>,
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

    /// The value a field write goes into.
    pub fn owner(&self, owner: Owner, id: &str) -> Option<&Value> {
        match owner {
            Owner::Node => self.nodes.get(id),
            Owner::Edge => self.edges.get(id),
        }
    }

    pub fn owner_mut(&mut self, owner: Owner, id: &str) -> Option<&mut Value> {
        match owner {
            Owner::Node => self.nodes.get_mut(id),
            Owner::Edge => self.edges.get_mut(id),
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
    /// The index of the list `items` at `path` of a node, built the first time it is addressed.
    pub fn index(
        &mut self,
        node_id: &str,
        path: &[String],
        keyed: &'static KeyedList,
        items: &[Value],
        context: &str,
    ) -> Result<&mut ListIndex> {
        let lists = self.by_node.entry(node_id.to_owned()).or_default();
        let position =
            if let Some(position) = lists.iter().position(|(list_path, _)| list_path == path) {
                position
            } else {
                lists.push((path.to_vec(), ListIndex::build(keyed, items, context)?));
                lists.len() - 1
            };
        Ok(&mut lists[position].1)
    }

    /// Forget the indexes of the lists at or under `path`, which a write replaced or removed.
    pub fn forget_under(&mut self, node_id: &str, path: &[&str]) {
        if let Some(lists) = self.by_node.get_mut(node_id) {
            lists.retain(|(list_path, _)| {
                list_path.len() < path.len() || !list_path.iter().zip(path).all(|(a, b)| a == b)
            });
        }
    }

    fn forget_node(&mut self, node_id: &str) {
        self.by_node.remove(node_id);
    }
}

/// What one batch did, so it can be undone and reported.
#[derive(Debug, Default)]
pub(crate) struct Batch {
    journal: Vec<Undo>,
    added_nodes: HashSet<String>,
    removed_base_nodes: HashSet<String>,
    added_edges: HashSet<String>,
    removed_base_edges: HashSet<String>,
    pub changed_nodes: IndexSet<String>,
    pub changed_edges: IndexSet<String>,
}

/// A flow graph, indexed for applying operations.
///
/// It holds the graph between calls: replay, history playback and rebase
/// apply many batches to one state and read the result once.
#[derive(Debug)]
pub struct FlowState {
    /// The flow's top-level object; `nodes` and `edges` hold placeholders.
    root: Map<String, Value>,
    pub(crate) graph: Graph,
    pub(crate) edge_index: EdgeIndex,
    pub(crate) lists: Lists,
    pub(crate) batch: Batch,
}

impl FlowState {
    /// Index a flow graph, after checking its structure.
    ///
    /// Values are not walked for numbers that are not finite: that check
    /// belongs to whoever accepts a graph from outside, and skipping it keeps
    /// indexing proportional to the number of nodes and edges.
    ///
    /// # Errors
    ///
    /// The graph breaks a structural rule.
    pub fn new(flow: Value) -> Result<Self> {
        validate_flow_data(&flow, false, "flow.data", None)?;
        let Value::Object(mut root) = flow else {
            return Err(Error::graph("flow data must be an object", Vec::new()));
        };
        let mut graph = Graph::default();
        for node in take_list(&mut root, "nodes") {
            let id = entry_id(&node);
            graph.nodes.insert(id, node);
        }
        for edge in take_list(&mut root, "edges") {
            let id = entry_id(&edge);
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

    /// Parse and index a flow graph given as JSON text.
    ///
    /// # Errors
    ///
    /// The text is not JSON, or the graph breaks a structural rule.
    pub fn from_json(text: &str) -> Result<Self> {
        Self::new(parse_json(text)?)
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

    /// The graph as JSON text.
    #[must_use]
    pub fn to_json(&self) -> String {
        self.to_value().to_string()
    }

    /// The flow's top-level object, without `nodes` and `edges`.
    pub(crate) fn root(&self) -> &Map<String, Value> {
        &self.root
    }

    // --- Batches ---------------------------------------------------------------------

    /// Start a batch: forget what the previous one did.
    pub(crate) fn begin(&mut self) {
        self.batch = Batch::default();
    }

    /// Undo everything the current batch changed, and drop the indexes it touched.
    pub(crate) fn rollback(&mut self) {
        while let Some(undo) = self.batch.journal.pop() {
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
            Undo::RootSet { key, old } => match old {
                Some(old) => {
                    self.root.insert(key, old);
                }
                None => {
                    self.root.shift_remove(&key);
                }
            },
            Undo::RootDeleted { key, index, old } => {
                self.root.shift_insert(index, key, old);
            }
            Undo::Field {
                owner,
                id,
                container,
                undo,
            } => {
                let container = self
                    .graph
                    .owner_mut(owner, &id)
                    .and_then(|root| resolve_mut(root, &container));
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

    /// Whether the edge existed when the batch started.
    pub(crate) fn is_base_edge(&self, id: &str) -> bool {
        if self.batch.added_edges.contains(id) {
            self.batch.removed_base_edges.contains(id)
        } else {
            self.graph.edges.contains_key(id) || self.batch.removed_base_edges.contains(id)
        }
    }

    // --- Changes that record their undo ---------------------------------------------------

    pub(crate) fn insert_node(&mut self, id: String, node: Value) {
        self.batch.added_nodes.insert(id.clone());
        self.batch.changed_nodes.insert(id.clone());
        self.batch.journal.push(Undo::NodeAdded(id.clone()));
        self.graph.nodes.insert(id, node);
    }

    /// Remove a node and return it. Its edges stay; the caller removes them.
    pub(crate) fn remove_node(&mut self, id: &str) -> Option<&Value> {
        let base = self.is_base_node(id);
        let (index, id, node) = self.graph.nodes.shift_remove_full(id)?;
        self.edge_index.forget_node(&id);
        self.lists.forget_node(&id);
        if base {
            self.batch.removed_base_nodes.insert(id.clone());
        }
        self.batch.changed_nodes.insert(id.clone());
        self.batch
            .journal
            .push(Undo::NodeRemoved { index, id, node });
        match self.batch.journal.last() {
            Some(Undo::NodeRemoved { node, .. }) => Some(node),
            _ => None,
        }
    }

    pub(crate) fn insert_edge(&mut self, id: String, edge: Value) {
        self.graph.attach(&id, &edge);
        if let Some(map) = edge.as_object() {
            self.edge_index.insert(map);
        }
        self.batch.added_edges.insert(id.clone());
        self.batch.changed_edges.insert(id.clone());
        self.batch.journal.push(Undo::EdgeAdded(id.clone()));
        self.graph.edges.insert(id, edge);
    }

    /// Remove the edges that exist among `ids`, each once. Return their ids,
    /// and with `keep`, copies of the edges.
    pub(crate) fn remove_edges<'i>(
        &mut self,
        ids: impl IntoIterator<Item = &'i str>,
        keep: bool,
    ) -> (Vec<String>, Vec<Map<String, Value>>) {
        let mut removed = Vec::new();
        let mut kept = Vec::new();
        let mut seen = HashSet::new();
        for id in ids {
            if !seen.insert(id) {
                continue;
            }
            let base = self.is_base_edge(id);
            let Some((index, id, edge)) = self.graph.edges.shift_remove_full(id) else {
                continue;
            };
            if let Some(map) = edge.as_object() {
                self.edge_index.forget(map);
                if keep {
                    kept.push(map.clone());
                }
            }
            self.graph.detach(&id, &edge);
            if base {
                self.batch.removed_base_edges.insert(id.clone());
            }
            self.batch.changed_edges.insert(id.clone());
            removed.push(id.clone());
            self.batch
                .journal
                .push(Undo::EdgeRemoved { index, id, edge });
        }
        (removed, kept)
    }

    pub(crate) fn set_root(&mut self, key: &str, value: Value) {
        let old = self.root.insert(key.to_owned(), value);
        self.batch.journal.push(Undo::RootSet {
            key: key.to_owned(),
            old,
        });
    }

    pub(crate) fn delete_root(&mut self, key: &str) {
        let Some(index) = self.root.keys().position(|existing| existing == key) else {
            return;
        };
        if let Some(old) = self.root.shift_remove(key) {
            self.batch.journal.push(Undo::RootDeleted {
                key: key.to_owned(),
                index,
                old,
            });
        }
    }

    /// Record how to undo a change made inside a node or an edge.
    pub(crate) fn record_field(
        &mut self,
        owner: Owner,
        id: &str,
        container: Vec<Step>,
        undo: FieldUndo,
    ) {
        match owner {
            Owner::Node => self.batch.changed_nodes.insert(id.to_owned()),
            Owner::Edge => self.batch.changed_edges.insert(id.to_owned()),
        };
        self.batch.journal.push(Undo::Field {
            owner,
            id: id.to_owned(),
            container,
            undo,
        });
    }

    /// The value the last recorded field change replaced or removed.
    pub(crate) fn last_replaced(&self) -> Option<&Value> {
        match self.batch.journal.last()? {
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

fn take_list(root: &mut Map<String, Value>, key: &str) -> Vec<Value> {
    match root.get_mut(key) {
        Some(value) => match std::mem::take(value) {
            Value::Array(items) => items,
            _ => Vec::new(),
        },
        None => Vec::new(),
    }
}

fn entry_id(entry: &Value) -> String {
    entry
        .get("id")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_owned()
}

/// Parse JSON text, reporting a parse failure as an invalid graph.
pub(crate) fn parse_json(text: &str) -> Result<Value> {
    serde_json::from_str(text)
        .map_err(|error| Error::graph(format!("flow data is not valid JSON: {error}"), Vec::new()))
}

/// The value at a resolved path.
pub(crate) fn resolve<'v>(root: &'v Value, steps: &[Step]) -> Option<&'v Value> {
    steps.iter().try_fold(root, |value, step| match step {
        Step::Key(key) => value.as_object()?.get(key),
        Step::Index(index) => value.as_array()?.get(*index),
    })
}

/// The value at a resolved path, to change it.
pub(crate) fn resolve_mut<'v>(root: &'v mut Value, steps: &[Step]) -> Option<&'v mut Value> {
    steps.iter().try_fold(root, |value, step| match step {
        Step::Key(key) => value.as_object_mut()?.get_mut(key),
        Step::Index(index) => value.as_array_mut()?.get_mut(*index),
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
