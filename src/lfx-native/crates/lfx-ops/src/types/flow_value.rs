//! [`FlowValue`]: a JSON value as the engine holds it.
//!
//! - An object ([`FlowObj`]) keeps insertion order. Copies
//!   share it until a write.
//! - Text of up to 24 bytes is inline. One input shares each
//!   long string.
//! - A number ([`Number`]) keeps `1` and `1.0` apart, as Python
//!   does. Example: `1e2` and `100.0` are the same number.

use std::ops::{Index, IndexMut};

use super::{FlowObj, FlowStr, Number};

/// A JSON value.
#[derive(Debug, Clone, PartialEq, Default)]
pub enum FlowValue {
    /// `null`.
    #[default]
    Null,
    /// `true` or `false`.
    Bool(bool),
    /// A number.
    Number(Number),
    /// A string.
    String(FlowStr),
    /// An array.
    Array(Vec<FlowValue>),
    /// An object, its keys in insertion order.
    Object(FlowObj),
}

/// Equality is reflexive: a number is never NaN.
impl Eq for FlowValue {}

/// The value at a missing index, as [`Index`] returns it.
static NULL: FlowValue = FlowValue::Null;

impl FlowValue {
    /// The value at a key of an object or an index of an array.
    pub fn get<I: FlowValueIndex>(&self, index: I) -> Option<&FlowValue> {
        index.index_into(self)
    }

    /// The value at a key or an index, to change it.
    pub fn get_mut<I: FlowValueIndex>(&mut self, index: I) -> Option<&mut FlowValue> {
        index.index_into_mut(self)
    }

    /// Whether the value is `null`.
    #[must_use]
    pub fn is_null(&self) -> bool {
        matches!(self, FlowValue::Null)
    }

    /// Whether the value is an array.
    #[must_use]
    pub fn is_array(&self) -> bool {
        matches!(self, FlowValue::Array(_))
    }

    /// Whether the value is an object.
    #[must_use]
    pub fn is_object(&self) -> bool {
        matches!(self, FlowValue::Object(_))
    }

    /// The boolean, when the value is one.
    #[must_use]
    pub fn as_bool(&self) -> Option<bool> {
        match self {
            FlowValue::Bool(flag) => Some(*flag),
            _ => None,
        }
    }

    /// The string, when the value is one.
    #[must_use]
    pub fn as_str(&self) -> Option<&str> {
        match self {
            FlowValue::String(text) => Some(text),
            _ => None,
        }
    }

    /// The number, when the value is one.
    #[must_use]
    pub fn as_number(&self) -> Option<&Number> {
        match self {
            FlowValue::Number(number) => Some(number),
            _ => None,
        }
    }

    /// The number as an `i64`, when it is an integer that one
    /// holds.
    #[must_use]
    pub fn as_i64(&self) -> Option<i64> {
        self.as_number().and_then(Number::as_i64)
    }

    /// The number as a `u64`, when it is an integer that one
    /// holds.
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
    pub fn as_array(&self) -> Option<&[FlowValue]> {
        match self {
            FlowValue::Array(items) => Some(items),
            _ => None,
        }
    }

    /// The array's items, when the value is an array, to change
    /// them in place.
    pub fn as_array_mut(&mut self) -> Option<&mut [FlowValue]> {
        match self {
            FlowValue::Array(items) => Some(items),
            _ => None,
        }
    }

    /// The array, when the value is one, to add or remove
    /// items.
    pub fn as_vec_mut(&mut self) -> Option<&mut Vec<FlowValue>> {
        match self {
            FlowValue::Array(items) => Some(items),
            _ => None,
        }
    }

    /// The object, when the value is one.
    #[must_use]
    pub fn as_object(&self) -> Option<&FlowObj> {
        match self {
            FlowValue::Object(map) => Some(map),
            _ => None,
        }
    }

    /// The object, when the value is one, to change it.
    pub fn as_object_mut(&mut self) -> Option<&mut FlowObj> {
        match self {
            FlowValue::Object(map) => Some(map),
            _ => None,
        }
    }
}

/// The JSON text of a value, compact, with its characters above
/// U+007F as they are. A value equals a string when it holds
/// that string.
impl PartialEq<&str> for FlowValue {
    fn eq(&self, other: &&str) -> bool {
        self.as_str() == Some(*other)
    }
}

impl PartialEq<FlowValue> for &str {
    fn eq(&self, value: &FlowValue) -> bool {
        value == self
    }
}

// --- Indexing ------------------------------------------------

/// What indexes a value: a key of an object, or an index of an
/// array.
pub trait FlowValueIndex {
    /// The value at this index of `value`.
    fn index_into<'v>(&self, value: &'v FlowValue) -> Option<&'v FlowValue>;
    /// The value at this index of `value`, to change it.
    fn index_into_mut<'v>(&self, value: &'v mut FlowValue) -> Option<&'v mut FlowValue>;
    /// The value at this index, made when it is missing, as
    /// `value[index] = ...` needs.
    fn index_or_insert<'v>(&self, value: &'v mut FlowValue) -> &'v mut FlowValue;
}

impl FlowValueIndex for str {
    fn index_into<'v>(&self, value: &'v FlowValue) -> Option<&'v FlowValue> {
        value.as_object()?.get(self)
    }
    fn index_into_mut<'v>(&self, value: &'v mut FlowValue) -> Option<&'v mut FlowValue> {
        value.as_object_mut()?.get_mut(self)
    }
    /// `null` becomes an empty object, and a missing key is
    /// added as `null`.
    fn index_or_insert<'v>(&self, value: &'v mut FlowValue) -> &'v mut FlowValue {
        if value.is_null() {
            *value = FlowValue::Object(FlowObj::new());
        }
        match value {
            FlowValue::Object(map) => map.entry_or_null(self),
            other => panic!("cannot index {} with a string", kind(other)),
        }
    }
}

impl FlowValueIndex for String {
    fn index_into<'v>(&self, value: &'v FlowValue) -> Option<&'v FlowValue> {
        self.as_str().index_into(value)
    }
    fn index_into_mut<'v>(&self, value: &'v mut FlowValue) -> Option<&'v mut FlowValue> {
        self.as_str().index_into_mut(value)
    }
    fn index_or_insert<'v>(&self, value: &'v mut FlowValue) -> &'v mut FlowValue {
        self.as_str().index_or_insert(value)
    }
}

impl FlowValueIndex for usize {
    fn index_into<'v>(&self, value: &'v FlowValue) -> Option<&'v FlowValue> {
        value.as_array()?.get(*self)
    }
    fn index_into_mut<'v>(&self, value: &'v mut FlowValue) -> Option<&'v mut FlowValue> {
        value.as_array_mut()?.get_mut(*self)
    }
    fn index_or_insert<'v>(&self, value: &'v mut FlowValue) -> &'v mut FlowValue {
        match value {
            FlowValue::Array(items) => {
                let len = items.len();
                items
                    .get_mut(*self)
                    .unwrap_or_else(|| panic!("index {self} out of bounds: the len is {len}"))
            }
            other => panic!("cannot index {} with a number", kind(other)),
        }
    }
}

impl<T: FlowValueIndex + ?Sized> FlowValueIndex for &T {
    fn index_into<'v>(&self, value: &'v FlowValue) -> Option<&'v FlowValue> {
        (**self).index_into(value)
    }
    fn index_into_mut<'v>(&self, value: &'v mut FlowValue) -> Option<&'v mut FlowValue> {
        (**self).index_into_mut(value)
    }
    fn index_or_insert<'v>(&self, value: &'v mut FlowValue) -> &'v mut FlowValue {
        (**self).index_or_insert(value)
    }
}

fn kind(value: &FlowValue) -> &'static str {
    match value {
        FlowValue::Null => "null",
        FlowValue::Bool(_) => "a boolean",
        FlowValue::Number(_) => "a number",
        FlowValue::String(_) => "a string",
        FlowValue::Array(_) => "an array",
        FlowValue::Object(_) => "an object",
    }
}

/// `value[key]`: `null` when the key or the index is missing.
impl<I: FlowValueIndex> Index<I> for FlowValue {
    type Output = FlowValue;
    fn index(&self, index: I) -> &FlowValue {
        index.index_into(self).unwrap_or(&NULL)
    }
}

/// `value[key] = ...`: adds a missing key, and makes `null` an
/// empty object first.
impl<I: FlowValueIndex> IndexMut<I> for FlowValue {
    fn index_mut(&mut self, index: I) -> &mut FlowValue {
        index.index_or_insert(self)
    }
}

// --- Conversions ---------------------------------------------

/// `From` each listed type for [`FlowValue`], converted into
/// the variant that holds it.
macro_rules! value_from {
    ($($variant:ident: $($from:ty),+;)*) => {$($(
        impl From<$from> for FlowValue {
            fn from(value: $from) -> Self {
                FlowValue::$variant(value.into())
            }
        }
    )+)*};
}
value_from! {
    String: &str, String;
    Number: i64, u64, i32, u32, usize;
}

/// A finite double, or `null` for a double that is not finite.
impl From<f64> for FlowValue {
    fn from(float: f64) -> Self {
        Number::from_f64(float).map_or(FlowValue::Null, FlowValue::Number)
    }
}

impl From<bool> for FlowValue {
    fn from(flag: bool) -> Self {
        FlowValue::Bool(flag)
    }
}

/// A copy of the value. Copies share their objects and long
/// strings.
impl From<&FlowValue> for FlowValue {
    fn from(value: &FlowValue) -> Self {
        value.clone()
    }
}

impl<T: Into<FlowValue>> From<Vec<T>> for FlowValue {
    fn from(items: Vec<T>) -> Self {
        FlowValue::Array(items.into_iter().map(Into::into).collect())
    }
}

impl From<FlowObj> for FlowValue {
    fn from(map: FlowObj) -> Self {
        FlowValue::Object(map)
    }
}

impl<T: Into<FlowValue>> FromIterator<T> for FlowValue {
    fn from_iter<I: IntoIterator<Item = T>>(items: I) -> Self {
        FlowValue::Array(items.into_iter().map(Into::into).collect())
    }
}

/// A [`FlowValue`] written in JSON syntax, built directly.
/// Example: `flow_value!({"id": "a", "tags": ["x", 1, null]})`.
/// A value can also be any expression with `Into<FlowValue>`.
#[macro_export]
macro_rules! flow_value {
    ($($json:tt)+) => {
        $crate::flow_value_tokens!($($json)+)
    };
}

/// The token muncher behind [`flow_value!`].
#[doc(hidden)]
#[macro_export]
macro_rules! flow_value_tokens {
    // An array: read items up to each comma.
    (@array [$($items:expr,)*]) => {
        ::std::vec![$($items,)*]
    };
    (@array [$($items:expr),*]) => {
        ::std::vec![$($items),*]
    };
    (@array [$($items:expr,)*] null $($rest:tt)*) => {
        $crate::flow_value_tokens!(@array [$($items,)* $crate::flow_value_tokens!(null)] $($rest)*)
    };
    (@array [$($items:expr,)*] true $($rest:tt)*) => {
        $crate::flow_value_tokens!(@array [$($items,)* $crate::flow_value_tokens!(true)] $($rest)*)
    };
    (@array [$($items:expr,)*] false $($rest:tt)*) => {
        $crate::flow_value_tokens!(@array [$($items,)* $crate::flow_value_tokens!(false)] $($rest)*)
    };
    (@array [$($items:expr,)*] [$($array:tt)*] $($rest:tt)*) => {
        $crate::flow_value_tokens!(@array [$($items,)* $crate::flow_value_tokens!([$($array)*])] $($rest)*)
    };
    (@array [$($items:expr,)*] {$($object:tt)*} $($rest:tt)*) => {
        $crate::flow_value_tokens!(@array [$($items,)* $crate::flow_value_tokens!({$($object)*})] $($rest)*)
    };
    (@array [$($items:expr,)*] $next:expr, $($rest:tt)*) => {
        $crate::flow_value_tokens!(@array [$($items,)* $crate::flow_value_tokens!($next),] $($rest)*)
    };
    (@array [$($items:expr,)*] $last:expr) => {
        $crate::flow_value_tokens!(@array [$($items,)* $crate::flow_value_tokens!($last),])
    };
    (@array [$($items:expr),*] , $($rest:tt)*) => {
        $crate::flow_value_tokens!(@array [$($items,)*] $($rest)*)
    };

    // An object: read a key up to its colon, then a value up to
    // its comma.
    (@object $object:ident () () ()) => {};
    (@object $object:ident [$($key:tt)+] ($value:expr) , $($rest:tt)*) => {
        let _ = $object.insert(::std::string::String::from($($key)+), $value);
        $crate::flow_value_tokens!(@object $object () ($($rest)*) ($($rest)*));
    };
    (@object $object:ident [$($key:tt)+] ($value:expr)) => {
        let _ = $object.insert(::std::string::String::from($($key)+), $value);
    };
    (@object $object:ident ($($key:tt)+) (: null $($rest:tt)*) $copy:tt) => {
        $crate::flow_value_tokens!(@object $object [$($key)+] ($crate::flow_value_tokens!(null)) $($rest)*);
    };
    (@object $object:ident ($($key:tt)+) (: true $($rest:tt)*) $copy:tt) => {
        $crate::flow_value_tokens!(@object $object [$($key)+] ($crate::flow_value_tokens!(true)) $($rest)*);
    };
    (@object $object:ident ($($key:tt)+) (: false $($rest:tt)*) $copy:tt) => {
        $crate::flow_value_tokens!(@object $object [$($key)+] ($crate::flow_value_tokens!(false)) $($rest)*);
    };
    (@object $object:ident ($($key:tt)+) (: [$($array:tt)*] $($rest:tt)*) $copy:tt) => {
        $crate::flow_value_tokens!(@object $object [$($key)+] ($crate::flow_value_tokens!([$($array)*])) $($rest)*);
    };
    (@object $object:ident ($($key:tt)+) (: {$($inner:tt)*} $($rest:tt)*) $copy:tt) => {
        $crate::flow_value_tokens!(@object $object [$($key)+] ($crate::flow_value_tokens!({$($inner)*})) $($rest)*);
    };
    (@object $object:ident ($($key:tt)+) (: $value:expr , $($rest:tt)*) $copy:tt) => {
        $crate::flow_value_tokens!(@object $object [$($key)+] ($crate::flow_value_tokens!($value)) , $($rest)*);
    };
    (@object $object:ident ($($key:tt)+) (: $value:expr) $copy:tt) => {
        $crate::flow_value_tokens!(@object $object [$($key)+] ($crate::flow_value_tokens!($value)));
    };
    (@object $object:ident ($($key:tt)*) ($tt:tt $($rest:tt)*) $copy:tt) => {
        $crate::flow_value_tokens!(@object $object ($($key)* $tt) ($($rest)*) ($($rest)*));
    };

    (null) => {
        $crate::types::FlowValue::Null
    };
    (true) => {
        $crate::types::FlowValue::Bool(true)
    };
    (false) => {
        $crate::types::FlowValue::Bool(false)
    };
    ([]) => {
        $crate::types::FlowValue::Array(::std::vec::Vec::new())
    };
    ([ $($tt:tt)+ ]) => {
        $crate::types::FlowValue::Array($crate::flow_value_tokens!(@array [] $($tt)+))
    };
    ({}) => {
        $crate::types::FlowValue::Object($crate::types::FlowObj::new())
    };
    ({ $($tt:tt)+ }) => {
        $crate::types::FlowValue::Object({
            let mut object = $crate::types::FlowObj::new();
            $crate::flow_value_tokens!(@object object () ($($tt)+) ($($tt)+));
            object
        })
    };
    ($other:expr) => {
        $crate::types::FlowValue::from($other)
    };
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[cfg(target_pointer_width = "64")]
    fn a_value_takes_the_room_of_a_string() {
        assert_eq!(std::mem::size_of::<FlowValue>(), 32);
    }

    #[test]
    fn indexing_reads_null_when_missing_and_adds_when_written() {
        let mut value = FlowValue::Null;
        assert!(value["a"]["b"].is_null());
        value["a"] = flow_value!({"b": [1, 2]});
        value["a"]["c"] = flow_value!(true);
        assert_eq!(value["a"]["b"][1], flow_value!(2));
        assert_eq!(value.to_string(), r#"{"a":{"b":[1,2],"c":true}}"#);
    }
}
