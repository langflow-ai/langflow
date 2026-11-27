//! rust types for deserialized flow jsons.

mod flow_obj;
mod flow_str;
mod flow_value;
mod number;

pub use flow_obj::FlowObj;
pub(crate) use flow_obj::{Entries, entries_of, small_and_unique};
pub(crate) use flow_str::StringSeed;
pub use flow_str::{FlowStr, StringPool};
pub use flow_value::{FlowValue, FlowValueIndex};
pub(crate) use number::finite_double;
pub use number::{
    NonFinite, NotANumber, Number, as_double, is_finite_number, is_row_position, utf16_cmp,
};
