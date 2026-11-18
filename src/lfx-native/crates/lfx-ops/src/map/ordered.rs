//! [`OrderedMap`]: a map that preserves insert order.
//!
//! Deleted keys stay in `data` and are pruned when they outnumber live keys.

use hashbrown::HashTable;
use hashbrown::hash_table::OccupiedEntry;

use crate::map::hash::State;

/// Map preserving insert order.
/// deleted keys stay in `data` and are pruned
/// when they outnumber non-deleted keys.
#[derive(Debug)]
pub(crate) struct OrderedMap<V> {
    // actual data: (key, value) pairs
    data: Vec<Entry<V>>,
    // maps the key to its index in  `data`
    index: HashTable<usize>,
    state: State,
}

#[derive(Debug)]
struct Entry<V> {
    // kept so the table never hashes the key again
    hash: u64,
    key: String,
    // None once removed
    value: Option<V>,
}

/// The hash of the entry at a position, for the table to rehash.
fn hash_at<V>(data: &[Entry<V>]) -> impl Fn(&usize) -> u64 {
    move |&i| data[i].hash
}

/// Whether the entry at a position has `key`.
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

    /// The index of `key`, whose hash is `hash`.
    fn find(&self, hash: u64, key: &str) -> Option<&usize> {
        self.index.find(hash, has_key(&self.data, key))
    }

    /// [`Self::find`], copied.
    fn find_copied(&self, hash: u64, key: &str) -> Option<usize> {
        self.find(hash, key).copied()
    }

    /// The table entry of `key`, whose hash is `hash`, to remove it.
    fn find_mut(&mut self, hash: u64, key: &str) -> Option<OccupiedEntry<'_, usize>> {
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
        self.find_copied(self.hash(key), key)
    }

    /// Replace the value of `key` in its position, or add it last.
    pub fn insert(&mut self, key: String, value: V) {
        let hash = self.hash(&key);
        if let Some(&i) = self.find(hash, &key) {
            self.data[i].value = Some(value);
            return;
        }
        self.index
            .insert_unique(hash, self.data.len(), hash_at(&self.data));
        self.data.push(Entry {
            hash,
            key,
            value: Some(value),
        });
    }

    /// Remove `key`, and leave its position empty.
    pub fn remove(&mut self, key: &str) -> Option<V> {
        let (i, _) = self.find_mut(self.hash(key), key)?.remove();
        self.data[i].value.take()
    }

    /// Prune deleted entries in `data`
    pub(super) fn prune_garbage(&mut self) -> bool {
        if self.data.len() - self.index.len() <= self.index.len() {
            return false;
        }
        // prune
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

    /// Remove every entry and return the values in order, keeping the allocations.
    pub(super) fn drain(&mut self) -> impl Iterator<Item = (String, V)> {
        self.index.clear();
        self.data
            .drain(..)
            .filter_map(|entry| Some((entry.key, entry.value?)))
    }

    /// Remove every entry, keeping the allocations.
    pub(super) fn clear(&mut self) {
        self.index.clear();
        self.data.clear();
    }

    /// The number of entries `data` holds without allocating.
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
                positions.prune_garbage();
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
