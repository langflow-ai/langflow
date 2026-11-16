//! [`AnyMap`]: a JSON object in insertion order. Copies share it until a write.

use crate::data::maps::{IndexMap, State};
use std::ops::Index;
use std::sync::Arc;

use crate::data::value::{AnyString, AnyValue};

/// The most keys of a small object. A larger object uses a hash map.
const SMALL_OBJECT_KEYS: usize = 32;
pub(super) type Row = (AnyString, AnyValue);
/// The key-value entries of an object, in insertion order.
#[derive(Debug, Clone)]
pub(super) enum Entries {
    /// At most [`SMALL_OBJECT_KEYS`] entries, in one allocation.
    Small(Arc<[Row]>),
    Indexed(Arc<IndexMap<AnyString, AnyValue>>),
}
impl Default for Entries {
    fn default() -> Self {
        Self::Small(Arc::from(Vec::new()))
    }
}

/// The rows of a small object: moved when unshared, copied otherwise.
fn take_rows(rows: &mut Arc<[Row]>) -> Vec<Row> {
    match Arc::get_mut(rows) {
        Some(owned) => owned.iter_mut().map(std::mem::take).collect(),
        None => rows.to_vec(),
    }
}

/// Whether `rows` fit a small object: few enough, and no key repeated.
pub(super) fn small_and_unique(rows: &[Row]) -> bool {
    rows.len() <= SMALL_OBJECT_KEYS
        && rows.iter().enumerate().all(|(i, (key, _))| {
            rows[..i]
                .iter()
                .all(|(other, _)| other.as_str() != key.as_str())
        })
}

/// Entries without a repeated key, as an object holds them.
pub(super) fn entries_of(mut rows: Vec<Row>) -> Entries {
    if small_and_unique(&rows) {
        return Entries::Small(Arc::from(rows));
    }
    // A repeated key keeps its first position and its last value.
    let mut map = AnyMap::with_capacity(rows.len());
    for (key, value) in rows.drain(..) {
        map.insert_shared(key, value);
    }
    map.entries
}

impl Entries {
    fn ptr(&self) -> usize {
        match self {
            Self::Small(v) => Arc::as_ptr(v).cast::<()>() as usize,
            Self::Indexed(v) => Arc::as_ptr(v).cast::<()>() as usize,
        }
    }
}

/// An object whose entries keep insertion order.
///
/// A clone shares the entries. A write copies only the objects on its path.
/// The object is one pointer wide, so an [`AnyValue`] fits in a string's room.
#[derive(Debug, Clone, Default)]
pub struct AnyMap {
    pub(super) entries: Entries,
}

/// Two objects are equal when they hold equal entries in the same order.
impl PartialEq for AnyMap {
    fn eq(&self, other: &Self) -> bool {
        (self.entries.ptr() == other.entries.ptr() && self.len() == other.len())
            || (self.len() == other.len() && self.iter().eq(other.iter()))
    }
}

impl AnyMap {
    /// The address of the shared entries: equal for two copies that share them.
    #[must_use]
    pub fn entries_ptr(&self) -> usize {
        self.entries.ptr()
    }

    /// An empty object.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// An empty object with room for `capacity` entries.
    #[must_use]
    pub fn with_capacity(capacity: usize) -> Self {
        let entries = if capacity <= SMALL_OBJECT_KEYS {
            Entries::default()
        } else {
            Entries::Indexed(Arc::new(IndexMap::with_capacity_and_hasher(
                capacity,
                State::default(),
            )))
        };
        Self { entries }
    }

    /// Consume this object. Return its entries when it is their only owner,
    /// so a caller can drop them on a worker. Otherwise return `None`.
    #[must_use]
    pub fn into_unshared_entries(self) -> Option<impl Send + 'static> {
        let mut entries = self.entries;
        let unique = match &mut entries {
            Entries::Small(v) => Arc::get_mut(v).is_some(),
            Entries::Indexed(v) => Arc::get_mut(v).is_some(),
        };
        unique.then_some(entries)
    }

    /// An object of these entries. A repeated key keeps its first position
    /// and its last value.
    #[must_use]
    pub fn from_entries(rows: Vec<(AnyString, AnyValue)>) -> Self {
        Self {
            entries: entries_of(rows),
        }
    }

    /// The number of entries.
    #[must_use]
    pub fn len(&self) -> usize {
        match &self.entries {
            Entries::Small(v) => v.len(),
            Entries::Indexed(v) => v.len(),
        }
    }

    /// Whether the object has no entries.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// The value at `key`.
    #[must_use]
    pub fn get(&self, key: &str) -> Option<&AnyValue> {
        match &self.entries {
            Entries::Small(v) => v.iter().find(|(k, _)| k.as_str() == key).map(|(_, v)| v),
            Entries::Indexed(v) => v.get(key),
        }
    }

    /// The value at `key`, to change it.
    pub fn get_mut(&mut self, key: &str) -> Option<&mut AnyValue> {
        match &mut self.entries {
            Entries::Small(v) => {
                let slot = v.iter().position(|(k, _)| k.as_str() == key)?;
                Some(&mut Arc::make_mut(v)[slot].1)
            }
            Entries::Indexed(v) => Arc::make_mut(v).get_mut(key),
        }
    }

    /// Whether the object has `key`.
    #[must_use]
    pub fn contains_key(&self, key: &str) -> bool {
        self.get(key).is_some()
    }

    /// Insert or replace. A replaced key keeps its place. A new key goes last.
    pub fn insert(&mut self, key: String, value: AnyValue) -> Option<AnyValue> {
        self.insert_shared(key.into(), value)
    }

    /// Insert a key whose text can be shared with other objects.
    pub fn insert_shared(&mut self, key: AnyString, value: AnyValue) -> Option<AnyValue> {
        let v = match &mut self.entries {
            Entries::Small(v) => v,
            Entries::Indexed(v) => return Arc::make_mut(v).insert(key, value),
        };
        if let Some(slot) = v.iter().position(|(k, _)| k.as_str() == key.as_str()) {
            return Some(std::mem::replace(&mut Arc::make_mut(v)[slot].1, value));
        }
        let mut rows = take_rows(v);
        if rows.len() < SMALL_OBJECT_KEYS {
            rows.push((key, value));
            *v = Arc::from(rows);
            return None;
        }
        let mut map = IndexMap::with_capacity_and_hasher(SMALL_OBJECT_KEYS * 2, State::default());
        map.extend(rows);
        let old = map.insert(key, value);
        self.entries = Entries::Indexed(Arc::new(map));
        old
    }

    /// Remove a key, keeping the order of the others.
    pub fn remove(&mut self, key: &str) -> Option<AnyValue> {
        self.shift_remove(key)
    }

    /// Remove a key, keeping the order of the others.
    pub fn shift_remove(&mut self, key: &str) -> Option<AnyValue> {
        match &mut self.entries {
            Entries::Small(v) => {
                let slot = v.iter().position(|(k, _)| k.as_str() == key)?;
                let mut rows = take_rows(v);
                let removed = rows.remove(slot).1;
                *v = Arc::from(rows);
                Some(removed)
            }
            Entries::Indexed(v) => Arc::make_mut(v).shift_remove(key),
        }
    }

    /// The value at `key`, added as `null` when it is missing.
    pub(super) fn entry_or_null(&mut self, key: &str) -> &mut AnyValue {
        let slot = match &self.entries {
            Entries::Small(v) => v.iter().position(|(k, _)| k.as_str() == key),
            Entries::Indexed(v) => v.get_index_of(key),
        };
        let slot = slot.unwrap_or_else(|| {
            self.insert_shared(key.into(), AnyValue::Null);
            self.len() - 1
        });
        match &mut self.entries {
            Entries::Small(v) => &mut Arc::make_mut(v)[slot].1,
            Entries::Indexed(v) => &mut Arc::make_mut(v)[slot],
        }
    }

    /// The entries, in order.
    #[must_use]
    pub fn iter(&self) -> Iter<'_> {
        Iter(match &self.entries {
            Entries::Small(v) => EntryIter::Small(v.iter()),
            Entries::Indexed(v) => EntryIter::Indexed(v.iter()),
        })
    }

    /// The entries, in order, to change the values.
    pub fn iter_mut(&mut self) -> IterMut<'_> {
        IterMut(match &mut self.entries {
            Entries::Small(v) => EntryIter::Small(Arc::make_mut(v).iter_mut()),
            Entries::Indexed(v) => EntryIter::Indexed(Arc::make_mut(v).iter_mut()),
        })
    }

    /// The keys, in order.
    pub fn keys(&self) -> impl DoubleEndedIterator<Item = &AnyString> + ExactSizeIterator {
        self.iter().map(|(key, _)| key)
    }

    /// The values, in order.
    pub fn values(&self) -> impl DoubleEndedIterator<Item = &AnyValue> + ExactSizeIterator {
        self.iter().map(|(_, value)| value)
    }
}

/// The iterator of a small object's rows, or of a large object's map.
#[derive(Debug, Clone)]
enum EntryIter<S, I> {
    Small(S),
    Indexed(I),
}

/// An iterator over an object's entries, in insertion order. `$row` turns a
/// small object's row into the item.
macro_rules! entries_iter {
    ($(#[$attr:meta])* $name:ident$(<$l:lifetime>)?($small:ty, $indexed:ty) -> $item:ty, $row:expr) => {
        $(#[$attr])*
        #[derive(Debug)]
        pub struct $name$(<$l>)?(EntryIter<$small, $indexed>);

        impl$(<$l>)? Iterator for $name$(<$l>)? {
            type Item = $item;
            fn next(&mut self) -> Option<$item> {
                match &mut self.0 {
                    EntryIter::Small(v) => v.next().map($row),
                    EntryIter::Indexed(v) => v.next(),
                }
            }
            fn size_hint(&self) -> (usize, Option<usize>) {
                match &self.0 {
                    EntryIter::Small(v) => v.size_hint(),
                    EntryIter::Indexed(v) => v.size_hint(),
                }
            }
        }

        impl$(<$l>)? DoubleEndedIterator for $name$(<$l>)? {
            fn next_back(&mut self) -> Option<$item> {
                match &mut self.0 {
                    EntryIter::Small(v) => v.next_back().map($row),
                    EntryIter::Indexed(v) => v.next_back(),
                }
            }
        }

        impl$(<$l>)? ExactSizeIterator for $name$(<$l>)? {}
    };
}

entries_iter!(
    /// Borrowed entries.
    #[derive(Clone)]
    Iter<'m>(std::slice::Iter<'m, Row>, indexmap::map::Iter<'m, AnyString, AnyValue>)
        -> (&'m AnyString, &'m AnyValue),
    |(key, value)| (key, value)
);

entries_iter!(
    /// Borrowed entries with values to change.
    IterMut<'m>(std::slice::IterMut<'m, Row>, indexmap::map::IterMut<'m, AnyString, AnyValue>)
        -> (&'m AnyString, &'m mut AnyValue),
    |row| (&row.0, &mut row.1)
);

entries_iter!(
    /// Owned entries.
    IntoIter(std::vec::IntoIter<Row>, indexmap::map::IntoIter<AnyString, AnyValue>) -> Row,
    std::convert::identity
);

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

impl IntoIterator for AnyMap {
    type Item = Row;
    type IntoIter = IntoIter;
    fn into_iter(self) -> IntoIter {
        IntoIter(match self.entries {
            Entries::Small(mut v) => EntryIter::Small(take_rows(&mut v).into_iter()),
            Entries::Indexed(v) => EntryIter::Indexed(Arc::unwrap_or_clone(v).into_iter()),
        })
    }
}

impl<K: Into<AnyString>> FromIterator<(K, AnyValue)> for AnyMap {
    fn from_iter<T: IntoIterator<Item = (K, AnyValue)>>(entries: T) -> Self {
        Self::from_entries(
            entries
                .into_iter()
                .map(|(key, value)| (key.into(), value))
                .collect(),
        )
    }
}

/// `map[key]`: panics when the key is missing.
impl Index<&str> for AnyMap {
    type Output = AnyValue;
    fn index(&self, key: &str) -> &AnyValue {
        self.get(key).expect("no entry found for key")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(text: &str) -> AnyValue {
        serde_json::from_str(text).unwrap()
    }

    /// A weak reference to a small object's entries.
    fn weak(map: &AnyMap) -> std::sync::Weak<[Row]> {
        match &map.entries {
            Entries::Small(v) => Arc::downgrade(v),
            Entries::Indexed(_) => panic!("small object"),
        }
    }

    #[test]
    fn consuming_shared_maps_never_destroys_their_payload() {
        let child = AnyMap::new();
        let weak = weak(&child);
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
    fn concurrent_last_map_owners_take_at_most_one_payload() {
        let child = AnyMap::new();
        let weak = weak(&child);
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
        assert!(payloads.iter().flatten().count() <= 1);
        drop(payloads);
        assert!(weak.upgrade().is_none());
    }

    #[test]
    fn objects_keep_their_order_and_take_the_last_repeated_value() {
        let value = parse(r#"{"b": 1, "a": 2, "b": 3}"#);
        assert_eq!(value.to_string(), r#"{"b":3,"a":2}"#);
    }

    #[test]
    fn remove_keeps_the_order() {
        let mut map: AnyMap = parse(r#"{"a": 1, "b": 2, "c": 3}"#)
            .as_object()
            .unwrap()
            .clone();
        let mut shifted = map.clone();
        map.remove("a");
        shifted.shift_remove("a");

        assert_eq!(AnyValue::Object(map).to_string(), r#"{"b":2,"c":3}"#);
        assert_eq!(AnyValue::Object(shifted).to_string(), r#"{"b":2,"c":3}"#);
    }

    #[test]
    fn objects_are_equal_only_with_their_entries_in_the_same_order() {
        assert_eq!(parse(r#"{"a": 1, "b": 2}"#), parse(r#"{"a": 1, "b": 2}"#));
        assert_ne!(parse(r#"{"a": 1, "b": 2}"#), parse(r#"{"b": 2, "a": 1}"#));
    }

    #[test]
    fn adaptive_objects_preserve_order_duplicate_and_cow_across_promotion() {
        for size in [1_usize, 4, 8, 9, 32, 33, 40] {
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
            value["k0"] = AnyValue::from(100);
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
            map.shift_remove("added");
            for (_, value) in &mut map {
                *value = AnyValue::Null;
            }
            assert!(map.values().all(AnyValue::is_null));
            assert_eq!(map.into_iter().count(), size - 1);
        }
        let mut map = AnyMap::new();
        for i in 0..SMALL_OBJECT_KEYS {
            map.insert(format!("k{i}"), AnyValue::Null);
        }
        assert!(matches!(&map.entries, Entries::Small(_)));
        map.insert("k0".into(), AnyValue::Bool(true));
        assert!(matches!(&map.entries, Entries::Small(_)));
        map.insert("one more".into(), AnyValue::Null);
        assert!(matches!(&map.entries, Entries::Indexed(_)));
        assert_eq!(map.keys().last().unwrap().as_str(), "one more");
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
            for (_, value) in map.iter_mut().rev() {
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
