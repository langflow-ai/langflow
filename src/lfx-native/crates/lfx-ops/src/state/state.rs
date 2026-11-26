//! [`GraphState`]: the indexed graph that apply and replay work
//! on, kept between batches.
//!
//! A batch stages changes in the graph's maps. A batch that
//! succeeds commits its pending changes to the graph. A batch
//! that fails drops them, so nothing is undone.
//!
//! A staged batch ([`GraphState::stage`]) waits for
//! [`GraphState::keep`] or [`GraphState::drop_staged`]. Until
//! then, reads give the committed graph.

use std::borrow::Cow;
use std::sync::atomic::AtomicUsize;
use std::sync::{Arc, Mutex, PoisonError, TryLockError, Weak};

use crate::json::serialize::{self, Ascii};
use crate::json::{FlowObj, FlowStr, FlowValue};
use crate::map::patched::PatchedMap;

use crate::compare;
use crate::flow::deserialize::DeserializeError;
use crate::flow::edge::Edge;
use crate::flow::node::Node;
use crate::rule::edge::{EdgeIndex, GraphRead};
use crate::state::field_write::{self, PathWrites};
use crate::validate::{Numbers, validate_flow_data};
use crate::violation::error::{Error, Result};

use crate::snapshot::{GraphSnapshot, SnapshotData, sized_text, write_graph};
use crate::state::index::{EdgesAt, Graph, Lists};

/// A flow graph, indexed for applying operations. It keeps its
/// indexes between batches, so each batch costs only what it
/// changes.
#[derive(Debug)]
pub struct GraphState {
    /// The flow's top-level object; `nodes` and `edges` hold
    /// placeholders. No operation writes its other keys, which
    /// are view state.
    root: FlowObj,
    pub(crate) graph: Graph,
    pub(crate) edge_index: EdgeIndex,
    pub(crate) lists: Lists,
    /// Whether a batch waits for [`Self::keep`] or
    /// [`Self::drop_staged`].
    staged: bool,
    /// The length of the last JSON text, to pre-size the next
    /// buffer. Growing a buffer of megabytes copies it each
    /// time.
    text_len: Arc<AtomicUsize>,
    /// Readers can share the current snapshot while any reader
    /// still owns it.
    snapshot_cache: Mutex<Weak<SnapshotData>>,
    /// The nodes and edges that batches removed since
    /// [`Self::take_released`].
    released: Released,
}

/// The nodes and edges that kept batches removed, for the
/// caller to free.
#[derive(Debug, Default)]
struct Released {
    nodes: Vec<Node>,
    edges: Vec<Edge>,
}

impl Released {
    fn is_empty(&self) -> bool {
        self.nodes.is_empty() && self.edges.is_empty()
    }
}

impl GraphState {
    /// Load a flow graph and build its indexes.
    ///
    /// Loading checks every structural rule. Apply then checks
    /// only what its batch changes. It does not check for
    /// numbers that are not finite. The caller that accepts the
    /// graph does that.
    ///
    /// # Errors
    ///
    /// The graph breaks a structural rule.
    pub fn new(flow: FlowValue) -> Result<Self> {
        validate_flow_data(&flow, Numbers::Skip, "flow.data", None)?;
        Self::from_checked(flow)
    }

    /// [`GraphState::new`] for a graph that passed its
    /// structural check.
    pub(crate) fn from_checked(flow: FlowValue) -> Result<Self> {
        let FlowValue::Object(mut root) = flow else {
            unreachable!("the load check refuses flow data that is not an object")
        };
        let nodes = by_id(take_list(&mut root, "nodes"), "node", Node::try_from)?;
        let edges = by_id(take_list(&mut root, "edges"), "edge", Edge::try_from)?;
        let mut edges_at = EdgesAt::new();
        for edge in edges.values() {
            edges_at.attach(edge.id(), edge);
        }
        edges_at.commit();
        Ok(Self {
            root,
            snapshot_cache: Mutex::new(Weak::new()),
            graph: Graph {
                nodes,
                edges,
                edges_at,
            },
            edge_index: EdgeIndex::default(),
            lists: Lists::default(),
            staged: false,
            text_len: Arc::default(),
            released: Released::default(),
        })
    }

    /// The number of nodes and edges of the committed graph. It
    /// measures the cost of whole-graph work, such as
    /// [`Self::to_json`].
    #[must_use]
    pub fn item_count(&self) -> usize {
        self.graph.nodes.len() + self.graph.edges.len()
    }

    /// The graph as a JSON value.
    #[must_use]
    pub fn to_value(&self) -> FlowValue {
        let mut out = FlowObj::with_capacity(self.root.len());
        for (key, value) in &self.root {
            let value = match key.as_str() {
                "nodes" => FlowValue::Array(
                    self.graph
                        .nodes
                        .values()
                        .map(|node| node.as_value().clone())
                        .collect(),
                ),
                "edges" => FlowValue::Array(
                    self.graph
                        .edges
                        .values()
                        .map(|edge| FlowValue::Object(edge.as_map().clone()))
                        .collect(),
                ),
                _ => value.clone(),
            };
            out.insert_shared(key.clone(), value);
        }
        FlowValue::Object(out)
    }

    /// The committed graph as ASCII JSON text, written without
    /// a copy.
    #[must_use]
    pub fn to_json(&self) -> String {
        sized_text(&self.text_len, |out| {
            write_graph(
                out,
                &self.root,
                self.graph.nodes.values().map(Node::as_map),
                self.graph.edges.values().map(Edge::as_map),
                |out, node| serialize::write_map(out, node, Ascii::Escape),
            );
        })
    }

    /// [`GraphState::to_json`] with the staged batch, or `None`
    /// when no batch is staged.
    #[must_use]
    pub fn staged_to_json(&self) -> Option<String> {
        if !self.staged {
            return None;
        }
        Some(sized_text(&self.text_len, |out| {
            write_graph(
                out,
                &self.root,
                self.staged_nodes(),
                self.graph
                    .edges
                    .pending_values()
                    .map(|(edge, _)| edge.as_map()),
                |out, node| serialize::write_value(out, &node, Ascii::Escape),
            );
        }))
    }

    /// The nodes with the staged batch, in the order
    /// [`PatchedMap::commit`] gives them. A written node is a
    /// copy with its writes made.
    fn staged_nodes(&self) -> impl Iterator<Item = Cow<'_, FlowValue>> {
        self.graph.nodes.pending_values().map(|(node, writes)| {
            let value = node.as_value();
            let Some(writes) = writes.filter(|writes| !writes.is_empty()) else {
                return Cow::Borrowed(value);
            };

            let mut copy = value.clone();
            field_write::make_writes(&mut copy, writes.clone(), &mut Vec::new(), None);
            Cow::Owned(copy)
        })
    }

    /// [`compare::graph_hash`] of the committed graph, without
    /// a copy.
    ///
    /// # Errors
    ///
    /// A number that is not finite as JavaScript reads it.
    pub fn graph_hash(&self) -> Result<String> {
        Ok(compare::loaded_graph_hash(
            &self.root,
            self.graph
                .nodes
                .values()
                .map(|node| Cow::Borrowed(node.as_value()))
                .collect(),
            self.graph.edges.values().map(Edge::as_map).collect(),
        )?)
    }

    /// [`GraphState::graph_hash`] with the staged batch, or
    /// `None` when no batch is staged.
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
            .pending_values()
            .map(|(edge, _)| edge.as_map())
            .collect();
        Some(compare::loaded_graph_hash(&self.root, nodes, edges).map_err(Error::from))
    }

    /// The top-level entries in order, borrowed. A binding
    /// builds the graph from them without a copy.
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

    /// Move the graph into a JSON value, sharing objects with
    /// live snapshots.
    #[must_use]
    pub fn into_value(self) -> FlowValue {
        let Self {
            mut root, graph, ..
        } = self;
        root.insert(
            "nodes".into(),
            FlowValue::Array(graph.nodes.into_items(Node::into_value)),
        );
        root.insert(
            "edges".into(),
            FlowValue::Array(
                graph
                    .edges
                    .into_items(|edge| FlowValue::Object(edge.into_map())),
            ),
        );
        FlowValue::Object(root)
    }

    // --- Batches ---------------------------------------------

    /// End a batch that succeeded: its pending changes become
    /// the graph.
    pub(crate) fn commit(&mut self) {
        // Free what no caller took, so it waits at most one
        // batch.
        self.released.nodes.clear();
        self.released.edges.clear();
        *self
            .snapshot_cache
            .get_mut()
            .unwrap_or_else(PoisonError::into_inner) = Weak::new();
        self.graph
            .nodes
            .commit(&mut self.released.nodes, |id, node, writes| {
                if writes.is_empty() {
                    return;
                }

                let lists = if self.lists.by_node.contains_key(id) {
                    Some((&mut self.lists, id))
                } else {
                    None
                };
                field_write::make_writes(node.as_value_mut(), writes, &mut Vec::new(), lists);
            });
        self.graph
            .edges
            .commit(&mut self.released.edges, |_, _, ()| {});
        self.graph.edges_at.commit();
        self.edge_index.commit();
    }

    /// End a batch that failed: drop its pending changes.
    pub(crate) fn drop_pending(&mut self) {
        self.graph.drop_pending();
        self.edge_index.drop_pending();
    }

    /// Whether a batch is staged ([`Self::stage`]).
    #[must_use]
    pub fn is_staged(&self) -> bool {
        self.staged
    }

    /// Keep the batch that just succeeded staged.
    pub(crate) fn set_staged(&mut self) {
        self.staged = true;
    }

    /// The nodes and edges that kept batches removed, for the
    /// caller to free off the request path. `None` when there
    /// are none.
    pub fn take_released(&mut self) -> Option<impl Send + 'static + use<>> {
        if self.released.is_empty() {
            return None;
        }
        Some(std::mem::take(&mut self.released))
    }

    /// Keep the staged batch. Returns whether a batch was
    /// staged. Removed nodes and edges wait for
    /// [`Self::take_released`].
    pub fn keep(&mut self) -> bool {
        if !self.staged {
            return false;
        }
        self.staged = false;
        self.commit();
        true
    }

    /// Drop the staged batch. Returns whether a batch was
    /// staged.
    pub fn drop_staged(&mut self) -> bool {
        if !self.staged {
            return false;
        }
        self.staged = false;
        self.drop_pending();
        true
    }

    /// Whether the node existed when the batch started.
    pub(crate) fn is_base_node(&self, id: &str) -> bool {
        self.graph.nodes.is_based(id)
    }

    // --- Changes ---------------------------------------------

    /// Add `node`, whose id the graph does not have.
    pub(crate) fn insert_node(&mut self, node: Node) {
        debug_assert!(!self.graph.nodes.contains(node.id()), "a new node id");
        self.graph.nodes.insert(id_key(node.as_map()), node);
    }

    /// A copy of the node `id` as the batch sees it, for the
    /// backward operations.
    pub(crate) fn node_copy(&self, id: &str) -> Option<Node> {
        let node = self.graph.node_value(id, &[])?.into_owned();
        let FlowValue::Object(node) = node else {
            unreachable!("a node is a JSON object")
        };
        Some(Node::try_from(node).expect("a field write keeps the shape of a node"))
    }

    /// Remove the node `id`, if it exists. Its edges stay; the
    /// caller removes them.
    pub(crate) fn remove_node(&mut self, id: &str) {
        self.graph.nodes.remove(id);
        self.edge_index.forget_node(id);
        self.lists.forget_node(id);
    }

    /// Add `edge`, whose id the graph does not have.
    pub(crate) fn insert_edge(&mut self, edge: Edge) {
        debug_assert!(!self.graph.edges.contains(edge.id()), "a new edge id");
        self.graph.edges_at.attach(edge.id(), &edge);
        self.edge_index.insert(edge.as_map());
        self.graph.edges.insert(id_key(edge.as_map()), edge);
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

fn id_key(item: &FlowObj) -> FlowStr {
    let Some(FlowValue::String(id)) = item.get("id") else {
        unreachable!("a checked graph item has a string id");
    };
    id.clone()
}

/// Nodes or edges by id, in their order, each made by `make`.
fn by_id<T, P>(
    items: Vec<FlowValue>,
    root: &str,
    make: fn(FlowObj) -> Result<T, DeserializeError>,
) -> Result<PatchedMap<T, P>> {
    items
        .into_iter()
        .map(|item| {
            let FlowValue::Object(item) = item else {
                unreachable!("the load check refuses nodes and edges that are not objects")
            };
            let id = id_key(&item);
            let value = make(item).map_err(|error| error.into_error(root))?;
            Ok((id, value))
        })
        .collect()
}

/// A top-level entry of a [`GraphState`], borrowed from it
/// ([`GraphState::entries`]).
#[derive(Debug, Clone, Copy)]
pub enum Entry<'s> {
    /// A key that no operation writes, as stored.
    Value(&'s FlowValue),
    /// The nodes, in the graph's order.
    Nodes(Nodes<'s>),
    /// The edges, in the graph's order.
    Edges(Edges<'s>),
}

/// The nodes of a [`GraphState`], borrowed from it.
#[derive(Debug, Clone, Copy)]
pub struct Nodes<'s>(&'s PatchedMap<Node, PathWrites>);

impl<'s> Nodes<'s> {
    /// Each node's JSON object.
    pub fn iter(self) -> impl Iterator<Item = &'s FlowValue> {
        self.0.values().map(Node::as_value)
    }
}

/// The edges of a [`GraphState`], borrowed from it.
#[derive(Debug, Clone, Copy)]
pub struct Edges<'s>(&'s PatchedMap<Edge>);

impl<'s> Edges<'s> {
    /// Each edge's JSON object.
    pub fn iter(self) -> impl Iterator<Item = &'s FlowObj> {
        self.0.values().map(Edge::as_map)
    }
}

/// The list at `key`, moved out.
fn take_list(root: &mut FlowObj, key: &str) -> Vec<FlowValue> {
    match root.get_mut(key).map(std::mem::take) {
        Some(FlowValue::Array(items)) => items,
        _ => unreachable!("the load check refuses nodes and edges that are not lists"),
    }
}

impl GraphState {
    /// The committed graph, to read while the state goes on
    /// changing. A new snapshot copies the ordered node and
    /// edge lists and shares their JSON objects. Readers of the
    /// same revision can share a snapshot while it is alive.
    #[must_use]
    pub fn snapshot(&self) -> GraphSnapshot {
        let mut cache = self
            .snapshot_cache
            .lock()
            .unwrap_or_else(PoisonError::into_inner);
        self.snapshot_cached(&mut cache)
    }

    /// Try to take a snapshot without waiting for the snapshot
    /// lock. On `None`, a caller with the GIL can release it
    /// and wait.
    #[must_use]
    pub fn try_snapshot(&self) -> Option<GraphSnapshot> {
        let mut cache = match self.snapshot_cache.try_lock() {
            Ok(cache) => cache,
            Err(TryLockError::Poisoned(error)) => error.into_inner(),
            Err(TryLockError::WouldBlock) => return None,
        };
        Some(self.snapshot_cached(&mut cache))
    }

    fn snapshot_cached(&self, cache: &mut Weak<SnapshotData>) -> GraphSnapshot {
        if let Some(data) = cache.upgrade() {
            return GraphSnapshot { data };
        }
        let data = Arc::new(SnapshotData {
            root: self.root.clone(),
            nodes: self.graph.nodes.snapshot(),
            edges: self.graph.edges.snapshot(),
            text_len: Arc::clone(&self.text_len),
        });
        // The last reader releases the lists, without deferring
        // that work to the next write.
        *cache = Arc::downgrade(&data);
        GraphSnapshot { data }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_snapshot_keeps_the_graph_as_it_was() {
        use crate::flow_value;
        use crate::{ApplyOptions, Operation};
        let node = |id: &str| flow_value!({"id": id, "data": {"node": {"template": {"t": {"value": "x", "type": "str"}}}}});
        let flow = flow_value!({"nodes": [node("a"), node("b")], "edges": [{"id": "e", "source": "a", "target": "b"}], "name": "f"});
        let mut state = GraphState::new(flow).unwrap();
        let (text, hash) = (state.to_json(), state.graph_hash().unwrap());
        let snapshot = state.snapshot();
        let write = flow_value!([{"type": "update_nodes", "updates": [
            {"id": "a", "op": "set_field", "path": ["data", "node", "template", "t", "value"], "value": "y"}
        ]}]);
        let delete = flow_value!([{"type": "delete_nodes", "ids": ["b"]}]);
        for batch in [write, delete] {
            let operations = Operation::list_from_value(batch).unwrap();
            state.apply(operations, ApplyOptions::default()).unwrap();
        }
        // A staged batch is not in a snapshot either.
        let staged = flow_value!([{"type": "update_nodes", "updates": [
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
            (snapshot.to_json(), snapshot.graph_hash().unwrap()),
            (text, hash)
        );
        assert_eq!(later.to_json(), state.to_json());
        assert_eq!(later.graph_hash().unwrap(), state.graph_hash().unwrap());
        assert_ne!(later.graph_hash().unwrap(), snapshot.graph_hash().unwrap());
    }

    #[test]
    fn loading_refuses_an_edge_without_its_node() {
        let node = crate::flow_value!({"id": "a", "data": {"node": {"template": {}}}});
        let edge = crate::flow_value!({"id": "e", "source": "a", "target": "gone"});
        let flow = crate::flow_value!({"nodes": [node], "edges": [edge]});
        let error = GraphState::new(flow).unwrap_err();
        assert_eq!(error.code.as_str(), "FLOW_GRAPH_INVALID", "{error}");
        let violation = &error.violations[0];
        assert_eq!(
            violation.code,
            crate::validate::ViolationCode::EdgeEndpointInvalid
        );
    }

    #[test]
    fn cached_snapshots_follow_kept_batches_and_ignore_refused_or_dropped_batches() {
        let mut state = GraphState::new(
            crate::flow_value!({"nodes":[snapshot_node("a").into_value()],"edges":[]}),
        )
        .unwrap();
        let before = state.snapshot();
        assert!(Arc::ptr_eq(&before.data, &state.snapshot().data));
        let batch = |id: &str| set_t(id, "new");
        state
            .stage(batch("a"), crate::ApplyOptions::default())
            .unwrap();
        assert!(Arc::ptr_eq(&before.data, &state.snapshot().data));
        assert!(state.drop_staged());
        assert!(Arc::ptr_eq(&before.data, &state.snapshot().data));
        assert!(
            state
                .apply(batch("missing"), crate::ApplyOptions::default())
                .is_err()
        );
        assert!(Arc::ptr_eq(&before.data, &state.snapshot().data));
        state
            .stage(batch("a"), crate::ApplyOptions::default())
            .unwrap();
        assert!(state.keep());
        assert!(!Arc::ptr_eq(&before.data, &state.snapshot().data));
        assert_ne!(before.graph_hash().unwrap(), state.graph_hash().unwrap());
    }

    #[test]
    fn concurrent_snapshot_last_owners_transfer_one_old_payload() {
        let mut state = GraphState::new(
            crate::flow_value!({"nodes":[snapshot_node("a").into_value()],"edges":[]}),
        )
        .unwrap();
        let first = state.snapshot();
        let second = state.snapshot();
        let old_map = first.data.nodes[0].as_map().clone();
        let batch = set_t("a", "new");
        state.apply(batch, crate::ApplyOptions::default()).unwrap();
        let barrier = Arc::new(std::sync::Barrier::new(2));
        let threads: Vec<_> = [first, second]
            .into_iter()
            .map(|snapshot| {
                let barrier = barrier.clone();
                std::thread::spawn(move || {
                    barrier.wait();
                    snapshot.into_unshared_data()
                })
            })
            .collect();
        let payloads: Vec<_> = threads
            .into_iter()
            .map(|thread| thread.join().unwrap())
            .collect();
        assert_eq!(payloads.iter().flatten().count(), 1);
        assert!(old_map.clone().into_unshared_entries().is_none());
        drop(payloads);
        assert!(old_map.into_unshared_entries().is_some());
    }

    #[test]
    fn try_snapshot_returns_none_while_the_lock_is_held() {
        let state = GraphState::new(crate::flow_value!({"nodes":[],"edges":[]})).unwrap();
        let guard = state.snapshot_cache.lock().unwrap();
        assert!(state.try_snapshot().is_none());
        drop(guard);
        assert!(state.try_snapshot().is_some());
    }

    /// A batch that sets the field `t` of node `id` to `value`.
    fn set_t(id: &str, value: &str) -> Vec<crate::Operation> {
        crate::Operation::list_from_value(crate::flow_value!([{"type": "update_nodes", "updates": [
            {"id": id, "op": "set_field", "path": ["data", "node", "template", "t", "value"], "value": value}
        ]}]))
        .unwrap()
    }

    fn snapshot_node(id: &str) -> Node {
        let value = crate::flow_value!({"id":id,"data":{"node":{"template":{"t":{"type":"str","value":"x"}}}}});
        Node::try_from(value.as_object().unwrap().clone()).unwrap()
    }

    fn assert_snapshot_matches_state(state: &GraphState) {
        let snapshot = state.snapshot();
        assert_eq!(snapshot.item_count(), state.item_count());
        assert_eq!(snapshot.to_json(), state.to_json());
    }

    #[test]
    fn snapshots_keep_order_through_churn_and_dropped_batches() {
        let nodes = (0..128)
            .map(|i| snapshot_node(&format!("n{i}")).into_value())
            .collect::<Vec<_>>();
        let mut state = GraphState::new(crate::flow_value!({"nodes":nodes,"edges":[]})).unwrap();
        let before = state.snapshot();
        let text = before.to_json();
        for _ in 0..64 {
            state.remove_node("n32");
            state.remove_node("n64");
            state.commit();
            assert_snapshot_matches_state(&state);
            state.insert_node(snapshot_node("n64"));
            state.insert_node(snapshot_node("n32"));
            state.commit();
            assert_snapshot_matches_state(&state);
            state.remove_node("n0");
            state.insert_node(snapshot_node("discarded"));
            state.drop_pending();
            assert_snapshot_matches_state(&state);
        }
        let ids: Vec<_> = state.graph.nodes.values().map(Node::id).collect();
        let expected: Vec<_> = (0..128)
            .filter(|i| ![32, 64].contains(i))
            .chain([64, 32])
            .map(|i| format!("n{i}"))
            .collect();
        assert_eq!(ids, expected);
        assert_eq!(before.to_json(), text);
    }

    #[test]
    fn a_dropped_snapshot_does_not_force_later_node_copies() {
        let nodes = (0..128)
            .map(|i| snapshot_node(&format!("n{i}")).into_value())
            .collect::<Vec<_>>();
        let mut state = GraphState::new(crate::flow_value!({"nodes":nodes,"edges":[]})).unwrap();
        drop(state.snapshot());
        assert!(state.snapshot_cache.lock().unwrap().upgrade().is_none());
        let before = std::ptr::from_ref(
            state
                .graph
                .nodes
                .base_get("n0")
                .unwrap()
                .as_map()
                .get("id")
                .unwrap(),
        );
        let operations = set_t("n0", "y");
        state
            .apply(operations, crate::ApplyOptions::default())
            .unwrap();
        let after = std::ptr::from_ref(
            state
                .graph
                .nodes
                .base_get("n0")
                .unwrap()
                .as_map()
                .get("id")
                .unwrap(),
        );
        assert_eq!(before, after);
        assert_snapshot_matches_state(&state);
    }

    #[test]
    fn snapshots_release_deleted_and_replaced_payloads_immediately() {
        let mut state = GraphState::new(crate::flow_value!({"nodes":[snapshot_node("a").into_value(),snapshot_node("b").into_value()],"edges":[]})).unwrap();
        // A cached snapshot must not keep a deleted node
        // either.
        drop(state.snapshot());
        let deleted = state.graph.nodes.base_get("a").unwrap().as_map().clone();
        state.remove_node("a");
        state.commit();
        drop(state.take_released());
        assert!(deleted.into_unshared_entries().is_some());
        let replaced = state.graph.nodes.base_get("b").unwrap().as_map().clone();
        state.remove_node("b");
        state.insert_node(snapshot_node("b"));
        state.commit();
        drop(state.take_released());
        assert!(replaced.into_unshared_entries().is_some());
        assert_snapshot_matches_state(&state);
    }

    #[test]
    fn removed_items_no_caller_takes_wait_at_most_one_batch() {
        let mut state = GraphState::new(crate::flow_value!({"nodes":[snapshot_node("a").into_value(),snapshot_node("b").into_value()],"edges":[]})).unwrap();
        state.remove_node("a");
        state.commit();
        assert_eq!(state.released.nodes.len(), 1);
        state.remove_node("b");
        state.commit();
        assert_eq!(state.released.nodes.len(), 1);
        assert!(state.take_released().is_some());
        assert!(state.take_released().is_none());
    }
}
