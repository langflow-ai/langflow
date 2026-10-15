//! Reconstructing a flow's graph at a recorded revision.
//!
//! Replay starts from a checkpoint and applies recorded operations forward,
//! one revision at a time, so every revision is reachable, including one in
//! the middle of a row. It requires every revision to appear exactly once and
//! in order; anything else is corruption, reported with the revision and
//! kind of damage and never silently papered over with the nearest state.
//! Replay holds one graph and applies each operation to it, so it costs one
//! pass over the graph, not one per operation.

use serde_json::Value;

use crate::ops::apply::ApplyOptions;
use crate::ops::canonical::graph_hash;
use crate::ops::envelope::{Corruption, Damage, StoredRow, decode_row};
use crate::ops::state::FlowState;

/// Fail unless a checkpoint's graph still hashes to its stored hash.
///
/// # Errors
///
/// The graph's hash differs, or the graph cannot be hashed.
pub fn verify_checkpoint(
    graph: &Value,
    stored_hash: &str,
    revision: u64,
) -> Result<(), Corruption> {
    match graph_hash(graph) {
        Ok(hash) if hash == stored_hash => Ok(()),
        _ => Err(Corruption::at(Damage::CheckpointMismatch, revision)),
    }
}

/// Apply the recorded operations after a checkpoint up to and including `revision`.
///
/// `rows` are the rows whose ranges cover the revisions after the checkpoint,
/// in revision order; a row may begin before the checkpoint.
///
/// # Errors
///
/// A row is damaged, a revision is missing or repeated, or an operation does
/// not apply to the graph before it.
pub fn replay(
    checkpoint: Value,
    checkpoint_revision: u64,
    rows: &[StoredRow],
    revision: u64,
) -> Result<Value, Corruption> {
    let mut graph = Replayed::Checkpoint(checkpoint);
    let mut expected = checkpoint_revision + 1;
    for row in rows {
        for recorded in decode_row(row)? {
            if recorded.revision <= checkpoint_revision {
                // The row began before the checkpoint.
                continue;
            }
            if recorded.revision > revision {
                break;
            }
            if recorded.revision != expected {
                return Err(Corruption::at(Damage::MissingRevisions, expected));
            }
            let does_not_apply = |_| Corruption::at(Damage::OperationDoesNotApply, expected);
            let state = graph.state().map_err(does_not_apply)?;
            state
                .apply(vec![recorded.operation], ApplyOptions::default())
                .map_err(does_not_apply)?;
            expected += 1;
        }
    }
    if expected != revision + 1 {
        return Err(Corruption::at(Damage::MissingRevisions, expected));
    }
    Ok(match graph {
        Replayed::Checkpoint(graph) => graph,
        Replayed::State(state) => state.into_value(),
    })
}

/// The graph replay holds: the checkpoint as read, until an operation needs it indexed.
enum Replayed {
    Checkpoint(Value),
    State(Box<FlowState>),
}

impl Replayed {
    fn state(&mut self) -> crate::ops::error::Result<&mut FlowState> {
        if let Self::Checkpoint(graph) = self {
            *self = Self::State(Box::new(FlowState::new(std::mem::take(graph))?));
        }
        match self {
            Self::State(state) => Ok(state),
            Self::Checkpoint(_) => unreachable!("indexed just above"),
        }
    }
}
