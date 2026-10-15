//! The flow operation engine.
//!
//! Operations describe granular edits to a flow's `data`: nodes and edges
//! added, updated field by field, or deleted, and top-level metadata changes.
//! Paths address object keys, and items of the lists `node_schema.json`
//! declares keyed by selector, never by index. The engine has no transport or
//! database dependencies, so the same rules apply wherever an operation comes
//! from.

pub mod apply;
pub mod canonical;
pub mod edges;
pub mod error;
pub mod keyed;
#[expect(
    clippy::module_inception,
    reason = "the layout names the operation types ops::ops"
)]
pub mod ops;
pub mod schema;
pub mod state;
pub mod validate;

pub use apply::{Applied, ApplyOptions, apply_flow_operations};
pub use error::{Error, ErrorCode, ErrorKind, Result};
pub use ops::{Change, Expect, FieldUpdate, Operation, Segment};
pub use state::FlowState;
