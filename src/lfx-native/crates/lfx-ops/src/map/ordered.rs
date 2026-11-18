//! [`OrderedMap`]: a map that preserves insert order.
//!
//! Deleted keys are tombstoned in `data` and pruned when they outnumber live keys.

use crate::map::hash::HashMap;

/// Map preserving insert order.
/// deleted keys stay in `data` and are pruned
/// when they outnumber non-deleted keys.
#[derive(Debug)]
pub(crate) struct OrderedMap<V> {
    // actual data: (key, value) pairs
    data: Vec<Option<(String, V)>>,
    // maps the key to its index in  `data`
    index: HashMap<String, usize>,
}

impl<V> OrderedMap<V> {
    fn new() -> Self {
        Self {
            data: Vec::new(),
            index: HashMap::default(),
        }
    }

    /// The number of values.
    pub fn len(&self) -> usize {
        self.index.len()
    }

    pub fn get(&self, key: &str) -> Option<&V> {
        let i = *self.index.get(key)?;
        let (_, v) = self.data[i]
            .as_ref()
            .expect("data exists");
        return Some(v);
    }

    pub fn get_mut(&mut self, key: &str) -> Option<&mut V> {
        let position = *self.index.get(key)?;
        self.data[position].as_mut().map(|(_, value)| value)
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
        match self.index.get(&key) {
            None => {
                self.index.insert(key.clone(), self.data.len());
                self.data.push(Some((key, value)));
            }
            Some(&i) => {
                let (_, cur) = self.data[i]
                    .as_mut()
                    .expect("data must contain indexed item");

                *cur = value;
            }
        }

    }

    /// Remove `key`, and leave its position empty.
    pub fn remove(&mut self, key: &str) -> Option<V> {
        let position = self.index.remove(key)?;
        self.data[position].take().map(|(_, value)| value)
    }

    /// Prune deleted entries in `data`
    pub(super) fn prune_garbage(&mut self) -> bool {
        if self.data.len() - self.index.len() <= self.index.len() {
            return false;
        }
        // prune
        self.data.retain(Option::is_some);
        // reduce allocated capacity if 4x larger than current number of stored items
        if self.data.capacity() > 4 * self.data.len().max(4) {
            self.data.shrink_to_fit();
        }
        // update indexes
        self.data
            .iter()
            .flatten()
            .enumerate()
            .for_each(|(i, (key, _))| {
                *self.index
                    .get_mut(key)
                    .expect("an entry is indexed") = i;
            });

        return true;
    }

    /// The keys and values, in order.
    pub fn iter(&self) -> impl Iterator<Item = (&String, &V)> {
        self.data
            .iter()
            .flatten()
            .map(|(key, value)| (key, value))
    }


    pub fn values(&self) -> impl Iterator<Item = &V> {
        self.iter().map(|(_, value)| value)
    }

    pub(super) fn into_values(self) -> impl Iterator<Item = V> {
        self.data.into_iter().flatten().map(|(_, value)| value)
    }

    #[cfg(test)]
    pub fn keys(&self) -> impl Iterator<Item = &String> {
        self.iter().map(|(key, _)| key)
    }

    /// The number of positions, empty ones included.
    #[cfg(test)]
    pub(crate) fn positions(&self) -> usize {
        self.data.len()
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
