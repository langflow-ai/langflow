//! [`Layered`]: a map that a batch changes through a layer of its own.
//!
//! A batch that succeeds folds its layer into the stored map. A batch that
//! fails drops it, so nothing is undone.

use crate::data::maps::{HashMap, IndexMap};

/// The most map entries a layer keeps allocated between batches.
pub(crate) const MAX_RETAINED_BATCH_ENTRIES: usize = 256;

/// Entries by key in insertion order, as a Python `dict` keeps them.
///
/// A removal leaves a hole, so it moves no other entry. A new entry goes last.
/// [`Self::pack_if_sparse`] packs the slots when holes outnumber entries.
#[derive(Debug)]
pub(crate) struct Slots<V> {
    entries: Vec<Option<(String, V)>>,
    /// The slot of each entry.
    index: HashMap<String, usize>,
}

impl<V> Slots<V> {
    fn new() -> Self {
        Self {
            entries: Vec::new(),
            index: HashMap::default(),
        }
    }

    /// The number of entries.
    pub fn len(&self) -> usize {
        self.index.len()
    }

    /// The number of slots, holes included.
    #[cfg(test)]
    pub(crate) fn slots(&self) -> usize {
        self.entries.len()
    }

    pub fn get(&self, key: &str) -> Option<&V> {
        let slot = *self.index.get(key)?;
        self.entries[slot].as_ref().map(|(_, value)| value)
    }

    pub fn get_mut(&mut self, key: &str) -> Option<&mut V> {
        let slot = *self.index.get(key)?;
        self.entries[slot].as_mut().map(|(_, value)| value)
    }

    pub fn contains_key(&self, key: &str) -> bool {
        self.index.contains_key(key)
    }

    /// The slot of the entry with `key`.
    pub fn get_index_of(&self, key: &str) -> Option<usize> {
        self.index.get(key).copied()
    }

    /// Replace the entry with `key` in its slot, or add it last.
    pub fn insert(&mut self, key: String, value: V) {
        if let Some(&slot) = self.index.get(&key) {
            if let Some((_, stored)) = &mut self.entries[slot] {
                *stored = value;
            }
            return;
        }
        self.index.insert(key.clone(), self.entries.len());
        self.entries.push(Some((key, value)));
    }

    /// Remove the entry with `key`, leaving a hole in its slot.
    pub fn remove(&mut self, key: &str) -> Option<V> {
        let slot = self.index.remove(key)?;
        self.entries[slot].take().map(|(_, value)| value)
    }

    /// Pack the entries when holes outnumber them. Returns whether it did.
    fn pack_if_sparse(&mut self) -> bool {
        if self.entries.len() - self.index.len() <= self.index.len() {
            return false;
        }
        self.entries.retain(Option::is_some);
        if self.entries.capacity() > 4 * self.entries.len().max(4) {
            self.entries.shrink_to_fit();
        }
        for (slot, (key, _)) in self.entries.iter().flatten().enumerate() {
            *self.index.get_mut(key).expect("an entry is indexed") = slot;
        }
        true
    }

    /// The entries, in order.
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

impl<V> FromIterator<(String, V)> for Slots<V> {
    fn from_iter<I: IntoIterator<Item = (String, V)>>(entries: I) -> Self {
        let mut slots = Self::new();
        for (key, value) in entries {
            slots.insert(key, value);
        }
        slots
    }
}

/// A map that a batch changes through a layer of its own.
///
/// Reads look in the layer first. The first write to a stored entry copies it
/// into the layer. Entries keep their order ([`Slots`]).
#[derive(Debug)]
pub(crate) struct Layered<V> {
    pub(crate) stored: Slots<V>,
    /// What the batch wrote, by key. `None` is a removed stored entry.
    pub(crate) layer: IndexMap<String, Option<V>>,
}

impl<V: Clone> Layered<V> {
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

    /// The entry with `key`.
    pub fn get(&self, key: &str) -> Option<&V> {
        match self.layer.get(key) {
            Some(written) => written.as_ref(),
            None => self.stored.get(key),
        }
    }

    /// Whether there is an entry with `key`.
    pub fn contains(&self, key: &str) -> bool {
        self.get(key).is_some()
    }

    /// Whether the entry existed when the batch started.
    pub fn in_base(&self, key: &str) -> bool {
        self.stored.contains_key(key)
    }

    /// Whether the batch added, replaced or removed the entry.
    pub fn in_layer(&self, key: &str) -> bool {
        self.layer.contains_key(key)
    }

    /// The stored entry with `key`, to change in place between batches.
    pub fn stored_mut(&mut self, key: &str) -> Option<&mut V> {
        debug_assert!(self.layer.is_empty(), "write between batches only");
        self.stored.get_mut(key)
    }

    /// The entry with `key`, to change it. The first call in a batch copies a stored entry.
    pub fn get_mut(&mut self, key: &str) -> Option<&mut V> {
        if !self.layer.contains_key(key) {
            // No entry: leave the layer as it is.
            let copy = self.stored.get(key)?.clone();
            self.layer.insert(key.to_owned(), Some(copy));
        }
        self.layer.get_mut(key)?.as_mut()
    }

    /// The entry with `key`, to change it, added by `new` when there is none.
    pub fn get_or_insert_with(&mut self, key: &str, new: impl FnOnce() -> V) -> &mut V {
        if !self.contains(key) {
            self.insert(key.to_owned(), new());
        }
        self.get_mut(key)
            .expect("the entry exists or was just added")
    }

    /// Add an entry, or replace the one with the same key.
    pub fn insert(&mut self, key: String, value: V) {
        self.layer.insert(key, Some(value));
    }

    /// Remove the entry with `key`. Returns whether there was one.
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
    /// slots packed ([`Slots::pack_if_sparse`]).
    pub fn fold(&mut self) -> bool {
        self.fold_into(&mut Vec::new())
    }

    /// [`Self::fold`], and move each removed entry into `released`.
    pub fn fold_into(&mut self, released: &mut Vec<V>) -> bool {
        for (key, written) in self.layer.drain(..) {
            match written {
                Some(value) => self.stored.insert(key, value),
                None => released.extend(self.stored.remove(&key)),
            }
        }
        self.shrink_large_layer();
        self.stored.pack_if_sparse()
    }

    fn shrink_large_layer(&mut self) {
        if self.layer.capacity() > MAX_RETAINED_BATCH_ENTRIES {
            self.layer.shrink_to_fit();
        }
    }

    /// Drop the batch's changes.
    pub fn discard(&mut self) {
        self.layer.clear();
        self.shrink_large_layer();
    }

    /// The stored entries, without a staged batch's layer.
    pub(crate) fn values(&self) -> impl Iterator<Item = &V> {
        self.stored.values()
    }

    /// The entries with a staged batch's layer, in the order [`Self::fold`]
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

    /// The entries, without copying them. Only between batches.
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
        let mut layer = Layered::new();
        layer.insert("a".into(), payload);
        layer.fold();
        let capacity = layer.layer.capacity();
        assert!(capacity > 0);
        layer.remove("a");
        layer.fold();
        assert_eq!(layer.layer.capacity(), capacity);
        assert!(weak.upgrade().is_none());
        let refused = Arc::new(());
        let weak = Arc::downgrade(&refused);
        layer.insert("refused".into(), refused);
        layer.discard();
        assert!(weak.upgrade().is_none());
    }

    #[test]
    fn large_batch_maps_are_not_retained_after_success_or_rollback() {
        let mut layer = Layered::new();
        for i in 0..=MAX_RETAINED_BATCH_ENTRIES {
            layer.insert(i.to_string(), Arc::new(()));
        }
        layer.fold();
        assert_eq!(layer.layer.capacity(), 0);
        assert_eq!(layer.stored.len(), MAX_RETAINED_BATCH_ENTRIES + 1);
        for i in 0..=MAX_RETAINED_BATCH_ENTRIES {
            layer.remove(&i.to_string());
        }
        layer.fold();
        assert_eq!(layer.layer.capacity(), 0);
        assert_eq!(layer.stored.len(), 0);
        let payload = Arc::new(());
        let weak = Arc::downgrade(&payload);
        layer.insert("refused".into(), payload);
        for i in 0..=MAX_RETAINED_BATCH_ENTRIES {
            layer.insert(i.to_string(), Arc::new(()));
        }
        layer.discard();
        assert_eq!(layer.layer.capacity(), 0);
        assert!(weak.upgrade().is_none());
    }

    fn stored(keys: &[&str]) -> Layered<u32> {
        let map = keys
            .iter()
            .zip(1..)
            .map(|(key, value)| ((*key).to_owned(), value))
            .collect();
        Layered::with_stored(map)
    }

    fn keys(map: &Layered<u32>) -> Vec<&str> {
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
        map.discard();
        assert_eq!(keys(&map), ["a", "b"]);
        assert_eq!(map.get("a"), Some(&1));
        assert_eq!(map.get("c"), None);
    }

    #[test]
    fn a_folded_batch_writes_its_changes_to_the_stored_map() {
        let mut map = stored(&["a", "b", "c"]);
        map.insert("x".into(), 24);
        *map.get_mut("a").unwrap() = 10;
        map.remove("b");
        map.insert("b".into(), 20);
        map.remove("c");
        map.fold();
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
        map.fold();
        assert_eq!(keys(&map), ["a", "c", "d"]);

        let mut map = stored(&["a", "b", "c", "d", "e"]);
        map.insert("x".into(), 24);
        map.insert("y".into(), 25);
        map.insert("z".into(), 26);
        map.remove("x");
        map.remove("b");
        map.remove("d");
        map.fold();
        assert_eq!(keys(&map), ["a", "c", "e", "y", "z"]);

        // Entries near the end are removed one by one.
        let mut map = stored(&["a", "b", "c", "d", "e"]);
        map.remove("e");
        map.remove("c");
        map.fold();
        assert_eq!(keys(&map), ["a", "b", "d"]);
    }

    #[test]
    fn an_entry_added_and_removed_in_one_batch_leaves_no_trace() {
        let mut map = stored(&["a"]);
        map.insert("x".into(), 24);
        assert!(map.remove("x"));
        assert!(!map.remove("x"));
        map.fold();
        assert_eq!(keys(&map), ["a"]);
    }

    #[test]
    fn slots_keep_order_as_a_python_dict_does() {
        // A plain list with shifting removal is the order a Python dict keeps.
        let mut slots = Slots::new();
        let mut reference: Vec<(String, usize)> = Vec::new();
        let mut seed = 0x9e37_79b9_7f4a_7c15_u64;
        for step in 0..20_000 {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            let key = format!("k{}", seed % 97);
            if seed.is_multiple_of(3) {
                let removed = slots.remove(&key);
                let position = reference.iter().position(|(k, _)| *k == key);
                assert_eq!(removed, position.map(|at| reference.remove(at).1));
            } else {
                slots.insert(key.clone(), step);
                match reference.iter_mut().find(|(k, _)| *k == key) {
                    Some(entry) => entry.1 = step,
                    None => reference.push((key, step)),
                }
            }
            if seed.is_multiple_of(5) {
                slots.pack_if_sparse();
            }
            assert_eq!(slots.len(), reference.len());
            assert!(slots.slots() - slots.len() <= slots.len() + reference.len().max(64));
        }
        let order: Vec<(String, usize)> = slots.iter().map(|(k, v)| (k.clone(), *v)).collect();
        assert_eq!(order, reference);
        for (key, value) in &reference {
            assert_eq!(slots.get(key), Some(value));
            assert_eq!(*slots.get(key).unwrap(), *value);
        }
    }
}
