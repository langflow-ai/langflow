//! A field update's place in a batch, the `update_target` of its path, and the
//! operations that undo a batch's writes. Apply and replay share them.

use std::fmt;

use crate::collection::hash_map::HashSet;
use crate::json::FlowValue;

use crate::flow::edge::Edge;
use crate::flow::list::ListProblem;
use crate::flow::model::KeyedList;
use crate::flow::path::Segment;
use crate::json::serialize::quoted;
use crate::op::Report;
use crate::op::operation::{Change, FieldUpdate, NodePath, Operation};
use crate::violation::error::{Error, Result, invalid};

/// Check that the path exists up to its last segment.
pub(crate) fn require_path(
    sequenced: &SequencedUpdate<'_>,
    update_target: &UpdateTarget,
) -> Result<()> {
    match update_target.missing_at {
        Some(missing) => Err(missing_segment(sequenced, missing)),
        None => Ok(()),
    }
}

/// The value an update writes, or `Null` for a delete. It moves out of the
/// update unless `keep_update` is set.
pub(crate) fn written_value(update: &mut FieldUpdate, keep_update: bool) -> FlowValue {
    match &mut update.change {
        Change::Set(value) if keep_update => value.clone(),
        Change::Set(value) => std::mem::take(value),
        Change::Delete => FlowValue::Null,
    }
}

/// The edges an `add_edges` adds, kept for its forward and backward operations.
#[derive(Debug, Default)]
pub(crate) struct AddedEdges {
    /// With `forward`: the added edges.
    pub(crate) edges: Vec<Edge>,
    /// With `backward`: their ids.
    pub(crate) ids: Vec<String>,
    /// How many edges were added.
    pub(crate) count: usize,
}

impl AddedEdges {
    /// Record the `add_edges` and what undoes it, if it added an edge.
    pub(crate) fn record(self, report: &mut Report) {
        if self.count == 0 {
            return;
        }
        report.record(Operation::AddEdges(self.edges));
        report.record_backward(Operation::DeleteEdges(self.ids));
    }
}

/// A field update, with its place in its `update_nodes` for error messages.
#[derive(Debug)]
pub(crate) struct SequencedUpdate<'w> {
    pub(crate) update: &'w FieldUpdate,
    /// Where the update is in its operation, for messages.
    pub(crate) context: SeqNum,
}

/// Where a field update is, for error messages.
/// Example: `update_nodes[1]` or `update_nodes[1].path[2]`.
#[derive(Debug, Clone, Copy)]
pub(crate) struct SeqNum {
    update: usize,
    segment: Option<usize>,
}

impl SeqNum {
    pub(crate) fn new(update: usize) -> Self {
        Self {
            update,
            segment: None,
        }
    }

    /// The place of segment `index` of the update's path.
    pub(crate) fn segment(self, index: usize) -> Self {
        Self {
            segment: Some(index),
            ..self
        }
    }
}

impl fmt::Display for SeqNum {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "update_nodes[{}]", self.update)?;
        if let Some(segment) = self.segment {
            write!(f, ".path[{segment}]")?;
        }
        Ok(())
    }
}

/// Where a field update's path leads through the batch's pending field writes, and what it holds.
#[derive(Debug, Default)]
pub(crate) struct UpdateTarget {
    /// The path length of the write on the way that holds the last segment.
    /// `None` when the node itself holds it.
    pub(crate) write_len: Option<usize>,
    /// The keyed list items the path passes through, before its last segment.
    pub(crate) list_items: Vec<ListItemOnPath>,
    /// The keyed list whose item the last segment names, if it names one.
    pub(crate) last_list: Option<&'static KeyedList>,
    /// The first keyed list rule broken on the path, with its segment index.
    pub(crate) list_problem: Option<(usize, ListProblem)>,
    /// Whether the value that holds the last segment has it.
    pub(crate) found: bool,
    /// Whether the path holds a value as the batch sees it. It is
    /// [`Self::found`] unless a write at the path says otherwise.
    pub(crate) exists: bool,
    /// The index of the first segment that does not exist.
    pub(crate) missing_at: Option<usize>,
}

/// A keyed list item a path passes through.
#[derive(Debug)]
pub(crate) struct ListItemOnPath {
    pub(crate) keyed: &'static KeyedList,
    /// The index of the path segment that names the item.
    pub(crate) segment: usize,
}

/// The error for the first segment of a path that does not exist.
fn missing_segment(sequenced: &SequencedUpdate<'_>, missing: usize) -> Error {
    let context = sequenced.context;
    match &sequenced.update.path[missing] {
        Segment::Key(key) => invalid!(
            "{context}.path[{missing}]: object path part must be an existing string key: {}",
            quoted(key)
        ),
        Segment::Item(key) => invalid!(
            "{context}.path[{missing}]: list item does not exist: {}",
            quoted(key)
        ),
    }
}

// --- Backward operations of field writes ---------------------------------------------------

/// The writes that undo an `update_nodes`. One operation may write a path
/// only once, so a path written twice splits into separate operations.
#[derive(Debug, Default)]
pub(crate) struct FieldBackward {
    entries: Vec<FieldUpdate>,
}

impl FieldBackward {
    /// Add what undoes `update`, before it is applied. It puts back
    /// `current`, or deletes the path when `current` is `None`.
    pub(crate) fn add(&mut self, update: &FieldUpdate, current: Option<&FlowValue>) {
        let path = update.path.clone();
        match current {
            Some(current) => self
                .entries
                .push(FieldUpdate::set(&update.id, path, current.clone())),
            None if !update.is_delete() => self.entries.push(FieldUpdate::delete(&update.id, path)),
            // A delete that finds nothing writes nothing to undo.
            None => {}
        }
    }

    /// Record the `update_nodes` operations that undo the operation, last
    /// write first.
    pub(crate) fn record(self, report: &mut Report) {
        let mut batch: Vec<FieldUpdate> = Vec::new();
        let mut written: HashSet<(String, NodePath)> = HashSet::default();
        for entry in self.entries.into_iter().rev() {
            let key = (entry.id.clone(), entry.path.clone());
            if written.contains(&key) {
                report.record_backward(Operation::UpdateNodes(std::mem::take(&mut batch)));
                written.clear();
            }
            written.insert(key);
            batch.push(entry);
        }
        if !batch.is_empty() {
            report.record_backward(Operation::UpdateNodes(batch));
        }
    }
}
