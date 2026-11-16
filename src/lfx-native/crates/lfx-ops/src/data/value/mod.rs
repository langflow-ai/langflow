//! [`AnyValue`]: a JSON value as the engine holds it.
//!
//! - An object ([`AnyMap`]) keeps insertion order. Copies share it until a
//!   write.
//! - Text of up to 24 bytes is inline. One input shares each long string.
//! - A number ([`Number`]) keeps `1` and `1.0` apart, as Python does. Example:
//!   `1e2` and `100.0` are the same number.

mod json;
mod map;
mod number;
mod string;

use crate::data::json_out::{self, Ascii};
use std::fmt;
use std::ops::{Index, IndexMut};

pub(crate) use json::{Builder, FiniteSeed};
pub use json::{FiniteAnyValue, NOT_FINITE};
pub use map::AnyMap;
pub use number::{NotANumber, Number};
pub use string::{AnyString, StringPool};

/// A JSON value.
#[derive(Debug, Clone, PartialEq, Default)]
pub enum AnyValue {
    /// `null`.
    #[default]
    Null,
    /// `true` or `false`.
    Bool(bool),
    /// A number.
    Number(Number),
    /// A string.
    String(AnyString),
    /// An array.
    Array(Vec<AnyValue>),
    /// An object, its keys in insertion order.
    Object(AnyMap),
}

/// Equality is reflexive: a number is never NaN.
impl Eq for AnyValue {}

/// The value at a missing index, as [`Index`] returns it.
static NULL: AnyValue = AnyValue::Null;

impl AnyValue {
    /// The value at a key of an object or an index of an array.
    pub fn get<I: AnyValueIndex>(&self, index: I) -> Option<&AnyValue> {
        index.index_into(self)
    }

    /// The value at a key or an index, to change it.
    pub fn get_mut<I: AnyValueIndex>(&mut self, index: I) -> Option<&mut AnyValue> {
        index.index_into_mut(self)
    }

    /// Whether the value is `null`.
    #[must_use]
    pub fn is_null(&self) -> bool {
        matches!(self, AnyValue::Null)
    }

    /// Whether the value is an array.
    #[must_use]
    pub fn is_array(&self) -> bool {
        matches!(self, AnyValue::Array(_))
    }

    /// Whether the value is an object.
    #[must_use]
    pub fn is_object(&self) -> bool {
        matches!(self, AnyValue::Object(_))
    }

    /// The boolean, when the value is one.
    #[must_use]
    pub fn as_bool(&self) -> Option<bool> {
        match self {
            AnyValue::Bool(flag) => Some(*flag),
            _ => None,
        }
    }

    /// The string, when the value is one.
    #[must_use]
    pub fn as_str(&self) -> Option<&str> {
        match self {
            AnyValue::String(text) => Some(text),
            _ => None,
        }
    }

    /// The number, when the value is one.
    #[must_use]
    pub fn as_number(&self) -> Option<&Number> {
        match self {
            AnyValue::Number(number) => Some(number),
            _ => None,
        }
    }

    /// The number as an `i64`, when it is an integer that one holds.
    #[must_use]
    pub fn as_i64(&self) -> Option<i64> {
        self.as_number().and_then(Number::as_i64)
    }

    /// The number as a `u64`, when it is an integer that one holds.
    #[must_use]
    pub fn as_u64(&self) -> Option<u64> {
        self.as_number().and_then(Number::as_u64)
    }

    /// The number as a double.
    #[must_use]
    pub fn as_f64(&self) -> Option<f64> {
        self.as_number().and_then(Number::as_f64)
    }

    /// The array, when the value is one.
    #[must_use]
    pub fn as_array(&self) -> Option<&Vec<AnyValue>> {
        match self {
            AnyValue::Array(items) => Some(items),
            _ => None,
        }
    }

    /// The array, when the value is one, to change it.
    pub fn as_array_mut(&mut self) -> Option<&mut Vec<AnyValue>> {
        match self {
            AnyValue::Array(items) => Some(items),
            _ => None,
        }
    }

    /// The object, when the value is one.
    #[must_use]
    pub fn as_object(&self) -> Option<&AnyMap> {
        match self {
            AnyValue::Object(map) => Some(map),
            _ => None,
        }
    }

    /// The object, when the value is one, to change it.
    pub fn as_object_mut(&mut self) -> Option<&mut AnyMap> {
        match self {
            AnyValue::Object(map) => Some(map),
            _ => None,
        }
    }
}

/// The JSON text of a value, compact, with its characters above U+007F as they are.
impl fmt::Display for AnyValue {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let mut out = Vec::new();
        json_out::write_value(&mut out, self, Ascii::Keep);
        f.write_str(&json_out::into_string(out))
    }
}

/// A value equals a string when it holds that string.
impl PartialEq<&str> for AnyValue {
    fn eq(&self, other: &&str) -> bool {
        self.as_str() == Some(*other)
    }
}

impl PartialEq<AnyValue> for &str {
    fn eq(&self, value: &AnyValue) -> bool {
        value == self
    }
}

// --- Indexing --------------------------------------------------------------------------------

/// What indexes a value: a key of an object, or an index of an array.
pub trait AnyValueIndex {
    /// The value at this index of `value`.
    fn index_into<'v>(&self, value: &'v AnyValue) -> Option<&'v AnyValue>;
    /// The value at this index of `value`, to change it.
    fn index_into_mut<'v>(&self, value: &'v mut AnyValue) -> Option<&'v mut AnyValue>;
    /// The value at this index, made when it is missing, as `value[index] = ...` needs.
    fn index_or_insert<'v>(&self, value: &'v mut AnyValue) -> &'v mut AnyValue;
}

impl AnyValueIndex for str {
    fn index_into<'v>(&self, value: &'v AnyValue) -> Option<&'v AnyValue> {
        value.as_object()?.get(self)
    }
    fn index_into_mut<'v>(&self, value: &'v mut AnyValue) -> Option<&'v mut AnyValue> {
        value.as_object_mut()?.get_mut(self)
    }
    /// `null` becomes an empty object, and a missing key is added as `null`.
    fn index_or_insert<'v>(&self, value: &'v mut AnyValue) -> &'v mut AnyValue {
        if value.is_null() {
            *value = AnyValue::Object(AnyMap::new());
        }
        match value {
            AnyValue::Object(map) => map.entry_or_null(self),
            other => panic!("cannot index {} with a string", kind(other)),
        }
    }
}

impl AnyValueIndex for String {
    fn index_into<'v>(&self, value: &'v AnyValue) -> Option<&'v AnyValue> {
        self.as_str().index_into(value)
    }
    fn index_into_mut<'v>(&self, value: &'v mut AnyValue) -> Option<&'v mut AnyValue> {
        self.as_str().index_into_mut(value)
    }
    fn index_or_insert<'v>(&self, value: &'v mut AnyValue) -> &'v mut AnyValue {
        self.as_str().index_or_insert(value)
    }
}

impl AnyValueIndex for usize {
    fn index_into<'v>(&self, value: &'v AnyValue) -> Option<&'v AnyValue> {
        value.as_array()?.get(*self)
    }
    fn index_into_mut<'v>(&self, value: &'v mut AnyValue) -> Option<&'v mut AnyValue> {
        value.as_array_mut()?.get_mut(*self)
    }
    fn index_or_insert<'v>(&self, value: &'v mut AnyValue) -> &'v mut AnyValue {
        match value {
            AnyValue::Array(items) => {
                let len = items.len();
                items
                    .get_mut(*self)
                    .unwrap_or_else(|| panic!("index {self} out of bounds: the len is {len}"))
            }
            other => panic!("cannot index {} with a number", kind(other)),
        }
    }
}

impl<T: AnyValueIndex + ?Sized> AnyValueIndex for &T {
    fn index_into<'v>(&self, value: &'v AnyValue) -> Option<&'v AnyValue> {
        (**self).index_into(value)
    }
    fn index_into_mut<'v>(&self, value: &'v mut AnyValue) -> Option<&'v mut AnyValue> {
        (**self).index_into_mut(value)
    }
    fn index_or_insert<'v>(&self, value: &'v mut AnyValue) -> &'v mut AnyValue {
        (**self).index_or_insert(value)
    }
}

fn kind(value: &AnyValue) -> &'static str {
    match value {
        AnyValue::Null => "null",
        AnyValue::Bool(_) => "a boolean",
        AnyValue::Number(_) => "a number",
        AnyValue::String(_) => "a string",
        AnyValue::Array(_) => "an array",
        AnyValue::Object(_) => "an object",
    }
}

/// `value[key]`: `null` when the key or the index is missing.
impl<I: AnyValueIndex> Index<I> for AnyValue {
    type Output = AnyValue;
    fn index(&self, index: I) -> &AnyValue {
        index.index_into(self).unwrap_or(&NULL)
    }
}

/// `value[key] = ...`: adds a missing key, and makes `null` an empty object first.
impl<I: AnyValueIndex> IndexMut<I> for AnyValue {
    fn index_mut(&mut self, index: I) -> &mut AnyValue {
        index.index_or_insert(self)
    }
}

// --- Conversions -----------------------------------------------------------------------------

/// `From` each listed type for [`AnyValue`], converted into the variant that holds it.
macro_rules! value_from {
    ($($variant:ident: $($from:ty),+;)*) => {$($(
        impl From<$from> for AnyValue {
            fn from(value: $from) -> Self {
                AnyValue::$variant(value.into())
            }
        }
    )+)*};
}
value_from! {
    String: &str, String;
    Number: i64, u64, i32, u32, usize;
}

/// A finite double, or `null` for a double that is not finite.
impl From<f64> for AnyValue {
    fn from(float: f64) -> Self {
        Number::from_f64(float).map_or(AnyValue::Null, AnyValue::Number)
    }
}

impl From<AnyMap> for AnyValue {
    fn from(map: AnyMap) -> Self {
        AnyValue::Object(map)
    }
}

impl<T: Into<AnyValue>> FromIterator<T> for AnyValue {
    fn from_iter<I: IntoIterator<Item = T>>(items: I) -> Self {
        AnyValue::Array(items.into_iter().map(Into::into).collect())
    }
}

/// A value the `json!` macro builds.
impl From<serde_json::Value> for AnyValue {
    fn from(value: serde_json::Value) -> Self {
        match value {
            serde_json::Value::Null => AnyValue::Null,
            serde_json::Value::Bool(flag) => AnyValue::Bool(flag),
            serde_json::Value::Number(number) => number
                .to_string()
                .parse()
                .map_or(AnyValue::Null, AnyValue::Number),
            serde_json::Value::String(text) => AnyValue::String(text.into()),
            serde_json::Value::Array(items) => items.into_iter().map(AnyValue::from).collect(),
            serde_json::Value::Object(map) => AnyValue::Object(
                map.into_iter()
                    .map(|(key, value)| (key, AnyValue::from(value)))
                    .collect(),
            ),
        }
    }
}

/// A value written in JSON syntax, such as `json!({"a": [1, true]})`.
#[macro_export]
macro_rules! json {
    ($($json:tt)+) => {
        $crate::value::AnyValue::from(::serde_json::json!($($json)+))
    };
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[cfg(target_pointer_width = "64")]
    fn a_value_takes_the_room_of_a_string() {
        assert_eq!(std::mem::size_of::<AnyValue>(), 32);
    }

    #[test]
    fn indexing_reads_null_when_missing_and_adds_when_written() {
        let mut value = AnyValue::Null;
        assert!(value["a"]["b"].is_null());
        value["a"] = json!({"b": [1, 2]});
        value["a"]["c"] = json!(true);
        assert_eq!(value["a"]["b"][1], json!(2));
        assert_eq!(value.to_string(), r#"{"a":{"b":[1,2],"c":true}}"#);
    }
}
