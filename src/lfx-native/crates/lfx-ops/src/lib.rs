//! Langflow's flow operation engine.
//!
//! Operations add, update or delete the nodes and edges of a flow's `data`.
//! Apply checks every rule on a new batch. Replay runs stored operations
//! with no rule. A path names a list item by its key, never by its index.
//!
//! Each folder imports only from the folders before it:
//! `data`, `models`, `graph`, `ops`, then [`api`].

mod data;
mod graph;
mod models;
mod ops;

pub mod api;

pub use data::value;
pub use models::{canonical, handle, ids, keyed, schema, validate};
pub use ops::{repair, restore, rows};

pub use graph::plain::GraphPlain;
pub use graph::{Edges, Entry, GraphSnapshot, GraphState, Nodes};
pub use models::error::{Error, ErrorCode, ErrorKind, Result};
pub use models::operation::{
    AsKey, Change, Edge, FieldUpdate, Node, NodePath, Operation, OperationKind, Segment,
};
pub use ops::apply::apply_flow_operations;
pub use ops::diff::{Derived, derive_flow_operations, diff_flow_data};
pub use ops::replay::replay_flow_operations;
pub use ops::{Applied, ApplyOptions, ReplayOptions, Replayed};
pub use repair::{Fix, Repaired, repair_flow_data};
