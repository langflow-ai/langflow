//! Langflow's native core.
//!
//! Each feature is a module. [`ops`] is the flow operation engine: it applies,
//! diffs, validates, repairs and hashes flow graphs for the server and the
//! editor alike.

pub mod ops;
