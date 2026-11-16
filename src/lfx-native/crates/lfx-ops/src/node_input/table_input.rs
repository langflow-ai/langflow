//! Table rows: their `__id__` and `__pos__` keys, which the engine owns.
//!
//! The editor and the server call these before they save a table, and to
//! read or export one.

use std::collections::VecDeque;
use std::collections::hash_map::RandomState;
use std::hash::{BuildHasher, Hash, Hasher};

use crate::collection::hash_map::{HashMap, HashSet};
use crate::json::FlowValue;

use crate::compare::values_equal;
use crate::flow::model::EntryExt;
use crate::json::NonFinite;
use crate::json::{as_double, is_row_position};

type Result<T, E = NonFinite> = std::result::Result<T, E>;
use crate::flow::id::{new_table_row_id, unused_id};
use crate::flow::list::{Position, Renumber, fill_missing_positions, item_order};
use crate::flow::model::{FLOW_MODEL, field_value_path};

fn row_id_key() -> &'static str {
    &FLOW_MODEL.table_input_keys.id
}

fn row_position_key() -> &'static str {
    &FLOW_MODEL.table_input_keys.position
}

fn is_row_key(key: &str) -> bool {
    key == row_id_key() || key == row_position_key()
}

/// A row without `__id__` and `__pos__`. A value that is not an object stays as is.
fn without_row_keys(row: &FlowValue) -> FlowValue {
    match row {
        FlowValue::Object(map) => FlowValue::Object(
            map.iter()
                .filter(|(key, _)| !is_row_key(key))
                .map(|(key, value)| (key.clone(), value.clone()))
                .collect(),
        ),
        other => other.clone(),
    }
}

/// Table rows in order, without `__id__` and `__pos__`. A value that is not a list stays as is.
#[must_use]
pub fn strip_row_keys(rows: &FlowValue) -> FlowValue {
    match rows {
        FlowValue::Array(rows) => FlowValue::Array(
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
pub fn table_fields(node: &FlowValue) -> Vec<String> {
    let Some(template) = node.template() else {
        return Vec::new();
    };
    template
        .iter()
        .filter(|(name, field)| {
            field.get("value").is_some_and(FlowValue::is_array)
                && FLOW_MODEL.is_table_input_at(node, &field_value_path(name))
        })
        .map(|(name, _)| name.to_string())
        .collect()
}

fn table_value_mut<'n>(node: &'n mut FlowValue, field: &str) -> Option<&'n mut Vec<FlowValue>> {
    node.get_mut("data")?
        .get_mut("node")?
        .get_mut("template")?
        .get_mut(field)?
        .get_mut("value")?
        .as_array_mut()
}

/// Order the rows of every table value of a node and strip `__id__` and `__pos__`, in place.
pub fn strip_node_table_row_keys(node: &mut FlowValue) {
    for field in table_fields(node) {
        if let Some(rows) = table_value_mut(node, &field) {
            let stripped = strip_row_keys(&FlowValue::Array(std::mem::take(rows)));
            if let FlowValue::Array(stripped) = stripped {
                *rows = stripped;
            }
        }
    }
}

/// Order and strip the table values of every node of a flow, in place.
pub fn strip_flow_table_row_keys(flow: &mut FlowValue) {
    for node in flow
        .get_mut("nodes")
        .and_then(FlowValue::as_array_mut)
        .into_iter()
        .flatten()
    {
        strip_node_table_row_keys(node);
    }
}

/// Whether each row is an object with a unique `__id__` and a numeric `__pos__`.
#[must_use]
pub fn has_table_row_ids(rows: &[FlowValue]) -> bool {
    let mut seen = HashSet::default();
    rows.iter().all(|row| {
        row.non_empty_str(row_id_key())
            .is_some_and(|id| seen.insert(id))
            && row.get(row_position_key()).is_some_and(is_row_position)
    })
}

/// Give one table's rows ids and positions, in place ([`match_row_ids`],
/// [`fill_missing_positions`]). A table with a row that is not an object stays as is.
///
/// # Errors
///
/// A compared row holds a number that is not finite.
pub fn assign_row_ids(
    rows: &mut [FlowValue],
    previous: Option<&FlowValue>,
    renumber: Renumber,
) -> Result<()> {
    if !rows.iter().all(FlowValue::is_object) {
        return Ok(());
    }
    match_row_ids(rows, previous)?;
    fill_missing_positions(&FLOW_MODEL.table_input, rows, renumber);
    Ok(())
}

/// Hash a value in its canonical form, without copying it.
/// Example: `{"x":1,"y":-0.0}` and `{"y":0,"x":1.0}` have the same hash.
/// With `row`, the row keys at the top level do not count.
fn content_hash(value: &FlowValue, state: &RandomState, row: bool) -> Result<u64> {
    let mut hash = state.build_hasher();
    std::mem::discriminant(value).hash(&mut hash);
    match value {
        FlowValue::Null => {}
        FlowValue::Bool(value) => value.hash(&mut hash),
        FlowValue::String(value) => value.hash(&mut hash),
        FlowValue::Number(value) => {
            let value = as_double(value);
            if !value.is_finite() {
                return Err(NonFinite);
            }
            // Both zero signs have the same canonical form.
            (if value == 0.0 { 0 } else { value.to_bits() }).hash(&mut hash);
        }
        FlowValue::Array(values) => {
            values.len().hash(&mut hash);
            for value in values {
                content_hash(value, state, false)?.hash(&mut hash);
            }
        }
        FlowValue::Object(values) => {
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

fn row_contents_equal(left: &FlowValue, right: &FlowValue) -> Result<bool> {
    let (Some(left), Some(right)) = (left.as_object(), right.as_object()) else {
        return values_equal(left, right);
    };
    let visible = |map: &crate::json::FlowObj| map.keys().filter(|key| !is_row_key(key)).count();
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

/// Remove and return the first row of `bucket` that equals `row`.
/// It also drops rows whose id is in `used`. A hash collision gives no match.
fn take_matching_row<'a>(
    bucket: &mut VecDeque<&'a FlowValue>,
    row: &FlowValue,
    used: &HashSet<String>,
) -> Result<Option<&'a FlowValue>> {
    let mut item_index = 0;
    while item_index < bucket.len() {
        if used.contains(
            bucket[item_index]
                .non_empty_str(row_id_key())
                .unwrap_or_default(),
        ) {
            bucket.remove(item_index);
        } else if row_contents_equal(bucket[item_index], row)? {
            return Ok(bucket.remove(item_index));
        } else {
            item_index += 1;
        }
    }
    Ok(None)
}

/// Give each row without a unique `__id__` one, in place.
///
/// A row equal to an unmatched row of `previous` takes its id, and its position
/// if the row has none. Other rows get a new random id.
///
/// # Errors
///
/// A compared row holds a number that is not finite.
pub fn match_row_ids(rows: &mut [FlowValue], previous: Option<&FlowValue>) -> Result<()> {
    let (id_key, position_key) = (row_id_key(), row_position_key());
    let mut used: HashSet<String> = HashSet::default();
    let mut need_id = Vec::new();
    for (index, row) in rows.iter().enumerate() {
        match row.non_empty_str(id_key) {
            Some(id) if !used.contains(id) => {
                used.insert(id.to_owned());
            }
            _ => need_id.push(index),
        }
    }
    if need_id.is_empty() {
        return Ok(());
    }
    let candidates: Vec<&FlowValue> = previous
        .and_then(FlowValue::as_array)
        .into_iter()
        .flatten()
        .filter(|row| row.is_object() && row.non_empty_str(id_key).is_some())
        .collect();
    let state = RandomState::new();
    let mut by_content: HashMap<u64, VecDeque<&FlowValue>> = HashMap::default();
    // A candidate with a number that is not finite fails to hash. Then the
    // rows are compared one by one, so the error comes only if that candidate is reached.
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
            row.insert(id_key.to_owned(), FlowValue::from(new_id));
        }
    }
    Ok(())
}

/// Give each table of a new node row ids and positions, in place.
///
/// # Errors
///
/// A compared row holds a number that is not finite.
pub fn assign_table_row_ids(node: &mut FlowValue, renumber: Renumber) -> Result<()> {
    for field in table_fields(node) {
        if let Some(rows) = table_value_mut(node, &field) {
            assign_row_ids(rows, None, renumber)?;
        }
    }
    Ok(())
}

/// Give row ids and positions to the tables of `node` that differ from `previous`, in place.
///
/// A table equal to the stored one stays as is, so opening a flow does not rewrite it.
///
/// # Errors
///
/// A compared row holds a number that is not finite.
pub fn assign_changed_node_table_row_ids(
    node: &mut FlowValue,
    previous: Option<&FlowValue>,
    renumber: Renumber,
) -> Result<()> {
    let stored: HashMap<String, &FlowValue> = previous
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

/// Give row ids and positions to the tables of `target` that differ from `base`, in place.
///
/// # Errors
///
/// A compared row holds a number that is not finite.
pub fn assign_changed_table_row_ids(
    base: &FlowValue,
    target: &mut FlowValue,
    renumber: Renumber,
) -> Result<()> {
    let mut stored: HashMap<&str, &FlowValue> = HashMap::default();
    for node in base
        .get("nodes")
        .and_then(FlowValue::as_array)
        .into_iter()
        .flatten()
    {
        if let Some(id) = node.get("id").and_then(FlowValue::as_str) {
            stored.entry(id).or_insert(node);
        }
    }
    for node in target
        .get_mut("nodes")
        .and_then(FlowValue::as_array_mut)
        .into_iter()
        .flatten()
    {
        if !node.is_object() {
            continue;
        }
        let previous = node
            .get("id")
            .and_then(FlowValue::as_str)
            .and_then(|id| stored.get(id))
            .copied();
        assign_changed_node_table_row_ids(node, previous, renumber)?;
    }
    Ok(())
}

/// Append `new_rows`, each with a new `__id__` and the next whole `__pos__`.
/// Example: after rows at 1 and 2.5, a new row gets 3.
///
/// # Errors
///
/// A compared row holds a number that is not finite.
pub fn append_table_rows(rows: &mut Vec<FlowValue>, new_rows: &[FlowValue]) -> Result<()> {
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
            fresh.insert(id_key.to_owned(), FlowValue::from(id));
            fresh.insert(position_key.to_owned(), Position::integer(last).to_value());
        }
        rows.push(fresh);
    }
    Ok(())
}

/// A table's rows in order: by `(__pos__, __id__)`, or as stored for a legacy table without them.
///
/// The order is the editor's: positions as doubles, ids by UTF-16 code units.
#[must_use]
pub fn ordered_rows(rows: &[FlowValue]) -> Vec<&FlowValue> {
    row_order(rows)
        .into_iter()
        .map(|item_index| &rows[item_index])
        .collect()
}

/// The array indexes of a table's rows, in the order [`ordered_rows`] gives.
pub(crate) fn row_order(rows: &[FlowValue]) -> Vec<usize> {
    item_order(&FLOW_MODEL.table_input, rows)
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
            take_matching_row(&mut bucket, &row, &HashSet::default()).unwrap(),
            Some(&equal)
        );
        assert_eq!(bucket, VecDeque::from([&different]));
    }

    #[test]
    fn an_unused_invalid_candidate_does_not_change_short_circuit_errors() {
        let previous: FlowValue =
            serde_json::from_str(r#"[{"__id__":"ok","v":1},{"__id__":"bad","v":1e400}]"#).unwrap();
        let mut rows = vec![json!({"v":1})];
        match_row_ids(&mut rows, Some(&previous)).unwrap();
        assert_eq!(rows[0]["__id__"], json!("ok"));
        let mut rows: Vec<FlowValue> = serde_json::from_str(r#"[{"v":1e400}]"#).unwrap();
        assert!(match_row_ids(&mut rows, Some(&previous)).is_err());
    }

    #[test]
    fn equal_rows_claim_each_previous_id_only_once() {
        let previous = FlowValue::Array(
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
