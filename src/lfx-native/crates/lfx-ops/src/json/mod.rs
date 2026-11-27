//! The JSON value the engine holds, and its text.

pub(crate) mod deserialize;
pub(crate) mod pointer;
pub(crate) mod serialize;

pub(crate) use crate::types::finite_double;
pub use crate::types::{
    FlowObj, FlowStr, FlowValue, FlowValueIndex, NonFinite, NotANumber, Number, StringPool,
    as_double, is_finite_number, is_row_position, utf16_cmp,
};
#[cfg(feature = "bindings")]
pub(crate) use deserialize::{Builder, FiniteSeed};
pub use deserialize::{FiniteFlowValue, NOT_FINITE};
