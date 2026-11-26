//! [`OrderedMap`]: a map that preserves insert order.

use std::borrow::Borrow;
use std::hash::Hash;

use hashbrown::HashTable;
use hashbrown::hash_table;

use crate::map::hash::State;
use crate::types::FlowStr;

// Small maps use a dense list and defer hashing until they
// grow.
const LINEAR_LIMIT: usize = 2;

/// Map preserving insert order.
/// Indexed maps mark deleted entries as `None`.
/// They stay in `data` until they
/// outnumber non-deleted keys.
#[derive(Debug, Clone)]
pub(crate) struct OrderedMap<V, K = FlowStr> {
    /// The map's actual data
    data: Vec<Entry<V, K>>,
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
#[derive(Debug, Clone)]
struct Entry<V, K> {
    /// The cached hash of the key once the map is indexed.
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
        if self.data.len() <= LINEAR_LIMIT {
            self.data.len()
        } else {
            self.index.len()
        }
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    pub fn get<Q: Hash + Eq + ?Sized>(&self, key: &Q) -> Option<&V>
    where
        K: Borrow<Q>,
    {
        let i = self.get_index_of(key)?;
        self.data[i].value.as_ref()
    }

    pub fn get_mut<Q: Hash + Eq + ?Sized>(&mut self, key: &Q) -> Option<&mut V>
    where
        K: Borrow<Q>,
    {
        let i = self.get_index_of(key)?;
        self.data[i].value.as_mut()
    }

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
        if self.data.len() <= LINEAR_LIMIT {
            return self.data.iter().position(|entry| entry.key.borrow() == key);
        }

        let hash = self.state.hash_one(key);
        self.index.find(hash, has_key(&self.data, key)).copied()
    }

    /// Locate the value's slot, appending the key if needed.
    fn slot<I, Q: Hash + Eq + ?Sized>(
        &mut self,
        key: I,
        borrowed: impl FnOnce(&I) -> &Q,
        owned: impl FnOnce(I) -> K,
    ) -> &mut Option<V>
    where
        K: Borrow<Q> + Hash,
    {
        let key_ref = borrowed(&key);
        // Most path branches are small enough to keep as a
        // dense list.
        if self.data.len() <= LINEAR_LIMIT {
            if let Some(position) = self.get_index_of(key_ref) {
                return &mut self.data[position].value;
            }
            let position = self.data.len();
            let entry = Entry {
                hash: 0,
                key: owned(key),
                value: None,
            };
            if position == 0 {
                self.data.reserve_exact(1);
            }
            self.data.push(entry);
            if position == LINEAR_LIMIT {
                for entry in &mut self.data {
                    entry.hash = self.state.hash_one(&entry.key);
                }
                self.reindex();
            }
            return &mut self.data[position].value;
        }
        let hash = self.state.hash_one(key_ref);
        let entry = self
            .index
            .entry(hash, has_key(&self.data, key_ref), hash_at(&self.data));
        match entry {
            hash_table::Entry::Occupied(slot) => &mut self.data[*slot.get()].value,
            hash_table::Entry::Vacant(slot) => {
                let position = self.data.len();
                self.data.push(Entry {
                    hash,
                    key: owned(key),
                    value: None,
                });
                slot.insert(position);
                &mut self.data[position].value
            }
        }
    }

    pub(super) fn get_or_insert_default(&mut self, key: &K) -> &mut V
    where
        K: Clone + Eq + Hash,
        V: Default,
    {
        self.slot(key, |key| *key, K::clone)
            .get_or_insert_with(V::default)
    }

    /// Remove `key`. Indexed maps leave its position empty.
    pub fn remove<Q: Hash + Eq + ?Sized>(&mut self, key: &Q) -> Option<V>
    where
        K: Borrow<Q>,
    {
        if self.data.len() <= LINEAR_LIMIT {
            let position = self.get_index_of(key)?;
            return self.data.remove(position).value;
        }
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
        // reduce allocated capacity if 4x larger than current
        // number of stored items
        if self.data.capacity() > 4 * self.data.len().max(4) {
            self.data.shrink_to_fit();
        }
        self.reindex();
    }

    fn reindex(&mut self) {
        self.index.clear();
        if self.data.len() > LINEAR_LIMIT {
            for (i, entry) in self.data.iter().enumerate() {
                self.index.insert_unique(entry.hash, i, hash_at(&self.data));
            }
        }
    }

    /// The keys and values, in order.
    pub fn iter(&self) -> impl Iterator<Item = (&K, &V)> {
        self.data
            .iter()
            .filter_map(|entry| Some((&entry.key, entry.value.as_ref()?)))
    }

    pub(super) fn into_entries(self) -> impl Iterator<Item = (K, V)> {
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

impl<V> OrderedMap<V> {
    /// Add or replace a string-keyed value, taking ownership of
    /// an owned key.
    pub fn insert<K: AsRef<str> + Into<FlowStr>>(&mut self, key: K, value: V) {
        *self.slot(key, K::as_ref, K::into) = Some(value);
    }

    pub(super) fn get_or_insert_with(&mut self, key: &str, value: impl FnOnce() -> V) -> &mut V {
        self.slot(key, |key| *key, FlowStr::from)
            .get_or_insert_with(value)
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
    fn promotion_and_compaction_preserve_insertion_order() {
        let mut map = OrderedMap::new();
        for i in 0..LINEAR_LIMIT {
            map.insert(i.to_string(), i);
        }
        assert!(map.index.is_empty());
        assert_eq!(map.remove("0"), Some(0));
        map.insert("0", 0);
        map.insert("extra", LINEAR_LIMIT);
        assert_eq!(map.index.len(), LINEAR_LIMIT + 1);
        let order = map.iter().map(|(_, value)| *value).collect::<Vec<_>>();
        assert_eq!(
            order,
            (1..LINEAR_LIMIT)
                .chain([0, LINEAR_LIMIT])
                .collect::<Vec<_>>()
        );

        for i in 1..LINEAR_LIMIT {
            assert_eq!(map.remove(i.to_string().as_str()), Some(i));
        }
        assert_eq!(map.remove("extra"), Some(LINEAR_LIMIT));
        map.clear_garbage();
        assert!(map.index.is_empty());
        assert_eq!(map.get("0"), Some(&0));
        for i in 1..=LINEAR_LIMIT {
            map.insert(i.to_string(), i);
        }
        assert_eq!(map.index.len(), LINEAR_LIMIT + 1);
        assert_eq!(map.get("0"), Some(&0));
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
                positions.insert(key.as_str(), step);
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
