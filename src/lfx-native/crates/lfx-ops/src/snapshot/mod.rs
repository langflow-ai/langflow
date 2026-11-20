//! [`GraphSnapshot`]: the committed graph, to read and write as text on another thread.

pub(crate) mod list;

use std::borrow::Cow;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};

use crate::json::serialize::{self, Ascii};
use crate::json::{FlowObj, FlowValue};
use crate::map::pending::{PendingMap, Write};

use crate::compare;
use crate::violation::error::Result;

/// The committed nodes or edges, one per position of the map ([`OrderedMap`](crate::map::ordered::OrderedMap)): `None` where one was removed.
pub(crate) type SnapshotObjects = list::SnapshotList<Option<FlowObj>>;

/// Commit the batch's pending changes to `entries`, and keep the snapshot list in step.
pub(crate) fn commit_with_snapshot<V: Clone>(
    entries: &mut PendingMap<V>,
    mirror: &mut SnapshotObjects,
    released: &mut Vec<V>,
    object: impl Fn(&V) -> &FlowObj,
) {
    for (id, written) in entries.writes() {
        match (written, entries.base().get_index_of(id)) {
            (Write::Set(value), Some(position)) => {
                mirror.set(position, Some(object(value).clone()));
            }
            (Write::Set(value), None) => mirror.push_back(Some(object(value).clone())),
            (Write::Delete, Some(position)) => mirror.set(position, None),
            (Write::Delete, None) => {}
        }
    }
    if entries.commit_into(released) {
        *mirror = snapshot_objects_of(entries, object);
    }
}

/// The snapshot list of `entries`, with no removed positions: after a load, or after the map packs.
pub(crate) fn snapshot_objects_of<V>(
    entries: &PendingMap<V>,
    object: impl Fn(&V) -> &FlowObj,
) -> SnapshotObjects {
    entries
        .values()
        .map(|value| Some(object(value).clone()))
        .collect()
}

/// A read-only graph from [`GraphState::snapshot`](crate::GraphState::snapshot). Later batches do not
/// change it, so another thread can write and hash it.
#[derive(Debug, Clone)]
pub struct GraphSnapshot {
    pub(crate) data: Arc<SnapshotData>,
}

#[derive(Debug)]
pub(crate) struct SnapshotData {
    /// The flow's top-level object; `nodes` and `edges` hold placeholders.
    pub(crate) root: FlowObj,
    // SnapshotList hold shared objects, not node values, to avoid a copy per node.
    pub(crate) nodes: SnapshotObjects,
    pub(crate) edges: SnapshotObjects,
    /// The length of the state's last JSON text, shared with the state.
    pub(crate) text_len: Arc<AtomicUsize>,
}

impl GraphSnapshot {
    /// The data, when this is its last owner, to drop on another thread.
    #[must_use]
    pub fn into_unshared_data(self) -> Option<impl Send + 'static> {
        Arc::into_inner(self.data)
    }

    /// The number of nodes and edges.
    #[must_use]
    pub fn item_count(&self) -> usize {
        self.data.nodes.len() + self.data.edges.len()
    }

    /// [`GraphState::to_json`](crate::GraphState::to_json) at the time of the snapshot.
    #[must_use]
    pub fn to_json(&self) -> String {
        let data = &self.data;
        sized_text(&data.text_len, |out| {
            write_graph(
                out,
                &data.root,
                data.nodes.iter().flatten(),
                data.edges.iter().flatten(),
                |out, node| serialize::write_map(out, node, Ascii::Escape),
            );
        })
    }

    /// [`GraphState::graph_hash`](crate::GraphState::graph_hash) at the time of the snapshot.
    ///
    /// # Panics
    ///
    /// A snapshot row invariant is broken.
    ///
    /// # Errors
    ///
    /// A number that is not finite as JavaScript reads it.
    pub fn graph_hash(&self) -> Result<String> {
        Ok(compare::loaded_graph_hash(
            &self.data.root,
            self.data
                .nodes
                .iter()
                .flatten()
                .map(|node| Cow::Owned(FlowValue::Object(node.clone())))
                .collect(),
            self.data.edges.iter().flatten().collect(),
        )?)
    }
}

/// Text written into a buffer pre-sized from `text_len`, which it then
/// updates. Growing a buffer of megabytes copies it each time.
pub(crate) fn sized_text(text_len: &AtomicUsize, write: impl FnOnce(&mut Vec<u8>)) -> String {
    let last = text_len.load(Ordering::Relaxed);
    let mut out = Vec::with_capacity(last + last / 16);
    write(&mut out);
    text_len.store(out.len(), Ordering::Relaxed);
    serialize::into_string(out)
}

/// A loaded graph as ASCII JSON text, each node written by `write_node`.
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
