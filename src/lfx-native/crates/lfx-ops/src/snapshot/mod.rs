//! [`GraphSnapshot`]: the committed graph, to read and write as
//! text on another thread.
//!
//! Taking a snapshot copies references to node and edge JSON
//! objects.
//!
//! The server can use a snapshot to send the graph to a user
//! who opens the flow or to save the graph to the database.
//! Both happen less often than graph edits.
//!
//! A persistent segment tree can take a snapshot in `O(1)`
//! by sharing its root. The tree adds
//! `O(log n)` work for each changed node or edge. A flat map
//! updates an entry in expected `O(1)` time and takes `O(n)` to
//! copy `n` entries for a snapshot.

use std::borrow::Cow;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};

use crate::flow::{edge::Edge, node::Node};
use crate::json::FlowObj;
use crate::json::serialize::{self, Ascii};

use crate::compare;
use crate::violation::error::Result;

/// A read-only graph from
/// [`GraphState::snapshot`](crate::GraphState::snapshot). Later
/// batches do not change it, so another thread can write and
/// hash it.
#[derive(Debug, Clone)]
pub struct GraphSnapshot {
    pub(crate) data: Arc<SnapshotData>,
}

#[derive(Debug)]
pub(crate) struct SnapshotData {
    /// The flow's top-level object; `nodes` and `edges` hold
    /// placeholders.
    pub(crate) root: FlowObj,
    pub(crate) nodes: Vec<Node>,
    pub(crate) edges: Vec<Edge>,
    /// The length of the state's last JSON text, shared with
    /// the state.
    pub(crate) text_len: Arc<AtomicUsize>,
}

impl GraphSnapshot {
    /// The data, when this is its last owner, to drop on
    /// another thread.
    #[must_use]
    pub fn into_unshared_data(self) -> Option<impl Send + 'static> {
        Arc::into_inner(self.data)
    }

    /// The number of nodes and edges.
    #[must_use]
    pub fn item_count(&self) -> usize {
        self.data.nodes.len() + self.data.edges.len()
    }

    /// [`GraphState::to_json`](crate::GraphState::to_json) at
    /// the time of the snapshot.
    #[must_use]
    pub fn to_json(&self) -> String {
        let data = &self.data;
        sized_text(&data.text_len, |out| {
            write_graph(
                out,
                &data.root,
                data.nodes.iter().map(Node::as_map),
                data.edges.iter().map(Edge::as_map),
                |out, node| serialize::write_map(out, node, Ascii::Escape),
            );
        })
    }

    /// The [graph hash](crate::GraphState::graph_hash) at the
    /// time of the snapshot.
    ///
    /// # Errors
    ///
    /// A number that is not finite as JavaScript reads it.
    pub fn graph_hash(&self) -> Result<String> {
        let data = &self.data;
        let nodes = data
            .nodes
            .iter()
            .map(|node| Cow::Borrowed(node.as_value()))
            .collect();
        let edges = data.edges.iter().map(Edge::as_map).collect();
        Ok(compare::loaded_graph_hash(&data.root, nodes, edges)?)
    }
}

/// Text written into a buffer pre-sized from `text_len`, which
/// it then updates. Growing a buffer of megabytes copies it
/// each time.
pub(crate) fn sized_text(text_len: &AtomicUsize, write: impl FnOnce(&mut Vec<u8>)) -> String {
    let last = text_len.load(Ordering::Relaxed);
    let mut out = Vec::with_capacity(last + last / 16);
    write(&mut out);
    text_len.store(out.len(), Ordering::Relaxed);
    serialize::into_string(out)
}

/// A loaded graph as ASCII JSON text, each node written by
/// `write_node`.
pub(crate) fn write_graph<'g, N>(
    out: &mut Vec<u8>,
    root: &FlowObj,
    nodes: impl IntoIterator<Item = N>,
    edges: impl IntoIterator<Item = &'g FlowObj>,
    write_node: impl FnMut(&mut Vec<u8>, N),
) {
    let mut nodes = Some((nodes, write_node));
    let mut edges = Some(edges);
    serialize::write_entries(
        out,
        root.iter().map(|(key, value)| (key, (key.as_str(), value))),
        |out, (key, value)| match key {
            "nodes" => {
                if let Some((nodes, write_node)) = nodes.take() {
                    serialize::write_seq(out, nodes, write_node);
                }
            }
            "edges" => {
                serialize::write_seq(out, edges.take().into_iter().flatten(), |out, edge| {
                    serialize::write_map(out, edge, Ascii::Escape);
                });
            }
            _ => serialize::write_value(out, value, Ascii::Escape),
        },
        Ascii::Escape,
    );
}
