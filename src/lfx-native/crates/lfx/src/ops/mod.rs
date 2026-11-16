//! The flow operation engine.
//!
//! Operations add, update or delete the nodes and edges of a flow's `data`.
//! Apply checks every rule on a new batch. Replay runs stored operations
//! with no rule. A path names a list item by its key, never by its index.

pub mod api;
pub mod apply;
pub mod canonical;
pub mod diff;
pub mod edges;
pub(crate) mod entry;
pub mod error;
pub(crate) mod fields;
pub(crate) mod from_value;
pub mod ids;
pub mod keyed;
pub(crate) mod maps;
#[expect(
    clippy::module_inception,
    reason = "the layout names the operation types ops::ops"
)]
pub mod ops;
pub mod plain;
pub mod repair;
pub mod replay;
pub mod restore;
pub mod schema;
pub mod state;
pub mod validate;

pub use apply::{Applied, ApplyOptions, apply_flow_operations};
pub use diff::{Derived, derive_flow_operations, diff_flow_data};
pub use error::{Error, ErrorCode, ErrorKind, Result};
pub use ops::{
    AsKey, Change, Edge, FieldUpdate, Node, NodePath, Operation, OperationKind, Segment,
};
pub use plain::GraphPlain;
pub use repair::{Fix, Repaired, repair_flow_data};
pub use replay::{ReplayOptions, Replayed, replay_flow_operations};
pub use state::{Edges, Entry, GraphSnapshot, GraphState, Nodes};
