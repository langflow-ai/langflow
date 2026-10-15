//! Keyed lists, indexed by item key.
//!
//! Outputs, tool actions and table rows are lists whose items carry a key: an
//! output's `name`, a tool action's first tag, a row's `_id`. A write finds
//! its item through an index instead of scanning the list, and building the
//! index checks the list once: every item has a key, no key repeats, and
//! every table row carries a numeric `_pos`.
//!
//! Natural lists keep the order writes leave them in. A table's order is its
//! rows' `(_pos, _id)`, not their places in the array: readers sort rows when
//! they strip the row keys, so the engine never sorts a table. A new row is
//! appended, and a deleted row's slot is taken by the last row.

use std::collections::HashMap;

use serde_json::Value;

use crate::ops::canonical::is_row_position;
use crate::ops::error::{Error, Result};
use crate::ops::schema::{KeyedList, ListKind};

/// The slot of every item of one keyed list, by key.
#[derive(Debug, Clone)]
pub struct ListIndex {
    /// The list's kind and keys.
    pub keyed: &'static KeyedList,
    slots: HashMap<String, usize>,
}

/// How an item left a list, so it can be put back.
#[derive(Debug)]
pub(crate) enum Removal {
    /// Removed from `slot`; the items after it moved up.
    Shifted { slot: usize },
    /// Removed from `slot`; the last item took its place.
    Swapped { slot: usize },
}

impl ListIndex {
    /// Index `items`, checking every item's key, and every table row's position.
    ///
    /// # Errors
    ///
    /// An item without a non-empty string key, two items with one key, or a
    /// table row without a finite numeric position.
    pub fn build(keyed: &'static KeyedList, items: &[Value], context: &str) -> Result<Self> {
        let mut index = Self {
            keyed,
            slots: HashMap::with_capacity(items.len()),
        };
        for (slot, item) in items.iter().enumerate() {
            let key = index.require_key(item, context)?;
            if index.slots.contains_key(key) {
                return Err(Error::invalid(format!(
                    "{context}: two items have the key {key:?}"
                )));
            }
            if keyed.kind == ListKind::Table {
                index.require_position(item, context)?;
            }
            index.slots.insert(key.to_owned(), slot);
        }
        Ok(index)
    }

    /// The slot of the item with `key`.
    #[must_use]
    pub fn slot(&self, key: &str) -> Option<usize> {
        self.slots.get(key).copied()
    }

    /// Whether an item has `key`.
    #[must_use]
    pub fn contains(&self, key: &str) -> bool {
        self.slots.contains_key(key)
    }

    /// The keys of the list, in no particular order.
    pub fn keys(&self) -> impl Iterator<Item = &str> {
        self.slots.keys().map(String::as_str)
    }

    /// An item's key, which must be a non-empty string.
    ///
    /// # Errors
    ///
    /// The item has no non-empty string key.
    pub fn require_key<'v>(&self, item: &'v Value, context: &str) -> Result<&'v str> {
        match self.keyed.key_of(item) {
            Some(key) if !key.is_empty() => Ok(key),
            _ => Err(Error::invalid(format!(
                "{context}: every item of this list needs a non-empty string {}",
                self.keyed.selector_name()
            ))),
        }
    }

    /// Check that a table row carries a finite numeric position.
    ///
    /// # Errors
    ///
    /// The row's position is missing, not a number, or not finite.
    pub fn require_position(&self, row: &Value, context: &str) -> Result<()> {
        let key = self.keyed.position.as_deref().unwrap_or_default();
        if row.get(key).is_some_and(is_row_position) {
            Ok(())
        } else {
            Err(Error::invalid(format!(
                "{context}: a table row's {key} must be a finite number"
            )))
        }
    }

    /// Append an item whose key is not in the list yet.
    pub(crate) fn add(&mut self, items: &mut Vec<Value>, item: Value, context: &str) -> Result<()> {
        let key = self.require_key(&item, context)?.to_owned();
        if self.keyed.kind == ListKind::Table {
            self.require_position(&item, context)?;
        }
        self.slots.insert(key, items.len());
        items.push(item);
        Ok(())
    }

    /// Remove the item with `key`, which must exist, and say how it left.
    pub(crate) fn remove(&mut self, items: &mut Vec<Value>, key: &str) -> (Value, Removal) {
        let slot = self.slots.remove(key).unwrap_or_default();
        if self.keyed.kind == ListKind::Natural {
            // Natural lists are short (a component's outputs or tool actions), and their order is kept.
            let item = items.remove(slot);
            for later in self.slots.values_mut() {
                if *later > slot {
                    *later -= 1;
                }
            }
            return (item, Removal::Shifted { slot });
        }
        let item = items.swap_remove(slot);
        if let Some(moved) = items.get(slot)
            && let Some(moved_key) = self.keyed.key_of(moved)
        {
            self.slots.insert(moved_key.to_owned(), slot);
        }
        (item, Removal::Swapped { slot })
    }

    /// Replace the item with `key` by `item`, which carries the same key, and return the old item.
    pub(crate) fn replace(
        &mut self,
        items: &mut [Value],
        key: &str,
        item: Value,
        context: &str,
    ) -> Result<Value> {
        if self.keyed.kind == ListKind::Table {
            self.require_position(&item, context)?;
        }
        let slot = self.slots.get(key).copied().unwrap_or_default();
        Ok(std::mem::replace(&mut items[slot], item))
    }
}
