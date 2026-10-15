//! The node schema: where the units, view state and keyed lists of a flow are.
//!
//! `node_schema.json` is the single description of where things are in a node,
//! so no code hard-codes those paths. It is embedded in the crate and read once.

use std::collections::HashSet;
use std::sync::LazyLock;

use serde_json::Value;

/// The schema file, as shipped with the engine.
pub const NODE_SCHEMA_JSON: &str = include_str!("node_schema.json");

/// A path segment that matches any object key.
const WILDCARD: &str = "*";

/// How the items of a keyed list are addressed and ordered.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ListKind {
    /// Outputs and tool actions: selected with `{"key": ...}`, in the order
    /// writes leave them.
    Natural,
    /// Table rows: selected with `{"id": ...}`, ordered by their numeric
    /// position, then id. Their place in the array is not state.
    Table,
}

/// One step of the path to an item's key inside the item.
#[derive(Debug, Clone, PartialEq, Eq)]
enum KeyPart {
    Key(String),
    Index(usize),
}

/// A list whose items are addressed by a key instead of an index.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KeyedList {
    /// How items are addressed and ordered.
    pub kind: ListKind,
    key: Vec<KeyPart>,
    /// The key of a table row's position; `None` for a natural list.
    pub position: Option<String>,
}

impl KeyedList {
    /// The selector key that addresses an item: `"id"` for tables, `"key"` otherwise.
    #[must_use]
    pub fn selector_name(&self) -> &'static str {
        match self.kind {
            ListKind::Table => "id",
            ListKind::Natural => "key",
        }
    }

    /// An item's key, or `None` when the item has no string key.
    #[must_use]
    pub fn key_of<'a>(&self, item: &'a Value) -> Option<&'a str> {
        let mut value = item;
        for part in &self.key {
            value = match part {
                KeyPart::Key(key) => value.as_object()?.get(key)?,
                KeyPart::Index(index) => value.as_array()?.get(*index)?,
            };
        }
        value.as_str()
    }

    /// The key that holds an item's key, when that is one object key (a table row's `_id`).
    #[must_use]
    pub fn id_key(&self) -> Option<&str> {
        match self.key.as_slice() {
            [KeyPart::Key(key)] => Some(key),
            _ => None,
        }
    }
}

/// The parsed `node_schema.json`.
#[derive(Debug)]
pub struct NodeSchema {
    /// The schema file's version.
    pub version: u64,
    /// Top-level flow keys that are view state.
    pub flow_view_state: HashSet<String>,
    /// Node keys that are view state.
    pub node_view_state: HashSet<String>,
    /// Keys of `data.node` that are view state.
    pub node_data_view_state: HashSet<String>,
    /// Template keys that are view state.
    pub template_view_state: HashSet<String>,
    /// Template field keys that are display only.
    pub field_view_state: HashSet<String>,
    /// Edge keys that are view state.
    pub edge_view_state: HashSet<String>,
    /// The keys of a template field's value unit, written together.
    pub value_unit: Vec<String>,
    /// Template field keys that are each a value of their own.
    pub toggles: Vec<String>,
    /// Node paths the diff splits into their keys; any other value is written whole.
    pub recursed_paths: Vec<Vec<String>>,
    natural_lists: Vec<(Vec<String>, KeyedList)>,
    table_path: Vec<String>,
    table_when_field: Vec<serde_json::Map<String, Value>>,
    /// The table list, which every table field's value is.
    pub table: KeyedList,
}

/// The engine's node schema.
pub static NODE_SCHEMA: LazyLock<NodeSchema> = LazyLock::new(|| {
    let raw: Value =
        serde_json::from_str(NODE_SCHEMA_JSON).expect("node_schema.json is valid JSON");
    NodeSchema::from_json(&raw).expect("node_schema.json has the expected shape")
});

impl NodeSchema {
    fn from_json(raw: &Value) -> Option<Self> {
        let view_state = raw.get("view_state")?;
        let keyed_lists = raw.get("keyed_lists")?;
        let tables = keyed_lists.get("tables")?;
        let strings = |value: &Value| -> Option<Vec<String>> {
            value
                .as_array()?
                .iter()
                .map(|item| item.as_str().map(str::to_owned))
                .collect()
        };
        let set = |value: &Value| strings(value).map(|items| items.into_iter().collect());
        let paths = |value: &Value| -> Option<Vec<Vec<String>>> {
            value.as_array()?.iter().map(strings).collect()
        };
        let node_data_view_state = paths(view_state.get("node_paths")?)?
            .into_iter()
            .filter_map(|path| match path.as_slice() {
                [data, node, key] if data == "data" && node == "node" => Some(key.clone()),
                _ => None,
            })
            .collect();
        let natural_lists = keyed_lists
            .get("natural")?
            .as_array()?
            .iter()
            .map(|entry| {
                let path = strings(entry.get("path")?)?;
                let key = entry
                    .get("key")?
                    .as_array()?
                    .iter()
                    .map(|part| match part {
                        Value::String(key) => Some(KeyPart::Key(key.clone())),
                        Value::Number(index) => index
                            .as_u64()
                            .and_then(|index| usize::try_from(index).ok())
                            .map(KeyPart::Index),
                        _ => None,
                    })
                    .collect::<Option<Vec<_>>>()?;
                Some((
                    path,
                    KeyedList {
                        kind: ListKind::Natural,
                        key,
                        position: None,
                    },
                ))
            })
            .collect::<Option<Vec<_>>>()?;
        Some(Self {
            version: raw.get("version")?.as_u64()?,
            flow_view_state: set(view_state.get("flow")?)?,
            node_view_state: set(view_state.get("node")?)?,
            node_data_view_state,
            template_view_state: set(view_state.get("template")?)?,
            field_view_state: set(view_state.get("template_field")?)?,
            edge_view_state: set(view_state.get("edge")?)?,
            value_unit: strings(raw.get("field_units")?.get("value")?)?,
            toggles: strings(raw.get("field_units")?.get("toggles")?)?,
            recursed_paths: paths(raw.get("whole_values")?.get("recursed")?)?,
            natural_lists,
            table_path: strings(tables.get("path")?)?,
            table_when_field: tables
                .get("when_field")?
                .as_array()?
                .iter()
                .map(|condition| condition.as_object().cloned())
                .collect::<Option<Vec<_>>>()?,
            table: KeyedList {
                kind: ListKind::Table,
                key: vec![KeyPart::Key(tables.get("id")?.as_str()?.to_owned())],
                position: Some(tables.get("position")?.as_str()?.to_owned()),
            },
        })
    }

    /// The keyed list a node holds at `path`, or `None` if the schema declares none there.
    ///
    /// A table is declared at every template field's `value` whose field
    /// matches one of the schema's `when_field` conditions.
    #[must_use]
    pub fn keyed_list_at<S: AsRef<str>>(&self, node: &Value, path: &[S]) -> Option<&KeyedList> {
        if let Some((_, keyed)) = self
            .natural_lists
            .iter()
            .find(|(list_path, _)| same_path(list_path, path))
        {
            return Some(keyed);
        }
        if path.len() != self.table_path.len() {
            return None;
        }
        let mut wildcard = None;
        for (index, (part, pattern)) in path.iter().zip(&self.table_path).enumerate() {
            if pattern == WILDCARD {
                wildcard = Some(index);
            } else if part.as_ref() != pattern {
                return None;
            }
        }
        let Some(wildcard) = wildcard else {
            return Some(&self.table);
        };
        let mut field = node;
        for part in &path[..=wildcard] {
            field = field.as_object()?.get(part.as_ref())?;
        }
        let field = field.as_object()?;
        self.table_when_field
            .iter()
            .any(|condition| {
                condition
                    .iter()
                    .all(|(key, value)| field.get(key) == Some(value))
            })
            .then_some(&self.table)
    }

    /// Whether the list at `path` of `node` is a table.
    #[must_use]
    pub fn is_table_at<S: AsRef<str>>(&self, node: &Value, path: &[S]) -> bool {
        self.keyed_list_at(node, path)
            .is_some_and(|keyed| keyed.kind == ListKind::Table)
    }
}

fn same_path<S: AsRef<str>>(left: &[String], right: &[S]) -> bool {
    left.len() == right.len() && left.iter().zip(right).all(|(a, b)| a == b.as_ref())
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    #[test]
    fn the_embedded_schema_loads() {
        assert_eq!(NODE_SCHEMA.version, 1);
        assert!(NODE_SCHEMA.node_data_view_state.contains("last_updated"));
        assert_eq!(NODE_SCHEMA.table.id_key(), Some("_id"));
    }

    #[test]
    fn natural_lists_are_found_by_path() {
        let outputs = NODE_SCHEMA
            .keyed_list_at(&json!({}), &["data", "node", "outputs"])
            .unwrap();
        assert_eq!(outputs.kind, ListKind::Natural);
        assert_eq!(outputs.key_of(&json!({"name": "out"})), Some("out"));

        let tools = NODE_SCHEMA
            .keyed_list_at(
                &json!({}),
                &["data", "node", "template", "tools_metadata", "value"],
            )
            .unwrap();
        assert_eq!(
            tools.key_of(&json!({"tags": ["first", "second"]})),
            Some("first")
        );
        assert_eq!(tools.key_of(&json!({"tags": []})), None);
    }

    #[test]
    fn tables_depend_on_the_field() {
        let node = json!({"data": {"node": {"template": {
            "rows": {"type": "table", "value": []},
            "legacy": {"_input_type": "TableInput", "value": []},
            "text": {"type": "str", "value": []},
        }}}});
        let path = |field: &str| ["data", "node", "template", field, "value"].map(str::to_owned);
        assert!(NODE_SCHEMA.is_table_at(&node, &path("rows")));
        assert!(NODE_SCHEMA.is_table_at(&node, &path("legacy")));
        assert!(!NODE_SCHEMA.is_table_at(&node, &path("text")));
        assert!(!NODE_SCHEMA.is_table_at(&node, &path("missing")));
    }
}
