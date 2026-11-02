//! Keyed lists, indexed by item key.
//!
//! Outputs, tool actions and table rows are lists whose items carry a key: an
//! output's `name`, a tool action's first tag, a row's `__id__`. A write finds
//! its item through an index instead of scanning the list. Building the
//! index reads the list once, and counts what breaks the keyed list rules:
//! an item without a key, a key that repeats, a table row without a numeric
//! `__pos__`. Apply refuses a write into such a list; replay does not.
//!
//! Every keyed list is ordered by its items' `(__pos__, key)`, not by their
//! places in the array: readers sort items when they strip `__pos__`, so the
//! engine never sorts a list. A new item is appended, and the last item moves
//! into a deleted item's place. A list whose items carry no `__pos__` keeps
//! its array order.

use std::collections::hash_map::RandomState;
use std::collections::{HashMap, HashSet, VecDeque};
use std::fmt;
use std::hash::{BuildHasher, Hash, Hasher};

use indexmap::IndexSet;

use crate::value::AnyValue;

use crate::ops::canonical::{
    as_double, is_finite_number, is_integer_text, is_row_position, ordered_rows, row_order,
    values_equal,
};
use crate::ops::entry::EntryExt;
use crate::ops::error::{Result, bail, invalid, quoted};
use crate::ops::ids::{new_table_row_id, unused_id};
use crate::ops::schema::{KeyedList, NODE_SCHEMA, field_value_path};

/// The array index of every item of one keyed list, by key, and what the
/// list breaks of the keyed list rules.
///
/// Building the index never fails. Apply refuses a write into a list that
/// breaks the rules ([`ListIndex::problem`]); replay writes into it, and fails
/// only when a key it looks up names two items.
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
    /// A table row has no finite numeric position, which this key holds.
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
            slots: HashMap::with_capacity(items.len()),
            repeated: IndexSet::new(),
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

    /// The first rule the list breaks, if any: an item without a key, then
    /// a repeated key, then an item without a position.
    #[must_use]
    pub fn problem(&self) -> Option<ListProblem> {
        self.key_problem().or_else(|| {
            (self.unpositioned > 0).then_some(ListProblem::Unpositioned(&self.keyed.position))
        })
    }

    /// The first rule about keys the list breaks, if any: an item without a
    /// key, then a repeated key.
    #[must_use]
    pub fn key_problem(&self) -> Option<ListProblem> {
        if self.keyless > 0 {
            return Some(ListProblem::Keyless);
        }
        self.repeated
            .first()
            .map(|key| ListProblem::RepeatedKey(key.clone()))
    }

    /// Check that every item has a key that no other item has. A reader that
    /// finds items by key needs this, and not their positions.
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

/// Check that a list item carries a finite numeric position.
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

/// The array index of the item with `key`, found by reading every item. For
/// a list without an index, such as one a batch wrote.
pub(crate) fn find_item(keyed: &KeyedList, items: &[AnyValue], key: &str) -> Option<usize> {
    items
        .iter()
        .position(|item| keyed.key_of(item) == Some(key))
}

/// Remove the item at `slot`. The order of a list is its items' positions,
/// so the last item moves into the gap. An item without a position belongs
/// to a list that keeps its array order, so the items after it move up.
pub(crate) fn remove_item(keyed: &KeyedList, items: &mut Vec<AnyValue>, slot: usize) -> AnyValue {
    if keyed.has_position(&items[slot]) {
        items.swap_remove(slot)
    } else {
        items.remove(slot)
    }
}

// --- Table rows ----------------------------------------------------------------------------
//
// Every row of a table value stored in a flow carries a stable `__id__` and a
// numeric position `__pos__`, so concurrent edits address rows instead of
// indexes. The table's order is its rows' `(__pos__, __id__)`, not their places in
// the stored array, which nothing keeps sorted. Both keys exist for the
// flow's history and are not data: components never see them, so every place
// that hands a stored table to anything outside the engine strips them first,
// and puts the rows in order as it does.

/// Whether positions are renumbered when no number fits between two rows.
///
/// Only the editor renumbers: the server never changes a position.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Renumber {
    /// Renumber the table `1..n`, in the same order, when a gap has no room left.
    WhenNoRoom,
    /// Never renumber.
    Never,
}

fn row_id_key() -> &'static str {
    &NODE_SCHEMA.table_keys.id
}

fn row_position_key() -> &'static str {
    &NODE_SCHEMA.table_keys.position
}

fn is_row_key(key: &str) -> bool {
    key == row_id_key() || key == row_position_key()
}

/// A row without `__id__` and `__pos__`; a value that is not an object is returned as is.
fn without_row_keys(row: &AnyValue) -> AnyValue {
    match row {
        AnyValue::Object(map) => AnyValue::Object(
            map.iter()
                .filter(|(key, _)| !is_row_key(key))
                .map(|(key, value)| (key.clone(), value.clone()))
                .collect(),
        ),
        other => other.clone(),
    }
}

/// Table rows in order and without `__id__` and `__pos__`; a value that is not a list is returned as is.
#[must_use]
pub fn strip_row_keys(rows: &AnyValue) -> AnyValue {
    match rows {
        AnyValue::Array(rows) => AnyValue::Array(
            ordered_rows(rows)
                .into_iter()
                .map(without_row_keys)
                .collect(),
        ),
        other => other.clone(),
    }
}

/// The names of a node's template fields whose value is a table list.
#[must_use]
pub fn table_fields(node: &AnyValue) -> Vec<String> {
    let Some(template) = node.template() else {
        return Vec::new();
    };
    template
        .iter()
        .filter(|(name, field)| {
            field.get("value").is_some_and(AnyValue::is_array)
                && NODE_SCHEMA.is_table_at(node, &field_value_path(name))
        })
        .map(|(name, _)| name.to_string())
        .collect()
}

fn table_value_mut<'n>(node: &'n mut AnyValue, field: &str) -> Option<&'n mut Vec<AnyValue>> {
    node.get_mut("data")?
        .get_mut("node")?
        .get_mut("template")?
        .get_mut(field)?
        .get_mut("value")?
        .as_array_mut()
}

/// Order the rows of every table value of a node and strip `__id__` and `__pos__`, in place.
pub fn strip_node_table_row_keys(node: &mut AnyValue) {
    for field in table_fields(node) {
        if let Some(rows) = table_value_mut(node, &field) {
            let stripped = strip_row_keys(&AnyValue::Array(std::mem::take(rows)));
            if let AnyValue::Array(stripped) = stripped {
                *rows = stripped;
            }
        }
    }
}

/// Order and strip the table values of every node of a flow, in place.
pub fn strip_flow_table_row_keys(flow: &mut AnyValue) {
    for node in flow
        .get_mut("nodes")
        .and_then(AnyValue::as_array_mut)
        .into_iter()
        .flatten()
    {
        strip_node_table_row_keys(node);
    }
}

/// Whether every row is an object with a unique `__id__` and a numeric `__pos__`:
/// the shape the server accepts.
#[must_use]
pub fn has_table_row_ids(rows: &[AnyValue]) -> bool {
    let mut seen = HashSet::new();
    rows.iter().all(|row| {
        row.non_empty_str(row_id_key())
            .is_some_and(|id| seen.insert(id))
            && row.get(row_position_key()).is_some_and(is_row_position)
    })
}

/// Give one table value's rows the ids and positions a write needs, in place.
///
/// Rows that already have a unique `__id__` keep it, and rows with a position
/// keep it. A row without an id that equals a not yet matched row of
/// `previous` (the stored value, apart from ids and positions) takes that
/// row's id and position; the others get a new random id. Rows still without
/// a position get one that keeps them where they are stored, so a legacy
/// table keeps its order. A table with a row that is not an object is left
/// for validation to report.
///
/// # Errors
///
/// A compared row holds a number that is not finite.
pub fn assign_row_ids(
    rows: &mut [AnyValue],
    previous: Option<&AnyValue>,
    renumber: Renumber,
) -> Result<()> {
    if !rows.iter().all(AnyValue::is_object) {
        return Ok(());
    }
    match_row_ids(rows, previous)?;
    fill_missing_positions(rows, renumber);
    Ok(())
}

/// Hash canonical values without serializing or copying them. Object order
/// does not matter, numbers use JavaScript doubles, and row metadata is
/// excluded only at the row's root. Equality still decides every match.
fn content_hash(value: &AnyValue, state: &RandomState, row: bool) -> Result<u64> {
    let mut hash = state.build_hasher();
    std::mem::discriminant(value).hash(&mut hash);
    match value {
        AnyValue::Null => {}
        AnyValue::Bool(value) => value.hash(&mut hash),
        AnyValue::String(value) => value.hash(&mut hash),
        AnyValue::Number(value) => {
            let value = as_double(value);
            if !value.is_finite() {
                return Err(crate::ops::error::Error::non_finite());
            }
            // Both zero signs have the same canonical form.
            (if value == 0.0 { 0 } else { value.to_bits() }).hash(&mut hash);
        }
        AnyValue::Array(values) => {
            values.len().hash(&mut hash);
            for value in values {
                content_hash(value, state, false)?.hash(&mut hash);
            }
        }
        AnyValue::Object(values) => {
            let mut sum = 0_u64;
            let mut count = 0_usize;
            for (key, value) in values {
                if row && is_row_key(key) {
                    continue;
                }
                let mut entry = state.build_hasher();
                key.hash(&mut entry);
                content_hash(value, state, false)?.hash(&mut entry);
                sum = sum.wrapping_add(entry.finish());
                count += 1;
            }
            count.hash(&mut hash);
            sum.hash(&mut hash);
        }
    }
    Ok(hash.finish())
}

fn row_contents_equal(left: &AnyValue, right: &AnyValue) -> Result<bool> {
    let (Some(left), Some(right)) = (left.as_object(), right.as_object()) else {
        return values_equal(left, right);
    };
    let visible = |map: &crate::value::AnyMap| map.keys().filter(|key| !is_row_key(key)).count();
    if visible(left) != visible(right) {
        return Ok(false);
    }
    for (key, value) in left {
        if !is_row_key(key)
            && !right
                .get(key)
                .map(|right| values_equal(value, right))
                .transpose()?
                .unwrap_or(false)
        {
            return Ok(false);
        }
    }
    Ok(true)
}

/// Remove one equal row from a fingerprint bucket. A fingerprint collision
/// cannot reuse another row's id, and every claimed candidate is removed once.
fn take_matching_row<'a>(
    bucket: &mut VecDeque<&'a AnyValue>,
    row: &AnyValue,
    used: &HashSet<String>,
) -> Result<Option<&'a AnyValue>> {
    let mut slot = 0;
    while slot < bucket.len() {
        if used.contains(bucket[slot].non_empty_str(row_id_key()).unwrap_or_default()) {
            bucket.remove(slot);
        } else if row_contents_equal(bucket[slot], row)? {
            return Ok(bucket.remove(slot));
        } else {
            slot += 1;
        }
    }
    Ok(None)
}

/// Give every row without a unique `__id__` one, in place, keeping stored ids.
///
/// A row that equals a not yet matched row of `previous` (the stored value,
/// apart from ids and positions) takes that row's id, and its position when
/// it has none; the others get a new random id. So a table rewritten with the
/// rows it already held keeps them, and a new row changes nothing about the
/// others.
///
/// # Errors
///
/// A compared row holds a number that is not finite.
pub fn match_row_ids(rows: &mut [AnyValue], previous: Option<&AnyValue>) -> Result<()> {
    let (id_key, position_key) = (row_id_key(), row_position_key());
    let mut used: HashSet<String> = HashSet::new();
    let mut need_id = Vec::new();
    for (index, row) in rows.iter().enumerate() {
        match row.non_empty_str(id_key) {
            Some(id) if !used.contains(id) => {
                used.insert(id.to_owned());
            }
            _ => need_id.push(index),
        }
    }
    let candidates: Vec<&AnyValue> = previous
        .and_then(AnyValue::as_array)
        .into_iter()
        .flatten()
        .filter(|row| row.is_object() && row.non_empty_str(id_key).is_some())
        .collect();
    if need_id.is_empty() {
        return Ok(());
    }
    let state = RandomState::new();
    let mut by_content: HashMap<u64, VecDeque<&AnyValue>> = HashMap::new();
    // Preserve the old short-circuit errors for invalid numbers. Such input
    // uses the borrowed comparison below instead of constructing an index.
    let indexed = candidates
        .iter()
        .filter(|row| !used.contains(row.non_empty_str(id_key).unwrap_or_default()))
        .try_for_each(|row| -> Result<()> {
            by_content
                .entry(content_hash(row, &state, true)?)
                .or_default()
                .push_back(*row);
            Ok(())
        })
        .is_ok();
    for index in need_id {
        let mut matched = None;
        let hash = if indexed && !candidates.is_empty() {
            content_hash(&rows[index], &state, true).ok()
        } else {
            None
        };
        if let Some(bucket) = hash.and_then(|hash| by_content.get_mut(&hash)) {
            matched = take_matching_row(bucket, &rows[index], &used)?;
        } else if !indexed || (hash.is_none() && !candidates.is_empty()) {
            for candidate in &candidates {
                let id = candidate.non_empty_str(id_key).unwrap_or_default();
                if !used.contains(id) && row_contents_equal(candidate, &rows[index])? {
                    matched = Some(*candidate);
                    break;
                }
            }
        }
        let row = &mut rows[index];
        let new_id = if let Some(matched) = matched {
            if !row.get(position_key).is_some_and(is_row_position)
                && let Some(position) = matched
                    .get(position_key)
                    .filter(|position| is_row_position(position))
                && let Some(row) = row.as_object_mut()
            {
                row.insert(position_key.to_owned(), position.clone());
            }
            matched.non_empty_str(id_key).unwrap_or_default().to_owned()
        } else {
            unused_id(&used, new_table_row_id)
        };
        used.insert(new_id.clone());
        if let Some(row) = row.as_object_mut() {
            row.insert(id_key.to_owned(), AnyValue::from(new_id));
        }
    }
    Ok(())
}

/// A row position, keeping whether Python would hold it as an integer.
#[derive(Debug, Clone, Copy)]
struct Position {
    value: f64,
    integer: bool,
}

/// The position a value holds, when it is a finite number.
impl TryFrom<&AnyValue> for Position {
    type Error = ();

    fn try_from(value: &AnyValue) -> Result<Self, ()> {
        match value {
            AnyValue::Number(number) if is_finite_number(number) => Ok(Self {
                value: as_double(number),
                integer: is_integer_text(number),
            }),
            _ => Err(()),
        }
    }
}

impl Position {
    fn integer(value: f64) -> Self {
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
    fn to_value(self) -> AnyValue {
        let whole = self.value as i64;
        if self.integer && whole as f64 == self.value {
            AnyValue::from(whole)
        } else {
            crate::value::Number::from_f64(self.value).map_or(AnyValue::Null, AnyValue::Number)
        }
    }
}

/// Give each row without a valid position one that keeps it where it is stored, in place.
///
/// Positioned rows keep their positions. A run of rows without one is spread
/// evenly between the positioned rows stored before and after it, or placed
/// one apart before the first or after the last; when those neighbours are
/// out of order, the run follows the one before it. A table with no
/// positions at all gets `1..n`.
///
/// With [`Renumber::WhenNoRoom`], a gap that has no room left for its run
/// renumbers the whole table `1..n`. The new numbers follow the order that
/// [`ordered_rows`] gives after the runs are filled, so the order does not
/// change. Returns the indexes of the rows it gave a position.
pub fn fill_missing_positions(rows: &mut [AnyValue], renumber: Renumber) -> Vec<usize> {
    let key = row_position_key();
    let position_at = |rows: &[AnyValue], index: usize| {
        rows[index]
            .get(key)
            .and_then(|value| Position::try_from(value).ok())
    };
    let mut filled = Vec::new();
    let mut no_room = false;
    let mut index = 0;
    while index < rows.len() {
        if position_at(rows, index).is_some() {
            index += 1;
            continue;
        }
        let mut end = index;
        while end < rows.len() && position_at(rows, end).is_none() {
            end += 1;
        }
        let count = end - index;
        let before = index
            .checked_sub(1)
            .and_then(|before| position_at(rows, before));
        let after = (end < rows.len()).then(|| position_at(rows, end)).flatten();
        let positions = spread(before, after, count);
        no_room |= !fits_between(&positions, before, after);
        for (offset, position) in positions.into_iter().enumerate() {
            set_position(&mut rows[index + offset], key, position);
            filled.push(index + offset);
        }
        index = end;
    }
    if no_room && renumber == Renumber::WhenNoRoom {
        for (rank, slot) in row_order(rows).into_iter().enumerate() {
            let number = f64::from(u32::try_from(rank + 1).unwrap_or(u32::MAX));
            set_position(&mut rows[slot], key, Position::integer(number));
        }
        return (0..rows.len()).collect();
    }
    filled
}

/// The positions of a run of `count` rows between `before` and `after`.
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

/// Whether new positions are distinct and strictly between their neighbours,
/// when those are in order.
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

fn set_position(row: &mut AnyValue, key: &str, position: Position) {
    if let Some(row) = row.as_object_mut() {
        row.insert(key.to_owned(), position.to_value());
    }
}

/// Give every table value of a node being added row ids and positions, in place.
///
/// # Errors
///
/// A compared row holds a number that is not finite.
pub fn assign_table_row_ids(node: &mut AnyValue, renumber: Renumber) -> Result<()> {
    for field in table_fields(node) {
        if let Some(rows) = table_value_mut(node, &field) {
            assign_row_ids(rows, None, renumber)?;
        }
    }
    Ok(())
}

/// Give row ids and positions to the table values a node adds or changes
/// relative to `previous`, the same node as stored, in place.
///
/// A table equal to the stored one is left as it is, ids or not, so opening
/// or refreshing a flow never rewrites an untouched legacy table. A changed
/// table keeps the ids of rows it still holds. A node without `previous` gets
/// ids on every table.
///
/// # Errors
///
/// A compared row holds a number that is not finite.
pub fn assign_changed_node_table_row_ids(
    node: &mut AnyValue,
    previous: Option<&AnyValue>,
    renumber: Renumber,
) -> Result<()> {
    let stored: HashMap<String, &AnyValue> = previous
        .map(|previous| {
            table_fields(previous)
                .into_iter()
                .filter_map(|field| Some((field.clone(), previous.field_value(&field)?)))
                .collect()
        })
        .unwrap_or_default();
    for field in table_fields(node) {
        let previous_value = stored.get(&field).copied();
        if let (Some(previous_value), Some(value)) = (previous_value, node.field_value(&field))
            && values_equal(previous_value, value)?
        {
            continue;
        }
        if let Some(rows) = table_value_mut(node, &field) {
            assign_row_ids(rows, previous_value, renumber)?;
        }
    }
    Ok(())
}

/// Give row ids and positions to the table values `target` adds or changes
/// relative to `base`, in place.
///
/// Afterwards the write passes the table rules: tables of new nodes get ids,
/// a changed table keeps the ids of rows it still holds, and a table equal to
/// the stored one is left as it is, ids or not.
///
/// # Errors
///
/// A compared row holds a number that is not finite.
pub fn assign_changed_table_row_ids(
    base: &AnyValue,
    target: &mut AnyValue,
    renumber: Renumber,
) -> Result<()> {
    let mut stored: HashMap<&str, &AnyValue> = HashMap::new();
    for node in base
        .get("nodes")
        .and_then(AnyValue::as_array)
        .into_iter()
        .flatten()
    {
        if let Some(id) = node.get("id").and_then(AnyValue::as_str) {
            stored.entry(id).or_insert(node);
        }
    }
    for node in target
        .get_mut("nodes")
        .and_then(AnyValue::as_array_mut)
        .into_iter()
        .flatten()
    {
        if !node.is_object() {
            continue;
        }
        let previous = node
            .get("id")
            .and_then(AnyValue::as_str)
            .and_then(|id| stored.get(id))
            .copied();
        assign_changed_node_table_row_ids(node, previous, renumber)?;
    }
    Ok(())
}

/// Rows appended after `rows`, each with a new `__id__` and a `__pos__` one past
/// the last position. Keys the new rows carried (a duplicated row's) are
/// replaced. `rows` first gets ids and positions where it lacks them.
///
/// # Errors
///
/// A compared row holds a number that is not finite.
pub fn append_table_rows(rows: &mut Vec<AnyValue>, new_rows: &[AnyValue]) -> Result<()> {
    if !has_table_row_ids(rows) {
        assign_row_ids(rows, None, Renumber::WhenNoRoom)?;
    }
    let (id_key, position_key) = (row_id_key(), row_position_key());
    let mut used: HashSet<String> = rows
        .iter()
        .filter_map(|row| row.non_empty_str(id_key).map(str::to_owned))
        .collect();
    let mut last = rows
        .iter()
        .filter_map(|row| {
            row.get(position_key)
                .and_then(|value| Position::try_from(value).ok())
        })
        .map(|position| position.value)
        .fold(0.0, f64::max);
    for row in new_rows {
        let mut fresh = without_row_keys(row);
        let id = unused_id(&used, new_table_row_id);
        used.insert(id.clone());
        last = last.floor() + 1.0;
        if let Some(fresh) = fresh.as_object_mut() {
            fresh.insert(id_key.to_owned(), AnyValue::from(id));
            fresh.insert(position_key.to_owned(), Position::integer(last).to_value());
        }
        rows.push(fresh);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::json;

    #[test]
    fn row_matching_uses_canonical_content_and_previous_order() {
        let previous = json!([
            {"__id__":"first", "__pos__":1, "v":{"x":1,"y":-0.0}},
            {"__id__":"second", "__pos__":2, "v":{"y":0,"x":1.0}},
            {"__id__":"large", "__pos__":3, "v":9_007_199_254_740_993_u64}
        ]);
        let mut rows = vec![
            json!({"v":{"y":0.0,"x":1}}),
            json!({"v":{"x":1.0,"y":0}}),
            json!({"v":9_007_199_254_740_992_u64}),
        ];
        match_row_ids(&mut rows, Some(&previous)).unwrap();
        for (row, id) in rows.iter().zip(["first", "second", "large"]) {
            assert_eq!(row["__id__"].as_str(), Some(id));
        }
        assert_eq!(rows[0]["__pos__"], json!(1));
        assert_eq!(rows[1]["__pos__"], json!(2));
    }

    #[test]
    fn row_matching_reserves_existing_ids_and_keeps_nested_metadata() {
        let previous = json!([
            {"__id__":"reserved", "__pos__":1, "v":{"__id__":"nested-a"}},
            {"__id__":"other", "__pos__":2, "v":{"__id__":"nested-a"}},
            {"__id__":"different", "__pos__":3, "v":{"__id__":"nested-b"}}
        ]);
        let mut rows = vec![
            json!({"__id__":"reserved", "v":0}),
            json!({"v":{"__id__":"nested-a"}}),
            json!({"v":{"__id__":"nested-b"},"__pos__":9}),
        ];
        match_row_ids(&mut rows, Some(&previous)).unwrap();
        assert_eq!(rows[1]["__id__"], json!("other"));
        assert_eq!(rows[2]["__id__"], json!("different"));
        assert_eq!(rows[2]["__pos__"], json!(9));
    }

    #[test]
    fn fingerprint_collisions_still_require_equal_content() {
        let different = json!({"__id__":"wrong", "v":1});
        let equal = json!({"__id__":"right", "v":2});
        let mut bucket = VecDeque::from([&different, &equal]);
        let row = json!({"v":2.0});
        assert_eq!(
            take_matching_row(&mut bucket, &row, &HashSet::new()).unwrap(),
            Some(&equal)
        );
        assert_eq!(bucket, VecDeque::from([&different]));
    }

    #[test]
    fn an_unused_invalid_candidate_does_not_change_short_circuit_errors() {
        let previous: AnyValue =
            serde_json::from_str(r#"[{"__id__":"ok","v":1},{"__id__":"bad","v":1e400}]"#).unwrap();
        let mut rows = vec![json!({"v":1})];
        match_row_ids(&mut rows, Some(&previous)).unwrap();
        assert_eq!(rows[0]["__id__"], json!("ok"));
        let mut rows: Vec<AnyValue> = serde_json::from_str(r#"[{"v":1e400}]"#).unwrap();
        assert!(match_row_ids(&mut rows, Some(&previous)).is_err());
    }

    #[test]
    fn equal_rows_claim_each_previous_id_only_once() {
        let previous = AnyValue::Array(
            (0..2000)
                .map(|i| json!({"__id__":i.to_string(),"__pos__":i,"v":1}))
                .collect(),
        );
        let mut rows = vec![json!({"v":1}); 2000];
        match_row_ids(&mut rows, Some(&previous)).unwrap();
        for (i, row) in rows.iter().enumerate() {
            assert_eq!(row["__id__"], json!(i.to_string()));
        }
    }
}
