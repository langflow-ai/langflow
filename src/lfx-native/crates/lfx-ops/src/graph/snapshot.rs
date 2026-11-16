//! [`GraphSnapshot`]: the committed graph, to read and write as text on another thread.

use std::borrow::Cow;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, PoisonError, TryLockError};

use crate::data::json_out::{self, Ascii};
use crate::data::layered::Layered;
use crate::data::value::{AnyMap, AnyValue};

use crate::graph::GraphState;
use crate::models::canonical;
use crate::models::error::Result;

/// The committed entries slot for slot ([`Slots`](crate::data::layered::Slots)): `None` in a hole.
pub(super) type SnapshotRows = crate::data::snapshot_rows::Rows<Option<AnyMap>>;

/// Fold the batch's layer into `entries`, and keep `mirror` slot for slot.
pub(super) fn fold_mirrored<V: Clone>(
    entries: &mut Layered<V>,
    mirror: &mut SnapshotRows,
    released: &mut Vec<V>,
    object: impl Fn(&V) -> &AnyMap,
) {
    for (id, written) in &entries.layer {
        match (written, entries.stored.get_index_of(id)) {
            (Some(value), Some(slot)) => mirror.set(slot, Some(object(value).clone())),
            (Some(value), None) => mirror.push_back(Some(object(value).clone())),
            (None, Some(slot)) => mirror.set(slot, None),
            (None, None) => {}
        }
    }
    if entries.fold_into(released) {
        *mirror = packed_mirror(entries, object);
    }
}

/// A mirror of `entries` with no holes: after a load, or after the slots pack.
pub(super) fn packed_mirror<V>(
    entries: &Layered<V>,
    object: impl Fn(&V) -> &AnyMap,
) -> SnapshotRows {
    entries
        .stored
        .values()
        .map(|value| Some(object(value).clone()))
        .collect()
}

impl GraphState {
    /// The committed graph, to read while the state goes on changing.
    /// It shares the mirror rows, so a later write copies only what it changes.
    #[must_use]
    pub fn snapshot(&self) -> GraphSnapshot {
        let mut cache = self
            .snapshot_cache
            .lock()
            .unwrap_or_else(PoisonError::into_inner);
        self.snapshot_cached(&mut cache)
    }

    /// [`Self::snapshot`] without waiting for another capture. On `None`, a
    /// caller with the GIL can release it and wait.
    #[must_use]
    pub fn try_snapshot(&self) -> Option<GraphSnapshot> {
        let mut cache = match self.snapshot_cache.try_lock() {
            Ok(cache) => cache,
            Err(TryLockError::Poisoned(error)) => error.into_inner(),
            Err(TryLockError::WouldBlock) => return None,
        };
        Some(self.snapshot_cached(&mut cache))
    }

    fn snapshot_cached(&self, cache: &mut Option<Arc<SnapshotData>>) -> GraphSnapshot {
        let data = cache.get_or_insert_with(|| {
            Arc::new(SnapshotData {
                root: self.root.clone(),
                nodes: self.snapshot_nodes.clone(),
                edges: self.snapshot_edges.clone(),
                text_len: Arc::clone(&self.text_len),
            })
        });
        GraphSnapshot {
            data: Arc::clone(data),
        }
    }
}

/// A read-only graph from [`GraphState::snapshot`]. Later batches do not
/// change it, so another thread can write and hash it.
#[derive(Debug, Clone)]
pub struct GraphSnapshot {
    pub(super) data: Arc<SnapshotData>,
}

#[derive(Debug)]
pub(super) struct SnapshotData {
    /// The flow's top-level object; `nodes` and `edges` hold placeholders.
    pub(super) root: AnyMap,
    // Rows hold shared objects, not node values, to avoid a copy per node.
    pub(super) nodes: SnapshotRows,
    pub(super) edges: SnapshotRows,
    /// The length of the state's last JSON text, shared with the state.
    pub(super) text_len: Arc<AtomicUsize>,
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

    /// [`GraphState::to_json`] at the time of the snapshot.
    #[must_use]
    pub fn to_json(&self) -> String {
        let data = &self.data;
        sized_text(&data.text_len, |out| {
            write_graph(
                out,
                &data.root,
                data.nodes.iter().flatten(),
                data.edges.iter().flatten(),
                |out, node| json_out::write_map(out, node, Ascii::Escape),
            );
        })
    }

    /// [`GraphState::graph_hash`] at the time of the snapshot.
    ///
    /// # Panics
    ///
    /// A snapshot row invariant is broken.
    ///
    /// # Errors
    ///
    /// A number that is not finite as JavaScript reads it.
    pub fn graph_hash(&self) -> Result<String> {
        canonical::loaded_graph_hash(
            &self.data.root,
            self.data
                .nodes
                .iter()
                .flatten()
                .map(|node| Cow::Owned(AnyValue::Object(node.clone())))
                .collect(),
            self.data.edges.iter().flatten().collect(),
        )
    }
}

/// Text written into a buffer pre-sized from `text_len`, which it then
/// updates. Growing a buffer of megabytes copies it each time.
pub(super) fn sized_text(text_len: &AtomicUsize, write: impl FnOnce(&mut Vec<u8>)) -> String {
    let last = text_len.load(Ordering::Relaxed);
    let mut out = Vec::with_capacity(last + last / 16);
    write(&mut out);
    text_len.store(out.len(), Ordering::Relaxed);
    json_out::into_string(out)
}

/// A loaded graph as ASCII JSON text, each node written by `write_node`.
pub(super) fn write_graph<'g, N>(
    out: &mut Vec<u8>,
    root: &AnyMap,
    nodes: impl IntoIterator<Item = N>,
    edges: impl IntoIterator<Item = &'g AnyMap>,
    write_node: impl FnMut(&mut Vec<u8>, N),
) {
    let (mut nodes, mut edges) = (Some((nodes, write_node)), Some(edges));
    json_out::write_entries(
        out,
        root.iter().map(|(key, value)| (key, (key.as_str(), value))),
        |out, (key, value)| match key {
            "nodes" => {
                if let Some((nodes, write_node)) = nodes.take() {
                    json_out::write_seq(out, nodes, write_node);
                }
            }
            "edges" => json_out::write_seq(out, edges.take().into_iter().flatten(), |out, edge| {
                json_out::write_map(out, edge, Ascii::Escape);
            }),
            _ => json_out::write_value(out, value, Ascii::Escape),
        },
        Ascii::Escape,
    );
}
