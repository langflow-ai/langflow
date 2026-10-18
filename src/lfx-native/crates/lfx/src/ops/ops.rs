//! Operation types and their strict parser.
//!
//! The parser accepts exactly the shapes the operation protocol defines: no
//! unknown keys, no missing fields, no wrong types. A list item is addressed
//! by a selector, never by an index. Dumping leaves optional fields out when
//! they are unset, so a parsed and dumped operation reads as it was sent.

use serde_json::{Map, Value};

use crate::ops::canonical::JsonType;
use crate::ops::error::{Error, Result, bail, invalid, quoted};

/// One step of a field path.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum Segment {
    /// An object key.
    Key(String),
    /// An item of a keyed list, selected by its key: `{"key": ...}`. A table
    /// row's key is its `_id`; any other item's is the field the node schema
    /// names, such as an output's `name`.
    Item(String),
}

impl Segment {
    /// The object key, if this segment is one.
    #[must_use]
    pub fn as_key(&self) -> Option<&str> {
        match self {
            Self::Key(key) => Some(key),
            Self::Item(_) => None,
        }
    }

    /// The key a selector names, or `None` for an object key.
    #[must_use]
    pub fn selector_key(&self) -> Option<&str> {
        match self {
            Self::Key(_) => None,
            Self::Item(key) => Some(key),
        }
    }

    fn to_value(&self) -> Value {
        match self {
            Self::Key(key) => Value::from(key.as_str()),
            Self::Item(key) => single("key", Value::from(key.as_str())),
        }
    }
}

/// A field path.
pub type Path = Vec<Segment>;

/// Questions about a field path, asked in object keys.
pub(crate) trait PathExt {
    /// Whether the path is exactly the object keys `keys`.
    fn is_keys<S: AsRef<str>>(&self, keys: &[S]) -> bool;
    /// Whether the path starts with the object keys `keys`.
    fn starts_with_keys<S: AsRef<str>>(&self, keys: &[S]) -> bool;
    /// The path's object keys, or `None` when it has a selector.
    fn keys(&self) -> Option<Vec<&str>>;
    /// The path with one more object key.
    fn child(&self, key: &str) -> Path;
}

impl PathExt for [Segment] {
    fn is_keys<S: AsRef<str>>(&self, keys: &[S]) -> bool {
        self.len() == keys.len() && self.starts_with_keys(keys)
    }

    fn starts_with_keys<S: AsRef<str>>(&self, keys: &[S]) -> bool {
        self.len() >= keys.len()
            && self
                .iter()
                .zip(keys)
                .all(|(segment, key)| segment.as_key() == Some(key.as_ref()))
    }

    fn keys(&self) -> Option<Vec<&str>> {
        self.iter().map(Segment::as_key).collect()
    }

    fn child(&self, key: &str) -> Path {
        self.iter()
            .cloned()
            .chain([Segment::Key(key.to_owned())])
            .collect()
    }
}

/// The JSON label of a path, for messages.
#[must_use]
pub fn path_label(path: &[Segment]) -> String {
    Value::Array(path.iter().map(Segment::to_value).collect()).to_string()
}

/// What a path must hold before a write.
#[derive(Debug, Clone, PartialEq)]
pub enum Expect {
    /// The path holds this value, compared canonically.
    Value(Value),
    /// The path does not exist.
    Absent,
}

/// What a field update does at its path.
#[derive(Debug, Clone, PartialEq)]
pub enum Change {
    /// Write a value.
    Set {
        /// The value written.
        value: Value,
        /// The JSON type the write replaces. Required when the type changes,
        /// so a number cannot silently become a string.
        from_type: Option<JsonType>,
        /// The metadata of the template field the path writes into, as of
        /// this operation. The engine ignores it; readers use it to strip
        /// secret values without replaying the flow.
        template_field: Option<Map<String, Value>>,
    },
    /// Remove the value.
    Delete,
}

/// One `set_field` or `delete_field` on a node.
#[derive(Debug, Clone, PartialEq)]
pub struct FieldUpdate {
    /// The node written.
    pub id: String,
    /// Where it is written.
    pub path: Path,
    /// What the path must hold first. On a mismatch the whole batch fails.
    pub expect: Option<Expect>,
    /// The write.
    pub change: Change,
}

impl FieldUpdate {
    /// Whether this update is a `delete_field`.
    #[must_use]
    pub fn is_delete(&self) -> bool {
        matches!(self.change, Change::Delete)
    }

    /// A `set_field` of `value` at `path`.
    #[must_use]
    pub fn set(id: &str, path: Path, value: Value) -> Self {
        Self {
            id: id.to_owned(),
            path,
            expect: None,
            change: Change::Set {
                value,
                from_type: None,
                template_field: None,
            },
        }
    }

    /// A `delete_field` at `path`.
    #[must_use]
    pub fn delete(id: &str, path: Path) -> Self {
        Self {
            id: id.to_owned(),
            path,
            expect: None,
            change: Change::Delete,
        }
    }
}

/// A flow operation.
#[derive(Debug, Clone, PartialEq)]
pub enum Operation {
    /// Add nodes.
    AddNodes(Vec<Map<String, Value>>),
    /// Write fields of existing nodes.
    UpdateNodes(Vec<FieldUpdate>),
    /// Delete nodes, and the edges at them.
    DeleteNodes(Vec<String>),
    /// Add edges. An edge changes by being deleted and added again.
    AddEdges(Vec<Map<String, Value>>),
    /// Delete edges.
    DeleteEdges(Vec<String>),
    /// Set and delete top-level keys other than `nodes` and `edges`.
    UpdateMetadata {
        /// Keys to set.
        fields: Map<String, Value>,
        /// Keys to delete.
        delete_keys: Vec<String>,
    },
}

impl Operation {
    /// The operation's `type`.
    #[must_use]
    pub fn type_name(&self) -> &'static str {
        match self {
            Self::AddNodes(_) => "add_nodes",
            Self::UpdateNodes(_) => "update_nodes",
            Self::DeleteNodes(_) => "delete_nodes",
            Self::AddEdges(_) => "add_edges",
            Self::DeleteEdges(_) => "delete_edges",
            Self::UpdateMetadata { .. } => "update_metadata",
        }
    }

    /// Parse a list of operations.
    ///
    /// # Errors
    ///
    /// `operations` is not a list, or an operation does not parse.
    pub fn list_from_value(operations: Value) -> Result<Vec<Self>> {
        let Value::Array(operations) = operations else {
            bail!("operations must be a list");
        };
        operations.into_iter().map(Self::try_from).collect()
    }

    /// The operation as JSON, leaving out optional fields that are unset.
    #[must_use]
    pub fn to_value(&self) -> Value {
        let mut object = Map::new();
        object.insert("type".into(), Value::from(self.type_name()));
        match self {
            Self::AddNodes(items) => {
                object.insert("nodes".into(), objects_json(items));
            }
            Self::AddEdges(items) => {
                object.insert("edges".into(), objects_json(items));
            }
            Self::DeleteNodes(ids) | Self::DeleteEdges(ids) => {
                object.insert("ids".into(), strings_json(ids));
            }
            Self::UpdateNodes(updates) => {
                object.insert(
                    "updates".into(),
                    Value::Array(updates.iter().map(FieldUpdate::to_value).collect()),
                );
            }
            Self::UpdateMetadata {
                fields,
                delete_keys,
            } => {
                if !fields.is_empty() {
                    object.insert("fields".into(), Value::Object(fields.clone()));
                }
                if !delete_keys.is_empty() {
                    object.insert("delete_keys".into(), strings_json(delete_keys));
                }
            }
        }
        Value::Object(object)
    }
}

impl TryFrom<Value> for Operation {
    type Error = Error;

    /// Parse one operation. It fails unless the operation has exactly one of
    /// the protocol's shapes.
    fn try_from(operation: Value) -> Result<Self> {
        let Value::Object(mut operation) = operation else {
            bail!("operation must be a dict");
        };
        let type_name = match operation.get("type") {
            Some(Value::String(name)) => name.clone(),
            other => {
                let shown = other.map_or_else(|| "None".to_owned(), Value::to_string);
                bail!("Unsupported operation type: {shown}");
            }
        };
        let context = type_name.as_str();
        // Each type allows `type` and its own payload key, and requires the payload.
        let mut payload = |key: &str| -> Result<Value> {
            only_keys(&operation, &["type", key], context)?;
            required(&mut operation, key, context)
        };
        Ok(match context {
            "add_nodes" => Self::AddNodes(objects(payload("nodes")?, context)?),
            "add_edges" => Self::AddEdges(objects(payload("edges")?, context)?),
            "delete_nodes" => Self::DeleteNodes(strings(payload("ids")?, context)?),
            "delete_edges" => Self::DeleteEdges(strings(payload("ids")?, context)?),
            "update_nodes" => Self::UpdateNodes(updates(payload("updates")?, context)?),
            "update_metadata" => {
                only_keys(&operation, &["type", "fields", "delete_keys"], context)?;
                let fields = match operation.remove("fields") {
                    None => Map::new(),
                    Some(Value::Object(fields)) => fields,
                    Some(_) => bail!("update_metadata.fields must be an object"),
                };
                let delete_keys = match operation.remove("delete_keys") {
                    None => Vec::new(),
                    Some(keys) => strings(keys, "update_metadata.delete_keys")?,
                };
                Self::UpdateMetadata {
                    fields,
                    delete_keys,
                }
            }
            _ => bail!("Unsupported operation type: {}", quoted(context)),
        })
    }
}

impl FieldUpdate {
    /// The update as JSON, leaving out optional fields that are unset.
    #[must_use]
    pub fn to_value(&self) -> Value {
        let mut object = Map::new();
        object.insert("id".into(), Value::from(self.id.as_str()));
        object.insert(
            "path".into(),
            Value::Array(self.path.iter().map(Segment::to_value).collect()),
        );
        if let Some(expect) = &self.expect {
            object.insert(
                "expect".into(),
                match expect {
                    Expect::Value(value) => single("value", value.clone()),
                    Expect::Absent => single("absent", Value::Bool(true)),
                },
            );
        }
        match &self.change {
            Change::Set {
                value,
                from_type,
                template_field,
            } => {
                object.insert("op".into(), Value::from("set_field"));
                object.insert("value".into(), value.clone());
                if let Some(from_type) = from_type {
                    object.insert("from_type".into(), Value::from(from_type.as_str()));
                }
                if let Some(template_field) = template_field {
                    object.insert(
                        "template_field".into(),
                        Value::Object(template_field.clone()),
                    );
                }
            }
            Change::Delete => {
                object.insert("op".into(), Value::from("delete_field"));
            }
        }
        Value::Object(object)
    }
}

fn single(key: &str, value: Value) -> Value {
    let mut object = Map::new();
    object.insert(key.to_owned(), value);
    Value::Object(object)
}

fn objects_json(items: &[Map<String, Value>]) -> Value {
    Value::Array(items.iter().cloned().map(Value::Object).collect())
}

fn strings_json(items: &[String]) -> Value {
    Value::Array(
        items
            .iter()
            .map(|item| Value::from(item.as_str()))
            .collect(),
    )
}

fn only_keys(object: &Map<String, Value>, allowed: &[&str], context: &str) -> Result<()> {
    match object.keys().find(|key| !allowed.contains(&key.as_str())) {
        Some(key) => Err(invalid!("{context}: unexpected key {}", quoted(key))),
        None => Ok(()),
    }
}

fn required(object: &mut Map<String, Value>, key: &str, context: &str) -> Result<Value> {
    object
        .remove(key)
        .ok_or_else(|| invalid!("{context}: {key} is required"))
}

fn objects(value: Value, context: &str) -> Result<Vec<Map<String, Value>>> {
    let Value::Array(items) = value else {
        bail!("{context}: must be a list of objects");
    };
    items
        .into_iter()
        .map(|item| match item {
            Value::Object(object) => Ok(object),
            _ => Err(invalid!("{context}: must be a list of objects")),
        })
        .collect()
}

fn strings(value: Value, context: &str) -> Result<Vec<String>> {
    let Value::Array(items) = value else {
        bail!("{context}: must be a list of strings");
    };
    items
        .into_iter()
        .map(|item| match item {
            Value::String(string) => Ok(string),
            _ => Err(invalid!("{context}: must be a list of strings")),
        })
        .collect()
}

fn updates(value: Value, context: &str) -> Result<Vec<FieldUpdate>> {
    let Value::Array(items) = value else {
        bail!("{context}.updates must be a list");
    };
    items
        .into_iter()
        .enumerate()
        .map(|(index, item)| parse_update(item, &format!("{context}.updates[{index}]")))
        .collect()
}

fn parse_update(update: Value, context: &str) -> Result<FieldUpdate> {
    let Value::Object(mut update) = update else {
        bail!("{context} must be an object");
    };
    let set = match update.get("op") {
        Some(Value::String(op)) if op == "set_field" => true,
        Some(Value::String(op)) if op == "delete_field" => false,
        _ => {
            bail!("{context}: op must be set_field or delete_field");
        }
    };
    let allowed: &[&str] = if set {
        &[
            "id",
            "op",
            "path",
            "expect",
            "value",
            "from_type",
            "template_field",
        ]
    } else {
        &["id", "op", "path", "expect"]
    };
    only_keys(&update, allowed, context)?;
    let id = match update.remove("id") {
        Some(Value::String(id)) if !id.is_empty() => id,
        _ => {
            bail!("{context}: id must be a non-empty string");
        }
    };
    let path = match update.remove("path") {
        Some(Value::Array(segments)) if !segments.is_empty() => segments
            .into_iter()
            .map(|segment| parse_segment(segment, context))
            .collect::<Result<Path>>()?,
        Some(Value::Array(_)) => {
            bail!("{context}: path must not be empty");
        }
        _ => return Err(invalid!("{context}: path must be a list")),
    };
    let expect = match update.remove("expect") {
        None | Some(Value::Null) => None,
        Some(expect) => Some(parse_expect(expect, context)?),
    };
    let change = if set {
        let value = required(&mut update, "value", context)?;
        let from_type = match update.remove("from_type") {
            None | Some(Value::Null) => None,
            Some(Value::String(name)) => Some(
                name.parse::<JsonType>()
                    .map_err(|_| invalid!("{context}: from_type must name a JSON type"))?,
            ),
            Some(_) => {
                bail!("{context}: from_type must name a JSON type");
            }
        };
        let template_field = match update.remove("template_field") {
            None | Some(Value::Null) => None,
            Some(Value::Object(field)) => Some(field),
            Some(_) => {
                bail!("{context}: template_field must be an object");
            }
        };
        Change::Set {
            value,
            from_type,
            template_field,
        }
    } else {
        Change::Delete
    };
    Ok(FieldUpdate {
        id,
        path,
        expect,
        change,
    })
}

fn parse_segment(segment: Value, context: &str) -> Result<Segment> {
    match segment {
        Value::String(key) => Ok(Segment::Key(key)),
        Value::Number(_) | Value::Bool(_) => Err(invalid!(
            "{context}: path segments must be object keys or selectors; integer list indexes are not allowed"
        )),
        Value::Object(selector) if selector.len() == 1 => match selector.into_iter().next() {
            Some((name, Value::String(key))) if !key.is_empty() && name == "key" => {
                Ok(Segment::Item(key))
            }
            _ => Err(invalid!("{context}: invalid path segment")),
        },
        _ => Err(invalid!("{context}: invalid path segment")),
    }
}

fn parse_expect(expect: Value, context: &str) -> Result<Expect> {
    if let Value::Object(expect) = expect
        && expect.len() == 1
    {
        match expect.into_iter().next() {
            Some((key, value)) if key == "value" => return Ok(Expect::Value(value)),
            Some((key, Value::Bool(true))) if key == "absent" => return Ok(Expect::Absent),
            _ => {}
        }
    }
    Err(invalid!(
        "{context}.expect must be {{\"value\": ...}} or {{\"absent\": true}}"
    ))
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    #[test]
    fn operations_round_trip() {
        for operation in [
            json!({"type": "add_nodes", "nodes": [{"id": "a"}]}),
            json!({"type": "delete_edges", "ids": ["e"]}),
            json!({"type": "update_metadata", "fields": {"name": 1.0}}),
            json!({"type": "update_metadata", "delete_keys": ["x"]}),
            json!({"type": "update_nodes", "updates": [
                {"id": "a", "path": ["data", "node", "outputs", {"key": "out"}], "expect": {"absent": true}, "op": "set_field",
                 "value": null, "from_type": "string", "template_field": {"name": "x"}},
                {"id": "a", "path": ["data", "node", "template", "rows", "value", {"key": "r"}], "expect": {"value": [1]}, "op": "delete_field"},
            ]}),
        ] {
            let parsed = Operation::try_from(operation.clone()).unwrap();
            assert_eq!(parsed.to_value(), operation);
        }
    }

    #[test]
    fn unset_optional_fields_are_left_out() {
        let parsed = Operation::try_from(json!({"type": "update_nodes", "updates": [
            {"id": "n", "op": "set_field", "path": ["data"], "value": 1, "from_type": null, "expect": null}
        ]}))
        .unwrap();
        assert_eq!(
            parsed.to_value(),
            json!({"type": "update_nodes", "updates": [{"id": "n", "path": ["data"], "op": "set_field", "value": 1}]})
        );
        let empty = Operation::try_from(json!({"type": "update_metadata"})).unwrap();
        assert_eq!(empty.to_value(), json!({"type": "update_metadata"}));
    }

    #[test]
    fn malformed_operations_are_refused() {
        for operation in [
            json!([]),
            json!({"type": "rename_nodes"}),
            json!({"type": "update_edges", "updates": []}),
            json!({"type": "add_nodes"}),
            json!({"type": "add_nodes", "nodes": [1]}),
            json!({"type": "add_nodes", "nodes": [], "extra": 1}),
            json!({"type": "delete_nodes", "ids": [1]}),
            json!({"type": "update_metadata", "fields": null}),
            json!({"type": "update_metadata", "delete_keys": null}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x"], "value": 1}]}),
            json!({"type": "update_nodes", "updates": [{"id": "", "op": "delete_field", "path": ["x"]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": []}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x", 0]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": [{"key": ""}]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": [{"id": "r"}]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": [{"id": "r", "key": "k"}]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x"], "expect": {}}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x"], "expect": {"absent": false}}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"], "value": 1, "from_type": "integer"}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "move_field", "path": ["x"]}]}),
        ] {
            let error = Operation::try_from(operation.clone()).unwrap_err();
            assert_eq!(error.code.as_str(), "FLOW_OPERATION_INVALID", "{operation}");
        }
        assert!(Operation::list_from_value(json!({})).is_err());
    }
}
