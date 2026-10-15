//! The flow operation engine.
//!
//! Operations describe granular edits to a flow's `data`: nodes and edges
//! added, updated field by field, or deleted, and top-level metadata changes.
//! Paths address object keys, and items of the lists `node_schema.json`
//! declares keyed by selector, never by index. The engine has no transport or
//! database dependencies, so the same rules apply wherever an operation comes
//! from.

pub mod schema;
