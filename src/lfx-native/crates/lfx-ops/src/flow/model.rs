//! The flow model (`model.json`): where a flow keeps its view state and keyed lists.

use std::borrow::Cow;
use std::sync::LazyLock;

use crate::json::{FlowObj, FlowValue};

use crate::flow::path::{AsKey, PathExt};
use crate::json::is_row_position;
use crate::json::pointer::PathPart;
use crate::json::pointer::resolve;

/// `model.json`, as shipped with the engine.
pub const FLOW_MODEL_JSON: &str = include_str!("model.json");

/// A path segment that matches any object key.
const WILDCARD: &str = "*";

/// The path of a node's template.
pub const TEMPLATE_PATH: [&str; 3] = ["data", "node", "template"];
/// The path of a node's outputs.
pub const OUTPUTS_PATH: [&str; 3] = ["data", "node", "outputs"];
/// The objects every node always has: `data`, `data.node` and `data.node.template`.
pub const NODE_OBJECT_PATHS: [&[&str]; 3] = [&["data"], &["data", "node"], &TEMPLATE_PATH];

/// The path of a template field's value.
#[must_use]
pub fn field_value_path(field: &str) -> [&str; 5] {
    ["data", "node", "template", field, "value"]
}

/// How a keyed list names its items. Items sort by position, then key.
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
    pub(crate) key: Vec<PathPart>,
    /// The key of an item's position, `__pos__`.
    pub position: String,
}

/// The two keys every table row carries.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TableInputKeys {
    /// The row id key, `__id__`.
    pub id: String,
    /// The row position key, `__pos__`.
    pub position: String,
}

impl KeyedList {
    /// An item's key, or `None` when the item has no string key.
    #[must_use]
    pub fn key_of<'a>(&self, item: &'a FlowValue) -> Option<&'a str> {
        resolve(item, &self.key)?.as_str()
    }

    /// Whether an item carries a finite number as its position.
    #[must_use]
    pub fn has_position(&self, item: &FlowValue) -> bool {
        item.get(&self.position).is_some_and(is_row_position)
    }
}

/// A set of a few keys. For a few keys, a linear scan is faster than a hash.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct KeySet(Vec<String>);

impl KeySet {
    /// Whether the set has `key`.
    #[must_use]
    pub fn contains(&self, key: &str) -> bool {
        // The length and the first byte tell most keys apart without a full compare.
        let key = key.as_bytes();
        self.0.iter().any(|member| {
            let member = member.as_bytes();
            member.len() == key.len() && member.first() == key.first() && member == key
        })
    }

    /// The keys, in the order `model.json` lists them.
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

/// The parsed `model.json`.
#[derive(Debug)]
pub struct FlowModel {
    /// The version of `model.json`.
    pub version: u64,
    /// The top-level flow keys that are not view state.
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
    named_lists: Vec<(Vec<String>, KeyedList)>,
    table_input_path: Vec<String>,
    table_input_when_field: Vec<FlowObj>,
    /// The table list, which every table field's value is.
    pub table_input: KeyedList,
    /// The keys of a table row, the same ones `table` reads.
    pub table_input_keys: TableInputKeys,
}

/// The engine's flow model.
pub static FLOW_MODEL: LazyLock<FlowModel> = LazyLock::new(|| {
    let raw: FlowValue = serde_json::from_str(FLOW_MODEL_JSON).expect("model.json is valid JSON");
    FlowModel::parse(&raw).unwrap_or_else(|error| panic!("model.json: {error}"))
});

impl FlowModel {
    /// Read `model.json`. The error names the first key that is missing
    /// or has the wrong shape.
    fn parse(raw: &FlowValue) -> Result<Self, String> {
        let view_state = key(raw, "", "view_state")?;
        let view_set = |name: &str| -> Result<KeySet, String> {
            Ok(at(view_state, "view_state", name, strings)?
                .into_iter()
                .collect())
        };
        let flow = key(view_state, "view_state", "flow")?;
        let flow_graph_keys = at(flow, "view_state.flow", "except", strings)?
            .into_iter()
            .collect();
        let keyed_lists = key(raw, "", "keyed_lists")?;
        let table_input = key(keyed_lists, "keyed_lists", "table_input")?;
        let table_input_keys = TableInputKeys {
            id: at(table_input, "keyed_lists.table_input", "id", string)?,
            position: at(table_input, "keyed_lists.table_input", "position", string)?,
        };
        let node_data_view_state = at(view_state, "view_state", "node_paths", paths)?
            .into_iter()
            .filter_map(|path| match path.as_slice() {
                [data, node, key] if data == "data" && node == "node" => Some(key.clone()),
                _ => None,
            })
            .collect();
        let named = key(keyed_lists, "keyed_lists", "named")?;
        let named_lists = named
            .as_array()
            .ok_or("keyed_lists.named must be a list")?
            .iter()
            .enumerate()
            .map(|(index, list)| named_list(list, &format!("keyed_lists.named[{index}]")))
            .collect::<Result<_, _>>()?;
        let when_field = key(table_input, "keyed_lists.table_input", "when_field")?;
        let table_input_when_field = when_field
            .as_array()
            .and_then(|conditions| conditions.iter().map(|c| c.as_object().cloned()).collect())
            .ok_or("keyed_lists.table_input.when_field must be a list of objects")?;
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
            named_lists,
            table_input_path: at(table_input, "keyed_lists.table_input", "path", strings)?,
            table_input_when_field,
            table_input: KeyedList {
                kind: ListKind::Table,
                key: vec![PathPart::Key(table_input_keys.id.clone())],
                position: table_input_keys.position.clone(),
            },
            table_input_keys,
        })
    }

    /// Whether a top-level flow key is view state.
    #[must_use]
    pub fn is_flow_view_state(&self, key: &str) -> bool {
        !self.flow_graph_keys.contains(key)
    }

    /// The keyed list a node holds at `path`, or `None` if there is none.
    /// A field's `value` is a table when the field matches a `when_field` condition.
    #[must_use]
    pub fn keyed_list_at<S: AsRef<str>>(&self, node: &FlowValue, path: &[S]) -> Option<&KeyedList> {
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
    pub fn field_value_list(&self, name: &str, field: &FlowObj) -> Option<&KeyedList> {
        self.keyed_list_by(&field_value_path(name), |_, key| {
            field.get(key).map(Cow::Borrowed)
        })
    }

    /// The keyed list at `path`. `field_key(field_path, key)` reads a key of
    /// the template field, for the `when_field` conditions.
    pub(crate) fn keyed_list_by<'f, T: AsKey>(
        &self,
        path: &[T],
        field_key: impl Fn(&[T], &str) -> Option<Cow<'f, FlowValue>>,
    ) -> Option<&KeyedList> {
        if let Some((_, keyed)) = self
            .named_lists
            .iter()
            .find(|(list_path, _)| path.equals(list_path))
        {
            return Some(keyed);
        }
        if path.len() != self.table_input_path.len() {
            return None;
        }
        let mut wildcard = None;
        for (index, (part, pattern)) in path.iter().zip(&self.table_input_path).enumerate() {
            if pattern == WILDCARD {
                wildcard = Some(index);
            } else if part.as_key() != Some(pattern.as_str()) {
                return None;
            }
        }
        let Some(wildcard) = wildcard else {
            return Some(&self.table_input);
        };
        let field_path = &path[..=wildcard];
        self.table_input_when_field
            .iter()
            .any(|condition| {
                condition
                    .iter()
                    .all(|(key, value)| field_key(field_path, key).as_deref() == Some(value))
            })
            .then_some(&self.table_input)
    }

    /// The keyed list at `path`: the named list there, or else a table input.
    /// Use it only on a checked path, because it does not read the field's type.
    #[must_use]
    pub fn listed_at<T: AsKey>(&self, path: &[T]) -> &KeyedList {
        self.named_list_at(path).unwrap_or(&self.table_input)
    }

    /// The named lists `model.json` declares, each with its path.
    pub fn named_lists(&self) -> impl Iterator<Item = (&[String], &KeyedList)> {
        self.named_lists
            .iter()
            .map(|(list_path, keyed)| (list_path.as_slice(), keyed))
    }

    /// The named list `model.json` declares at `path`, if any.
    #[must_use]
    pub fn named_list_at<T: AsKey>(&self, path: &[T]) -> Option<&KeyedList> {
        self.named_lists
            .iter()
            .find(|(list_path, _)| path.equals(list_path))
            .map(|(_, keyed)| keyed)
    }

    /// Whether the list at `path` of `node` is a table.
    #[must_use]
    pub fn is_table_input_at<S: AsRef<str>>(&self, node: &FlowValue, path: &[S]) -> bool {
        self.keyed_list_at(node, path)
            .is_some_and(|keyed| keyed.kind == ListKind::Table)
    }
}

/// The value at `parent.name` of `model.json`.
fn key<'v>(value: &'v FlowValue, parent: &str, name: &str) -> Result<&'v FlowValue, String> {
    value.get(name).ok_or_else(|| {
        if parent.is_empty() {
            format!("{name} is missing")
        } else {
            format!("{parent}.{name} is missing")
        }
    })
}

/// Read `parent.name` with `read`, which names that path in its error.
fn at<T>(
    value: &FlowValue,
    parent: &str,
    name: &str,
    read: fn(&FlowValue, &str) -> Result<T, String>,
) -> Result<T, String> {
    read(key(value, parent, name)?, &format!("{parent}.{name}"))
}

fn string(value: &FlowValue, path: &str) -> Result<String, String> {
    value
        .as_str()
        .map(str::to_owned)
        .ok_or_else(|| format!("{path} must be a string"))
}

fn strings(value: &FlowValue, path: &str) -> Result<Vec<String>, String> {
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

fn paths(value: &FlowValue, path: &str) -> Result<Vec<Vec<String>>, String> {
    value
        .as_array()
        .ok_or_else(|| format!("{path} must be a list of paths"))?
        .iter()
        .enumerate()
        .map(|(index, item)| strings(item, &format!("{path}[{index}]")))
        .collect()
}

/// A named list's path and its key: object keys and list indexes.
fn named_list(entry: &FlowValue, path: &str) -> Result<(Vec<String>, KeyedList), String> {
    let list_path = at(entry, path, "path", strings)?;
    let position = at(entry, path, "position", string)?;
    let item_key = key(entry, path, "key")?
        .as_array()
        .and_then(|parts| {
            parts
                .iter()
                .map(|part| match part {
                    FlowValue::String(key) => Some(PathPart::Key(key.to_string())),
                    FlowValue::Number(index) => index
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

// --- Reading nodes, edges and rows --------------------------------------------------------

/// What the engine reads from a node, an edge or a table row.
pub(crate) trait EntryExt {
    /// The string at `key`, when it is a string that is not empty.
    fn non_empty_str(&self, key: &str) -> Option<&str>;

    /// The id, or `""` when there is no string id.
    fn id(&self) -> &str;

    /// A node's template: `data.node.template`.
    fn template(&self) -> Option<&FlowObj>;

    /// The value of a node's template field: `data.node.template.<field>.value`.
    fn field_value(&self, field: &str) -> Option<&FlowValue> {
        self.template()?.get(field)?.get("value")
    }
}

impl EntryExt for FlowObj {
    fn non_empty_str(&self, key: &str) -> Option<&str> {
        self.get(key)?.as_str().filter(|text| !text.is_empty())
    }

    fn id(&self) -> &str {
        self.get("id")
            .and_then(FlowValue::as_str)
            .unwrap_or_default()
    }

    fn template(&self) -> Option<&FlowObj> {
        self.get("data")?.get("node")?.get("template")?.as_object()
    }
}

impl EntryExt for FlowValue {
    fn non_empty_str(&self, key: &str) -> Option<&str> {
        self.as_object()?.non_empty_str(key)
    }

    fn id(&self) -> &str {
        self.as_object().map_or("", EntryExt::id)
    }

    fn template(&self) -> Option<&FlowObj> {
        self.as_object()?.template()
    }
}

#[cfg(test)]
mod tests {
    use crate::json;

    use super::*;

    #[test]
    fn a_broken_schema_names_the_bad_key() {
        let mut raw: FlowValue = serde_json::from_str(FLOW_MODEL_JSON).unwrap();
        raw["view_state"].as_object_mut().unwrap().remove("flow");
        assert_eq!(
            FlowModel::parse(&raw).unwrap_err(),
            "view_state.flow is missing"
        );
        raw["view_state"]["flow"] = json!({"except": [1]});
        assert_eq!(
            FlowModel::parse(&raw).unwrap_err(),
            "view_state.flow.except must be a list of strings"
        );
    }

    #[test]
    fn the_embedded_schema_loads() {
        assert_eq!(FLOW_MODEL.version, 2);
        assert!(FLOW_MODEL.node_data_view_state.contains("last_updated"));
        assert!(FLOW_MODEL.is_flow_view_state("viewport"));
        assert!(FLOW_MODEL.is_flow_view_state("name"));
        assert!(!FLOW_MODEL.is_flow_view_state("nodes"));
        assert!(!FLOW_MODEL.is_flow_view_state("edges"));
        assert_eq!(FLOW_MODEL.table_input_keys.id, "__id__");
        assert_eq!(FLOW_MODEL.table_input_keys.position, "__pos__");
    }

    #[test]
    fn named_lists_are_found_by_path() {
        let outputs = FLOW_MODEL
            .keyed_list_at(&json!({}), &["data", "node", "outputs"])
            .unwrap();
        assert_eq!(outputs.kind, ListKind::Natural);
        assert_eq!(outputs.key_of(&json!({"name": "out"})), Some("out"));

        let tools = FLOW_MODEL
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
        assert!(FLOW_MODEL.is_table_input_at(&node, &path("rows")));
        assert!(FLOW_MODEL.is_table_input_at(&node, &path("legacy")));
        assert!(!FLOW_MODEL.is_table_input_at(&node, &path("text")));
        assert!(!FLOW_MODEL.is_table_input_at(&node, &path("missing")));
    }
}
