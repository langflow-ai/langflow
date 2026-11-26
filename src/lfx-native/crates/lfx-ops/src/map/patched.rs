//! An insertion-ordered map with staged replacements and
//! patches.

use super::ordered::OrderedMap;
use super::pending::MAX_RETAINED_BATCH_ENTRIES;
use crate::types::FlowStr;

#[derive(Debug)]
pub(crate) struct PatchedMap<V, P = ()> {
    base: OrderedMap<V>,
    // A patch and any replacement for the same key travel
    // together.
    pending: OrderedMap<Change<V, P>>,
}

#[derive(Debug)]
enum Change<V, P> {
    Write { replacement: Option<V>, patch: P },
    Delete,
}

impl<V, P> PatchedMap<V, P> {
    /// The number of committed values.
    pub(crate) fn len(&self) -> usize {
        self.base.len()
    }

    pub(crate) fn is_based(&self, key: &str) -> bool {
        self.base.contains_key(key)
    }

    /// Only an unchanged or patched base value can use the base
    /// value's indexes.
    pub(crate) fn is_stored(&self, key: &str) -> bool {
        if !self.is_based(key) {
            return false;
        }

        match self.pending.get(key) {
            None => true,
            Some(Change::Write { replacement, .. }) => replacement.is_none(),
            Some(Change::Delete) => false,
        }
    }

    pub(crate) fn base_get(&self, key: &str) -> Option<&V> {
        self.base.get(key)
    }

    pub(crate) fn values(&self) -> impl Iterator<Item = &V> {
        self.base.iter().map(|(_, value)| value)
    }

    /// Copy the committed values in insertion order.
    pub(crate) fn snapshot(&self) -> Vec<V>
    where
        V: Clone,
    {
        let mut values = Vec::with_capacity(self.len());
        values.extend(self.values().cloned());
        values
    }

    pub(crate) fn into_items<T>(self, mut convert: impl FnMut(V) -> T) -> Vec<T> {
        let Self { base, pending } = self;
        debug_assert!(pending.is_empty(), "consume between batches only");
        let mut result = Vec::with_capacity(base.len());
        result.extend(base.into_entries().map(|(_, value)| convert(value)));
        result
    }

    fn resolve<'a>(
        base: impl FnOnce() -> Option<&'a V>,
        change: Option<&'a Change<V, P>>,
    ) -> Option<(&'a V, Option<&'a P>)> {
        match change {
            Some(Change::Write { replacement, patch }) => {
                if let Some(value) = replacement {
                    return Some((value, Some(patch)));
                }
                Some((base()?, Some(patch)))
            }
            Some(Change::Delete) => None,
            None => Some((base()?, None)),
        }
    }

    pub(crate) fn read(&self, key: &str) -> Option<(&V, Option<&P>)> {
        Self::resolve(|| self.base_get(key), self.pending.get(key))
    }

    pub(crate) fn get(&self, key: &str) -> Option<&V> {
        self.read(key).map(|(value, _)| value)
    }

    pub(crate) fn contains(&self, key: &str) -> bool {
        self.get(key).is_some()
    }

    /// The values and patches in the order a commit gives them.
    pub(crate) fn pending_values(&self) -> impl Iterator<Item = (&V, Option<&P>)> {
        let kept = self.base.iter().filter_map(|(key, value)| {
            Self::resolve(|| Some(value), self.pending.get(key.as_str()))
        });
        let added = self.pending.iter().filter_map(|(key, change)| {
            if self.is_based(key) {
                return None;
            }
            Self::resolve(|| None, Some(change))
        });
        kept.chain(added)
    }

    pub(crate) fn remove(&mut self, key: &str) {
        if self.is_based(key) {
            self.pending.insert(key, Change::Delete);
        } else {
            self.pending.remove(key);
        }
    }

    /// Apply each key's replacement, deletion or patch in batch
    /// order.
    pub(crate) fn commit(&mut self, released: &mut Vec<V>, mut apply: impl FnMut(&str, &mut V, P)) {
        for (key, change) in self.pending.drain() {
            match change {
                Change::Write { replacement, patch } => {
                    let Some(value) = self.base.get_mut(key.as_str()) else {
                        let mut value = replacement.expect("a patched value exists");
                        apply(&key, &mut value, patch);
                        self.base.insert(key, value);
                        continue;
                    };
                    if let Some(replacement) = replacement {
                        *value = replacement;
                    }
                    apply(&key, value, patch);
                }
                Change::Delete => {
                    if let Some(value) = self.base.remove(key.as_str()) {
                        released.push(value);
                    }
                }
            }
        }
        self.shrink_pending();
        self.base.clear_garbage();
    }

    pub(crate) fn drop_pending(&mut self) {
        self.pending.clear();
        self.shrink_pending();
    }

    fn shrink_pending(&mut self) {
        if self.pending.capacity() > MAX_RETAINED_BATCH_ENTRIES {
            self.pending.shrink_to_fit();
        }
    }
}

impl<V, P: Default> PatchedMap<V, P> {
    pub(crate) fn insert(&mut self, key: FlowStr, value: V) {
        self.pending.insert(
            key,
            Change::Write {
                replacement: Some(value),
                patch: P::default(),
            },
        );
    }

    pub(crate) fn patch_mut(&mut self, key: &str) -> &mut P {
        let change = self.pending.get_or_insert_with(key, || {
            debug_assert!(self.base.contains_key(key), "a patched value exists");
            Change::Write {
                replacement: None,
                patch: P::default(),
            }
        });
        match change {
            Change::Write { patch, .. } => patch,
            Change::Delete => unreachable!("a patched value is present"),
        }
    }
}

impl<V, P> FromIterator<(FlowStr, V)> for PatchedMap<V, P> {
    fn from_iter<I: IntoIterator<Item = (FlowStr, V)>>(items: I) -> Self {
        Self {
            base: items.into_iter().collect(),
            pending: OrderedMap::new(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn committing_a_batch_preserves_order_and_leaves_a_prior_snapshot_intact() {
        let mut map: PatchedMap<_, Option<i32>> =
            [("a".into(), 1), ("b".into(), 2)].into_iter().collect();
        let before = map.snapshot();
        let mut released = Vec::new();

        map.remove("a");
        *map.patch_mut("b") = Some(3);
        map.insert("c".into(), 4);
        map.commit(&mut released, |_, value, patch| {
            if let Some(patch) = patch {
                *value = patch;
            }
        });

        assert_eq!(released, [1]);
        assert_eq!(map.base_get("b"), Some(&3));
        assert!(map.values().copied().eq([3, 4]));
        assert_eq!(map.snapshot(), [3, 4]);
        assert_eq!(before, [1, 2]);
    }
}
