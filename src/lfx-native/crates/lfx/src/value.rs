//! [`AnyValue`]: a JSON value as the engine holds it.
//!
//! A value is `null`, a boolean, a number, a string, an array or an object.
//!
//! - An object ([`AnyMap`]) keeps its keys in insertion order. Small objects
//!   use a bounded list, and larger objects use a hash map. Removing a key keeps the order of the others. Copies of an object
//!   share it until one of them is written.
//! - Keys and string values share immutable text. Each parse or Python input
//!   keeps one shared copy of each distinct string, then releases its pool.
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

use std::borrow::Borrow;
use std::collections::HashSet;
use std::fmt;
use std::hash::BuildHasher;
use std::ops::{Index, IndexMut};
use std::str::FromStr;
use std::sync::{Arc, OnceLock};

use indexmap::IndexMap;

use serde::de::{self, Deserialize, DeserializeSeed, Deserializer, MapAccess, SeqAccess, Visitor};
use serde::ser::{Serialize, SerializeMap, Serializer};

/// Immutable text. Copies share the same allocation.
#[derive(Debug, Clone)]
pub struct AnyString(Arc<Text>);

#[derive(Debug)]
struct Text {
    text: Box<str>,
    ascii_json: OnceLock<Box<[u8]>>,
}

impl PartialEq for AnyString {
    fn eq(&self, other: &Self) -> bool {
        Arc::ptr_eq(&self.0, &other.0) || self.as_str() == other.as_str()
    }
}
impl Eq for AnyString {}
impl std::hash::Hash for AnyString {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.as_str().hash(state);
    }
}
impl PartialOrd for AnyString {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}
impl Ord for AnyString {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        self.as_str().cmp(other.as_str())
    }
}

impl AnyString {
    /// The text, borrowed.
    #[must_use]
    pub fn as_str(&self) -> &str {
        &self.0.text
    }

    /// Reuse the JSON spelling of long repeated text. Unique text is written
    /// directly, so unshared strings do not retain a second copy.
    pub(crate) fn shared_ascii_json(&self) -> Option<&[u8]> {
        if self.len() < 256 {
            return None;
        }
        if let Some(encoded) = self.0.ascii_json.get() {
            return Some(encoded);
        }
        if Arc::strong_count(&self.0) <= 1 {
            return None;
        }
        Some(self.0.ascii_json.get_or_init(|| {
            let mut encoded = Vec::with_capacity(self.len() + 2);
            crate::json_out::write_str(&mut encoded, self, crate::json_out::Ascii::Escape);
            encoded.into_boxed_slice()
        }))
    }
}

impl std::ops::Deref for AnyString {
    type Target = str;
    fn deref(&self) -> &str {
        self.as_str()
    }
}
impl Borrow<str> for AnyString {
    fn borrow(&self) -> &str {
        self.as_str()
    }
}
impl AsRef<str> for AnyString {
    fn as_ref(&self) -> &str {
        self.as_str()
    }
}
impl From<&str> for AnyString {
    fn from(text: &str) -> Self {
        Self(Arc::new(Text {
            text: text.into(),
            ascii_json: OnceLock::new(),
        }))
    }
}
impl From<String> for AnyString {
    fn from(text: String) -> Self {
        Self(Arc::new(Text {
            text: text.into_boxed_str(),
            ascii_json: OnceLock::new(),
        }))
    }
}
impl fmt::Display for AnyString {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self)
    }
}
impl PartialEq<str> for AnyString {
    fn eq(&self, other: &str) -> bool {
        self.as_str() == other
    }
}
impl PartialEq<&str> for AnyString {
    fn eq(&self, other: &&str) -> bool {
        self.as_str() == *other
    }
}
impl Serialize for AnyString {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.serialize_str(self)
    }
}

/// Text shared within one input. The pool ends when reading ends; values
/// retain their own references. Separate inputs never retain each other.
#[derive(Debug, Default)]
pub struct StringPool {
    // Edge handles and small operation inputs usually fit here. Avoid a
    // separate hash-table allocation for those short-lived inputs.
    small: [Option<AnyString>; 16],
    large: Option<HashSet<AnyString, ahash::RandomState>>,
}

impl StringPool {
    /// Reuse equal text, or allocate its first copy.
    pub fn intern(&mut self, text: &str) -> AnyString {
        if let Some(strings) = &mut self.large {
            if let Some(shared) = strings.get(text) {
                return shared.clone();
            }
            let shared = AnyString::from(text);
            strings.insert(shared.clone());
            return shared;
        }
        for slot in &mut self.small {
            if let Some(shared) = slot {
                if shared.as_str() == text {
                    return shared.clone();
                }
            } else {
                let shared = AnyString::from(text);
                *slot = Some(shared.clone());
                return shared;
            }
        }
        // Keep standard-library random seeding on every target. Only the
        // temporary pool uses the faster string hasher.
        let seed = std::collections::hash_map::RandomState::new();
        let state = ahash::RandomState::with_seeds(
            seed.hash_one(0_u8),
            seed.hash_one(1_u8),
            seed.hash_one(2_u8),
            seed.hash_one(3_u8),
        );
        #[expect(
            clippy::mutable_key_type,
            reason = "the JSON cache is excluded from equality and hashing"
        )]
        let mut strings = HashSet::with_capacity_and_hasher(self.small.len() * 2, state);
        strings.extend(self.small.iter_mut().filter_map(Option::take));
        self.large = Some(strings);
        self.intern(text)
    }
}

struct StringSeed<'a>(&'a mut StringPool);
impl<'de> DeserializeSeed<'de> for StringSeed<'_> {
    type Value = AnyString;
    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<AnyString, D::Error> {
        deserializer.deserialize_str(self)
    }
}
impl Visitor<'_> for StringSeed<'_> {
    type Value = AnyString;
    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("a string")
    }
    fn visit_str<E>(self, text: &str) -> Result<AnyString, E> {
        Ok(self.0.intern(text))
    }
}

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

/// Comparisons with plain values: a value equals a string, a boolean or a
/// number when it holds that string, boolean or number.
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

// --- Objects ---------------------------------------------------------------------------------

/// The entries of an object (an entry is a key and its value), by key, in
/// insertion order.
const SMALL_OBJECT_KEYS: usize = 8;
type Row = (AnyString, AnyValue);
#[derive(Debug, Clone)]
enum Entries {
    Small(Vec<Row>),
    Indexed(IndexMap<AnyString, AnyValue>),
}
impl Default for Entries {
    fn default() -> Self {
        Self::Small(Vec::new())
    }
}
impl Entries {
    fn with_capacity(n: usize) -> Self {
        if n <= SMALL_OBJECT_KEYS {
            Self::Small(Vec::with_capacity(n))
        } else {
            Self::Indexed(IndexMap::with_capacity(n))
        }
    }
    fn len(&self) -> usize {
        match self {
            Self::Small(v) => v.len(),
            Self::Indexed(v) => v.len(),
        }
    }
    fn is_empty(&self) -> bool {
        self.len() == 0
    }
    fn get(&self, key: &str) -> Option<&AnyValue> {
        match self {
            Self::Small(v) => v.iter().find(|(k, _)| k.as_str() == key).map(|(_, v)| v),
            Self::Indexed(v) => v.get(key),
        }
    }
    fn get_mut(&mut self, key: &str) -> Option<&mut AnyValue> {
        match self {
            Self::Small(v) => v
                .iter_mut()
                .find(|(k, _)| k.as_str() == key)
                .map(|(_, v)| v),
            Self::Indexed(v) => v.get_mut(key),
        }
    }
    fn contains_key(&self, key: &str) -> bool {
        self.get(key).is_some()
    }
    fn get_index_of(&self, key: &str) -> Option<usize> {
        match self {
            Self::Small(v) => v.iter().position(|(k, _)| k.as_str() == key),
            Self::Indexed(v) => v.get_index_of(key),
        }
    }
    fn insert(&mut self, key: AnyString, value: AnyValue) -> Option<AnyValue> {
        match self {
            Self::Small(v) => {
                if let Some((_, old)) = v.iter_mut().find(|(k, _)| k.as_str() == key.as_str()) {
                    return Some(std::mem::replace(old, value));
                }
                if v.len() < SMALL_OBJECT_KEYS {
                    v.push((key, value));
                    return None;
                }
            }
            Self::Indexed(v) => return v.insert(key, value),
        }
        let Self::Small(rows) = std::mem::take(self) else {
            unreachable!()
        };
        let mut map = IndexMap::with_capacity(SMALL_OBJECT_KEYS * 2);
        map.extend(rows);
        let old = map.insert(key, value);
        *self = Self::Indexed(map);
        old
    }
    fn insert_full(&mut self, key: AnyString, value: AnyValue) -> (usize, Option<AnyValue>) {
        let slot = self.get_index_of(&key).unwrap_or(self.len());
        (slot, self.insert(key, value))
    }
    fn shift_remove(&mut self, key: &str) -> Option<AnyValue> {
        match self {
            Self::Small(v) => {
                let slot = v.iter().position(|(k, _)| k.as_str() == key)?;
                Some(v.remove(slot).1)
            }
            Self::Indexed(v) => v.shift_remove(key),
        }
    }
    fn swap_remove(&mut self, key: &str) -> Option<AnyValue> {
        match self {
            Self::Small(v) => {
                let slot = v.iter().position(|(k, _)| k.as_str() == key)?;
                Some(v.swap_remove(slot).1)
            }
            Self::Indexed(v) => v.swap_remove(key),
        }
    }
    fn retain(&mut self, mut keep: impl FnMut(&AnyString, &mut AnyValue) -> bool) {
        match self {
            Self::Small(v) => v.retain_mut(|(k, v)| keep(k, v)),
            Self::Indexed(v) => v.retain(keep),
        }
    }
    fn iter(&self) -> Iter<'_> {
        Iter(match self {
            Self::Small(v) => IterInner::Small(v.iter()),
            Self::Indexed(v) => IterInner::Indexed(v.iter()),
        })
    }
    fn iter_mut(&mut self) -> IterMut<'_> {
        IterMut(match self {
            Self::Small(v) => IterMutInner::Small(v.iter_mut()),
            Self::Indexed(v) => IterMutInner::Indexed(v.iter_mut()),
        })
    }
}
impl Index<usize> for Entries {
    type Output = AnyValue;
    fn index(&self, slot: usize) -> &AnyValue {
        match self {
            Self::Small(v) => &v[slot].1,
            Self::Indexed(v) => &v[slot],
        }
    }
}
impl IndexMut<usize> for Entries {
    fn index_mut(&mut self, slot: usize) -> &mut AnyValue {
        match self {
            Self::Small(v) => &mut v[slot].1,
            Self::Indexed(v) => &mut v[slot],
        }
    }
}
impl IntoIterator for Entries {
    type Item = Row;
    type IntoIter = IntoIter;
    fn into_iter(self) -> IntoIter {
        IntoIter(match self {
            Self::Small(v) => IntoIterInner::Small(v.into_iter()),
            Self::Indexed(v) => IntoIterInner::Indexed(v.into_iter()),
        })
    }
}

/// An object whose entries keep insertion order.
///
/// A new key goes last, and a replaced key keeps its place. A removal keeps
/// the order of the other entries ([`AnyMap::remove`], [`AnyMap::shift_remove`]),
/// except [`AnyMap::swap_remove`], which moves the last entry into the gap.
///
/// A clone shares the entries. The first write to a shared object copies
/// its keys and values, and an object nested in a copied value stays
/// shared. So a write copies only the objects on the way to the value it
/// writes. The object takes the room of a pointer, so an [`AnyValue`] takes
/// the room of a string.
#[derive(Debug, Clone, Default)]
pub struct AnyMap {
    entries: Arc<Entries>,
}

/// Two objects are equal when they hold equal entries in the same order.
impl PartialEq for AnyMap {
    fn eq(&self, other: &Self) -> bool {
        Arc::ptr_eq(&self.entries, &other.entries)
            || (self.len() == other.len() && self.iter().eq(other.iter()))
    }
}

impl Eq for AnyMap {}

impl AnyMap {
    /// An empty object.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// An empty object with room for `capacity` entries.
    #[must_use]
    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            entries: Arc::new(Entries::with_capacity(capacity)),
        }
    }

    /// Consume this object without destroying shared entries. `None` proves
    /// this reference was released without dropping its payload. `Some` owns
    /// the last entries, so a caller can move their destruction to a worker.
    /// The entries are moved, never cloned, and the ownership decision is atomic.
    #[must_use]
    pub fn into_unshared_entries(self) -> Option<impl Send + 'static> {
        Arc::into_inner(self.entries)
    }

    /// The number of entries.
    #[must_use]
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Whether the object has no entries.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// The value at `key`.
    #[must_use]
    pub fn get(&self, key: &str) -> Option<&AnyValue> {
        self.entries.get(key)
    }

    /// The value at `key`, to change it.
    pub fn get_mut(&mut self, key: &str) -> Option<&mut AnyValue> {
        self.entries_mut().get_mut(key)
    }

    /// Whether the object has `key`.
    #[must_use]
    pub fn contains_key(&self, key: &str) -> bool {
        self.entries.contains_key(key)
    }

    /// Insert or replace. A replaced key keeps its position; a new key goes last.
    pub fn insert(&mut self, key: String, value: AnyValue) -> Option<AnyValue> {
        self.insert_shared(key.into(), value)
    }

    /// Insert a key whose text can be shared with other objects.
    pub fn insert_shared(&mut self, key: AnyString, value: AnyValue) -> Option<AnyValue> {
        self.entries_mut().insert(key, value)
    }

    /// Remove a key, keeping the order of the others.
    pub fn remove(&mut self, key: &str) -> Option<AnyValue> {
        self.shift_remove(key)
    }

    /// Remove a key, moving the last entry into its place.
    pub fn swap_remove(&mut self, key: &str) -> Option<AnyValue> {
        self.entries_mut().swap_remove(key)
    }

    /// Remove a key, keeping the order of the others.
    pub fn shift_remove(&mut self, key: &str) -> Option<AnyValue> {
        self.entries_mut().shift_remove(key)
    }

    /// The value at `key`, added as `null` when it is missing.
    fn entry_or_null(&mut self, key: &str) -> &mut AnyValue {
        let entries = self.entries_mut();
        let index = match entries.get_index_of(key) {
            Some(index) => index,
            None => entries.insert_full(key.into(), AnyValue::Null).0,
        };
        &mut entries[index]
    }

    /// Keep the entries `keep` holds for, in order.
    pub fn retain(&mut self, keep: impl FnMut(&AnyString, &mut AnyValue) -> bool) {
        self.entries_mut().retain(keep);
    }

    /// The entries, to change them: copied first while a clone shares them.
    fn entries_mut(&mut self) -> &mut Entries {
        Arc::make_mut(&mut self.entries)
    }

    /// The entries, in order.
    #[must_use]
    pub fn iter(&self) -> Iter<'_> {
        self.entries.iter()
    }

    /// The entries, in order, to change the values.
    pub fn iter_mut(&mut self) -> IterMut<'_> {
        self.entries_mut().iter_mut()
    }

    /// The keys, in order.
    pub fn keys(&self) -> impl DoubleEndedIterator<Item = &AnyString> + ExactSizeIterator {
        self.iter().map(|(key, _)| key)
    }

    /// The values, in order.
    pub fn values(&self) -> impl DoubleEndedIterator<Item = &AnyValue> + ExactSizeIterator {
        self.iter().map(|(_, value)| value)
    }

    /// The values, in order, to change them.
    pub fn values_mut(
        &mut self,
    ) -> impl DoubleEndedIterator<Item = &mut AnyValue> + ExactSizeIterator {
        self.iter_mut().map(|(_, value)| value)
    }
}

/// Borrowed entries, in insertion order.
#[derive(Debug, Clone)]
pub struct Iter<'m>(IterInner<'m>);
#[derive(Debug, Clone)]
enum IterInner<'m> {
    Small(std::slice::Iter<'m, Row>),
    Indexed(indexmap::map::Iter<'m, AnyString, AnyValue>),
}
impl<'m> Iterator for Iter<'m> {
    type Item = (&'m AnyString, &'m AnyValue);
    fn next(&mut self) -> Option<Self::Item> {
        match &mut self.0 {
            IterInner::Small(v) => v.next().map(|(k, v)| (k, v)),
            IterInner::Indexed(v) => v.next(),
        }
    }
    fn size_hint(&self) -> (usize, Option<usize>) {
        match &self.0 {
            IterInner::Small(v) => v.size_hint(),
            IterInner::Indexed(v) => v.size_hint(),
        }
    }
}
impl DoubleEndedIterator for Iter<'_> {
    fn next_back(&mut self) -> Option<Self::Item> {
        match &mut self.0 {
            IterInner::Small(v) => v.next_back().map(|(k, v)| (k, v)),
            IterInner::Indexed(v) => v.next_back(),
        }
    }
}
impl ExactSizeIterator for Iter<'_> {}
/// Borrowed entries with mutable values.
#[derive(Debug)]
pub struct IterMut<'m>(IterMutInner<'m>);
#[derive(Debug)]
enum IterMutInner<'m> {
    Small(std::slice::IterMut<'m, Row>),
    Indexed(indexmap::map::IterMut<'m, AnyString, AnyValue>),
}
impl<'m> Iterator for IterMut<'m> {
    type Item = (&'m AnyString, &'m mut AnyValue);
    fn next(&mut self) -> Option<Self::Item> {
        match &mut self.0 {
            IterMutInner::Small(v) => v.next().map(|row| (&row.0, &mut row.1)),
            IterMutInner::Indexed(v) => v.next(),
        }
    }
    fn size_hint(&self) -> (usize, Option<usize>) {
        match &self.0 {
            IterMutInner::Small(v) => v.size_hint(),
            IterMutInner::Indexed(v) => v.size_hint(),
        }
    }
}
impl DoubleEndedIterator for IterMut<'_> {
    fn next_back(&mut self) -> Option<Self::Item> {
        match &mut self.0 {
            IterMutInner::Small(v) => v.next_back().map(|row| (&row.0, &mut row.1)),
            IterMutInner::Indexed(v) => v.next_back(),
        }
    }
}
impl ExactSizeIterator for IterMut<'_> {}
impl<'m> IntoIterator for &'m AnyMap {
    type Item = (&'m AnyString, &'m AnyValue);
    type IntoIter = Iter<'m>;
    fn into_iter(self) -> Iter<'m> {
        self.iter()
    }
}
impl<'m> IntoIterator for &'m mut AnyMap {
    type Item = (&'m AnyString, &'m mut AnyValue);
    type IntoIter = IterMut<'m>;
    fn into_iter(self) -> IterMut<'m> {
        self.iter_mut()
    }
}
/// Owned entries, in insertion order.
#[derive(Debug)]
pub struct IntoIter(IntoIterInner);
#[derive(Debug)]
enum IntoIterInner {
    Small(std::vec::IntoIter<Row>),
    Indexed(indexmap::map::IntoIter<AnyString, AnyValue>),
}
impl Iterator for IntoIter {
    type Item = Row;
    fn next(&mut self) -> Option<Self::Item> {
        match &mut self.0 {
            IntoIterInner::Small(v) => v.next(),
            IntoIterInner::Indexed(v) => v.next(),
        }
    }
    fn size_hint(&self) -> (usize, Option<usize>) {
        match &self.0 {
            IntoIterInner::Small(v) => v.size_hint(),
            IntoIterInner::Indexed(v) => v.size_hint(),
        }
    }
}
impl DoubleEndedIterator for IntoIter {
    fn next_back(&mut self) -> Option<Self::Item> {
        match &mut self.0 {
            IntoIterInner::Small(v) => v.next_back(),
            IntoIterInner::Indexed(v) => v.next_back(),
        }
    }
}
impl ExactSizeIterator for IntoIter {}
impl IntoIterator for AnyMap {
    type Item = Row;
    type IntoIter = IntoIter;
    fn into_iter(self) -> IntoIter {
        Arc::unwrap_or_clone(self.entries).into_iter()
    }
}

/// Insert each entry: a repeated key keeps its first position and its last value.
impl<K: Into<AnyString>> Extend<(K, AnyValue)> for AnyMap {
    fn extend<T: IntoIterator<Item = (K, AnyValue)>>(&mut self, entries: T) {
        for (key, value) in entries {
            self.insert_shared(key.into(), value);
        }
    }
}

impl<K: Into<AnyString>> FromIterator<(K, AnyValue)> for AnyMap {
    fn from_iter<T: IntoIterator<Item = (K, AnyValue)>>(entries: T) -> Self {
        let mut map = AnyMap::new();
        map.extend(entries);
        map
    }
}

/// `map[key]`: panics when the key is missing.
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
        AnyValue::String(text.into())
    }
}

impl From<String> for AnyValue {
    fn from(text: String) -> Self {
        AnyValue::String(text.into())
    }
}

impl From<&String> for AnyValue {
    fn from(text: &String) -> Self {
        AnyValue::String(text.as_str().into())
    }
}

impl From<AnyString> for AnyValue {
    fn from(text: AnyString) -> Self {
        AnyValue::String(text)
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
/// JSON text does not say how many members an object has, so a map or a list
/// that grows as they come reallocates several times, and ends with room to
/// spare. Each member goes on the stack instead, and when the object or the
/// array ends its members move off the stack into a map or a list made for
/// exactly their number.
#[derive(Debug, Default)]
struct Builder<const FINITE: bool> {
    strings: StringPool,
    entries: Vec<(AnyString, AnyValue)>,
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
        Ok(AnyValue::String(self.0.strings.intern(text)))
    }

    fn visit_string<E>(self, text: String) -> Result<AnyValue, E> {
        Ok(AnyValue::String(self.0.strings.intern(&text)))
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
        while let Some(key) = access.next_key_seed(StringSeed(&mut builder.strings))? {
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
            builder.entries.push((key, value));
        }
        // A repeated key keeps its first position and its last value. The
        // entries are built before they are shared, so no insert checks the
        // reference count.
        let mut entries = Entries::with_capacity(builder.entries.len() - start);
        for (key, value) in builder.entries.drain(start..) {
            entries.insert(key, value);
        }
        Ok(AnyValue::Object(AnyMap {
            entries: Arc::new(entries),
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
    fn consuming_shared_maps_never_destroys_their_payload() {
        let child = AnyMap::new();
        let weak = Arc::downgrade(&child.entries);
        let mut map = AnyMap::new();
        map.insert("child".into(), AnyValue::Object(child));
        let shared = map.clone();
        assert!(map.into_unshared_entries().is_none());
        assert!(weak.upgrade().is_some());
        let payload = shared
            .into_unshared_entries()
            .expect("the last owner takes the entries");
        assert!(weak.upgrade().is_some());
        drop(payload);
        assert!(weak.upgrade().is_none());
    }

    #[test]
    fn concurrent_last_map_owners_transfer_one_payload_without_dropping_it() {
        let child = AnyMap::new();
        let weak = Arc::downgrade(&child.entries);
        let mut map = AnyMap::new();
        map.insert("child".into(), AnyValue::Object(child));
        let other = map.clone();
        let barrier = Arc::new(std::sync::Barrier::new(2));
        let threads: Vec<_> = [map, other]
            .into_iter()
            .map(|map| {
                let barrier = barrier.clone();
                std::thread::spawn(move || {
                    barrier.wait();
                    map.into_unshared_entries()
                })
            })
            .collect();
        let payloads: Vec<_> = threads
            .into_iter()
            .map(|thread| thread.join().unwrap())
            .collect();
        assert_eq!(payloads.iter().flatten().count(), 1);
        assert!(weak.upgrade().is_some());
        drop(payloads);
        assert!(weak.upgrade().is_none());
    }

    #[test]
    fn a_pool_keeps_shared_text_when_it_grows_beyond_small_inputs() {
        let mut pool = StringPool::default();
        let first = pool.intern("first");
        for i in 0..32 {
            pool.intern(&format!("key-{i}"));
        }
        let again = pool.intern("first");
        assert!(Arc::ptr_eq(&first.0, &again.0));
        drop(pool);
        assert_eq!(first.as_str(), "first");
        assert_eq!(again.as_str(), "first");
    }

    #[test]
    fn shared_json_cache_preserves_equality_hashes_and_thread_safety() {
        let mut pool = StringPool::default();
        let text = "code \"quoted\"\nœ 😀 ".repeat(50);
        let a = pool.intern(&text);
        let b = pool.intern(&text);
        drop(pool);
        let independent = AnyString::from(text.clone());
        let hash = std::collections::hash_map::RandomState::new();
        let before = hash.hash_one(&a);
        let threads: Vec<_> = [a.clone(), b.clone()]
            .into_iter()
            .map(|text| {
                std::thread::spawn(move || crate::ops::api::json_text(&AnyValue::String(text)))
            })
            .collect();
        for thread in threads {
            let encoded = thread.join().unwrap();
            assert!(encoded.is_ascii());
            assert_eq!(serde_json::from_str::<String>(&encoded).unwrap(), text);
        }
        assert!(a.0.ascii_json.get().is_some());
        assert_eq!(a, independent);
        assert_eq!(hash.hash_one(&a), before);
        assert_eq!(hash.hash_one(&a), hash.hash_one(&independent));
    }

    #[test]
    fn unique_long_text_is_written_without_a_cache() {
        let text = AnyString::from("unique \"text\"\n".repeat(100));
        let value = AnyValue::String(text);
        let encoded = crate::ops::api::json_text(&value);
        assert_eq!(serde_json::from_str::<AnyValue>(&encoded).unwrap(), value);
        let AnyValue::String(text) = value else {
            panic!("string");
        };
        assert!(text.0.ascii_json.get().is_none());
    }

    #[test]
    fn parsed_keys_and_values_share_text_within_one_input() {
        let value = parse(r#"[{"repeat":"shared"},{"repeat":"sh\u0061red"}]"#);
        let a = value[0].as_object().unwrap();
        let b = value[1].as_object().unwrap();
        let (ka, va) = a.iter().next().unwrap();
        let (kb, vb) = b.iter().next().unwrap();
        assert!(Arc::ptr_eq(&ka.0, &kb.0));
        let (AnyValue::String(va), AnyValue::String(vb)) = (va, vb) else {
            panic!("strings");
        };
        assert!(Arc::ptr_eq(&va.0, &vb.0));
        let mut copied = value.clone();
        copied[0]["repeat"] = AnyValue::from("changed");
        assert_eq!(value[0]["repeat"].as_str(), Some("shared"));
        let AnyValue::String(unchanged) = &copied[1]["repeat"] else {
            panic!("string");
        };
        assert!(Arc::ptr_eq(&va.0, &unchanged.0));
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
    fn remove_keeps_the_order_and_swap_remove_moves_the_last_entry() {
        let mut map: AnyMap = parse(r#"{"a": 1, "b": 2, "c": 3}"#)
            .as_object()
            .unwrap()
            .clone();
        let mut shifted = map.clone();
        let mut swapped = map.clone();
        map.remove("a");
        shifted.shift_remove("a");
        swapped.swap_remove("a");
        assert_eq!(AnyValue::Object(map).to_string(), r#"{"b":2,"c":3}"#);
        assert_eq!(AnyValue::Object(shifted).to_string(), r#"{"b":2,"c":3}"#);
        assert_eq!(AnyValue::Object(swapped).to_string(), r#"{"c":3,"b":2}"#);
    }

    #[test]
    fn objects_are_equal_only_with_their_entries_in_the_same_order() {
        assert_eq!(parse(r#"{"a": 1, "b": 2}"#), parse(r#"{"a": 1, "b": 2}"#));
        assert_ne!(parse(r#"{"a": 1, "b": 2}"#), parse(r#"{"b": 2, "a": 1}"#));
    }

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

    #[test]
    fn json_text_reads_back_as_written() {
        let text = r#"{"x":[null,true,"é",{"k":-3}],"y":2.5}"#;
        assert_eq!(parse(text).to_string(), text);
    }

    #[test]
    fn adaptive_objects_preserve_order_duplicate_and_cow_across_promotion() {
        for size in [1_usize, 4, 8, 9, 32] {
            let mut map = AnyMap::with_capacity(size);
            for i in 0..size {
                map.insert(format!("k{i}"), AnyValue::from(i as u64));
            }
            let original = map.clone();
            assert_eq!(
                map.insert("k0".into(), AnyValue::from(99)),
                Some(AnyValue::from(0))
            );
            assert_eq!(map.keys().next().unwrap().as_str(), "k0");
            assert_eq!(original.get("k0"), Some(&AnyValue::from(0)));
            let mut value = AnyValue::Object(map);
            *value.pointer_mut("/k0").unwrap() = AnyValue::from(100);
            value["added"] = AnyValue::Bool(true);
            assert_eq!(
                serde_json::from_str::<AnyValue>(&value.to_string()).unwrap(),
                value
            );
            assert_eq!(value.as_object().unwrap().iter().len(), size + 1);
            let mut map = value.as_object().unwrap().clone();
            map.shift_remove("k0");
            let keys: Vec<_> = map.keys().map(AnyString::as_str).collect();
            let expected: Vec<_> = (1..size)
                .map(|i| format!("k{i}"))
                .chain(["added".to_owned()])
                .collect();
            assert_eq!(keys, expected);
            map.swap_remove("added");
            map.retain(|_, value| {
                *value = AnyValue::Null;
                true
            });
            assert!(map.values().all(AnyValue::is_null));
            assert_eq!(map.into_iter().count(), size - 1);
        }
        let mut map = AnyMap::new();
        for i in 0..8 {
            map.insert(format!("k{i}"), AnyValue::Null);
        }
        assert!(matches!(&*map.entries, Entries::Small(_)));
        map.insert("k0".into(), AnyValue::Bool(true));
        assert!(matches!(&*map.entries, Entries::Small(_)));
        map.insert("ninth".into(), AnyValue::Null);
        assert!(matches!(&*map.entries, Entries::Indexed(_)));
        assert_eq!(map.keys().last().unwrap().as_str(), "ninth");
    }

    #[test]
    fn adaptive_iterators_preserve_exact_size_and_both_ends() {
        for size in [4_usize, 16] {
            let mut map = AnyMap::with_capacity(size);
            for i in 0..size {
                map.insert(format!("k{i}"), AnyValue::from(i as u64));
            }
            let mut entries = map.iter();
            assert_eq!(entries.len(), size);
            assert_eq!(entries.next().unwrap().0.as_str(), "k0");
            assert_eq!(
                entries.next_back().unwrap().0.as_str(),
                format!("k{}", size - 1)
            );
            assert_eq!(entries.len(), size - 2);
            for value in map.values_mut().rev() {
                *value = AnyValue::Null;
            }
            let mut entries = map.into_iter();
            assert_eq!(entries.next().unwrap().0.as_str(), "k0");
            assert_eq!(
                entries.next_back().unwrap().0.as_str(),
                format!("k{}", size - 1)
            );
            assert_eq!(entries.len(), size - 2);
        }
    }
}
