//! [`AnyValue`]: a JSON value as the engine holds it.
//!
//! It has the shape and the method names of `serde_json::Value`, with two
//! differences that make a flow cheaper to hold and to walk:
//!
//! - An object is a list of key-value pairs in insertion order ([`AnyMap`]), not
//!   an `IndexMap`. A flow has thousands of small objects, and a hash table for
//!   each one costs more memory and time than it saves. Finding a key scans the
//!   list, which is fast for the short objects of a flow.
//! - A number is an integer or a double ([`Number`]), not its text. `1` and
//!   `1.0` stay apart, as Python's `int` and `float` do. A number that neither
//!   holds exactly, an integer too large for 64 bits or a value that is
//!   infinite as a double, keeps its text. The spelling of a double is not
//!   kept: `1e2` and `100.0` are the same number, as the hash and `json.loads`
//!   already read them.
//!
//! JSON text goes through `serde_json`'s parser and writer, by the
//! [`serde::Deserialize`] and [`serde::Serialize`] implementations here.
//! [`FiniteAnyValue`] parses text as [`AnyValue`] does, but refuses a number that
//! is infinite as a double, as reading a Python `float` refuses Infinity.

use std::fmt;
use std::ops::{Index, IndexMut};
use std::str::FromStr;

use serde::de::{self, Deserialize, DeserializeSeed, Deserializer, MapAccess, SeqAccess, Visitor};
use serde::ser::{Serialize, SerializeMap, Serializer};

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
    String(String),
    /// An array.
    Array(Vec<AnyValue>),
    /// An object, its keys in insertion order.
    Object(AnyMap),
}

/// The reference tokens of a JSON Pointer, unescaped: `~1` is `/` and `~0` is `~`.
fn pointer_steps(pointer: &str) -> Option<Vec<String>> {
    if pointer.is_empty() {
        return Some(Vec::new());
    }
    let rest = pointer.strip_prefix('/')?;
    Some(
        rest.split('/')
            .map(|step| step.replace("~1", "/").replace("~0", "~"))
            .collect(),
    )
}

/// An array index token: digits, with no leading zero.
fn array_index(step: &str) -> Option<usize> {
    if step.starts_with('+') || (step.len() > 1 && step.starts_with('0')) {
        return None;
    }
    step.parse().ok()
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

    /// The value at a JSON Pointer (RFC 6901), such as `/data/node/template`.
    #[must_use]
    pub fn pointer(&self, pointer: &str) -> Option<&AnyValue> {
        pointer_steps(pointer)?
            .into_iter()
            .try_fold(self, |value, step| match value {
                AnyValue::Object(map) => map.get(&step),
                AnyValue::Array(items) => items.get(array_index(&step)?),
                _ => None,
            })
    }

    /// The value at a JSON Pointer (RFC 6901), to change it.
    pub fn pointer_mut(&mut self, pointer: &str) -> Option<&mut AnyValue> {
        pointer_steps(pointer)?
            .into_iter()
            .try_fold(self, |value, step| match value {
                AnyValue::Object(map) => map.get_mut(&step),
                AnyValue::Array(items) => items.get_mut(array_index(&step)?),
                _ => None,
            })
    }

    /// The value, leaving `null` in its place.
    #[must_use = "the value is moved out"]
    pub fn take(&mut self) -> AnyValue {
        std::mem::take(self)
    }

    /// Whether the value is `null`.
    #[must_use]
    pub fn is_null(&self) -> bool {
        matches!(self, AnyValue::Null)
    }

    /// Whether the value is `true` or `false`.
    #[must_use]
    pub fn is_boolean(&self) -> bool {
        matches!(self, AnyValue::Bool(_))
    }

    /// Whether the value is a number.
    #[must_use]
    pub fn is_number(&self) -> bool {
        matches!(self, AnyValue::Number(_))
    }

    /// Whether the value is a string.
    #[must_use]
    pub fn is_string(&self) -> bool {
        matches!(self, AnyValue::String(_))
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

/// The JSON text of a value, compact.
impl fmt::Display for AnyValue {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&serde_json::to_string(self).map_err(|_| fmt::Error)?)
    }
}

/// Comparisons with plain values, as `serde_json` has.
macro_rules! eq_with {
    ($($type:ty => $value:ident => $body:expr),* $(,)?) => {$(
        impl PartialEq<$type> for AnyValue {
            fn eq(&self, $value: &$type) -> bool {
                $body(self)
            }
        }
        impl PartialEq<AnyValue> for $type {
            fn eq(&self, value: &AnyValue) -> bool {
                value == self
            }
        }
    )*};
}

eq_with! {
    str => other => |value: &AnyValue| value.as_str() == Some(other),
    &str => other => |value: &AnyValue| value.as_str() == Some(*other),
    String => other => |value: &AnyValue| value.as_str() == Some(other.as_str()),
    bool => other => |value: &AnyValue| value.as_bool() == Some(*other),
    i64 => other => |value: &AnyValue| value.as_i64() == Some(*other),
    u64 => other => |value: &AnyValue| value.as_u64() == Some(*other),
    f64 => other => |value: &AnyValue| value.as_f64() == Some(*other),
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
    /// As `serde_json`: `null` becomes an empty object, and a missing key is added as `null`.
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

/// `value[key]`: `null` when the key or the index is missing, as `serde_json`.
impl<I: AnyValueIndex> Index<I> for AnyValue {
    type Output = AnyValue;
    fn index(&self, index: I) -> &AnyValue {
        index.index_into(self).unwrap_or(&NULL)
    }
}

/// `value[key] = ...`: adds a missing key, as `serde_json`.
impl<I: AnyValueIndex> IndexMut<I> for AnyValue {
    fn index_mut(&mut self, index: I) -> &mut AnyValue {
        index.index_or_insert(self)
    }
}

// --- Objects ---------------------------------------------------------------------------------

/// A JSON object: its key-value pairs, in insertion order.
///
/// The method names follow `serde_json::Map` with its `preserve_order`
/// feature, so [`AnyMap::remove`] moves the last pair into the gap, as
/// `swap_remove` does, and [`AnyMap::shift_remove`] keeps the order.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct AnyMap {
    entries: Vec<(String, AnyValue)>,
}

impl AnyMap {
    /// An empty object.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// An empty object with room for `capacity` pairs.
    #[must_use]
    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            entries: Vec::with_capacity(capacity),
        }
    }

    /// The number of pairs.
    #[must_use]
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Whether the object has no pairs.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    fn position(&self, key: &str) -> Option<usize> {
        self.entries.iter().position(|(k, _)| k == key)
    }

    /// The value at `key`.
    #[must_use]
    pub fn get(&self, key: &str) -> Option<&AnyValue> {
        self.entries.iter().find(|(k, _)| k == key).map(|(_, v)| v)
    }

    /// The value at `key`, to change it.
    pub fn get_mut(&mut self, key: &str) -> Option<&mut AnyValue> {
        self.entries
            .iter_mut()
            .find(|(k, _)| k == key)
            .map(|(_, v)| v)
    }

    /// Whether the object has `key`.
    #[must_use]
    pub fn contains_key(&self, key: &str) -> bool {
        self.position(key).is_some()
    }

    /// Insert or replace. A replaced key keeps its position; a new key goes last.
    pub fn insert(&mut self, key: String, value: AnyValue) -> Option<AnyValue> {
        if let Some(index) = self.position(&key) {
            return Some(std::mem::replace(&mut self.entries[index].1, value));
        }
        self.entries.push((key, value));
        None
    }

    /// Add a pair whose key the object does not have, without looking for it:
    /// for a caller that knows its keys are unique, such as a Python dict.
    /// A key that is already there would be held twice.
    pub fn push(&mut self, key: String, value: AnyValue) {
        debug_assert!(
            !self.contains_key(&key),
            "push of a key the object has: {key}"
        );
        self.entries.push((key, value));
    }

    /// Remove a key, moving the last pair into its place, as `serde_json`'s
    /// `remove` with `preserve_order` does.
    pub fn remove(&mut self, key: &str) -> Option<AnyValue> {
        self.swap_remove(key)
    }

    /// Remove a key, moving the last pair into its place.
    pub fn swap_remove(&mut self, key: &str) -> Option<AnyValue> {
        let index = self.position(key)?;
        Some(self.entries.swap_remove(index).1)
    }

    /// Remove a key, keeping the order of the others.
    pub fn shift_remove(&mut self, key: &str) -> Option<AnyValue> {
        let index = self.position(key)?;
        Some(self.entries.remove(index).1)
    }

    /// The value at `key`, added as `null` when it is missing.
    fn entry_or_null(&mut self, key: &str) -> &mut AnyValue {
        let index = self.position(key).unwrap_or_else(|| {
            self.entries.push((key.to_owned(), AnyValue::Null));
            self.entries.len() - 1
        });
        &mut self.entries[index].1
    }

    /// Keep the pairs `keep` holds for, in order.
    pub fn retain(&mut self, mut keep: impl FnMut(&String, &mut AnyValue) -> bool) {
        self.entries.retain_mut(|(k, v)| keep(k, v));
    }

    /// The pairs, in order.
    #[must_use]
    pub fn iter(&self) -> Iter<'_> {
        Iter(self.entries.iter())
    }

    /// The pairs, in order, to change the values.
    pub fn iter_mut(&mut self) -> IterMut<'_> {
        IterMut(self.entries.iter_mut())
    }

    /// The keys, in order.
    pub fn keys(&self) -> impl DoubleEndedIterator<Item = &String> + ExactSizeIterator {
        self.entries.iter().map(|(k, _)| k)
    }

    /// The values, in order.
    pub fn values(&self) -> impl DoubleEndedIterator<Item = &AnyValue> + ExactSizeIterator {
        self.entries.iter().map(|(_, v)| v)
    }

    /// The values, in order, to change them.
    pub fn values_mut(
        &mut self,
    ) -> impl DoubleEndedIterator<Item = &mut AnyValue> + ExactSizeIterator {
        self.entries.iter_mut().map(|(_, v)| v)
    }
}

/// The pairs of an [`AnyMap`], borrowed.
#[derive(Debug, Clone)]
pub struct Iter<'m>(std::slice::Iter<'m, (String, AnyValue)>);

impl<'m> Iterator for Iter<'m> {
    type Item = (&'m String, &'m AnyValue);
    fn next(&mut self) -> Option<Self::Item> {
        self.0.next().map(|(k, v)| (k, v))
    }
    fn size_hint(&self) -> (usize, Option<usize>) {
        self.0.size_hint()
    }
}

impl DoubleEndedIterator for Iter<'_> {
    fn next_back(&mut self) -> Option<Self::Item> {
        self.0.next_back().map(|(k, v)| (k, v))
    }
}

impl ExactSizeIterator for Iter<'_> {}

/// The pairs of an [`AnyMap`], borrowed to change the values.
#[derive(Debug)]
pub struct IterMut<'m>(std::slice::IterMut<'m, (String, AnyValue)>);

impl<'m> Iterator for IterMut<'m> {
    type Item = (&'m String, &'m mut AnyValue);
    fn next(&mut self) -> Option<Self::Item> {
        self.0.next().map(|(k, v)| (&*k, v))
    }
    fn size_hint(&self) -> (usize, Option<usize>) {
        self.0.size_hint()
    }
}

impl ExactSizeIterator for IterMut<'_> {}

impl<'m> IntoIterator for &'m AnyMap {
    type Item = (&'m String, &'m AnyValue);
    type IntoIter = Iter<'m>;
    fn into_iter(self) -> Iter<'m> {
        self.iter()
    }
}

impl<'m> IntoIterator for &'m mut AnyMap {
    type Item = (&'m String, &'m mut AnyValue);
    type IntoIter = IterMut<'m>;
    fn into_iter(self) -> IterMut<'m> {
        self.iter_mut()
    }
}

impl IntoIterator for AnyMap {
    type Item = (String, AnyValue);
    type IntoIter = std::vec::IntoIter<(String, AnyValue)>;
    fn into_iter(self) -> Self::IntoIter {
        self.entries.into_iter()
    }
}

/// Insert each pair: a repeated key keeps its first position and its last value.
impl Extend<(String, AnyValue)> for AnyMap {
    fn extend<T: IntoIterator<Item = (String, AnyValue)>>(&mut self, pairs: T) {
        for (key, value) in pairs {
            self.insert(key, value);
        }
    }
}

impl FromIterator<(String, AnyValue)> for AnyMap {
    fn from_iter<T: IntoIterator<Item = (String, AnyValue)>>(pairs: T) -> Self {
        let mut map = AnyMap::new();
        map.extend(pairs);
        map
    }
}

/// `map[key]`: panics when the key is missing, as `serde_json`.
impl Index<&str> for AnyMap {
    type Output = AnyValue;
    fn index(&self, key: &str) -> &AnyValue {
        self.get(key).expect("no entry found for key")
    }
}

// --- Numbers ---------------------------------------------------------------------------------

/// A JSON number: an integer or a double, or the text of one that neither holds exactly.
#[derive(Debug, Clone, PartialEq)]
pub struct Number(N);

/// Equality is reflexive: a double here is always finite, never NaN.
impl Eq for Number {}

#[derive(Debug, Clone, PartialEq)]
enum N {
    /// An integer from 0 to `u64::MAX`.
    PosInt(u64),
    /// A negative integer from `i64::MIN`.
    NegInt(i64),
    /// A finite double, from text with a fraction or an exponent.
    Float(f64),
    /// The text of an integer too large for 64 bits, or of a number that is
    /// infinite as a double.
    Text(Box<str>),
}

impl Number {
    /// A finite double as a number, or `None`.
    #[must_use]
    pub fn from_f64(value: f64) -> Option<Number> {
        value.is_finite().then_some(Number(N::Float(value)))
    }

    /// The number as an `i64`, when it is an integer that one holds.
    #[must_use]
    pub fn as_i64(&self) -> Option<i64> {
        match self.0 {
            N::PosInt(int) => i64::try_from(int).ok(),
            N::NegInt(int) => Some(int),
            N::Float(_) | N::Text(_) => None,
        }
    }

    /// The number as a `u64`, when it is an integer that one holds.
    #[must_use]
    pub fn as_u64(&self) -> Option<u64> {
        match self.0 {
            N::PosInt(int) => Some(int),
            N::NegInt(_) | N::Float(_) | N::Text(_) => None,
        }
    }

    /// The number as a double, `None` only for text that is not a number.
    #[must_use]
    #[expect(clippy::cast_precision_loss, reason = "a double is what is asked for")]
    pub fn as_f64(&self) -> Option<f64> {
        match &self.0 {
            N::PosInt(int) => Some(*int as f64),
            N::NegInt(int) => Some(*int as f64),
            N::Float(float) => Some(*float),
            N::Text(text) => text.parse().ok(),
        }
    }

    /// Whether the number was written as an integer, with no fraction and no
    /// exponent: how Python tells an `int` from a `float`.
    #[must_use]
    pub fn is_integer(&self) -> bool {
        match &self.0 {
            N::PosInt(_) | N::NegInt(_) => true,
            N::Float(_) => false,
            N::Text(text) => !text.contains(['.', 'e', 'E']),
        }
    }

    /// The number as an integer, when it is one that 128 bits hold.
    #[must_use]
    pub fn as_i128(&self) -> Option<i128> {
        match &self.0 {
            N::PosInt(int) => Some(i128::from(*int)),
            N::NegInt(int) => Some(i128::from(*int)),
            N::Text(text) if self.is_integer() => text.parse().ok(),
            N::Float(_) | N::Text(_) => None,
        }
    }
}

impl From<i64> for Number {
    fn from(int: i64) -> Self {
        match u64::try_from(int) {
            Ok(positive) => Number(N::PosInt(positive)),
            Err(_) => Number(N::NegInt(int)),
        }
    }
}

impl From<u64> for Number {
    fn from(int: u64) -> Self {
        Number(N::PosInt(int))
    }
}

impl From<i32> for Number {
    fn from(int: i32) -> Self {
        Number::from(i64::from(int))
    }
}

impl From<u32> for Number {
    fn from(int: u32) -> Self {
        Number::from(u64::from(int))
    }
}

impl From<usize> for Number {
    fn from(int: usize) -> Self {
        Number(N::PosInt(int as u64))
    }
}

/// The text of a JSON number is not a number.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NotANumber;

impl fmt::Display for NotANumber {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("not a JSON number")
    }
}

impl std::error::Error for NotANumber {}

/// A number from its JSON text: an integer that 64 bits hold, a finite double
/// from text with a fraction or an exponent, or else the text.
impl FromStr for Number {
    type Err = NotANumber;
    fn from_str(text: &str) -> Result<Self, NotANumber> {
        if !is_json_number(text) {
            return Err(NotANumber);
        }
        if !text.contains(['.', 'e', 'E']) {
            if let Ok(int) = text.parse::<u64>() {
                return Ok(Number(N::PosInt(int)));
            }
            if let Ok(int) = text.parse::<i64>() {
                return Ok(Number(N::NegInt(int)));
            }
            return Ok(Number(N::Text(text.into())));
        }
        match text.parse::<f64>() {
            Ok(float) if float.is_finite() => Ok(Number(N::Float(float))),
            _ => Ok(Number(N::Text(text.into()))),
        }
    }
}

/// Whether text has the grammar of a JSON number (RFC 8259).
fn is_json_number(text: &str) -> bool {
    let bytes = text.as_bytes();
    let mut at = usize::from(bytes.first() == Some(&b'-'));
    let digits = |at: &mut usize| {
        let start = *at;
        while bytes.get(*at).is_some_and(u8::is_ascii_digit) {
            *at += 1;
        }
        *at - start
    };
    match bytes.get(at) {
        Some(b'0') => at += 1,
        Some(b'1'..=b'9') => {
            digits(&mut at);
        }
        _ => return false,
    }
    if bytes.get(at) == Some(&b'.') {
        at += 1;
        if digits(&mut at) == 0 {
            return false;
        }
    }
    if matches!(bytes.get(at), Some(b'e' | b'E')) {
        at += 1;
        if matches!(bytes.get(at), Some(b'+' | b'-')) {
            at += 1;
        }
        if digits(&mut at) == 0 {
            return false;
        }
    }
    at == bytes.len()
}

/// The number's JSON text: integers in full, doubles as `serde_json` writes them, text as it is.
impl fmt::Display for Number {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match &self.0 {
            N::PosInt(int) => write!(f, "{int}"),
            N::NegInt(int) => write!(f, "{int}"),
            N::Float(float) => f.write_str(&serde_json::to_string(float).map_err(|_| fmt::Error)?),
            N::Text(text) => f.write_str(text),
        }
    }
}

// --- Conversions -----------------------------------------------------------------------------

impl From<bool> for AnyValue {
    fn from(flag: bool) -> Self {
        AnyValue::Bool(flag)
    }
}

impl From<&str> for AnyValue {
    fn from(text: &str) -> Self {
        AnyValue::String(text.to_owned())
    }
}

impl From<String> for AnyValue {
    fn from(text: String) -> Self {
        AnyValue::String(text)
    }
}

impl From<&String> for AnyValue {
    fn from(text: &String) -> Self {
        AnyValue::String(text.clone())
    }
}

impl From<Number> for AnyValue {
    fn from(number: Number) -> Self {
        AnyValue::Number(number)
    }
}

impl From<i64> for AnyValue {
    fn from(int: i64) -> Self {
        AnyValue::Number(int.into())
    }
}

impl From<u64> for AnyValue {
    fn from(int: u64) -> Self {
        AnyValue::Number(int.into())
    }
}

impl From<i32> for AnyValue {
    fn from(int: i32) -> Self {
        AnyValue::Number(int.into())
    }
}

impl From<u32> for AnyValue {
    fn from(int: u32) -> Self {
        AnyValue::Number(int.into())
    }
}

impl From<usize> for AnyValue {
    fn from(int: usize) -> Self {
        AnyValue::Number(int.into())
    }
}

/// A finite double, or `null`, as `serde_json`.
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

impl<T: Into<AnyValue>> From<Vec<T>> for AnyValue {
    fn from(items: Vec<T>) -> Self {
        AnyValue::Array(items.into_iter().map(Into::into).collect())
    }
}

impl<T: Into<AnyValue>> From<Option<T>> for AnyValue {
    fn from(value: Option<T>) -> Self {
        value.map_or(AnyValue::Null, Into::into)
    }
}

impl<T: Into<AnyValue>> FromIterator<T> for AnyValue {
    fn from_iter<I: IntoIterator<Item = T>>(items: I) -> Self {
        AnyValue::Array(items.into_iter().map(Into::into).collect())
    }
}

/// A `serde_json` value, for the `json!` macro and for callers that hold one.
impl From<serde_json::Value> for AnyValue {
    fn from(value: serde_json::Value) -> Self {
        match value {
            serde_json::Value::Null => AnyValue::Null,
            serde_json::Value::Bool(flag) => AnyValue::Bool(flag),
            serde_json::Value::Number(number) => number
                .to_string()
                .parse()
                .map_or(AnyValue::Null, AnyValue::Number),
            serde_json::Value::String(text) => AnyValue::String(text),
            serde_json::Value::Array(items) => items.into_iter().map(AnyValue::from).collect(),
            serde_json::Value::Object(map) => AnyValue::Object(
                map.into_iter()
                    .map(|(key, value)| (key, AnyValue::from(value)))
                    .collect(),
            ),
        }
    }
}

/// A JSON value written as JSON, as `serde_json::json!` writes it.
#[macro_export]
macro_rules! json {
    ($($json:tt)+) => {
        $crate::value::AnyValue::from(::serde_json::json!($($json)+))
    };
}

// --- serde ------------------------------------------------------------------------------------

impl Serialize for AnyValue {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        match self {
            AnyValue::Null => serializer.serialize_unit(),
            AnyValue::Bool(flag) => serializer.serialize_bool(*flag),
            AnyValue::Number(number) => number.serialize(serializer),
            AnyValue::String(text) => serializer.serialize_str(text),
            AnyValue::Array(items) => serializer.collect_seq(items),
            AnyValue::Object(map) => map.serialize(serializer),
        }
    }
}

impl Serialize for AnyMap {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        let mut out = serializer.serialize_map(Some(self.len()))?;
        for (key, value) in self {
            out.serialize_entry(key, value)?;
        }
        out.end()
    }
}

impl Serialize for Number {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        match &self.0 {
            N::PosInt(int) => serializer.serialize_u64(*int),
            N::NegInt(int) => serializer.serialize_i64(*int),
            N::Float(float) => serializer.serialize_f64(*float),
            // serde_json writes a number's text as it is with arbitrary_precision.
            N::Text(text) => serde_json::Number::from_str(text)
                .map_err(serde::ser::Error::custom)?
                .serialize(serializer),
        }
    }
}

/// With `arbitrary_precision`, `serde_json` gives a number to a visitor as a
/// one-key map that holds its text.
const NUMBER_TOKEN: &str = "$serde_json::private::Number";

impl<'de> Deserialize<'de> for AnyValue {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<AnyValue, D::Error> {
        Builder::<false>::default().value(deserializer)
    }
}

/// Why [`FiniteAnyValue`] refuses a number.
pub const NOT_FINITE: &str = "NaN and Infinity are not JSON numbers";

/// A value parsed from JSON text with every number finite as a double. Text
/// with a number too large for a double, such as `1e400`, does not parse
/// ([`NOT_FINITE`]). An integer too large for a double still parses: it keeps
/// its digits, as a Python `int` does.
#[derive(Debug, Clone, PartialEq)]
pub struct FiniteAnyValue(pub AnyValue);

impl<'de> Deserialize<'de> for FiniteAnyValue {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<FiniteAnyValue, D::Error> {
        Builder::<true>::default()
            .value(deserializer)
            .map(FiniteAnyValue)
    }
}

/// What a parse holds while it builds an [`AnyValue`]: the members and items of
/// the objects and arrays it is inside, one stack for each kind.
///
/// JSON text does not say how many members an object has, so a list that
/// grows as they come reallocates its buffer several times, and ends with
/// room to spare. Each member goes on the stack instead, and when the object
/// ends its members move off the stack into a list of exactly their number:
/// one allocation for each object and array, with no room to spare.
#[derive(Debug, Default)]
struct Builder<const FINITE: bool> {
    entries: Vec<(String, AnyValue)>,
    items: Vec<AnyValue>,
}

impl<const FINITE: bool> Builder<FINITE> {
    fn value<'de, D: Deserializer<'de>>(mut self, deserializer: D) -> Result<AnyValue, D::Error> {
        deserializer.deserialize_any(AnyValueVisitor::<FINITE>(&mut self))
    }
}

/// Builds an [`AnyValue`] with a [`Builder`]; with `FINITE`, refuses a number that is not finite.
struct AnyValueVisitor<'b, const FINITE: bool>(&'b mut Builder<FINITE>);

impl<'de, const FINITE: bool> DeserializeSeed<'de> for AnyValueVisitor<'_, FINITE> {
    type Value = AnyValue;

    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<AnyValue, D::Error> {
        deserializer.deserialize_any(self)
    }
}

impl<'de, const FINITE: bool> Visitor<'de> for AnyValueVisitor<'_, FINITE> {
    type Value = AnyValue;

    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("a JSON value")
    }

    fn visit_bool<E>(self, flag: bool) -> Result<AnyValue, E> {
        Ok(AnyValue::Bool(flag))
    }

    fn visit_i64<E>(self, int: i64) -> Result<AnyValue, E> {
        Ok(AnyValue::Number(int.into()))
    }

    fn visit_u64<E>(self, int: u64) -> Result<AnyValue, E> {
        Ok(AnyValue::Number(int.into()))
    }

    fn visit_f64<E>(self, float: f64) -> Result<AnyValue, E> {
        Ok(AnyValue::from(float))
    }

    fn visit_str<E>(self, text: &str) -> Result<AnyValue, E> {
        Ok(AnyValue::String(text.to_owned()))
    }

    fn visit_string<E>(self, text: String) -> Result<AnyValue, E> {
        Ok(AnyValue::String(text))
    }

    fn visit_unit<E>(self) -> Result<AnyValue, E> {
        Ok(AnyValue::Null)
    }

    fn visit_none<E>(self) -> Result<AnyValue, E> {
        Ok(AnyValue::Null)
    }

    fn visit_some<D: Deserializer<'de>>(self, deserializer: D) -> Result<AnyValue, D::Error> {
        deserializer.deserialize_any(self)
    }

    fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<AnyValue, A::Error> {
        let builder = self.0;
        let start = builder.items.len();
        while let Some(item) = seq.next_element_seed(AnyValueVisitor(&mut *builder))? {
            builder.items.push(item);
        }
        Ok(AnyValue::Array(builder.items.drain(start..).collect()))
    }

    fn visit_map<A: MapAccess<'de>>(self, mut access: A) -> Result<AnyValue, A::Error> {
        let builder = self.0;
        let start = builder.entries.len();
        while let Some(key) = access.next_key::<String>()? {
            if builder.entries.len() == start && key == NUMBER_TOKEN {
                let text: String = access.next_value()?;
                let number: Number = text
                    .parse()
                    .map_err(|_| de::Error::custom("not a JSON number"))?;
                if FINITE && !number.is_integer() && number.as_f64().is_none_or(f64::is_infinite) {
                    return Err(de::Error::custom(NOT_FINITE));
                }
                return Ok(AnyValue::Number(number));
            }
            let value = access.next_value_seed(AnyValueVisitor(&mut *builder))?;
            // A repeated key keeps its first position and its last value, as serde_json.
            match builder.entries[start..]
                .iter_mut()
                .find(|(at, _)| *at == key)
            {
                Some(entry) => entry.1 = value,
                None => builder.entries.push((key, value)),
            }
        }
        Ok(AnyValue::Object(AnyMap {
            entries: builder.entries.drain(start..).collect(),
        }))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(text: &str) -> AnyValue {
        serde_json::from_str(text).unwrap()
    }

    #[test]
    fn numbers_keep_int_and_float_apart() {
        let value =
            parse("[1, 1.0, -0.0, 1e2, 12345678901234567890123, 1e400, -5, 18446744073709551615]");
        assert_eq!(
            value.to_string(),
            "[1,1.0,-0.0,100.0,12345678901234567890123,1e+400,-5,18446744073709551615]"
        );
        let items = value.as_array().unwrap();
        assert_ne!(items[0], items[1]);
        assert!(items[0].as_number().unwrap().is_integer());
        assert!(!items[1].as_number().unwrap().is_integer());
        assert!(items[5].as_f64().unwrap().is_infinite());
        assert_eq!(
            items[4].as_number().unwrap().as_i128(),
            Some(12_345_678_901_234_567_890_123)
        );
    }

    #[test]
    fn a_finite_value_refuses_a_number_too_large_for_a_double() {
        for text in ["1e400", "[1, -1e400]", r#"{"a": {"b": [1E999]}}"#] {
            let error = serde_json::from_str::<FiniteAnyValue>(text).unwrap_err();
            assert!(error.to_string().starts_with(NOT_FINITE), "{text}: {error}");
            // AnyValue keeps the number's text.
            serde_json::from_str::<AnyValue>(text).unwrap();
        }
        let digits = format!("1{}", "0".repeat(309));
        let text = format!(r#"[{digits}, 1.5e308, 1e-400, {{"a": 1}}]"#);
        let FiniteAnyValue(value) = serde_json::from_str(&text).unwrap();
        assert_eq!(value, parse(&text));
    }

    #[test]
    fn objects_keep_their_order_and_take_the_last_repeated_value() {
        let value = parse(r#"{"b": 1, "a": 2, "b": 3}"#);
        assert_eq!(value.to_string(), r#"{"b":3,"a":2}"#);
    }

    #[test]
    fn remove_moves_the_last_pair_and_shift_remove_keeps_the_order() {
        let mut map: AnyMap = parse(r#"{"a": 1, "b": 2, "c": 3}"#)
            .as_object()
            .unwrap()
            .clone();
        let mut shifted = map.clone();
        map.remove("a");
        shifted.shift_remove("a");
        assert_eq!(AnyValue::Object(map).to_string(), r#"{"c":3,"b":2}"#);
        assert_eq!(AnyValue::Object(shifted).to_string(), r#"{"b":2,"c":3}"#);
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

    #[test]
    fn json_text_reads_back_as_written() {
        let text = r#"{"x":[null,true,"é",{"k":-3}],"y":2.5}"#;
        assert_eq!(parse(text).to_string(), text);
    }
}
