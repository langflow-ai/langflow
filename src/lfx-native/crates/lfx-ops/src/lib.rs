//! Langflow's flow operation engine.
//!
//! Operations add, update or delete the nodes and edges of a
//! flow's `data`. Apply checks every rule on a new batch.
//! Replay runs stored operations with no rule. A path names a
//! list item by its key, never by its index.
//!
//! Each folder imports only from the folders before it: `map`,
//! `json`, `flow`, `compare`, `node_input`, `violation`,
//! `invariant`, `rule`, `validate`, `snapshot`, `state`, `op`,
//! then `bindings`, which the `bindings` feature turns on for
//! the bindings.

#[cfg(feature = "bindings")]
pub mod bindings;
pub mod compare;
pub mod flow;
mod invariant;
pub mod json;
mod map;
pub mod node_input;
mod op;
mod rule;
mod snapshot;
mod state;
pub mod types;
pub mod validate;
mod violation;

pub use op::{repair, restore};

pub use flow::edge::Edge;
pub use flow::node::Node;
pub use flow::path::{AsKey, Segment};
pub use op::apply::apply_flow_operations;
pub use op::diff::{Derived, derive_flow_operations, diff_flow_data};
pub use op::operation::{Change, FieldUpdate, NodePath, Operation, OperationKind};
pub use op::replay::replay_flow_operations;
pub use op::{Applied, ApplyOptions, ReplayOptions, Replayed};
pub use repair::{Fix, Repaired, repair_flow_data};
pub use snapshot::GraphSnapshot;
pub use state::{Edges, Entry, GraphPlain, GraphState, Nodes};
pub use violation::error::{Error, ErrorCode, ErrorKind, Result};
