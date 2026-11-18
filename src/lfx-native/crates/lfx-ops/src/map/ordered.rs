//! [`OrderedMap`]: a map that preserves insert order.

use hashbrown::HashTable;
use hashbrown::hash_table::{self, OccupiedEntry};

use crate::map::hash::State;

/// Map preserving insert order.
/// Deleted entries are marked as `None`
/// and stay in `data` until they
/// outnumber non-deleted keys.
#[derive(Debug)]
pub(crate) struct OrderedMap<V> {
    /// The map's actual data
    data: Vec<Entry<V>>,
    /// This table stores values
    /// by finding where the hashed
    /// key points to and finding the
    /// 'next' available slot.
    /// The Values we store in
    /// this table are `usize` integers
    /// pointing to an index in `data`
    /// where the actual value lives.
    index: HashTable<usize>,
    /// The random state used to compute hashes.
    state: State,
}
/// key and value are the
/// caller-supplied key and value.
/// hash is the hash of the key.
/// This hash is stored
/// to avoid re-computing
/// it in [`OrderedMap::clear_garbage`]
#[derive(Debug)]
struct Entry<V> {
    /// The hash of the key.
    hash: u64,
    /// The actual key
    key: String,
    /// The actual value.
    /// Set to None once deleted.
    /// Cleaned up in [`OrderedMap::clear_garbage`].
    value: Option<V>,
}

/// The hash of the entry at position `i`.
fn hash_at<V>(data: &[Entry<V>]) -> impl Fn(&usize) -> u64 {
    move |&i| data[i].hash
}

/// Whether the entry at position `i` has `key`.
fn has_key<'a, V>(data: &'a [Entry<V>], key: &'a str) -> impl Fn(&usize) -> bool {
    move |&i| data[i].key == key
}

impl<V> OrderedMap<V> {
    pub(super) fn new() -> Self {
        Self {
            data: Vec::new(),
            index: HashTable::new(),
            state: State::default(),
        }
    }

    fn hash(&self, key: &str) -> u64 {
        self.state.hash_one(key)
    }

    /// The position of `key` in `data`.
    fn find(&self, key: &str) -> Option<usize> {
        let hash = self.hash(key);
        self.index.find(hash, has_key(&self.data, key)).copied()
    }

    /// The table entry of `key`, to remove it.
    fn find_mut(&mut self, key: &str) -> Option<OccupiedEntry<'_, usize>> {
        let hash = self.hash(key);
        self.index.find_entry(hash, has_key(&self.data, key)).ok()
    }

    /// The number of values.
    pub fn len(&self) -> usize {
        self.index.len()
    }

    pub fn is_empty(&self) -> bool {
        self.index.is_empty()
    }

    pub fn get(&self, key: &str) -> Option<&V> {
        let i = self.get_index_of(key)?;
        self.data[i].value.as_ref()
    }

    pub fn get_mut(&mut self, key: &str) -> Option<&mut V> {
        let i = self.get_index_of(key)?;
        self.data[i].value.as_mut()
    }

    pub fn contains_key(&self, key: &str) -> bool {
        self.get_index_of(key).is_some()
    }

    /// The position of `key`.
    pub fn get_index_of(&self, key: &str) -> Option<usize> {
        self.find(key)
    }

    /// Add the key value pair to the map.
    /// Replaces the value of `key` if it already exists.
    pub fn insert(&mut self, key: String, value: V) {
        let hash = self.hash(&key);
        match self
            .index
            .entry(hash, has_key(&self.data, &key), hash_at(&self.data))
        {
            hash_table::Entry::Occupied(slot) => {
                self.data[*slot.get()].value = Some(value);
            }
            hash_table::Entry::Vacant(slot) => {
                slot.insert(self.data.len());
                self.data.push(Entry {
                    hash,
                    key,
                    value: Some(value),
                });
            }
        }
    }

    /// Remove `key`, and leave its position empty.
    pub fn remove(&mut self, key: &str) -> Option<V> {
        let (i, _) = self.find_mut(key)?.remove();
        self.data[i].value.take()
    }

    /// Clear deleted entries in `data`
    pub(super) fn clear_garbage(&mut self) -> bool {
        if self.data.len() - self.index.len() <= self.index.len() {
            return false;
        }
        // clear the garbage
        self.data.retain(|entry| entry.value.is_some());
        // reduce allocated capacity if 4x larger than current number of stored items
        if self.data.capacity() > 4 * self.data.len().max(4) {
            self.data.shrink_to_fit();
        }
        // update indexes
        self.index.clear();
        self.data.iter().enumerate().for_each(|(i, e)| {
            self.index.insert_unique(e.hash, i, hash_at(&self.data));
        });

        true
    }

    /// The keys and values, in order.
    pub fn iter(&self) -> impl Iterator<Item = (&String, &V)> {
        self.data
            .iter()
            .filter_map(|entry| Some((&entry.key, entry.value.as_ref()?)))
    }

    pub fn values(&self) -> impl Iterator<Item = &V> {
        self.iter().map(|(_, value)| value)
    }

    pub(super) fn into_values(self) -> impl Iterator<Item = V> {
        self.data.into_iter().filter_map(|entry| entry.value)
    }

    /// Remove every entry and consume the values in order.
    pub(super) fn drain(&mut self) -> impl Iterator<Item = (String, V)> {
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

    /// The number of entries `data` can hold without re-allocating.
    pub(super) fn capacity(&self) -> usize {
        self.data.capacity()
    }

    pub(super) fn shrink_to_fit(&mut self) {
        self.data.shrink_to_fit();
        self.index.shrink_to_fit(hash_at(&self.data));
    }
}

impl<V> FromIterator<(String, V)> for OrderedMap<V> {
    fn from_iter<I: IntoIterator<Item = (String, V)>>(entries: I) -> Self {
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
    fn ordered_map_keeps_order_as_a_python_dict_does() {
        // A plain list with shifting removal is the order a Python dict keeps.
        let mut positions = OrderedMap::new();
        let mut reference: Vec<(String, usize)> = Vec::new();
        let mut seed = 0x9e37_79b9_7f4a_7c15_u64;
        for step in 0..20_000 {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            let key = format!("k{}", seed % 97);
            if seed.is_multiple_of(3) {
                let removed = positions.remove(&key);
                let position = reference.iter().position(|(k, _)| *k == key);
                assert_eq!(removed, position.map(|at| reference.remove(at).1));
            } else {
                positions.insert(key.clone(), step);
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
        let order: Vec<(String, usize)> = positions.iter().map(|(k, v)| (k.clone(), *v)).collect();
        assert_eq!(order, reference);
        for (key, value) in &reference {
            assert_eq!(positions.get(key), Some(value));
            assert_eq!(*positions.get(key).unwrap(), *value);
        }
    }
}
