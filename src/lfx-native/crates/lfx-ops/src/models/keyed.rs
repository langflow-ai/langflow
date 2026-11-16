//! Keyed lists, indexed by item key.
//!
//! Example keys: an output's `name`, a tool action's first tag, a row's `__id__`.
//! A keyed list sorts by `(__pos__, key)`, so the engine does not sort the array.

use std::fmt;

use crate::data::maps::{HashMap, IndexSet, State};
use crate::data::value::AnyValue;

use crate::models::canonical::{as_double, is_finite_number, utf16_cmp};
use crate::models::error::{Result, bail, invalid, quoted};
use crate::models::schema::{KeyedList, NODE_SCHEMA};

/// The array index of each item of one keyed list, by key, and the rules the list breaks.
///
/// Apply refuses a write into a list with a [`ListIndex::problem`]. Replay does not.
#[derive(Debug, Clone)]
pub struct ListIndex {
    /// The list's kind and keys.
    pub keyed: &'static KeyedList,
    /// The array index of each item whose key no other item has, by key.
    slots: HashMap<String, usize>,
    /// The keys that two items or more have, in the order the list repeats them.
    repeated: IndexSet<String>,
    /// How many items have no non-empty string key.
    keyless: usize,
    /// How many table rows have no finite numeric position.
    unpositioned: usize,
}

/// What a keyed list breaks of the keyed list rules.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ListProblem {
    /// An item has no non-empty string key.
    Keyless,
    /// Two items have this key.
    RepeatedKey(String),
    /// A table row has no finite position at this key.
    Unpositioned(&'static str),
}

impl fmt::Display for ListProblem {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Keyless => f.write_str("every item of this list needs a non-empty string key"),
            Self::RepeatedKey(key) => write!(f, "two items have the key {}", quoted(key)),
            Self::Unpositioned(position) => {
                write!(f, "a list item's {position} must be a finite number")
            }
        }
    }
}

impl ListIndex {
    /// Index `items`, and count the items that break the keyed list rules.
    #[must_use]
    pub fn build(keyed: &'static KeyedList, items: &[AnyValue]) -> Self {
        let mut index = Self {
            keyed,
            slots: HashMap::with_capacity_and_hasher(items.len(), State::default()),
            repeated: IndexSet::default(),
            keyless: 0,
            unpositioned: 0,
        };
        for (slot, item) in items.iter().enumerate() {
            if !keyed.has_position(item) {
                index.unpositioned += 1;
            }
            match keyed.key_of(item).filter(|key| !key.is_empty()) {
                None => index.keyless += 1,
                Some(key) if index.repeated.contains(key) => {}
                Some(key) => {
                    if index.slots.remove(key).is_some() {
                        index.repeated.insert(key.to_owned());
                    } else {
                        index.slots.insert(key.to_owned(), slot);
                    }
                }
            }
        }
        index
    }

    /// The first rule the list breaks: a missing key, a repeated key, or a missing position.
    #[must_use]
    pub fn problem(&self) -> Option<ListProblem> {
        self.key_problem().or_else(|| {
            (self.unpositioned > 0).then_some(ListProblem::Unpositioned(&self.keyed.position))
        })
    }

    /// The first key rule the list breaks: a missing key, or a repeated key.
    #[must_use]
    pub fn key_problem(&self) -> Option<ListProblem> {
        if self.keyless > 0 {
            return Some(ListProblem::Keyless);
        }
        self.repeated
            .first()
            .map(|key| ListProblem::RepeatedKey(key.clone()))
    }

    /// Check that each item has a unique key. Positions are not checked.
    ///
    /// # Errors
    ///
    /// The first rule about keys the list breaks ([`Self::key_problem`]).
    pub fn check_keys(&self, context: &dyn fmt::Display) -> Result<()> {
        match self.key_problem() {
            Some(problem) => bail!("{context}: {problem}"),
            None => Ok(()),
        }
    }

    /// The array index of the item with `key`, or `None` when no item has it.
    ///
    /// # Errors
    ///
    /// Two items have `key`.
    pub fn find(&self, key: &str, context: &dyn fmt::Display) -> Result<Option<usize>> {
        if self.repeated.contains(key) {
            bail!("{context}: two items have the key {}", quoted(key));
        }
        Ok(self.slot(key))
    }

    /// The array index of the item with `key`, when only one item has it.
    #[must_use]
    pub fn slot(&self, key: &str) -> Option<usize> {
        self.slots.get(key).copied()
    }

    /// The keys that only one item has, in no particular order.
    pub fn keys(&self) -> impl Iterator<Item = &str> {
        self.slots.keys().map(String::as_str)
    }

    /// Append `item`, whose key `key` is not in the list yet.
    pub(crate) fn add(&mut self, items: &mut Vec<AnyValue>, key: &str, item: AnyValue) {
        if !self.keyed.has_position(&item) {
            self.unpositioned += 1;
        }
        self.slots.insert(key.to_owned(), items.len());
        items.push(item);
    }

    /// Replace the item at `slot` by `item`, which carries the same key.
    pub(crate) fn replace(&mut self, items: &mut [AnyValue], slot: usize, item: AnyValue) {
        let now = self.keyed.has_position(&item);
        let old = std::mem::replace(&mut items[slot], item);
        self.position_changed(self.keyed.has_position(&old), now);
    }

    /// Count a write inside an item that gave it, or took away, its position.
    pub(crate) fn position_changed(&mut self, before: bool, after: bool) {
        match (before, after) {
            (true, false) => self.unpositioned += 1,
            (false, true) => self.unpositioned -= 1,
            _ => {}
        }
    }

    /// Remove the item with `key` and return it, or `None` when no item has it.
    pub(crate) fn remove(&mut self, items: &mut Vec<AnyValue>, key: &str) -> Option<AnyValue> {
        let slot = self.slots.remove(key)?;
        let item = remove_item(self.keyed, items, slot);
        if !self.keyed.has_position(&item) {
            // The items after it moved up one place.
            self.unpositioned -= 1;
            for later in self.slots.values_mut() {
                if *later > slot {
                    *later -= 1;
                }
            }
            return Some(item);
        }
        if let Some(moved) = items.get(slot)
            && let Some(moved_key) = self.keyed.key_of(moved)
            && let Some(moved_slot) = self.slots.get_mut(moved_key)
        {
            *moved_slot = slot;
        }
        Some(item)
    }
}

/// Check that a list item has a finite position.
///
/// # Errors
///
/// The row's position is missing, not a number, or not finite.
pub(crate) fn check_position(
    keyed: &'static KeyedList,
    row: &AnyValue,
    context: &dyn fmt::Display,
) -> Result<()> {
    if keyed.has_position(row) {
        return Ok(());
    }
    Err(invalid!(
        "{context}: {}",
        ListProblem::Unpositioned(&keyed.position)
    ))
}

/// The array index of the item with `key`, found by a scan. For a list without an index.
pub(crate) fn find_item(keyed: &KeyedList, items: &[AnyValue], key: &str) -> Option<usize> {
    items
        .iter()
        .position(|item| keyed.key_of(item) == Some(key))
}

/// Remove the item at `slot`. The last item moves into the gap, unless the
/// item has no position. Then the list keeps its array order.
pub(crate) fn remove_item(keyed: &KeyedList, items: &mut Vec<AnyValue>, slot: usize) -> AnyValue {
    if keyed.has_position(&items[slot]) {
        items.swap_remove(slot)
    } else {
        items.remove(slot)
    }
}

/// A table's rows in order: by `(__pos__, __id__)`, or as stored for a legacy table without them.
///
/// The order is the editor's: positions as doubles, ids by UTF-16 code units.
#[must_use]
pub fn ordered_rows(rows: &[AnyValue]) -> Vec<&AnyValue> {
    row_order(rows)
        .into_iter()
        .map(|slot| &rows[slot])
        .collect()
}

/// The array indexes of a table's rows, in the order [`ordered_rows`] gives.
pub(crate) fn row_order(rows: &[AnyValue]) -> Vec<usize> {
    item_order(&NODE_SCHEMA.table, rows)
}

/// The array indexes of a keyed list's items, by `(__pos__, key)`. An item
/// without a numeric position or a string key keeps the stored order.
pub(crate) fn item_order(keyed: &KeyedList, items: &[AnyValue]) -> Vec<usize> {
    let keys: Option<Vec<(f64, &str)>> = items
        .iter()
        .map(|item| {
            let position = match item.as_object()?.get(&keyed.position)? {
                AnyValue::Number(number) if is_finite_number(number) => as_double(number),
                _ => return None,
            };
            Some((position, keyed.key_of(item)?))
        })
        .collect();
    let mut order: Vec<usize> = (0..items.len()).collect();
    if let Some(keys) = keys {
        order.sort_by(|&a, &b| {
            keys[a]
                .0
                .total_cmp(&keys[b].0)
                .then_with(|| utf16_cmp(keys[a].1, keys[b].1))
        });
    }
    order
}
