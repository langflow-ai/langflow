//! [`PendingMap`]: a map whose batch changes stay pending until the batch commits.
//!
//! A batch that succeeds commits its pending changes to the stored map. A batch that
//! fails drops it, so nothing is undone.

use super::ordered_map::OrderedMap;
use crate::collection::hash_map::IndexMap;

/// The most pending changes a map keeps allocated between batches.
pub(crate) const MAX_RETAINED_BATCH_ENTRIES: usize = 256;

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

    /// Make the batch's changes part of the stored map. Returns whether empty
    /// positions were pruned ([`OrderedMap::clear_garbage`]).
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
        self.stored.prune()
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
}
