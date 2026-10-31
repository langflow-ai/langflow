//! The flow operation engine.
//!
//! Operations describe granular edits to a flow's `data`: nodes and edges
//! added, updated field by field, or deleted. Every other top-level key is
//! view state, which no operation writes.
//! Paths name object keys, and the items of the lists that `node_schema.json`
//! declares keyed by their key, never by their index. The engine has no transport or
//! database dependencies, so the same rules apply wherever an operation comes
//! from.

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
#[expect(
    clippy::module_inception,
    reason = "the layout names the operation types ops::ops"
)]
pub mod ops;
pub mod plain;
pub mod repair;
pub mod restore;
pub mod schema;
pub mod state;
pub mod validate;

pub use apply::{Applied, ApplyOptions, Mode, apply_flow_operations};
pub use diff::{Derived, derive_flow_operations, diff_flow_data};
pub use error::{Error, ErrorCode, ErrorKind, Result};
pub use ops::{
    AsKey, Change, Edge, FieldUpdate, Node, NodePath, Operation, OperationKind, Segment,
};
pub use plain::GraphPlain;
pub use repair::{Fix, Repaired, repair_flow_data};
pub use state::{Edges, Entry, GraphState, Nodes};
