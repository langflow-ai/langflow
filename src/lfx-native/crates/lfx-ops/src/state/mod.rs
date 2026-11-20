//! The flow in memory: [`GraphState`], indexed and kept between batches, and
//! [`GraphPlain`], read once and not indexed.

pub(crate) mod field_write;
pub(crate) mod index;
pub(crate) mod plain;
#[expect(
    clippy::module_inception,
    reason = "the folder is the state, and state.rs holds GraphState"
)]
mod state;

pub(crate) use index::{Graph, Lists, field_value};
pub use plain::GraphPlain;
pub use state::{Edges, Entry, GraphState, Nodes};
