//! Keyed lists, indexed by item key.
//!
//! Outputs, tool actions and table rows are lists whose items carry a key: an
//! output's `name`, a tool action's first tag, a row's `__id__`. A write finds
//! its item through an index instead of scanning the list, and building the
//! index checks the list once: every item has a key, no key repeats, and
//! every table row carries a numeric `__pos__`.
//!
//! Natural lists keep the order writes leave them in. A table's order is its
//! rows' `(__pos__, __id__)`, not their places in the array: readers sort rows when
//! they strip the row keys, so the engine never sorts a table. A new row is
//! appended, and the last row moves into a deleted row's place.

use std::collections::{HashMap, HashSet};

use serde_json::Value;

use crate::ops::canonical::{
    as_double, is_finite_number, is_integer_text, is_row_position, ordered_rows, values_equal,
};
use crate::ops::entry::EntryExt;
use crate::ops::error::{Result, bail, invalid, quoted};
use crate::ops::ids::{new_table_row_id, unused_id};
use crate::ops::schema::{KeyedList, ListKind, NODE_SCHEMA, field_value_path};

/// The array index of every item of one keyed list, by key.
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
                bail!("{context}: two items have the key {}", quoted(key));
            }
            index.require_position(item, context)?;
            index.slots.insert(key.to_owned(), slot);
        }
        Ok(index)
    }

    /// The array index of the item with `key`.
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
            _ => Err(invalid!(
                "{context}: every item of this list needs a non-empty string key"
            )),
        }
    }

    /// Check that an item of a table carries a finite numeric position. An
    /// item of a natural list has no position, so it always passes.
    ///
    /// # Errors
    ///
    /// The row's position is missing, not a number, or not finite.
    pub fn require_position(&self, row: &Value, context: &str) -> Result<()> {
        match self.keyed.position.as_deref() {
            Some(key) if !row.get(key).is_some_and(is_row_position) => Err(invalid!(
                "{context}: a table row's {key} must be a finite number"
            )),
            _ => Ok(()),
        }
    }

    /// Append an item whose key is not in the list yet.
    pub(crate) fn add(&mut self, items: &mut Vec<Value>, item: Value, context: &str) -> Result<()> {
        let key = self.require_key(&item, context)?.to_owned();
        self.require_position(&item, context)?;
        self.slots.insert(key, items.len());
        items.push(item);
        Ok(())
    }

    /// Remove the item with `key` and say how it left, or `None` when no item has it.
    pub(crate) fn remove(&mut self, items: &mut Vec<Value>, key: &str) -> Option<(Value, Removal)> {
        let slot = self.slots.remove(key)?;
        if self.keyed.kind == ListKind::Natural {
            // Natural lists are short (a component's outputs or tool actions), and their order is kept.
            let item = items.remove(slot);
            for later in self.slots.values_mut() {
                if *later > slot {
                    *later -= 1;
                }
            }
            return Some((item, Removal::Shifted { slot }));
        }
        let item = items.swap_remove(slot);
        if let Some(moved) = items.get(slot)
            && let Some(moved_key) = self.keyed.key_of(moved)
        {
            self.slots.insert(moved_key.to_owned(), slot);
        }
        Some((item, Removal::Swapped { slot }))
    }

    /// Replace the item at `slot` by `item`, which carries the same key, and return the old item.
    pub(crate) fn replace(
        &self,
        items: &mut [Value],
        slot: usize,
        item: Value,
        context: &str,
    ) -> Result<Value> {
        self.require_position(&item, context)?;
        Ok(std::mem::replace(&mut items[slot], item))
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
    /// Renumber the table `1..n` in its stored order when a gap has no room left.
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
fn without_row_keys(row: &Value) -> Value {
    match row {
        Value::Object(map) => Value::Object(
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
pub fn strip_row_keys(rows: &Value) -> Value {
    match rows {
        Value::Array(rows) => Value::Array(
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
pub fn table_fields(node: &Value) -> Vec<String> {
    let Some(template) = node.template() else {
        return Vec::new();
    };
    template
        .iter()
        .filter(|(name, field)| {
            field.get("value").is_some_and(Value::is_array)
                && NODE_SCHEMA.is_table_at(node, &field_value_path(name))
        })
        .map(|(name, _)| name.clone())
        .collect()
}

fn table_value_mut<'n>(node: &'n mut Value, field: &str) -> Option<&'n mut Vec<Value>> {
    node.get_mut("data")?
        .get_mut("node")?
        .get_mut("template")?
        .get_mut(field)?
        .get_mut("value")?
        .as_array_mut()
}

/// Order the rows of every table value of a node and strip `__id__` and `__pos__`, in place.
pub fn strip_node_table_row_keys(node: &mut Value) {
    for field in table_fields(node) {
        if let Some(rows) = table_value_mut(node, &field) {
            let stripped = strip_row_keys(&Value::Array(std::mem::take(rows)));
            if let Value::Array(stripped) = stripped {
                *rows = stripped;
            }
        }
    }
}

/// Order and strip the table values of every node of a flow, in place.
pub fn strip_flow_table_row_keys(flow: &mut Value) {
    for node in flow
        .get_mut("nodes")
        .and_then(Value::as_array_mut)
        .into_iter()
        .flatten()
    {
        strip_node_table_row_keys(node);
    }
}

/// Whether every row is an object with a unique `__id__` and a numeric `__pos__`:
/// the shape the server accepts.
#[must_use]
pub fn has_table_row_ids(rows: &[Value]) -> bool {
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
    rows: &mut [Value],
    previous: Option<&Value>,
    renumber: Renumber,
) -> Result<()> {
    if !rows.iter().all(Value::is_object) {
        return Ok(());
    }
    match_row_ids(rows, previous)?;
    fill_missing_positions(rows, renumber);
    Ok(())
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
pub fn match_row_ids(rows: &mut [Value], previous: Option<&Value>) -> Result<()> {
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
    let candidates: Vec<&Value> = previous
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter(|row| row.is_object() && row.non_empty_str(id_key).is_some())
        .collect();
    for index in need_id {
        let content = without_row_keys(&rows[index]);
        let mut matched = None;
        for candidate in &candidates {
            let id = candidate.non_empty_str(id_key).unwrap_or_default();
            if !used.contains(id) && values_equal(&without_row_keys(candidate), &content)? {
                matched = Some(*candidate);
                break;
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
            row.insert(id_key.to_owned(), Value::String(new_id));
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
impl TryFrom<&Value> for Position {
    type Error = ();

    fn try_from(value: &Value) -> Result<Self, ()> {
        match value {
            Value::Number(number) if is_finite_number(number) => Ok(Self {
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
    fn to_value(self) -> Value {
        let whole = self.value as i64;
        if self.integer && whole as f64 == self.value {
            Value::from(whole)
        } else {
            serde_json::Number::from_f64(self.value).map_or(Value::Null, Value::Number)
        }
    }
}

/// Give each row without a valid position one that keeps it where it is stored, in place.
///
/// Positioned rows keep their positions. A run of rows without one is spread
/// evenly between the positioned rows stored before and after it, or placed
/// one apart before the first or after the last; when those neighbours are
/// out of order, the run follows the one before it. A table with no
/// positions at all gets `1..n`. With [`Renumber::WhenNoRoom`], a gap that
/// has no room left for its run renumbers the whole table `1..n` in stored
/// order instead. Returns the indexes of the rows it gave a position.
pub fn fill_missing_positions(rows: &mut [Value], renumber: Renumber) -> Vec<usize> {
    let key = row_position_key();
    let position_at = |rows: &[Value], index: usize| {
        rows[index]
            .get(key)
            .and_then(|value| Position::try_from(value).ok())
    };
    let mut filled = Vec::new();
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
        if renumber == Renumber::WhenNoRoom && !fits_between(&positions, before, after) {
            for (slot, row) in rows.iter_mut().enumerate() {
                set_position(
                    row,
                    key,
                    Position::integer(f64::from(u32::try_from(slot + 1).unwrap_or(u32::MAX))),
                );
            }
            return (0..rows.len()).collect();
        }
        for (offset, position) in positions.into_iter().enumerate() {
            set_position(&mut rows[index + offset], key, position);
            filled.push(index + offset);
        }
        index = end;
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

fn set_position(row: &mut Value, key: &str, position: Position) {
    if let Some(row) = row.as_object_mut() {
        row.insert(key.to_owned(), position.to_value());
    }
}

/// Give every table value of a node being added row ids and positions, in place.
///
/// # Errors
///
/// A compared row holds a number that is not finite.
pub fn assign_table_row_ids(node: &mut Value, renumber: Renumber) -> Result<()> {
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
    node: &mut Value,
    previous: Option<&Value>,
    renumber: Renumber,
) -> Result<()> {
    let stored: HashMap<String, &Value> = previous
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
    base: &Value,
    target: &mut Value,
    renumber: Renumber,
) -> Result<()> {
    let mut stored: HashMap<&str, &Value> = HashMap::new();
    for node in base
        .get("nodes")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        if let Some(id) = node.get("id").and_then(Value::as_str) {
            stored.entry(id).or_insert(node);
        }
    }
    for node in target
        .get_mut("nodes")
        .and_then(Value::as_array_mut)
        .into_iter()
        .flatten()
    {
        if !node.is_object() {
            continue;
        }
        let previous = node
            .get("id")
            .and_then(Value::as_str)
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
pub fn append_table_rows(rows: &mut Vec<Value>, new_rows: &[Value]) -> Result<()> {
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
            fresh.insert(id_key.to_owned(), Value::String(id));
            fresh.insert(position_key.to_owned(), Position::integer(last).to_value());
        }
        rows.push(fresh);
    }
    Ok(())
}
