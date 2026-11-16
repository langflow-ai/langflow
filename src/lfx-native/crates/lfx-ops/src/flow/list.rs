//! Keyed lists, indexed by item key.
//!
//! Example: in a list keyed by `name`, `[{"name": "a"}, {"name": "b"}]` holds the
//! items `a` and `b`.
//! A keyed list sorts by `(__pos__, key)`, so the engine does not sort the array.

use std::fmt;

use crate::collection::hash_map::{HashMap, IndexSet, State};
use crate::json::FlowValue;

use crate::flow::model::KeyedList;
use crate::json::serialize::quoted;
use crate::json::{as_double, is_finite_number, utf16_cmp};

/// The array index of each item of one keyed list, by key, and the rules the list breaks.
///
/// Apply refuses a write into a list with a [`ListIndex::problem`]. Replay does not.
#[derive(Debug, Clone)]
pub struct ListIndex {
    /// The list's kind and keys.
    pub keyed: &'static KeyedList,
    /// The array index of each item whose key no other item has, by key.
    item_indexes: HashMap<String, usize>,
    /// The keys that two items or more have, in the order the list repeats them.
    repeated: IndexSet<String>,
    /// How many items have no non-empty string key.
    keyless: usize,
    /// How many items have no finite numeric position.
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

/// A keyed list rule that a write breaks, with where it is.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
#[error("{0}")]
pub struct ListError(pub(crate) String);

impl ListIndex {
    /// Index `items`, and count the items that break the keyed list rules.
    #[must_use]
    pub fn build(keyed: &'static KeyedList, items: &[FlowValue]) -> Self {
        let mut index = Self {
            keyed,
            item_indexes: HashMap::with_capacity_and_hasher(items.len(), State::default()),
            repeated: IndexSet::default(),
            keyless: 0,
            unpositioned: 0,
        };
        for (item_index, item) in items.iter().enumerate() {
            if !keyed.has_position(item) {
                index.unpositioned += 1;
            }
            match keyed.key_of(item).filter(|key| !key.is_empty()) {
                None => index.keyless += 1,
                Some(key) if index.repeated.contains(key) => {}
                Some(key) => {
                    if index.item_indexes.remove(key).is_some() {
                        index.repeated.insert(key.to_owned());
                    } else {
                        index.item_indexes.insert(key.to_owned(), item_index);
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
    pub fn check_keys(&self, context: &dyn fmt::Display) -> Result<(), ListError> {
        match self.key_problem() {
            Some(problem) => Err(ListError(format!("{context}: {problem}"))),
            None => Ok(()),
        }
    }

    /// The array index of the item with `key`, or `None` when no item has it.
    ///
    /// # Errors
    ///
    /// Two items have `key`.
    pub fn find(&self, key: &str, context: &dyn fmt::Display) -> Result<Option<usize>, ListError> {
        if self.repeated.contains(key) {
            return Err(ListError(format!(
                "{context}: two items have the key {}",
                quoted(key)
            )));
        }
        Ok(self.item_index(key))
    }

    /// The array index of the item with `key`, when only one item has it.
    #[must_use]
    pub fn item_index(&self, key: &str) -> Option<usize> {
        self.item_indexes.get(key).copied()
    }

    /// The keys that only one item has, in no particular order.
    pub fn keys(&self) -> impl Iterator<Item = &str> {
        self.item_indexes.keys().map(String::as_str)
    }

    /// Append `item`, whose key `key` is not in the list yet.
    pub(crate) fn add(&mut self, items: &mut Vec<FlowValue>, key: &str, item: FlowValue) {
        if !self.keyed.has_position(&item) {
            self.unpositioned += 1;
        }
        self.item_indexes.insert(key.to_owned(), items.len());
        items.push(item);
    }

    /// Replace the item at `item_index` by `item`, which carries the same key.
    pub(crate) fn replace(&mut self, items: &mut [FlowValue], item_index: usize, item: FlowValue) {
        let now = self.keyed.has_position(&item);
        let old = std::mem::replace(&mut items[item_index], item);
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
    pub(crate) fn remove(&mut self, items: &mut Vec<FlowValue>, key: &str) -> Option<FlowValue> {
        let item_index = self.item_indexes.remove(key)?;
        let item = remove_item(self.keyed, items, item_index);
        if !self.keyed.has_position(&item) {
            // The items after it moved up one place.
            self.unpositioned -= 1;
            for later in self.item_indexes.values_mut() {
                if *later > item_index {
                    *later -= 1;
                }
            }
            return Some(item);
        }
        if let Some(moved) = items.get(item_index)
            && let Some(moved_key) = self.keyed.key_of(moved)
            && let Some(moved_index) = self.item_indexes.get_mut(moved_key)
        {
            *moved_index = item_index;
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
    row: &FlowValue,
    context: &dyn fmt::Display,
) -> Result<(), ListError> {
    if keyed.has_position(row) {
        return Ok(());
    }
    Err(ListError(format!(
        "{context}: {}",
        ListProblem::Unpositioned(&keyed.position)
    )))
}

/// The array index of the item with `key`, found by a scan. For a list without an index.
pub(crate) fn find_item(keyed: &KeyedList, items: &[FlowValue], key: &str) -> Option<usize> {
    items
        .iter()
        .position(|item| keyed.key_of(item) == Some(key))
}

/// Remove the item at `item_index`. The last item moves into the gap, unless the
/// item has no position. Then the list keeps its array order.
pub(crate) fn remove_item(
    keyed: &KeyedList,
    items: &mut Vec<FlowValue>,
    item_index: usize,
) -> FlowValue {
    if keyed.has_position(&items[item_index]) {
        items.swap_remove(item_index)
    } else {
        items.remove(item_index)
    }
}

/// The array indexes of a keyed list's items, by `(__pos__, key)`. An item
/// without a numeric position or a string key keeps the stored order.
pub(crate) fn item_order(keyed: &KeyedList, items: &[FlowValue]) -> Vec<usize> {
    let keys: Option<Vec<(f64, &str)>> = items
        .iter()
        .map(|item| {
            let position = match item.as_object()?.get(&keyed.position)? {
                FlowValue::Number(number) if is_finite_number(number) => as_double(number),
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

// --- Positions (`__pos__`) ---------------------------------------------------------------------

/// Whether positions are renumbered when no number fits between two items.
/// Only the editor renumbers.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Renumber {
    /// Renumber the list `1..n`, in the same order, when a gap has no room left.
    WhenNoRoom,
    /// Never renumber.
    Never,
}

/// An item's position, keeping whether Python would hold it as an integer.
#[derive(Debug, Clone, Copy)]
pub(crate) struct Position {
    pub(crate) value: f64,
    integer: bool,
}

/// The position a value holds, when it is a finite number.
impl TryFrom<&FlowValue> for Position {
    type Error = ();

    fn try_from(value: &FlowValue) -> Result<Self, ()> {
        match value {
            FlowValue::Number(number) if is_finite_number(number) => Ok(Self {
                value: as_double(number),
                integer: number.is_integer(),
            }),
            _ => Err(()),
        }
    }
}

impl Position {
    pub(crate) fn integer(value: f64) -> Self {
        Self {
            value,
            integer: true,
        }
    }

    /// The position as a JSON number: an integer while it is one, as Python keeps it.
    #[expect(
        clippy::cast_possible_truncation,
        clippy::cast_precision_loss,
        clippy::float_cmp,
        reason = "converts an integral double to an integer and checks that it was exact"
    )]
    pub(crate) fn to_value(self) -> FlowValue {
        let whole = self.value as i64;
        if self.integer && whole as f64 == self.value {
            FlowValue::from(whole)
        } else {
            crate::json::Number::from_f64(self.value).map_or(FlowValue::Null, FlowValue::Number)
        }
    }
}

/// Give each item without a position one that keeps its array place, in place.
///
/// Example: items at 1, none, 2 get 1, 1.5, 2. A list without positions gets `1..n`.
/// With [`Renumber::WhenNoRoom`], a gap without room renumbers the list `1..n`
/// in its order. Returns the indexes of the items it changed.
pub fn fill_missing_positions(
    keyed: &KeyedList,
    items: &mut [FlowValue],
    renumber: Renumber,
) -> Vec<usize> {
    let key = keyed.position.as_str();
    let position_at = |items: &[FlowValue], index: usize| {
        items[index]
            .get(key)
            .and_then(|value| Position::try_from(value).ok())
    };
    let mut filled = Vec::new();
    let mut no_room = false;
    let mut index = 0;
    while index < items.len() {
        if position_at(items, index).is_some() {
            index += 1;
            continue;
        }
        let mut end = index;
        while end < items.len() && position_at(items, end).is_none() {
            end += 1;
        }
        let count = end - index;
        let before = index
            .checked_sub(1)
            .and_then(|before| position_at(items, before));
        let after = (end < items.len())
            .then(|| position_at(items, end))
            .flatten();
        let positions = spread(before, after, count);
        no_room |= !fits_between(&positions, before, after);
        for (offset, position) in positions.into_iter().enumerate() {
            set_position(&mut items[index + offset], key, position);
            filled.push(index + offset);
        }
        index = end;
    }
    if no_room && renumber == Renumber::WhenNoRoom {
        for (rank, item_index) in item_order(keyed, items).into_iter().enumerate() {
            let number = f64::from(u32::try_from(rank + 1).unwrap_or(u32::MAX));
            set_position(&mut items[item_index], key, Position::integer(number));
        }
        return (0..items.len()).collect();
    }
    filled
}

/// The positions of a run of `count` items between `before` and `after`.
fn spread(before: Option<Position>, after: Option<Position>, count: usize) -> Vec<Position> {
    let steps = (1..=count).map(|step| f64::from(u32::try_from(step).unwrap_or(u32::MAX)));
    let total = f64::from(u32::try_from(count + 1).unwrap_or(u32::MAX));
    match (before, after) {
        (Some(before), Some(after)) if before.value < after.value => steps
            .map(|step| Position {
                value: before.value + (after.value - before.value) * step / total,
                integer: false,
            })
            .collect(),
        (Some(before), _) => steps
            .map(|step| Position {
                value: before.value + step,
                integer: before.integer,
            })
            .collect(),
        (None, Some(after)) => steps
            .map(|step| Position {
                value: after.value - total + step,
                integer: after.integer,
            })
            .collect(),
        (None, None) => steps.map(Position::integer).collect(),
    }
}

/// Whether new positions increase strictly between their neighbours, when those are in order.
fn fits_between(positions: &[Position], before: Option<Position>, after: Option<Position>) -> bool {
    let (Some(before), Some(after)) = (before, after) else {
        return true;
    };
    if before.value >= after.value {
        return true;
    }
    let mut previous = before.value;
    for position in positions {
        if position.value <= previous {
            return false;
        }
        previous = position.value;
    }
    previous < after.value
}

fn set_position(item: &mut FlowValue, key: &str, position: Position) {
    if let Some(item) = item.as_object_mut() {
        item.insert(key.to_owned(), position.to_value());
    }
}
