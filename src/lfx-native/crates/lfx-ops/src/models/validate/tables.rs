//! The rules for the table rows and keyed list positions a write adds or changes.

use crate::data::maps::{HashMap, HashSet};
use crate::data::value::{AnyMap, AnyValue};

use crate::models::canonical::{is_row_position, values_equal};
use crate::models::entry::EntryExt;
use crate::models::error::Result;
use crate::models::schema::{NODE_SCHEMA, field_value_path};
use crate::models::validate::{GraphPath, PathPart, Violation, ViolationCode};
use crate::models::validate::{list, path_of};

/// A table value a write adds or changes, where it is, and its field's column definition.
#[derive(Debug)]
pub(crate) struct ChangedTable<'a> {
    /// Where the table value is: `nodes.<index>.data.node.template.<field>.value`.
    pub path: GraphPath,
    /// `None` when the node has no string id.
    pub node_id: Option<&'a str>,
    /// The name of the template field that holds the table.
    pub field: &'a str,
    pub rows: &'a [AnyValue],
    /// The field's `table_schema`, which declares its columns.
    pub table_schema: Option<&'a AnyValue>,
}

/// An outputs or tool action list a write adds or changes, and where it is.
#[derive(Debug)]
pub(crate) struct ChangedList<'a> {
    /// Where the list is, for example `nodes.<index>.data.node.outputs`.
    pub path: GraphPath,
    pub items: &'a [AnyValue],
}

/// The outputs and tool action lists that `target` changes relative to `base`, in graph order.
pub(crate) fn changed_keyed_lists<'a>(
    base: &AnyValue,
    target: &'a AnyValue,
) -> Result<Vec<ChangedList<'a>>> {
    let stored: HashMap<&str, &AnyValue> = list(base, "nodes")
        .iter()
        .filter_map(|node| Some((node.get("id")?.as_str()?, node)))
        .collect();
    let mut lists = Vec::new();
    for (index, node) in list(target, "nodes").iter().enumerate() {
        let stored_node = node
            .get("id")
            .and_then(AnyValue::as_str)
            .and_then(|id| stored.get(id));
        for (list_path, _) in NODE_SCHEMA.natural_lists() {
            let Some(value) = list_path.iter().try_fold(node, |value, key| value.get(key)) else {
                continue;
            };
            let AnyValue::Array(items) = value else {
                continue;
            };
            let stored_list = stored_node.and_then(|stored| {
                list_path
                    .iter()
                    .try_fold(*stored, |value, key| value.get(key))
            });
            if let Some(stored_list) = stored_list
                && values_equal(stored_list, value)?
            {
                continue;
            }
            let path = ["nodes".into(), index.into()]
                .into_iter()
                .chain(list_path.iter().map(|key| PathPart::from(key.as_str())))
                .collect();
            lists.push(ChangedList { path, items });
        }
    }
    Ok(lists)
}

/// A violation for each item without a finite `__pos__` in the outputs and
/// tool action lists that `target` changes relative to `base`.
pub(super) fn find_list_position_violations(
    base: &AnyValue,
    target: &AnyValue,
) -> Result<Vec<Violation>> {
    let position_key = &NODE_SCHEMA.table_keys.position;
    let mut violations = Vec::new();
    for changed in changed_keyed_lists(base, target)? {
        for (index, item) in changed.items.iter().enumerate() {
            if !item.get(position_key).is_some_and(is_row_position) {
                let mut item_path = changed.path.clone();
                item_path.extend([index.into(), position_key.as_str().into()]);
                violations.push(Violation::new(
                    ViolationCode::ListItemMissingPos,
                    item_path,
                    format!("list item must have a finite numeric {position_key}"),
                ));
            }
        }
    }
    Ok(violations)
}

/// The tables that `target` changes relative to `base`, in graph order.
pub(crate) fn changed_tables<'a>(
    base: &AnyValue,
    target: &'a AnyValue,
) -> Result<Vec<ChangedTable<'a>>> {
    let mut stored: HashMap<&str, &AnyMap> = HashMap::default();
    for node in list(base, "nodes") {
        if let (Some(template), Some(id)) =
            (node.template(), node.get("id").and_then(AnyValue::as_str))
        {
            stored.entry(id).or_insert(template);
        }
    }
    let mut tables = Vec::new();
    for (index, node) in list(target, "nodes").iter().enumerate() {
        let Some(fields) = node.template() else {
            continue;
        };
        let node_id = node.get("id").and_then(AnyValue::as_str);
        let stored_fields = node_id.and_then(|id| stored.get(id));
        for (name, field) in fields {
            let Some(AnyValue::Array(rows)) =
                field.as_object().and_then(|field| field.get("value"))
            else {
                continue;
            };
            // Tool actions are not a table, even under a table-typed field.
            if !NODE_SCHEMA.is_table_at(node, &field_value_path(name)) {
                continue;
            }
            let stored_value = stored_fields
                .and_then(|fields| fields.get(name))
                .and_then(AnyValue::as_object)
                .and_then(|field| field.get("value"));
            if let Some(stored_value) = stored_value
                && values_equal(stored_value, &field["value"])?
            {
                continue;
            }
            tables.push(ChangedTable {
                path: vec![
                    "nodes".into(),
                    index.into(),
                    "data".into(),
                    "node".into(),
                    "template".into(),
                    name.as_str().into(),
                    "value".into(),
                ],
                node_id,
                field: name,
                rows,
                table_schema: field.get("table_schema"),
            });
        }
    }
    Ok(tables)
}

/// The column and row rules broken by the tables that `target` changes relative to `base`.
pub(super) fn find_table_violations(base: &AnyValue, target: &AnyValue) -> Result<Vec<Violation>> {
    let mut violations = Vec::new();
    for table in changed_tables(base, target)? {
        if let Some(table_schema) = table.table_schema {
            let field_path = &table.path[..table.path.len() - 1];
            let schema_path = path_of(field_path, &["table_schema"]);
            violations.extend(table_column_violations(table_schema, &schema_path));
        }
        violations.extend(table_row_violations(table.rows, &table.path));
    }
    Ok(violations)
}

/// A violation for each column named after a row key.
/// `table_schema` is a list of columns, or an object with a `columns` list.
#[must_use]
fn table_column_violations(table_schema: &AnyValue, path: &[PathPart]) -> Vec<Violation> {
    let (columns, columns_path) = match table_schema {
        AnyValue::Object(schema) => (schema.get("columns"), path_of(path, &["columns"])),
        list => (Some(list), path.to_vec()),
    };
    let Some(AnyValue::Array(columns)) = columns else {
        return Vec::new();
    };
    let mut violations = Vec::new();
    for (index, column) in columns.iter().enumerate() {
        let Some(name) = column.get("name").and_then(AnyValue::as_str) else {
            continue;
        };
        if is_row_key(name) {
            let mut name_path = columns_path.clone();
            name_path.extend([index.into(), "name".into()]);
            violations.push(Violation::new(
                ViolationCode::TableColumnReserved,
                name_path,
                format!("table column must not be named {name}"),
            ));
        }
    }
    violations
}

/// Whether `name` is `__id__` or `__pos__`.
fn is_row_key(name: &str) -> bool {
    let keys = &NODE_SCHEMA.table_keys;
    name == keys.id || name == keys.position
}

/// The row rules one table value breaks.
#[must_use]
fn table_row_violations(rows: &[AnyValue], path: &[PathPart]) -> Vec<Violation> {
    let (id_key, position_key) = (&NODE_SCHEMA.table_keys.id, &NODE_SCHEMA.table_keys.position);
    let mut violations = Vec::new();
    let mut seen = HashSet::default();
    for (index, row) in rows.iter().enumerate() {
        let row_path: GraphPath = path.iter().cloned().chain([index.into()]).collect();
        let AnyValue::Object(row) = row else {
            violations.push(Violation::new(
                ViolationCode::TableRowNotObject,
                row_path,
                "table row must be an object",
            ));
            continue;
        };
        match row.non_empty_str(id_key) {
            None => violations.push(Violation::new(
                ViolationCode::TableRowIdMissing,
                path_of(&row_path, &[id_key]),
                format!("table row must have a non-empty string {id_key}"),
            )),
            Some(id) if !seen.insert(id) => violations.push(Violation::new(
                ViolationCode::TableRowIdDuplicate,
                path_of(&row_path, &[id_key]),
                "duplicate row id",
            )),
            Some(_) => {}
        }
        if !row.get(position_key).is_some_and(is_row_position) {
            violations.push(Violation::new(
                ViolationCode::TableRowPosInvalid,
                path_of(&row_path, &[position_key]),
                format!("table row must have a finite numeric {position_key}"),
            ));
        }
    }
    violations
}
