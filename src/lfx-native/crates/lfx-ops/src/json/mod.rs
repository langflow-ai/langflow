//! The JSON value the engine holds, and its text.

pub(crate) mod deserialize;
mod flow_obj;
mod flow_str;
mod flow_value;
mod number;
pub(crate) mod pointer;
pub(crate) mod serialize;

pub(crate) use deserialize::{Builder, FiniteSeed};
pub use deserialize::{FiniteFlowValue, NOT_FINITE};
pub use flow_obj::FlowObj;
pub use flow_str::{FlowStr, StringPool};
pub use flow_value::{FlowValue, FlowValueIndex};
pub(crate) use number::finite_double;
pub use number::{
    NonFinite, NotANumber, Number, as_double, is_finite_number, is_row_position, utf16_cmp,
};
