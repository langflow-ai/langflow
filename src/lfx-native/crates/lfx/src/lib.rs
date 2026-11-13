//! Langflow's native core.
//!
//! Each feature is a module. [`ops`] is the flow operation engine: it applies,
//! diffs, validates, repairs and hashes flow graphs for the server and the
//! editor alike. [`value`] is the JSON value the engine holds.

pub mod ops;
pub mod value;
