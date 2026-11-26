//! [`PendingMap`]:

use super::ordered::OrderedMap;
use crate::types::FlowStr;

/// The most pending changes a map keeps allocated between
/// batches.
pub(crate) const MAX_RETAINED_BATCH_ENTRIES: usize = 256;

/// A map that stages every
/// write to its stored values.
/// Such writes are "pending".
/// Every read to a key
/// first looks up its pending
/// write, and falls back to
/// its original "base" value
/// if there isn't one.
#[derive(Debug)]
pub(crate) struct PendingMap<V> {
    /// original base values
    base: OrderedMap<V>,
    /// pending writes
    pending: OrderedMap<Write<V>>,
}

/// A pending write to a key.
#[derive(Debug)]
enum Write<V> {
    /// The key was created,
    /// or its value was updated.
    Set(V),
    /// The key was removed.
    Delete,
}

impl<V> Write<V> {
    fn get(&self) -> Option<&V> {
        match self {
            Self::Set(value) => Some(value),
            Self::Delete => None,
        }
    }

    fn get_mut(&mut self) -> Option<&mut V> {
        match self {
            Self::Set(value) => Some(value),
            Self::Delete => None,
        }
    }
}

impl<V: Clone> PendingMap<V> {
    pub fn new() -> Self {
        Self {
            base: OrderedMap::new(),
            pending: OrderedMap::new(),
        }
    }

    /// The staged value, or the base value if the batch has no
    /// write for the key. Returns `None` when the batch deletes
    /// the key or neither map has it.
    pub fn get(&self, key: &str) -> Option<&V> {
        match self.pending.get(key) {
            Some(write) => write.get(),
            None => self.base.get(key),
        }
    }

    /// Whether `self` contains `key`
    pub fn contains(&self, key: &str) -> bool {
        self.get(key).is_some()
    }

    /// Set the value of `key` through
    /// the `writer` function.
    /// Returns `None` of `key` is not found.
    pub fn update<R>(&mut self, key: &str, writer: impl FnOnce(&mut V) -> R) -> Option<R> {
        if !self.pending.contains_key(key) {
            let copy = self.base.get(key)?.clone();
            self.pending.insert(key, Write::Set(copy));
        }
        // if the second get_mut returns None
        // it means the key was deleted.
        // so the map does not run `writer`,
        // which is intended since
        // we want to return None if not found.
        self.pending.get_mut(key)?.get_mut().map(writer)
    }
    /// [`Self::update`] only if
    /// `cond` holds for the value of `key`.
    /// Returns whether `f` ran.
    pub fn update_if(
        &mut self,
        key: &str,
        cond: impl FnOnce(&V) -> bool,
        writer: impl FnOnce(&mut V),
    ) -> bool {
        self.get(key).is_some_and(cond) && self.update(key, writer).is_some()
    }

    /// Add the value from `new` if `key` has none.
    pub fn get_or_insert_with(&mut self, key: &str, new: impl FnOnce() -> V) {
        if !self.contains(key) {
            self.insert(key, new());
        }
    }

    /// Add a value, or replace the value of the same key.
    pub fn insert<K: AsRef<str> + Into<FlowStr>>(&mut self, key: K, value: V) {
        self.pending.insert(key, Write::Set(value));
    }

    /// Remove `key`. Returns whether it had a value.
    pub fn remove(&mut self, key: &str) -> bool {
        let existed = self.contains(key);
        if self.base.contains_key(key) {
            self.pending.insert(key, Write::Delete);
        } else {
            self.pending.remove(key);
        }
        existed
    }

    /// Make the batch's changes part of the base map.
    pub fn commit(&mut self) {
        for (key, written) in self.pending.drain() {
            match written {
                Write::Set(value) => self.base.insert(key, value),
                Write::Delete => {
                    self.base.remove(&key);
                }
            }
        }
        self.shrink_large_pending();
        self.base.clear_garbage();
    }

    fn shrink_large_pending(&mut self) {
        if self.pending.capacity() > MAX_RETAINED_BATCH_ENTRIES {
            self.pending.shrink_to_fit();
        }
    }

    /// Drop the batch's changes.
    pub fn drop_pending(&mut self) {
        self.pending.clear();
        self.shrink_large_pending();
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
        layer.insert("a", payload);
        layer.commit();
        let capacity = layer.pending.capacity();
        assert!(capacity > 0);
        layer.remove("a");
        layer.commit();
        assert_eq!(layer.pending.capacity(), capacity);
        assert!(weak.upgrade().is_none());
        let refused = Arc::new(());
        let weak = Arc::downgrade(&refused);
        layer.insert("refused", refused);
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
        assert_eq!(layer.pending.capacity(), 0);
        assert_eq!(layer.base.len(), MAX_RETAINED_BATCH_ENTRIES + 1);
        for i in 0..=MAX_RETAINED_BATCH_ENTRIES {
            layer.remove(&i.to_string());
        }
        layer.commit();
        assert_eq!(layer.pending.capacity(), 0);
        assert_eq!(layer.base.len(), 0);
        let payload = Arc::new(());
        let weak = Arc::downgrade(&payload);
        layer.insert("refused", payload);
        for i in 0..=MAX_RETAINED_BATCH_ENTRIES {
            layer.insert(i.to_string(), Arc::new(()));
        }
        layer.drop_pending();
        assert_eq!(layer.pending.capacity(), 0);
        assert!(weak.upgrade().is_none());
    }

    fn base(keys: &[&str]) -> PendingMap<u32> {
        let mut map = PendingMap::new();
        for (&key, value) in keys.iter().zip(1..) {
            map.insert(key, value);
        }
        map.commit();
        map
    }

    fn keys(map: &PendingMap<u32>) -> Vec<&str> {
        map.base.iter().map(|(key, _)| key.as_str()).collect()
    }

    #[test]
    fn a_batch_reads_its_own_writes_and_leaves_the_base_map_alone() {
        let mut map = base(&["a", "b"]);
        map.update("a", |value| *value = 10).unwrap();
        map.remove("b");
        map.insert("c", 3);
        assert_eq!(map.get("a"), Some(&10));
        assert_eq!(map.get("b"), None);
        assert_eq!(map.get("c"), Some(&3));
        assert_eq!(map.base.get("a"), Some(&1));
        assert!(map.base.contains_key("b") && !map.base.contains_key("c"));
    }

    #[test]
    fn a_dropped_batch_leaves_nothing_behind() {
        let mut map = base(&["a", "b"]);
        map.update("a", |value| *value = 10).unwrap();
        map.remove("b");
        map.insert("c", 3);
        map.drop_pending();
        assert_eq!(keys(&map), ["a", "b"]);
        assert_eq!(map.get("a"), Some(&1));
        assert_eq!(map.get("c"), None);
    }

    #[test]
    fn a_committed_batch_writes_its_changes_to_the_base_map() {
        let mut map = base(&["a", "b", "c"]);
        map.insert("x", 24);
        map.update("a", |value| *value = 10).unwrap();
        map.remove("b");
        map.insert("b", 20);
        map.remove("c");
        map.commit();
        let entries: Vec<_> = map
            .base
            .iter()
            .map(|(key, value)| (key.as_str(), *value))
            .collect();
        assert_eq!(entries, [("a", 10), ("b", 20), ("x", 24)]);
    }

    #[test]
    fn removals_keep_the_order_of_the_other_entries() {
        let mut map = base(&["a", "b", "c", "d"]);
        map.remove("b");
        map.commit();
        assert_eq!(keys(&map), ["a", "c", "d"]);

        let mut map = base(&["a", "b", "c", "d", "e"]);
        map.insert("x", 24);
        map.insert("y", 25);
        map.insert("z", 26);
        map.remove("x");
        map.remove("b");
        map.remove("d");
        map.commit();
        assert_eq!(keys(&map), ["a", "c", "e", "y", "z"]);

        // Entries near the end are removed one by one.
        let mut map = base(&["a", "b", "c", "d", "e"]);
        map.remove("e");
        map.remove("c");
        map.commit();
        assert_eq!(keys(&map), ["a", "b", "d"]);
    }

    #[test]
    fn an_entry_added_and_removed_in_one_batch_leaves_no_trace() {
        let mut map = base(&["a"]);
        map.insert("x", 24);
        assert!(map.remove("x"));
        assert!(!map.remove("x"));
        map.commit();
        assert_eq!(keys(&map), ["a"]);
    }
}
