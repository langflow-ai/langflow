//! [`PendingMap`]: a map whose batch changes stay pending until the batch commits.
//!
//! A batch that succeeds commits its pending changes to the stored map. A batch that
//! fails drops it, so nothing is undone.

use crate::collection::hash_map::{HashMap, IndexMap};

/// The most pending changes a map keeps allocated between batches.
pub(crate) const MAX_RETAINED_BATCH_ENTRIES: usize = 256;

/// Entries by key in insertion order, as a Python `dict` keeps them.
///
/// A removal leaves its position empty, so no other value moves. A new value goes last.
/// [`Self::pack_if_sparse`] packs the map when empty positions outnumber values.
#[derive(Debug)]
pub(crate) struct OrderedMap<V> {
    entries: Vec<Option<(String, V)>>,
    /// The position of each key.
    index: HashMap<String, usize>,
}

impl<V> OrderedMap<V> {
    fn new() -> Self {
        Self {
            entries: Vec::new(),
            index: HashMap::default(),
        }
    }

    /// The number of values.
    pub fn len(&self) -> usize {
        self.index.len()
    }

    /// The number of positions, empty ones included.
    #[cfg(test)]
    pub(crate) fn positions(&self) -> usize {
        self.entries.len()
    }

    pub fn get(&self, key: &str) -> Option<&V> {
        let position = *self.index.get(key)?;
        self.entries[position].as_ref().map(|(_, value)| value)
    }

    pub fn get_mut(&mut self, key: &str) -> Option<&mut V> {
        let position = *self.index.get(key)?;
        self.entries[position].as_mut().map(|(_, value)| value)
    }

    pub fn contains_key(&self, key: &str) -> bool {
        self.index.contains_key(key)
    }

    /// The position of `key`.
    pub fn get_index_of(&self, key: &str) -> Option<usize> {
        self.index.get(key).copied()
    }

    /// Replace the value of `key` in its position, or add it last.
    pub fn insert(&mut self, key: String, value: V) {
        if let Some(&position) = self.index.get(&key) {
            if let Some((_, stored)) = &mut self.entries[position] {
                *stored = value;
            }
            return;
        }
        self.index.insert(key.clone(), self.entries.len());
        self.entries.push(Some((key, value)));
    }

    /// Remove `key`, and leave its position empty.
    pub fn remove(&mut self, key: &str) -> Option<V> {
        let position = self.index.remove(key)?;
        self.entries[position].take().map(|(_, value)| value)
    }

    /// Pack the values when empty positions outnumber them. Returns whether it did.
    fn pack_if_sparse(&mut self) -> bool {
        if self.entries.len() - self.index.len() <= self.index.len() {
            return false;
        }
        self.entries.retain(Option::is_some);
        if self.entries.capacity() > 4 * self.entries.len().max(4) {
            self.entries.shrink_to_fit();
        }
        for (position, (key, _)) in self.entries.iter().flatten().enumerate() {
            *self.index.get_mut(key).expect("an entry is indexed") = position;
        }
        true
    }

    /// The keys and values, in order.
    pub fn iter(&self) -> impl Iterator<Item = (&String, &V)> {
        self.entries
            .iter()
            .flatten()
            .map(|(key, value)| (key, value))
    }

    #[cfg(test)]
    pub fn keys(&self) -> impl Iterator<Item = &String> {
        self.iter().map(|(key, _)| key)
    }

    pub fn values(&self) -> impl Iterator<Item = &V> {
        self.iter().map(|(_, value)| value)
    }

    fn into_values(self) -> impl Iterator<Item = V> {
        self.entries.into_iter().flatten().map(|(_, value)| value)
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

/// A map whose batch changes stay pending until the batch commits.
///
/// Reads look at the pending changes first. The first write to a stored value copies it
/// into the pending changes. Values keep their order ([`OrderedMap`]).
#[derive(Debug)]
pub(crate) struct PendingMap<V> {
    pub(crate) stored: OrderedMap<V>,
    /// What the batch wrote, by key. `None` is a removed stored value.
    pub(crate) layer: IndexMap<String, Option<V>>,
}

impl<V: Clone> PendingMap<V> {
    /// An empty map.
    pub fn new() -> Self {
        Self::with_stored(IndexMap::default())
    }

    pub(crate) fn with_stored(stored: IndexMap<String, V>) -> Self {
        Self {
            stored: stored.into_iter().collect(),
            layer: IndexMap::default(),
        }
    }

    /// The value of `key`.
    pub fn get(&self, key: &str) -> Option<&V> {
        match self.layer.get(key) {
            Some(written) => written.as_ref(),
            None => self.stored.get(key),
        }
    }

    /// Whether `key` has a value.
    pub fn contains(&self, key: &str) -> bool {
        self.get(key).is_some()
    }

    /// Whether `key` had a value when the batch started.
    pub fn in_base(&self, key: &str) -> bool {
        self.stored.contains_key(key)
    }

    /// Whether the batch added, replaced or removed the value of `key`.
    pub fn is_pending(&self, key: &str) -> bool {
        self.layer.contains_key(key)
    }

    /// The stored value of `key`, to change in place between batches.
    pub fn stored_mut(&mut self, key: &str) -> Option<&mut V> {
        debug_assert!(self.layer.is_empty(), "write between batches only");
        self.stored.get_mut(key)
    }

    /// The value of `key`, to change it. The first call in a batch copies a stored value.
    pub fn get_mut(&mut self, key: &str) -> Option<&mut V> {
        if !self.layer.contains_key(key) {
            // No value: leave the pending changes as they are.
            let copy = self.stored.get(key)?.clone();
            self.layer.insert(key.to_owned(), Some(copy));
        }
        self.layer.get_mut(key)?.as_mut()
    }

    /// The value of `key`, to change it, added by `new` when there is none.
    pub fn get_or_insert_with(&mut self, key: &str, new: impl FnOnce() -> V) -> &mut V {
        if !self.contains(key) {
            self.insert(key.to_owned(), new());
        }
        self.get_mut(key)
            .expect("the entry exists or was just added")
    }

    /// Add a value, or replace the value of the same key.
    pub fn insert(&mut self, key: String, value: V) {
        self.layer.insert(key, Some(value));
    }

    /// Remove `key`. Returns whether it had a value.
    pub fn remove(&mut self, key: &str) -> bool {
        let existed = self.contains(key);
        if self.stored.contains_key(key) {
            self.layer.insert(key.to_owned(), None);
        } else {
            self.layer.shift_remove(key);
        }
        existed
    }

    /// Make the batch's changes part of the stored map. Returns whether the
    /// positions packed ([`OrderedMap::pack_if_sparse`]).
    pub fn commit(&mut self) -> bool {
        self.commit_into(&mut Vec::new())
    }

    /// [`Self::commit`], and move each removed value into `released`.
    pub fn commit_into(&mut self, released: &mut Vec<V>) -> bool {
        for (key, written) in self.layer.drain(..) {
            match written {
                Some(value) => self.stored.insert(key, value),
                None => released.extend(self.stored.remove(&key)),
            }
        }
        self.shrink_large_pending();
        self.stored.pack_if_sparse()
    }

    fn shrink_large_pending(&mut self) {
        if self.layer.capacity() > MAX_RETAINED_BATCH_ENTRIES {
            self.layer.shrink_to_fit();
        }
    }

    /// Drop the batch's changes.
    pub fn drop_pending(&mut self) {
        self.layer.clear();
        self.shrink_large_pending();
    }

    /// The stored values, without a staged batch's pending changes.
    pub(crate) fn values(&self) -> impl Iterator<Item = &V> {
        self.stored.values()
    }

    /// The keys and values with a staged batch's pending changes, in the order [`Self::commit`]
    /// gives them.
    pub(crate) fn staged_entries(&self) -> impl Iterator<Item = (&String, &V)> {
        let kept = self
            .stored
            .iter()
            .filter_map(|(key, value)| match self.layer.get(key) {
                Some(written) => written.as_ref().map(|written| (key, written)),
                None => Some((key, value)),
            });
        let added = self
            .layer
            .iter()
            .filter(|(key, _)| !self.stored.contains_key(key))
            .filter_map(|(key, written)| written.as_ref().map(|value| (key, value)));
        kept.chain(added)
    }

    /// The values, without copying them. Only between batches.
    pub(crate) fn into_values(self) -> impl Iterator<Item = V> {
        debug_assert!(self.layer.is_empty(), "read between batches only");
        self.stored.into_values()
    }
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use super::*;

    #[test]
    fn retained_batch_maps_release_removed_and_refused_payloads() {
        let payload = Arc::new(());
        let weak = Arc::downgrade(&payload);
        let mut layer = PendingMap::new();
        layer.insert("a".into(), payload);
        layer.commit();
        let capacity = layer.layer.capacity();
        assert!(capacity > 0);
        layer.remove("a");
        layer.commit();
        assert_eq!(layer.layer.capacity(), capacity);
        assert!(weak.upgrade().is_none());
        let refused = Arc::new(());
        let weak = Arc::downgrade(&refused);
        layer.insert("refused".into(), refused);
        layer.drop_pending();
        assert!(weak.upgrade().is_none());
    }

    #[test]
    fn large_batch_maps_are_not_retained_after_success_or_rollback() {
        let mut layer = PendingMap::new();
        for i in 0..=MAX_RETAINED_BATCH_ENTRIES {
            layer.insert(i.to_string(), Arc::new(()));
        }
        layer.commit();
        assert_eq!(layer.layer.capacity(), 0);
        assert_eq!(layer.stored.len(), MAX_RETAINED_BATCH_ENTRIES + 1);
        for i in 0..=MAX_RETAINED_BATCH_ENTRIES {
            layer.remove(&i.to_string());
        }
        layer.commit();
        assert_eq!(layer.layer.capacity(), 0);
        assert_eq!(layer.stored.len(), 0);
        let payload = Arc::new(());
        let weak = Arc::downgrade(&payload);
        layer.insert("refused".into(), payload);
        for i in 0..=MAX_RETAINED_BATCH_ENTRIES {
            layer.insert(i.to_string(), Arc::new(()));
        }
        layer.drop_pending();
        assert_eq!(layer.layer.capacity(), 0);
        assert!(weak.upgrade().is_none());
    }

    fn stored(keys: &[&str]) -> PendingMap<u32> {
        let map = keys
            .iter()
            .zip(1..)
            .map(|(key, value)| ((*key).to_owned(), value))
            .collect();
        PendingMap::with_stored(map)
    }

    fn keys(map: &PendingMap<u32>) -> Vec<&str> {
        map.stored.keys().map(String::as_str).collect()
    }

    #[test]
    fn a_batch_reads_its_own_writes_and_leaves_the_stored_map_alone() {
        let mut map = stored(&["a", "b"]);
        *map.get_mut("a").unwrap() = 10;
        map.remove("b");
        map.insert("c".into(), 3);
        assert_eq!(map.get("a"), Some(&10));
        assert_eq!(map.get("b"), None);
        assert_eq!(map.get("c"), Some(&3));
        assert_eq!(map.stored.get("a"), Some(&1));
        assert!(map.in_base("b") && !map.in_base("c"));
    }

    #[test]
    fn a_dropped_batch_leaves_nothing_behind() {
        let mut map = stored(&["a", "b"]);
        *map.get_mut("a").unwrap() = 10;
        map.remove("b");
        map.insert("c".into(), 3);
        map.drop_pending();
        assert_eq!(keys(&map), ["a", "b"]);
        assert_eq!(map.get("a"), Some(&1));
        assert_eq!(map.get("c"), None);
    }

    #[test]
    fn a_committed_batch_writes_its_changes_to_the_stored_map() {
        let mut map = stored(&["a", "b", "c"]);
        map.insert("x".into(), 24);
        *map.get_mut("a").unwrap() = 10;
        map.remove("b");
        map.insert("b".into(), 20);
        map.remove("c");
        map.commit();
        let entries: Vec<_> = map
            .stored
            .iter()
            .map(|(key, value)| (key.as_str(), *value))
            .collect();
        assert_eq!(entries, [("a", 10), ("b", 20), ("x", 24)]);
    }

    #[test]
    fn removals_keep_the_order_of_the_other_entries() {
        let mut map = stored(&["a", "b", "c", "d"]);
        map.remove("b");
        map.commit();
        assert_eq!(keys(&map), ["a", "c", "d"]);

        let mut map = stored(&["a", "b", "c", "d", "e"]);
        map.insert("x".into(), 24);
        map.insert("y".into(), 25);
        map.insert("z".into(), 26);
        map.remove("x");
        map.remove("b");
        map.remove("d");
        map.commit();
        assert_eq!(keys(&map), ["a", "c", "e", "y", "z"]);

        // Entries near the end are removed one by one.
        let mut map = stored(&["a", "b", "c", "d", "e"]);
        map.remove("e");
        map.remove("c");
        map.commit();
        assert_eq!(keys(&map), ["a", "b", "d"]);
    }

    #[test]
    fn an_entry_added_and_removed_in_one_batch_leaves_no_trace() {
        let mut map = stored(&["a"]);
        map.insert("x".into(), 24);
        assert!(map.remove("x"));
        assert!(!map.remove("x"));
        map.commit();
        assert_eq!(keys(&map), ["a"]);
    }

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
                positions.pack_if_sparse();
            }
            assert_eq!(positions.len(), reference.len());
            assert!(
                positions.positions() - positions.len()
                    <= positions.len() + reference.len().max(64)
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
