//! The verbs: apply, replay, diff, repair and restore.
//!
//! This file holds what a batch takes and returns. Apply and replay share it.

pub mod apply;
pub mod diff;
pub(crate) mod place;
pub mod repair;
pub mod replay;
pub mod restore;
pub mod rows;

use crate::graph::GraphState;
use crate::models::error::Result;
use crate::models::operation::Operation;

/// What a batch returns besides the flow.
#[derive(Debug, Clone, Copy, Default)]
pub struct ApplyOptions {
    /// Return the forward operations.
    pub forward: bool,
    /// Return, for each operation, its backward operations.
    pub backward: bool,
}

/// What a batch did.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Applied {
    /// When the caller sets the `forward` option: the forward operations.
    pub forward: Vec<Operation>,
    /// When the caller sets the `backward` option: for each operation, the
    /// operations that undo it. An operation that changed nothing has an
    /// empty list.
    ///
    /// To undo the batch, run the lists from last to first. To show an
    /// earlier version, replay each list ([`GraphState::replay`]). To undo
    /// with a new edit, apply the lists as one batch, which checks the rules.
    pub backward: Vec<Vec<Operation>>,
}

/// The options of a batch, and the forward and backward operations it keeps.
#[derive(Debug)]
pub(crate) struct Report {
    options: ApplyOptions,
    applied: Applied,
}

impl Report {
    pub(crate) fn new(options: ApplyOptions) -> Self {
        Self {
            options,
            applied: Applied::default(),
        }
    }

    /// What the batch did, for the caller.
    pub(crate) fn into_applied(self) -> Applied {
        self.applied
    }

    /// Whether the caller asked for the backward operations.
    pub(crate) fn keeps_backward(&self) -> bool {
        self.options.backward
    }

    /// Start an operation: its backward operations go into a list of their own.
    fn begin_operation(&mut self) {
        if self.options.backward {
            self.applied.backward.push(Vec::new());
        }
    }

    /// Keep a forward operation. Kept only with `forward`.
    fn record(&mut self, operation: Operation) {
        if self.options.forward {
            self.applied.forward.push(operation);
        }
    }

    /// Record an operation that undoes part of the operation being applied.
    /// Kept only with `backward`.
    fn record_backward(&mut self, operation: Operation) {
        if self.options.backward {
            self.applied
                .backward
                .last_mut()
                .expect("begin_operation started a list")
                .push(operation);
        }
    }
}

/// One operation of a batch, carried out on the state.
pub(crate) type OperationStep = fn(&mut GraphState, Operation, &mut Report) -> Result<()>;

/// What a replay returns besides the flow.
#[derive(Debug, Clone, Copy, Default)]
pub struct ReplayOptions {
    /// Return, for each operation, its backward operations.
    pub backward: bool,
}

/// What a replay did.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Replayed {
    /// With the `backward` option: for each operation, the operations that
    /// undo it, as in [`Applied::backward`].
    pub backward: Vec<Vec<Operation>>,
}
