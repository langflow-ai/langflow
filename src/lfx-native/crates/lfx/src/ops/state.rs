//! [`GraphState`]: the indexed graph that apply and replay work on, kept between batches.
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
//!
//! A batch can also stay staged after it succeeds ([`GraphState::stage`]):
//! its layers wait until the caller keeps them ([`GraphState::keep`]) or
//! drops them ([`GraphState::drop_staged`]), for example after a database
//! commit. While a batch is staged, the graph as read
//! ([`GraphState::to_value`], [`GraphState::to_json`],
//! [`GraphState::entries`]) is the committed graph, without the batch.

use std::borrow::Cow;
use std::collections::HashMap;
use std::fmt;
use std::str::FromStr;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};

use crate::json_out::{self, Ascii};
use crate::value::{AnyMap, AnyValue, FiniteAnyValue};
use indexmap::{IndexMap, IndexSet};
use serde::ser::{Serialize, SerializeMap, Serializer};

use crate::ops::canonical;
use crate::ops::edges::{EdgeIndex, GraphRead};
use crate::ops::entry::EntryExt;
use crate::ops::error::{Error, Result};
use crate::ops::fields::{self, FieldLayer};
use crate::ops::keyed::ListIndex;
use crate::ops::ops::{Edge, Node, PathExt, Segment};
use crate::ops::schema::{KeyedList, NODE_SCHEMA};
use crate::ops::validate::{
    Numbers, PathPart, find_load_violations, validate_flow_data, violations_error,
};

// --- Layers --------------------------------------------------------------------------------

/// A map that a batch changes through a layer of its own.
///
/// Reads look in the layer first, then in the stored map. The first write to
/// a stored entry copies it into the layer. [`Layered::fold`] makes the layer
/// part of the stored map, and [`Layered::discard`] drops it.
///
/// Entries keep their order, as the nodes and edges of a flow keep theirs in
/// the Python engine and in the editor: a removal keeps the order of the
/// others, a replaced entry keeps its place, and a new one goes last.
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
            self.layer.shift_remove(key);
        }
        existed
    }

    /// Make the batch's changes part of the stored map, in time proportional
    /// to them, and for removals to the entries after the removed ones.
    pub fn fold(&mut self) {
        let mut removed = Vec::new();
        for (key, written) in std::mem::take(&mut self.layer) {
            match written {
                Some(value) => {
                    self.stored.insert(key, value);
                }
                None => removed.extend(self.stored.get_index_of(&key)),
            }
        }
        self.remove_slots(removed);
    }

    /// Remove the stored entries at `slots`, keeping the order of the others.
    ///
    /// Removing one entry moves every entry after it up one place. When that
    /// moves fewer entries in all than the map holds, as for entries near
    /// the end, each is removed in turn, from the last; else one pass keeps
    /// the entries not removed.
    fn remove_slots(&mut self, mut slots: Vec<usize>) {
        let len = self.stored.len();
        slots.sort_unstable();
        let moved: usize = slots.iter().map(|slot| len - slot).sum();
        if moved <= len {
            for slot in slots.into_iter().rev() {
                self.stored.shift_remove_index(slot);
            }
            return;
        }
        let mut slots = slots.into_iter().peekable();
        let mut slot = 0;
        self.stored.retain(|_, _| {
            let keep = slots.next_if_eq(&slot).is_none();
            slot += 1;
            keep
        });
    }

    /// Drop the batch's changes.
    pub fn discard(&mut self) {
        self.layer.clear();
    }

    /// The stored entries, without a staged batch's layer. Never in the
    /// middle of a batch, whose reads go through [`Self::get`].
    fn values(&self) -> impl Iterator<Item = &V> {
        self.stored.values()
    }

    /// The entries with a staged batch's layer, in the order [`Self::fold`]
    /// gives them: the stored entries that stay, each as the batch wrote it,
    /// then the entries the batch added.
    fn staged_entries(&self) -> impl Iterator<Item = (&String, &V)> {
        let kept = self
            .stored
            .iter()
            .filter_map(|(key, value)| match self.layer.get(key) {
                Some(written) => written.as_ref().map(|written| (key, written)),
                None => Some((key, value)),
            });
        let added = self
            .layer
            .iter()
            .filter(|(key, _)| !self.stored.contains_key(*key))
            .filter_map(|(key, written)| written.as_ref().map(|value| (key, value)));
        kept.chain(added)
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
                ids.shift_remove(id);
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
        step: impl FnMut(&'g AnyValue, usize, bool) -> Result<Option<&'g AnyValue>>,
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

    fn node_value(&self, id: &str, path: &[&str]) -> Option<Cow<'_, AnyValue>> {
        let node = self.nodes.get(id)?;
        let path: Vec<Segment> = path
            .iter()
            .map(|key| Segment::Key((*key).to_owned()))
            .collect();
        let step = |value, index: usize, _| Ok(fields::child(value, &path[..index], &path[index]));
        fields::read(node.as_value(), self.fields.node(id), &path, step)
            .expect("a read of object keys cannot fail")
    }

    fn edge(&self, id: &str) -> Option<&AnyMap> {
        self.edges.get(id).map(Edge::as_map)
    }

    fn edge_ids_at(&self, node_id: &str) -> impl Iterator<Item = &str> {
        self.edges_at(node_id).map(String::as_str)
    }
}

/// The value at `path` of node `id` as the batch sees it, with the batch's
/// field writes. A list item of a stored node is found through the list's
/// index, built the first time a read reaches it. `context` names the read
/// in an error.
///
/// # Errors
///
/// A key that the read looks up names two items of its list.
pub(crate) fn field_value<'g>(
    graph: &'g Graph,
    lists: &mut Lists,
    id: &str,
    path: &[Segment],
    context: &dyn fmt::Display,
) -> Result<Option<Cow<'g, AnyValue>>> {
    let Some(node) = graph.nodes.get(id) else {
        return Ok(None);
    };
    let stored = graph.is_stored_node(id);
    let step = |value: &'g AnyValue, index: usize, in_entry: bool| {
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
            .index(id, &list_path, keyed, items)
            .find(key, context)?;
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
        items: &[AnyValue],
    ) -> &mut ListIndex {
        let lists = self.by_node.entry(node_id.to_owned()).or_default();
        let position = if let Some(position) = lists
            .iter()
            .position(|(list_path, _)| list_path.equals(path))
        {
            position
        } else {
            let owned = path.iter().map(|key| (*key).to_owned()).collect();
            lists.push((owned, ListIndex::build(keyed, items)));
            lists.len() - 1
        };
        &mut lists[position].1
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
    root: AnyMap,
    pub(crate) graph: Graph,
    pub(crate) edge_index: EdgeIndex,
    pub(crate) lists: Lists,
    /// Whether the flow passed the structural rules since it was loaded or
    /// last replayed. Apply checks them once, before its first batch.
    base_checked: bool,
    /// Whether a batch is staged: its layers wait for [`Self::keep`] or
    /// [`Self::drop_staged`].
    staged: bool,
    /// The length of the graph's last JSON text, to size the next one's
    /// buffer: growing a buffer of megabytes copies it each time. Its
    /// snapshots share it.
    text_len: Arc<AtomicUsize>,
}

impl GraphState {
    /// Load a flow graph and build its indexes.
    ///
    /// Loading checks only what the indexes need: flow data is an object,
    /// `nodes` and `edges` are lists of objects, ids are unique, and each node
    /// and edge has its shape. Apply checks the other structural rules before
    /// its first batch; replay does not check them.
    ///
    /// # Errors
    ///
    /// The graph breaks a rule that the indexes need.
    pub fn new(flow: AnyValue) -> Result<Self> {
        violations_error(find_load_violations(&flow), "flow.data")?;
        let AnyValue::Object(mut root) = flow else {
            unreachable!("the load check refuses flow data that is not an object")
        };
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
            base_checked: false,
            staged: false,
            text_len: Arc::default(),
        })
    }

    /// Load a flow graph that apply changes next, after checking it against
    /// the structural rules. It does what the first batch would do, without
    /// a copy of the flow.
    ///
    /// Values are not walked for numbers that are not finite: that check
    /// belongs to whoever accepts a graph from outside, and skipping it keeps
    /// the check proportional to the number of nodes and edges.
    ///
    /// # Errors
    ///
    /// The graph breaks a structural rule.
    pub(crate) fn checked(flow: AnyValue) -> Result<Self> {
        validate_flow_data(&flow, Numbers::Skip, "flow.data", None)?;
        Ok(Self {
            base_checked: true,
            ..Self::new(flow)?
        })
    }

    /// Check the flow against the structural rules, unless it passed them
    /// since it was loaded or last replayed. Apply calls this before a batch.
    ///
    /// # Errors
    ///
    /// The graph breaks a structural rule.
    pub(crate) fn check_base(&mut self) -> Result<()> {
        if self.base_checked {
            return Ok(());
        }
        // Loading checked every structural rule but one: that each edge's
        // nodes exist. Apply and replay keep the others (they refuse a
        // repeated id, a node or edge without its shape, and a write of a
        // whole node object). So the graph passes when every edge's nodes
        // exist, which is checked in place. Else the whole check runs on a
        // copy, for the error and its violations in document order.
        let nodes = &self.graph.nodes.stored;
        let sound = self
            .graph
            .edges
            .stored
            .values()
            .all(|edge| nodes.contains_key(edge.source()) && nodes.contains_key(edge.target()));
        if !sound {
            validate_flow_data(&self.to_value(), Numbers::Skip, "flow.data", None)?;
        }
        self.base_checked = true;
        Ok(())
    }

    /// Note that a replay changed the flow, so apply checks it again.
    pub(crate) fn uncheck_base(&mut self) {
        self.base_checked = false;
    }

    /// Whether the next batch that apply or stage carries out checks the
    /// whole graph against the structural rules first ([`Self::check_base`]).
    #[must_use]
    pub fn needs_check(&self) -> bool {
        !self.base_checked
    }

    /// The number of nodes and edges of the committed graph: a measure of
    /// what work on the whole graph costs, such as [`Self::to_json`].
    #[must_use]
    pub fn item_count(&self) -> usize {
        self.graph.nodes.stored.len() + self.graph.edges.stored.len()
    }

    /// The graph as a JSON value.
    #[must_use]
    pub fn to_value(&self) -> AnyValue {
        let mut out = AnyMap::with_capacity(self.root.len());
        for (key, value) in &self.root {
            let value = match key.as_str() {
                "nodes" => AnyValue::Array(
                    self.graph
                        .nodes
                        .values()
                        .map(|node| node.as_value().clone())
                        .collect(),
                ),
                "edges" => AnyValue::Array(
                    self.graph
                        .edges
                        .values()
                        .map(|edge| AnyValue::Object(edge.as_map().clone()))
                        .collect(),
                ),
                _ => value.clone(),
            };
            out.insert(key.clone(), value);
        }
        AnyValue::Object(out)
    }

    /// The graph as JSON text: the text of [`GraphState::to_value`], written
    /// from the graph without copying it.
    ///
    /// # Panics
    ///
    /// A JSON value that `serde_json` cannot write, which a graph never holds:
    /// every key is a string.
    #[must_use]
    pub fn to_json(&self) -> String {
        serde_json::to_string(&self.json()).expect("a graph's keys are strings")
    }

    /// The graph, to serialize as JSON: it writes what [`GraphState::to_json`]
    /// writes, with any `serde_json` formatter.
    #[must_use]
    pub fn json(&self) -> impl Serialize + '_ {
        GraphJson(self)
    }

    /// The graph with the staged batch, to serialize as JSON: what
    /// [`GraphState::json`] writes after [`GraphState::keep`], without
    /// changing the committed graph. `None` when no batch is staged.
    ///
    /// A server writes the new graph in the transaction that records the
    /// batch, and keeps the batch only after that transaction commits.
    #[must_use]
    pub fn staged_json(&self) -> Option<impl Serialize + '_> {
        self.staged.then_some(StagedJson(self))
    }

    /// An empty buffer with room for the graph's last JSON text and a little more.
    fn text_buffer(&self) -> Vec<u8> {
        let last = self.text_len.load(Ordering::Relaxed);
        Vec::with_capacity(last + last / 16)
    }

    /// The graph as ASCII JSON text ([`crate::ops::api::json_text`]): what
    /// [`GraphState::json`] writes, with every character above U+007F
    /// escaped.
    pub(crate) fn json_text(&self) -> Vec<u8> {
        let out = graph_text(
            &self.root,
            self.graph.nodes.values().map(Node::as_value),
            self.graph.edges.values().map(Edge::as_map),
            self.text_buffer(),
        );
        self.text_len.store(out.len(), Ordering::Relaxed);
        out
    }

    /// The committed graph as it is now, without a staged batch, to read
    /// while the state goes on changing ([`GraphSnapshot`]). It shares every
    /// node and edge with the state, so it costs a pointer for each: a write
    /// after it copies only the node it changes.
    #[must_use]
    pub fn snapshot(&self) -> GraphSnapshot {
        GraphSnapshot {
            root: self.root.clone(),
            nodes: self.graph.nodes.values().cloned().collect(),
            edges: self.graph.edges.values().cloned().collect(),
            text_len: Arc::clone(&self.text_len),
        }
    }

    /// The graph with its staged batch as ASCII JSON text: what
    /// [`GraphState::staged_json`] writes, with every character above U+007F
    /// escaped. `None` when no batch is staged.
    pub(crate) fn staged_json_text(&self) -> Option<Vec<u8>> {
        if !self.staged {
            return None;
        }
        let graph = &self.graph;
        let mut out = self.text_buffer();
        json_out::write_entries(
            &mut out,
            self.root
                .iter()
                .map(|(key, value)| (key, (key.as_str(), value))),
            |out, (key, value)| match key {
                "nodes" => json_out::write_seq(out, self.staged_nodes(), |out, node| {
                    json_out::write_value(out, &node, Ascii::Escape);
                }),
                "edges" => {
                    json_out::write_seq(out, graph.edges.staged_entries(), |out, (_, edge)| {
                        json_out::write_map(out, edge.as_map(), Ascii::Escape);
                    });
                }
                _ => json_out::write_value(out, value, Ascii::Escape),
            },
            Ascii::Escape,
        );
        self.text_len.store(out.len(), Ordering::Relaxed);
        Some(out)
    }

    /// The nodes with the staged batch, in the order [`Layered::fold`] gives
    /// them: a node the batch writes as a copy with the writes, as the fold
    /// makes them, and any other node as it is.
    fn staged_nodes(&self) -> impl Iterator<Item = Cow<'_, AnyValue>> {
        let graph = &self.graph;
        graph
            .nodes
            .staged_entries()
            .map(|(id, node)| match graph.fields.node(id) {
                Some(writes) => {
                    let mut value = node.as_value().clone();
                    fields::make_writes(&mut value, writes.clone(), &mut Vec::new(), None);
                    Cow::Owned(value)
                }
                None => Cow::Borrowed(node.as_value()),
            })
    }

    /// The SHA-256 hex digest of the graph's canonical form: what
    /// [`canonical::graph_hash`] gives for [`GraphState::to_value`], from the
    /// loaded graph without a copy. The committed graph, without a staged batch.
    ///
    /// # Errors
    ///
    /// A number that is not finite as JavaScript reads it.
    pub fn graph_hash(&self) -> Result<String> {
        canonical::loaded_graph_hash(
            &self.root,
            self.graph
                .nodes
                .values()
                .map(|node| Cow::Borrowed(node.as_value()))
                .collect(),
            self.graph.edges.values().map(Edge::as_map).collect(),
        )
    }

    /// [`GraphState::graph_hash`] of the graph with its staged batch, as
    /// [`GraphState::keep`] will make it, or `None` when no batch is staged.
    ///
    /// # Errors
    ///
    /// A number that is not finite as JavaScript reads it.
    #[must_use]
    pub fn staged_graph_hash(&self) -> Option<Result<String>> {
        if !self.staged {
            return None;
        }
        let graph = &self.graph;
        let nodes = self.staged_nodes().collect();
        let edges = graph
            .edges
            .staged_entries()
            .map(|(_, edge)| edge.as_map())
            .collect();
        Some(canonical::loaded_graph_hash(&self.root, nodes, edges))
    }

    /// The graph's top-level keys in order, each with what [`GraphState::to_value`]
    /// puts there, borrowed from the graph: for a binding that builds the graph
    /// in its own language without a copy.
    pub fn entries(&self) -> impl Iterator<Item = (&str, Entry<'_>)> {
        self.root.iter().map(|(key, value)| {
            let entry = match key.as_str() {
                "nodes" => Entry::Nodes(Nodes(&self.graph.nodes)),
                "edges" => Entry::Edges(Edges(&self.graph.edges)),
                _ => Entry::Value(value),
            };
            (key.as_str(), entry)
        })
    }

    /// The graph as a JSON value, without copying it.
    #[must_use]
    pub fn into_value(self) -> AnyValue {
        let Self {
            mut root, graph, ..
        } = self;
        root.insert(
            "nodes".into(),
            AnyValue::Array(graph.nodes.into_values().map(Node::into_value).collect()),
        );
        root.insert(
            "edges".into(),
            AnyValue::Array(
                graph
                    .edges
                    .into_values()
                    .map(|edge| AnyValue::Object(edge.into_map()))
                    .collect(),
            ),
        );
        AnyValue::Object(root)
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

    /// Whether a batch is staged ([`Self::stage`]).
    #[must_use]
    pub fn is_staged(&self) -> bool {
        self.staged
    }

    /// Note that the batch that just succeeded stays staged.
    pub(crate) fn set_staged(&mut self) {
        self.staged = true;
    }

    /// Keep the staged batch: its layers become the graph. Returns whether a
    /// batch was staged; with none, nothing changes.
    pub fn keep(&mut self) -> bool {
        if !self.staged {
            return false;
        }
        self.staged = false;
        self.commit();
        true
    }

    /// Drop the staged batch: the graph stays as it was before it. Returns
    /// whether a batch was staged; with none, nothing changes.
    pub fn drop_staged(&mut self) -> bool {
        if !self.staged {
            return false;
        }
        self.staged = false;
        self.discard();
        true
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
        let AnyValue::Object(node) = node else {
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

/// Nodes or edges by id, in their order, each made by `make`. The load check
/// passed, so each one is an object with its shape and a unique id.
fn by_id<T>(items: Vec<AnyValue>, make: fn(AnyMap) -> Result<T>) -> Result<IndexMap<String, T>> {
    items
        .into_iter()
        .map(|item| {
            let AnyValue::Object(item) = item else {
                unreachable!("the load check refuses nodes and edges that are not objects")
            };
            Ok((item.id().to_owned(), make(item)?))
        })
        .collect()
}

/// Parse a flow graph given as JSON text, and load it into a [`GraphState`].
impl FromStr for GraphState {
    type Err = Error;

    fn from_str(text: &str) -> Result<Self> {
        Self::new(parse_finite_json(text)?)
    }
}

/// The graph as JSON text.
impl fmt::Display for GraphState {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.to_json())
    }
}

/// Writes a [`GraphState`] as [`GraphState::to_value`] builds it: the root's
/// keys in order, with the nodes and edges in place of their placeholders.
struct GraphJson<'s>(&'s GraphState);

impl Serialize for GraphJson<'_> {
    fn serialize<S: Serializer>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error> {
        let mut map = serializer.serialize_map(Some(self.0.root.len()))?;
        for (key, entry) in self.0.entries() {
            match entry {
                Entry::Value(value) => map.serialize_entry(key, value)?,
                Entry::Nodes(nodes) => map.serialize_entry(key, &NodesJson(nodes))?,
                Entry::Edges(edges) => map.serialize_entry(key, &EdgesJson(edges))?,
            }
        }
        map.end()
    }
}

/// A graph as a [`GraphState`] held it when [`GraphState::snapshot`] took
/// it: read only, and unchanged by the state's later batches. A server takes
/// one while it holds the state, and writes and hashes it after, on another
/// thread, while batches go on.
#[derive(Debug, Clone)]
pub struct GraphSnapshot {
    /// The flow's top-level object; `nodes` and `edges` hold placeholders.
    root: AnyMap,
    nodes: Vec<Node>,
    edges: Vec<Edge>,
    /// The length of the state's last JSON text, shared with the state.
    text_len: Arc<AtomicUsize>,
}

impl GraphSnapshot {
    /// The number of nodes and edges: a measure of what work on the whole graph costs.
    #[must_use]
    pub fn item_count(&self) -> usize {
        self.nodes.len() + self.edges.len()
    }

    /// The graph as ASCII JSON text: what [`GraphState`] wrote when the
    /// snapshot was taken ([`crate::ops::api::json_text`]).
    pub(crate) fn json_text(&self) -> Vec<u8> {
        let last = self.text_len.load(Ordering::Relaxed);
        let out = graph_text(
            &self.root,
            self.nodes.iter().map(Node::as_value),
            self.edges.iter().map(Edge::as_map),
            Vec::with_capacity(last + last / 16),
        );
        self.text_len.store(out.len(), Ordering::Relaxed);
        out
    }

    /// The SHA-256 hex digest of the graph's canonical form: what
    /// [`GraphState::graph_hash`] gave when the snapshot was taken.
    ///
    /// # Errors
    ///
    /// A number that is not finite as JavaScript reads it.
    pub fn graph_hash(&self) -> Result<String> {
        canonical::loaded_graph_hash(
            &self.root,
            self.nodes
                .iter()
                .map(|node| Cow::Borrowed(node.as_value()))
                .collect(),
            self.edges.iter().map(Edge::as_map).collect(),
        )
    }
}

/// A loaded graph as ASCII JSON text, into `out`: the top-level keys in
/// order, with `nodes` and `edges` in their place.
fn graph_text<'g>(
    root: &'g AnyMap,
    nodes: impl IntoIterator<Item = &'g AnyValue>,
    edges: impl IntoIterator<Item = &'g AnyMap>,
    mut out: Vec<u8>,
) -> Vec<u8> {
    let (mut nodes, mut edges) = (Some(nodes), Some(edges));
    json_out::write_entries(
        &mut out,
        root.iter().map(|(key, value)| (key, (key.as_str(), value))),
        |out, (key, value)| match key {
            "nodes" => json_out::write_seq(out, nodes.take().into_iter().flatten(), |out, node| {
                json_out::write_value(out, node, Ascii::Escape);
            }),
            "edges" => json_out::write_seq(out, edges.take().into_iter().flatten(), |out, edge| {
                json_out::write_map(out, edge, Ascii::Escape);
            }),
            _ => json_out::write_value(out, value, Ascii::Escape),
        },
        Ascii::Escape,
    );
    out
}

/// Writes a [`GraphState`] with its staged batch ([`GraphState::staged_json`]).
struct StagedJson<'s>(&'s GraphState);

impl Serialize for StagedJson<'_> {
    fn serialize<S: Serializer>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error> {
        let state = self.0;
        let mut map = serializer.serialize_map(Some(state.root.len()))?;
        for (key, value) in &state.root {
            match key.as_str() {
                "nodes" => map.serialize_entry(key, &StagedNodesJson(state))?,
                "edges" => map.serialize_entry(key, &StagedEdgesJson(state))?,
                _ => map.serialize_entry(key, value)?,
            }
        }
        map.end()
    }
}

struct StagedNodesJson<'s>(&'s GraphState);

impl Serialize for StagedNodesJson<'_> {
    fn serialize<S: Serializer>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error> {
        serializer.collect_seq(self.0.staged_nodes())
    }
}

struct StagedEdgesJson<'s>(&'s GraphState);

impl Serialize for StagedEdgesJson<'_> {
    fn serialize<S: Serializer>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error> {
        serializer.collect_seq(
            self.0
                .graph
                .edges
                .staged_entries()
                .map(|(_, edge)| edge.as_map()),
        )
    }
}

struct NodesJson<'s>(Nodes<'s>);

impl Serialize for NodesJson<'_> {
    fn serialize<S: Serializer>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error> {
        serializer.collect_seq(self.0.iter())
    }
}

struct EdgesJson<'s>(Edges<'s>);

impl Serialize for EdgesJson<'_> {
    fn serialize<S: Serializer>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error> {
        serializer.collect_seq(self.0.iter())
    }
}

/// A top-level entry of a [`GraphState`], borrowed from it ([`GraphState::entries`]).
#[derive(Debug, Clone, Copy)]
pub enum Entry<'s> {
    /// A key that no operation writes, as stored.
    Value(&'s AnyValue),
    /// The nodes, in the graph's order.
    Nodes(Nodes<'s>),
    /// The edges, in the graph's order.
    Edges(Edges<'s>),
}

/// The nodes of a [`GraphState`], borrowed from it.
#[derive(Debug, Clone, Copy)]
pub struct Nodes<'s>(&'s Layered<Node>);

impl<'s> Nodes<'s> {
    /// Each node's JSON object.
    pub fn iter(self) -> impl Iterator<Item = &'s AnyValue> {
        self.0.values().map(Node::as_value)
    }
}

/// The edges of a [`GraphState`], borrowed from it.
#[derive(Debug, Clone, Copy)]
pub struct Edges<'s>(&'s Layered<Edge>);

impl<'s> Edges<'s> {
    /// Each edge's JSON object.
    pub fn iter(self) -> impl Iterator<Item = &'s AnyMap> {
        self.0.values().map(Edge::as_map)
    }
}

/// The list at `key`, moved out. The load check passed, so it is a list.
fn take_list(root: &mut AnyMap, key: &str) -> Vec<AnyValue> {
    match root.get_mut(key).map(std::mem::take) {
        Some(AnyValue::Array(items)) => items,
        _ => unreachable!("the load check refuses nodes and edges that are not lists"),
    }
}

/// Parse JSON text, reporting a parse failure as an invalid graph.
pub(crate) fn parse_json(text: &str) -> Result<AnyValue> {
    serde_json::from_str(text).map_err(|error| graph_not_json(&error))
}

/// Parse JSON text as [`parse_json`] does, refusing a number that is not
/// finite as a double ([`FiniteAnyValue`]): for a graph that the engine holds
/// and changes, as a Python `float` that is not finite is refused.
pub(crate) fn parse_finite_json(text: &str) -> Result<AnyValue> {
    serde_json::from_str(text)
        .map(|FiniteAnyValue(value)| value)
        .map_err(|error| graph_not_json(&error))
}

fn graph_not_json(error: &serde_json::Error) -> Error {
    Error::graph_message(format!(
        "flow data is not valid JSON: {}",
        parse_problem(error)
    ))
}

/// Why JSON text does not parse. A value the parser read but refused, such
/// as a number that is not finite, is named without its place in the text,
/// as a Python value that breaks the same limit is.
pub(crate) fn parse_problem(error: &serde_json::Error) -> String {
    let text = error.to_string();
    if error.is_data()
        && let Some((problem, _)) = text.rsplit_once(" at line ")
    {
        return problem.to_owned();
    }
    text
}

/// The value at a path of object keys and array indexes.
pub(crate) fn resolve<'v>(root: &'v AnyValue, steps: &[PathPart]) -> Option<&'v AnyValue> {
    steps.iter().try_fold(root, |value, step| match step {
        PathPart::Key(key) => value.as_object()?.get(key),
        PathPart::Index(index) => value.as_array()?.get(*index),
    })
}

/// The value at a path of object keys and array indexes, to change it.
pub(crate) fn resolve_mut<'v>(
    root: &'v mut AnyValue,
    steps: &[PathPart],
) -> Option<&'v mut AnyValue> {
    steps.iter().try_fold(root, |value, step| match step {
        PathPart::Key(key) => value.as_object_mut()?.get_mut(key),
        PathPart::Index(index) => value.as_array_mut()?.get_mut(*index),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_snapshot_keeps_the_graph_as_it_was() {
        use crate::json;
        use crate::ops::api::{graph_json, snapshot_json, state_graph_hash};
        use crate::ops::{ApplyOptions, Operation};
        let node = |id: &str| json!({"id": id, "data": {"node": {"template": {"t": {"value": "x", "type": "str"}}}}});
        let flow = json!({"nodes": [node("a"), node("b")], "edges": [{"id": "e", "source": "a", "target": "b"}], "name": "f"});
        let mut state = GraphState::new(flow).unwrap();
        let (text, hash) = (graph_json(&state), state_graph_hash(&state).unwrap());
        let snapshot = state.snapshot();
        let write = json!([{"type": "update_nodes", "updates": [
            {"id": "a", "op": "set_field", "path": ["data", "node", "template", "t", "value"], "value": "y"}
        ]}]);
        let delete = json!([{"type": "delete_nodes", "ids": ["b"]}]);
        for batch in [write, delete] {
            let operations = Operation::list_from_value(batch).unwrap();
            state.apply(operations, ApplyOptions::default()).unwrap();
        }
        // A staged batch is not in a snapshot either.
        let staged = json!([{"type": "update_nodes", "updates": [
            {"id": "a", "op": "set_field", "path": ["data", "node", "template", "t", "value"], "value": "z"}
        ]}]);
        state
            .stage(
                Operation::list_from_value(staged).unwrap(),
                ApplyOptions::default(),
            )
            .unwrap();
        let later = state.snapshot();
        assert_eq!(
            (snapshot_json(&snapshot), snapshot.graph_hash().unwrap()),
            (text, hash)
        );
        assert_eq!(snapshot_json(&later), graph_json(&state));
        assert_eq!(
            later.graph_hash().unwrap(),
            state_graph_hash(&state).unwrap()
        );
        assert_ne!(later.graph_hash().unwrap(), snapshot.graph_hash().unwrap());
    }

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
        let entries: Vec<_> = map
            .stored
            .iter()
            .map(|(key, value)| (key.as_str(), *value))
            .collect();
        assert_eq!(entries, [("a", 10), ("b", 20), ("x", 24)]);
    }

    #[test]
    fn removals_keep_the_order_of_the_other_entries() {
        let mut map = stored(&["a", "b", "c", "d"]);
        map.remove("b");
        map.fold();
        assert_eq!(keys(&map), ["a", "c", "d"]);

        let mut map = stored(&["a", "b", "c", "d", "e"]);
        map.insert("x".into(), 24);
        map.insert("y".into(), 25);
        map.insert("z".into(), 26);
        map.remove("x");
        map.remove("b");
        map.remove("d");
        map.fold();
        assert_eq!(keys(&map), ["a", "c", "e", "y", "z"]);

        // Entries near the end are removed one by one.
        let mut map = stored(&["a", "b", "c", "d", "e"]);
        map.remove("e");
        map.remove("c");
        map.fold();
        assert_eq!(keys(&map), ["a", "b", "d"]);
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
