//! The node schema: where the units, view state and keyed lists of a flow are.
//!
//! `node_schema.json` is the single description of where things are in a node,
//! so no code hard-codes those paths. It is embedded in the crate and read once.

use std::borrow::Cow;
use std::sync::LazyLock;

use crate::value::{AnyMap, AnyValue};

use crate::ops::canonical::is_row_position;
use crate::ops::ops::{AsKey, Change, PathExt, Segment};
use crate::ops::state::resolve;
use crate::ops::validate::PathPart;

/// The schema file, as shipped with the engine.
pub const NODE_SCHEMA_JSON: &str = include_str!("node_schema.json");

/// A path segment that matches any object key.
const WILDCARD: &str = "*";

/// The path of a node's template.
pub const TEMPLATE_PATH: [&str; 3] = ["data", "node", "template"];
/// The path of a node's outputs.
pub const OUTPUTS_PATH: [&str; 3] = ["data", "node", "outputs"];
/// The paths of the objects every node carries for its whole lifetime:
/// `data`, `data.node` and `data.node.template`.
pub const NODE_OBJECT_PATHS: [&[&str]; 3] = [&["data"], &["data", "node"], &TEMPLATE_PATH];

/// The path of a template field's value.
#[must_use]
pub fn field_value_path(field: &str) -> [&str; 5] {
    ["data", "node", "template", field, "value"]
}

/// How the items of a keyed list are addressed. Every keyed list is ordered
/// by its items' numeric position, then key. Its array order is not state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ListKind {
    /// Outputs and tool actions: keyed by a field of their own.
    Natural,
    /// The rows of a table field: keyed by their `__id__`.
    Table,
}

/// A list whose items are addressed by a key instead of an index.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KeyedList {
    /// How items are addressed and ordered.
    pub kind: ListKind,
    /// The path from an item to its key.
    key: Vec<PathPart>,
    /// The key of an item's position, `__pos__`.
    pub position: String,
}

/// The two keys every table row carries.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TableKeys {
    /// The row id key, `__id__`.
    pub id: String,
    /// The row position key, `__pos__`.
    pub position: String,
}

impl KeyedList {
    /// An item's key, or `None` when the item has no string key.
    #[must_use]
    pub fn key_of<'a>(&self, item: &'a AnyValue) -> Option<&'a str> {
        resolve(item, &self.key)?.as_str()
    }

    /// Whether an item carries a finite number as its position.
    #[must_use]
    pub fn has_position(&self, item: &AnyValue) -> bool {
        item.get(&self.position).is_some_and(is_row_position)
    }

    /// What `change` at `inner`, a path inside an item, does to the item's
    /// key. For example, a set of `"r9"` at `["__id__"]` gives a row the key
    /// `r9`, and a delete there leaves it without a key.
    pub(crate) fn key_after_write<'c>(
        &self,
        inner: &[Segment],
        change: &'c Change,
    ) -> KeyWrite<'c> {
        if inner.len() > self.key.len() {
            return KeyWrite::Untouched;
        }
        let reaches = inner.iter().zip(&self.key).all(|pair| match pair {
            (Segment::Key(segment), PathPart::Key(part)) => segment == part,
            _ => false,
        });
        match change {
            _ if !reaches => KeyWrite::Untouched,
            Change::Set(value) => {
                match resolve(value, &self.key[inner.len()..]).and_then(AnyValue::as_str) {
                    Some(key) => KeyWrite::Key(key),
                    None => KeyWrite::Keyless,
                }
            }
            // A delete of the whole item leaves no item to key.
            Change::Delete if inner.is_empty() => KeyWrite::Untouched,
            Change::Delete => KeyWrite::Keyless,
        }
    }
}

/// What a write does to the key of the list item it writes in.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum KeyWrite<'c> {
    /// The write does not reach the key, or deletes the whole item.
    Untouched,
    /// After the write, the item has this key. It can be the key it had.
    Key(&'c str),
    /// After the write, the item has no key.
    Keyless,
}

/// A set of a few keys. Each lookup compares the key with each member,
/// which for the few keys of a view-state set is faster than hashing it:
/// the hash and the canonical form look up every key of a graph.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct KeySet(Vec<String>);

impl KeySet {
    /// Whether the set has `key`.
    #[must_use]
    pub fn contains(&self, key: &str) -> bool {
        // The length and the first byte tell most keys apart without a call to compare them.
        let key = key.as_bytes();
        self.0.iter().any(|member| {
            let member = member.as_bytes();
            member.len() == key.len() && member.first() == key.first() && member == key
        })
    }

    /// The keys, in the order the schema lists them.
    pub fn iter(&self) -> impl Iterator<Item = &String> {
        self.0.iter()
    }
}

/// A key that repeats is kept once.
impl FromIterator<String> for KeySet {
    fn from_iter<T: IntoIterator<Item = String>>(keys: T) -> Self {
        let mut set = Vec::new();
        for key in keys {
            if !set.contains(&key) {
                set.push(key);
            }
        }
        Self(set)
    }
}

/// The parsed `node_schema.json`.
#[derive(Debug)]
pub struct NodeSchema {
    /// The schema file's version.
    pub version: u64,
    /// The top-level flow keys that are not view state. Every other
    /// top-level key is.
    pub flow_graph_keys: KeySet,
    /// Node keys that are view state.
    pub node_view_state: KeySet,
    /// Keys of `data.node` that are view state.
    pub node_data_view_state: KeySet,
    /// Template keys that are view state.
    pub template_view_state: KeySet,
    /// Template field keys that are display only.
    pub field_view_state: KeySet,
    /// Edge keys that are view state.
    pub edge_view_state: KeySet,
    /// The keys of a template field's value unit, written together.
    pub value_unit: Vec<String>,
    /// Template field keys that are each a value of their own.
    pub toggles: Vec<String>,
    /// Node paths the diff splits into their keys; any other value is written whole.
    pub recursed_paths: Vec<Vec<String>>,
    natural_lists: Vec<(Vec<String>, KeyedList)>,
    table_path: Vec<String>,
    table_when_field: Vec<AnyMap>,
    /// The table list, which every table field's value is.
    pub table: KeyedList,
    /// The keys of a table row, the same ones `table` reads.
    pub table_keys: TableKeys,
}

/// The engine's node schema.
pub static NODE_SCHEMA: LazyLock<NodeSchema> = LazyLock::new(|| {
    let raw: AnyValue =
        serde_json::from_str(NODE_SCHEMA_JSON).expect("node_schema.json is valid JSON");
    NodeSchema::parse(&raw).unwrap_or_else(|error| panic!("node_schema.json: {error}"))
});

impl NodeSchema {
    /// Read the schema file. The error names the first key that is missing
    /// or has the wrong shape.
    fn parse(raw: &AnyValue) -> Result<Self, String> {
        let view_state = key(raw, "", "view_state")?;
        let view_set = |name: &str| -> Result<KeySet, String> {
            let path = format!("view_state.{name}");
            Ok(strings(key(view_state, "view_state", name)?, &path)?
                .into_iter()
                .collect())
        };
        let flow = key(view_state, "view_state", "flow")?;
        let flow_graph_keys = strings(
            key(flow, "view_state.flow", "except")?,
            "view_state.flow.except",
        )?
        .into_iter()
        .collect();
        let field_units = key(raw, "", "field_units")?;
        let keyed_lists = key(raw, "", "keyed_lists")?;
        let tables = key(keyed_lists, "keyed_lists", "tables")?;
        let table_keys = TableKeys {
            id: string(
                key(tables, "keyed_lists.tables", "id")?,
                "keyed_lists.tables.id",
            )?,
            position: string(
                key(tables, "keyed_lists.tables", "position")?,
                "keyed_lists.tables.position",
            )?,
        };
        let node_data_view_state = paths(
            key(view_state, "view_state", "node_paths")?,
            "view_state.node_paths",
        )?
        .into_iter()
        .filter_map(|path| match path.as_slice() {
            [data, node, key] if data == "data" && node == "node" => Some(key.clone()),
            _ => None,
        })
        .collect();
        let natural = key(keyed_lists, "keyed_lists", "natural")?;
        let natural_lists = natural
            .as_array()
            .ok_or("keyed_lists.natural must be a list")?
            .iter()
            .enumerate()
            .map(|(index, entry)| natural_list(entry, &format!("keyed_lists.natural[{index}]")))
            .collect::<Result<_, _>>()?;
        let when_field = key(tables, "keyed_lists.tables", "when_field")?;
        let table_when_field = when_field
            .as_array()
            .and_then(|conditions| conditions.iter().map(|c| c.as_object().cloned()).collect())
            .ok_or("keyed_lists.tables.when_field must be a list of objects")?;
        Ok(Self {
            version: key(raw, "", "version")?
                .as_u64()
                .ok_or("version must be a non-negative integer")?,
            flow_graph_keys,
            node_view_state: view_set("node")?,
            node_data_view_state,
            template_view_state: view_set("template")?,
            field_view_state: view_set("template_field")?,
            edge_view_state: view_set("edge")?,
            value_unit: strings(
                key(field_units, "field_units", "value")?,
                "field_units.value",
            )?,
            toggles: strings(
                key(field_units, "field_units", "toggles")?,
                "field_units.toggles",
            )?,
            recursed_paths: paths(
                key(key(raw, "", "whole_values")?, "whole_values", "recursed")?,
                "whole_values.recursed",
            )?,
            natural_lists,
            table_path: strings(
                key(tables, "keyed_lists.tables", "path")?,
                "keyed_lists.tables.path",
            )?,
            table_when_field,
            table: KeyedList {
                kind: ListKind::Table,
                key: vec![PathPart::Key(table_keys.id.clone())],
                position: table_keys.position.clone(),
            },
            table_keys,
        })
    }

    /// Whether a top-level flow key is view state.
    #[must_use]
    pub fn is_flow_view_state(&self, key: &str) -> bool {
        !self.flow_graph_keys.contains(key)
    }

    /// The keyed list a node holds at `path`, or `None` if the schema declares none there.
    ///
    /// A table is declared at every template field's `value` whose field
    /// matches one of the schema's `when_field` conditions.
    #[must_use]
    pub fn keyed_list_at<S: AsRef<str>>(&self, node: &AnyValue, path: &[S]) -> Option<&KeyedList> {
        self.keyed_list_by(path, |field_path, key| {
            let mut field = node;
            for part in field_path {
                field = field.as_object()?.get(part.as_ref())?;
            }
            field.as_object()?.get(key).map(Cow::Borrowed)
        })
    }

    /// The keyed list a template field's `value` is, given the field itself.
    #[must_use]
    pub fn field_value_list(&self, name: &str, field: &AnyMap) -> Option<&KeyedList> {
        self.keyed_list_by(&field_value_path(name), |_, key| {
            field.get(key).map(Cow::Borrowed)
        })
    }

    /// The keyed list at `path`. When a table pattern matches, it reads the
    /// keys of the template field that `when_field` names through
    /// `field_key(field_path, key)`, which gives `None` for a field that is
    /// not an object or lacks the key.
    pub(crate) fn keyed_list_by<'f, S: AsRef<str>>(
        &self,
        path: &[S],
        field_key: impl Fn(&[S], &str) -> Option<Cow<'f, AnyValue>>,
    ) -> Option<&KeyedList> {
        if let Some((_, keyed)) = self
            .natural_lists
            .iter()
            .find(|(list_path, _)| list_path.equals(path))
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
        let field_path = &path[..=wildcard];
        self.table_when_field
            .iter()
            .any(|condition| {
                condition
                    .iter()
                    .all(|(key, value)| field_key(field_path, key).as_deref() == Some(value))
            })
            .then_some(&self.table)
    }

    /// The keyed list whose items a checked path names at `path`: the natural
    /// list the schema declares there, or else a table. Only a path that a
    /// write already checked may name list items, so the field's type is not
    /// read again.
    #[must_use]
    pub fn listed_at<T: AsKey>(&self, path: &[T]) -> &KeyedList {
        self.natural_list_at(path).unwrap_or(&self.table)
    }

    /// The natural lists the schema declares, each with its path.
    pub fn natural_lists(&self) -> impl Iterator<Item = (&[String], &KeyedList)> {
        self.natural_lists
            .iter()
            .map(|(list_path, keyed)| (list_path.as_slice(), keyed))
    }

    /// The natural list the schema declares at `path`, if any.
    #[must_use]
    pub fn natural_list_at<T: AsKey>(&self, path: &[T]) -> Option<&KeyedList> {
        self.natural_lists
            .iter()
            .find(|(list_path, _)| path.equals(list_path))
            .map(|(_, keyed)| keyed)
    }

    /// Whether the list at `path` of `node` is a table.
    #[must_use]
    pub fn is_table_at<S: AsRef<str>>(&self, node: &AnyValue, path: &[S]) -> bool {
        self.keyed_list_at(node, path)
            .is_some_and(|keyed| keyed.kind == ListKind::Table)
    }
}

/// The value at `parent.name` of the schema file.
fn key<'v>(value: &'v AnyValue, parent: &str, name: &str) -> Result<&'v AnyValue, String> {
    value.get(name).ok_or_else(|| {
        if parent.is_empty() {
            format!("{name} is missing")
        } else {
            format!("{parent}.{name} is missing")
        }
    })
}

fn string(value: &AnyValue, path: &str) -> Result<String, String> {
    value
        .as_str()
        .map(str::to_owned)
        .ok_or_else(|| format!("{path} must be a string"))
}

fn strings(value: &AnyValue, path: &str) -> Result<Vec<String>, String> {
    value
        .as_array()
        .and_then(|items| {
            items
                .iter()
                .map(|item| item.as_str().map(str::to_owned))
                .collect()
        })
        .ok_or_else(|| format!("{path} must be a list of strings"))
}

fn paths(value: &AnyValue, path: &str) -> Result<Vec<Vec<String>>, String> {
    value
        .as_array()
        .ok_or_else(|| format!("{path} must be a list of paths"))?
        .iter()
        .enumerate()
        .map(|(index, item)| strings(item, &format!("{path}[{index}]")))
        .collect()
}

/// A natural list's path and its key: object keys and list indexes.
fn natural_list(entry: &AnyValue, path: &str) -> Result<(Vec<String>, KeyedList), String> {
    let list_path = strings(key(entry, path, "path")?, &format!("{path}.path"))?;
    let position = string(key(entry, path, "position")?, &format!("{path}.position"))?;
    let item_key = key(entry, path, "key")?
        .as_array()
        .and_then(|parts| {
            parts
                .iter()
                .map(|part| match part {
                    AnyValue::String(key) => Some(PathPart::Key(key.to_string())),
                    AnyValue::Number(index) => index
                        .as_u64()
                        .and_then(|index| usize::try_from(index).ok())
                        .map(PathPart::Index),
                    _ => None,
                })
                .collect()
        })
        .ok_or_else(|| format!("{path}.key must be a list of keys and indexes"))?;
    Ok((
        list_path,
        KeyedList {
            kind: ListKind::Natural,
            key: item_key,
            position,
        },
    ))
}

#[cfg(test)]
mod tests {
    use crate::json;

    use super::*;

    #[test]
    fn a_broken_schema_names_the_bad_key() {
        let mut raw: AnyValue = serde_json::from_str(NODE_SCHEMA_JSON).unwrap();
        raw["view_state"].as_object_mut().unwrap().remove("flow");
        assert_eq!(
            NodeSchema::parse(&raw).unwrap_err(),
            "view_state.flow is missing"
        );
        raw["view_state"]["flow"] = json!({"except": [1]});
        assert_eq!(
            NodeSchema::parse(&raw).unwrap_err(),
            "view_state.flow.except must be a list of strings"
        );
    }

    #[test]
    fn the_embedded_schema_loads() {
        assert_eq!(NODE_SCHEMA.version, 1);
        assert!(NODE_SCHEMA.node_data_view_state.contains("last_updated"));
        assert!(NODE_SCHEMA.is_flow_view_state("viewport"));
        assert!(NODE_SCHEMA.is_flow_view_state("name"));
        assert!(!NODE_SCHEMA.is_flow_view_state("nodes"));
        assert!(!NODE_SCHEMA.is_flow_view_state("edges"));
        assert_eq!(NODE_SCHEMA.table_keys.id, "__id__");
        assert_eq!(NODE_SCHEMA.table_keys.position, "__pos__");
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
