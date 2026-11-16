//! Canonical form of flow data, for equality and checkpoint hashes.
//!
//! Two graphs are equal when their canonical forms are the same JSON value.
//! The form drops view state, which `node_schema.json` declares display only.
//!
//! - Values compare as RFC 8785 prints them. Example: `1` equals `1.0`,
//!   because the editor gives back `0.0` as `0`. Key order is never a change.
//! - `nodes`, `edges` and keyed lists compare by id or item key, in any order.
//!   A keyed list's order is `(__pos__, key)`.
//! - An edge handle string is JSON with `œ` for `"`. It compares by the
//!   object it encodes.
//! - A handle's `inputTypes` and `output_types` compare as sets. The hash
//!   keeps their order, so no stored hash changes.
//! - Numbers compare as JavaScript doubles. An integer above 2^53 compares as
//!   the double it rounds to, because the editor cannot hold it either.
//!
//! The form is defined for any graph, valid or not.

mod equal;
mod number;
#[cfg(test)]
mod tests;
mod text;

use crate::data::value::AnyValue;

use crate::models::error::Result;

pub use equal::graphs_equal;
pub(crate) use equal::{
    Proven, edge_data_with_type_sets, graphs_equal_given, handle_with_type_sets,
};
use number::finite_double;
pub use number::{as_double, is_finite_number, is_row_position, utf16_cmp};
pub(crate) use text::loaded_graph_hash;
pub use text::{canonical_json, graph_hash};

/// The keys of a handle that hold a list of types. Their order is not state.
pub const TYPE_LIST_KEYS: [&str; 2] = ["inputTypes", "output_types"];

/// The six JSON types. Integer versus float is not a type.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[expect(missing_docs, reason = "each variant is the JSON type it names")]
pub enum JsonType {
    Object,
    Array,
    String,
    Number,
    Boolean,
    Null,
}

/// The JSON type of a value.
impl From<&AnyValue> for JsonType {
    fn from(value: &AnyValue) -> Self {
        match value {
            AnyValue::Null => Self::Null,
            AnyValue::Bool(_) => Self::Boolean,
            AnyValue::Number(_) => Self::Number,
            AnyValue::String(_) => Self::String,
            AnyValue::Array(_) => Self::Array,
            AnyValue::Object(_) => Self::Object,
        }
    }
}

/// Whether two JSON values have the same canonical form, stopping at the first difference.
///
/// # Errors
///
/// A compared number that is not finite as JavaScript reads it.
#[expect(
    clippy::float_cmp,
    reason = "canonical equality compares the exact doubles"
)]
pub fn values_equal(left: &AnyValue, right: &AnyValue) -> Result<bool> {
    Ok(match (left, right) {
        (AnyValue::Number(a), AnyValue::Number(b)) => finite_double(a)? == finite_double(b)?,
        (AnyValue::Array(a), AnyValue::Array(b)) => {
            if a.len() != b.len() {
                return Ok(false);
            }
            for (a, b) in a.iter().zip(b) {
                if !values_equal(a, b)? {
                    return Ok(false);
                }
            }
            true
        }
        (AnyValue::Object(a), AnyValue::Object(b)) => {
            if a.len() != b.len() {
                return Ok(false);
            }
            for (key, a) in a {
                match b.get(key) {
                    Some(b) if values_equal(a, b)? => {}
                    _ => return Ok(false),
                }
            }
            true
        }
        _ => left == right,
    })
}
