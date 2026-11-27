//! [`OrderedMap`]: a map that preserves insert order.
//! We considered using the
//! well known `IndexMap` crate
//! but deletions that preserve
//! order are O(n) so we
//! build a simplified version
//! of such order-preserving map
//! which can delete entries
//! in O(1) time on average
//! and preserve order
//! by retaining deleted entries
//! until they outnumber live ones.
use std::borrow::Borrow;
use std::hash::Hash;

use hashbrown::HashTable;
use hashbrown::hash_table;

use crate::map::hash::State;
use crate::types::FlowStr;

/// Map preserving insert order.
/// Deleted `Entry`s stay in `data`
/// until they outnumber non-deleted `Entry`s.
#[derive(Debug, Clone)]
pub(crate) struct OrderedMap<V, K = FlowStr> {
    /// The map's actual data
    data: Vec<Entry<V, K>>,
    /// Stores values
    /// by finding where the hashed
    /// key points to and finding the
    /// "next" available slot.
    /// The Values we store in
    /// this table are `usize` integers
    /// pointing to an index in `data`
    /// where the actual value lives.
    index: HashTable<usize>,
    /// The random state used to compute hashes.
    state: State,
}
#[derive(Debug, Clone)]
struct Entry<V, K> {
    /// The hash of the key.
    /// Used to rebuild the table
    /// after clearing garbage in
    /// [`OrderedMap::clear_garbage`]
    /// without re-computing the hashes again.
    hash: u64,
    /// The actual key
    key: K,
    /// The actual value.
    /// Set to None once deleted.
    /// Cleaned up in [`OrderedMap::clear_garbage`].
    value: Option<V>,
}

/// The hash of the entry at position `i`.
fn hash_at<V, K>(data: &[Entry<V, K>]) -> impl Fn(&usize) -> u64 {
    move |&i| data[i].hash
}

/// Whether the entry at position `i` has `key`.
fn has_key<'a, V, K: Borrow<Q>, Q: Eq + ?Sized>(
    data: &'a [Entry<V, K>],
    key: &'a Q,
) -> impl Fn(&usize) -> bool {
    move |&i| data[i].key.borrow() == key
}

impl<V, K> OrderedMap<V, K> {
    pub(super) fn new() -> Self {
        Self {
            data: Vec::new(),
            index: HashTable::new(),
            state: State::default(),
        }
    }

    /// The number of values.
    pub fn len(&self) -> usize {
        self.index.len()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
    /// Get the data held under `key`
    pub fn get<Q: Hash + Eq + ?Sized>(&self, key: &Q) -> Option<&V>
    where
        K: Borrow<Q>,
    {
        let i = self.get_index_of(key)?;
        self.data[i].value.as_ref()
    }

    /// Get a mutable reference to the data held under `key`.
    pub fn get_mut<Q: Hash + Eq + ?Sized>(&mut self, key: &Q) -> Option<&mut V>
    where
        K: Borrow<Q>,
    {
        let i = self.get_index_of(key)?;
        self.data[i].value.as_mut()
    }
    /// Whether the map contains `key`.
    pub fn contains_key<Q: Hash + Eq + ?Sized>(&self, key: &Q) -> bool
    where
        K: Borrow<Q>,
    {
        self.get_index_of(key).is_some()
    }

    /// The position of `key`.
    pub fn get_index_of<Q: Hash + Eq + ?Sized>(&self, key: &Q) -> Option<usize>
    where
        K: Borrow<Q>,
    {
        let hash = self.state.hash_one(key);
        self.index.find(hash, has_key(&self.data, key)).copied()
    }

    /// Add a key or replace its value in place.
    pub(super) fn insert(&mut self, key: K, value: V)
    where
        K: Hash + Eq,
    {
        let hash = self.state.hash_one(&key);
        let entry = self
            .index
            .entry(hash, has_key(&self.data, &key), hash_at(&self.data));
        match entry {
            hash_table::Entry::Occupied(slot) => {
                self.data[*slot.get()].value = Some(value);
            }
            hash_table::Entry::Vacant(slot) => {
                let position = self.data.len();
                self.data.push(Entry {
                    hash,
                    key,
                    value: Some(value),
                });
                slot.insert(position);
            }
        }
    }

    /// Remove `key` and leave its position empty.
    pub fn remove<Q: Hash + Eq + ?Sized>(&mut self, key: &Q) -> Option<V>
    where
        K: Borrow<Q>,
    {
        let hash = self.state.hash_one(key);
        let entry = self.index.find_entry(hash, has_key(&self.data, key)).ok()?;
        let (position, _) = entry.remove();
        self.data[position].value.take()
    }

    /// Clear deleted entries in `data`
    pub(super) fn clear_garbage(&mut self) {
        if self.data.len() - self.len() <= self.len() {
            return;
        }
        // clear the garbage
        self.data.retain(|entry| entry.value.is_some());
        // reduce allocated capacity
        // if 4x larger than current
        // number of stored items
        if self.data.capacity() > 4 * self.data.len().max(4) {
            self.data.shrink_to_fit();
        }
        self.index.clear();
        for (i, entry) in self.data.iter().enumerate() {
            self.index.insert_unique(entry.hash, i, hash_at(&self.data));
        }
    }

    /// The keys and values, in order.
    pub fn iter(&self) -> impl Iterator<Item = (&K, &V)> {
        self.data
            .iter()
            .filter_map(|entry| Some((&entry.key, entry.value.as_ref()?)))
    }

    pub(crate) fn into_entries(self) -> impl Iterator<Item = (K, V)> {
        self.data
            .into_iter()
            .filter_map(|entry| Some((entry.key, entry.value?)))
    }

    /// Remove every entry and consume the values in order.
    pub(super) fn drain(&mut self) -> impl Iterator<Item = (K, V)> {
        self.index.clear();
        self.data
            .drain(..)
            .filter_map(|entry| Some((entry.key, entry.value?)))
    }

    /// Remove every entry. Does not reduce allocated capacity.
    pub(super) fn clear(&mut self) {
        self.index.clear();
        self.data.clear();
    }

    /// The number of entries `data` can hold without
    /// re-allocating.
    pub(super) fn capacity(&self) -> usize {
        self.data.capacity()
    }

    pub(super) fn shrink_to_fit(&mut self) {
        self.data.shrink_to_fit();
        self.index.shrink_to_fit(hash_at(&self.data));
    }
}

impl<V> FromIterator<(FlowStr, V)> for OrderedMap<V> {
    fn from_iter<I: IntoIterator<Item = (FlowStr, V)>>(entries: I) -> Self {
        let mut positions = Self::new();
        for (key, value) in entries {
            positions.insert(key, value);
        }
        positions
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn compaction_keeps_small_maps_indexed_and_preserves_insertion_order() {
        let mut map = OrderedMap::new();
        map.insert(FlowStr::from("a"), 1);
        assert_eq!(map.index.len(), 1);
        map.insert(FlowStr::from("b"), 2);
        assert_eq!(map.remove("a"), Some(1));
        map.insert(FlowStr::from("a"), 3);
        assert!(map.iter().map(|(_, value)| *value).eq([2, 3]));

        assert_eq!(map.remove("b"), Some(2));
        map.clear_garbage();
        assert_eq!(map.data.len(), 1);
        assert_eq!(map.index.len(), 1);
        assert_eq!(map.get("a"), Some(&3));
    }

    #[test]
    fn ordered_map_keeps_order_as_a_python_dict_does() {
        // A plain list with shifting removal is the order a
        // Python dict keeps.
        let mut positions = OrderedMap::new();
        let mut reference: Vec<(String, usize)> = Vec::new();
        let mut seed = 0x9e37_79b9_7f4a_7c15_u64;
        for step in 0..20_000 {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            let key = format!("k{}", seed % 97);
            if seed.is_multiple_of(3) {
                let removed = positions.remove(key.as_str());
                let position = reference.iter().position(|(k, _)| *k == key);
                assert_eq!(removed, position.map(|at| reference.remove(at).1));
            } else {
                positions.insert(FlowStr::from(key.as_str()), step);
                match reference.iter_mut().find(|(k, _)| *k == key) {
                    Some(entry) => entry.1 = step,
                    None => reference.push((key, step)),
                }
            }
            if seed.is_multiple_of(5) {
                positions.clear_garbage();
            }
            assert_eq!(positions.len(), reference.len());
            assert!(
                positions.data.len() - positions.len() <= positions.len() + reference.len().max(64)
            );
        }
        let order: Vec<(String, usize)> = positions
            .iter()
            .map(|(k, v)| (k.as_str().to_owned(), *v))
            .collect();
        assert_eq!(order, reference);
        for (key, value) in &reference {
            assert_eq!(positions.get(key.as_str()), Some(value));
            assert_eq!(*positions.get(key.as_str()).unwrap(), *value);
        }
    }
}
