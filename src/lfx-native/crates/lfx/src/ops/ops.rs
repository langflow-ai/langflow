//! Operation types and their strict parser.
//!
//! Each type reads itself from a parsed JSON value (`FromValue`), so the
//! parser accepts exactly the shapes the operation protocol defines: no
//! unknown keys, no missing fields, no wrong types. A path names a list item
//! by its key, never by its index. An operation that is parsed and printed
//! again reads as it was sent.

use std::str::FromStr;

use serde_json::{Map, Value, json};

use crate::ops::error::{Error, Result, quoted};
use crate::ops::from_value::{FromValue, FromValueError, missing, read, unexpected};

/// One step of a field path.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum Segment {
    /// An object key.
    Key(String),
    /// An item of a keyed list, named by its key: `{"key": ...}` in JSON. A
    /// table row's key is its `__id__`. Any other item's key is the field that
    /// the node schema names, such as an output's `name`.
    Item(String),
}

impl Segment {
    /// The key of the list item this segment names, or `None` when it is an
    /// object key. For example, `Item("r1")` gives `Some("r1")`.
    #[must_use]
    pub fn as_item(&self) -> Option<&str> {
        match self {
            Self::Key(_) => None,
            Self::Item(key) => Some(key),
        }
    }

    /// The segment as a path writes it in JSON: an object key as a string,
    /// a list item as `{"key": ...}`. For example, `Key("outputs")` gives
    /// `"outputs"`, and `Item("r1")` gives `{"key": "r1"}`.
    fn to_value(&self) -> Value {
        match self {
            Self::Key(key) => Value::from(key.as_str()),
            Self::Item(key) => json!({"key": key}),
        }
    }

    /// The same JSON as [`Self::to_value`], but it moves the key into the
    /// value instead of copying it.
    fn into_value(self) -> Value {
        match self {
            Self::Key(key) => Value::String(key),
            Self::Item(key) => json!({"key": key}),
        }
    }
}

/// A field path.
pub type Path = Vec<Segment>;

/// A part of a path that may be an object key, as `PathExt` compares it.
pub trait AsKey {
    /// The object key, or `None` when this part is not one, such as a
    /// segment that names a list item.
    fn as_key(&self) -> Option<&str>;
}

impl AsKey for Segment {
    fn as_key(&self) -> Option<&str> {
        match self {
            Self::Key(key) => Some(key),
            Self::Item(_) => None,
        }
    }
}

impl AsKey for String {
    fn as_key(&self) -> Option<&str> {
        Some(self)
    }
}

impl AsKey for &str {
    fn as_key(&self) -> Option<&str> {
        Some(self)
    }
}

/// Compare a path with a list of object keys, such as
/// `["data", "node", "template"]`.
///
/// A path is a list of parts. A part of a field path is a [`Segment`]: an
/// object key or a list item. A part of a node-schema path is always an
/// object key. Both kinds of path work here, because each part gives its
/// object key through [`AsKey`].
pub(crate) trait PathExt {
    /// Whether `self` is exactly the object keys `path`.
    fn equals<S: AsRef<str>>(&self, path: &[S]) -> bool;

    /// Whether `self` starts with the object keys `path`. It may be exactly
    /// `path`.
    fn has_start<S: AsRef<str>>(&self, path: &[S]) -> bool;

    /// Whether `self` and `path` have the same object keys up to the length
    /// of the shorter one. An empty `self` matches any `path`. A caller that
    /// needs one to be a prefix of the other also compares their lengths.
    fn shares_start<S: AsRef<str>>(&self, path: &[S]) -> bool;

    /// The object keys of `self`, or `None` if any segment is a list item.
    fn to_list(&self) -> Option<Vec<&str>>;
}

impl<T: AsKey> PathExt for [T] {
    fn equals<S: AsRef<str>>(&self, path: &[S]) -> bool {
        self.len() == path.len() && self.shares_start(path)
    }

    fn has_start<S: AsRef<str>>(&self, path: &[S]) -> bool {
        self.len() >= path.len() && self.shares_start(path)
    }

    fn shares_start<S: AsRef<str>>(&self, path: &[S]) -> bool {
        self.iter()
            .zip(path)
            .all(|(seg, key)| seg.as_key() == Some(key.as_ref()))
    }

    fn to_list(&self) -> Option<Vec<&str>> {
        self.iter().map(AsKey::as_key).collect()
    }
}

/// A path as JSON text, for error messages. For example,
/// `[Key("outputs"), Item("text"), Key("name")]` prints as
/// `["outputs",{"key":"text"},"name"]`.
#[must_use]
pub fn path_label(path: &[Segment]) -> String {
    Value::Array(path.iter().map(Segment::to_value).collect()).to_string()
}

/// What a field update does at its path.
#[derive(Debug, Clone, PartialEq)]
pub enum Change {
    /// Write this value.
    Set(Value),
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
            change: Change::Set(value),
        }
    }

    /// A `delete_field` at `path`.
    #[must_use]
    pub fn delete(id: &str, path: Path) -> Self {
        Self {
            id: id.to_owned(),
            path,
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
}

/// An operation's `type`, without its payload.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OperationKind {
    /// `add_nodes`.
    AddNodes,
    /// `update_nodes`.
    UpdateNodes,
    /// `delete_nodes`.
    DeleteNodes,
    /// `add_edges`.
    AddEdges,
    /// `delete_edges`.
    DeleteEdges,
}

impl OperationKind {
    /// The `type` as the protocol spells it.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Self::AddNodes => "add_nodes",
            Self::UpdateNodes => "update_nodes",
            Self::DeleteNodes => "delete_nodes",
            Self::AddEdges => "add_edges",
            Self::DeleteEdges => "delete_edges",
        }
    }

    /// The kind an operation object names in its `type`. It only borrows the
    /// object and reads its `type`, so the caller can consume the object after.
    fn from_map(object: &Map<String, Value>) -> Result<Self, FromValueError> {
        match object.get("type") {
            None => Err(FromValueError::new("type is missing")),
            Some(Value::String(name)) => name.parse(),
            _ => Err(FromValueError::new("must be a string").at_key("type")),
        }
    }
}

impl FromStr for OperationKind {
    type Err = FromValueError;

    /// The kind that a `type` names.
    fn from_str(name: &str) -> Result<Self, FromValueError> {
        match name {
            "add_nodes" => Ok(Self::AddNodes),
            "update_nodes" => Ok(Self::UpdateNodes),
            "delete_nodes" => Ok(Self::DeleteNodes),
            "add_edges" => Ok(Self::AddEdges),
            "delete_edges" => Ok(Self::DeleteEdges),
            _ => {
                let message = format!("unsupported operation type {}", quoted(name));
                Err(FromValueError::new(message).at_key("type"))
            }
        }
    }
}

impl Operation {
    /// The operation's `type`, without its payload.
    #[must_use]
    pub fn kind(&self) -> OperationKind {
        match self {
            Self::AddNodes(_) => OperationKind::AddNodes,
            Self::UpdateNodes(_) => OperationKind::UpdateNodes,
            Self::DeleteNodes(_) => OperationKind::DeleteNodes,
            Self::AddEdges(_) => OperationKind::AddEdges,
            Self::DeleteEdges(_) => OperationKind::DeleteEdges,
        }
    }

    /// Parse a list of operations.
    ///
    /// # Errors
    ///
    /// Fails when `operations` is not a JSON list, or when one of its
    /// operations is not a valid operation.
    pub fn list_from_value(operations: Value) -> Result<Vec<Self>> {
        Vec::from_value(operations).map_err(|error| error.into_error("operations"))
    }

    /// The operation as JSON. It copies every payload; a caller that owns
    /// the operation and drops it after printing uses [`Self::into_value`].
    #[must_use]
    pub fn to_value(&self) -> Value {
        match self {
            Self::AddNodes(nodes) => json!({"type": "add_nodes", "nodes": nodes}),
            Self::UpdateNodes(updates) => json!({
                "type": "update_nodes",
                "updates": updates.iter().map(FieldUpdate::to_value).collect::<Vec<_>>(),
            }),
            Self::DeleteNodes(ids) => json!({"type": "delete_nodes", "ids": ids}),
            Self::AddEdges(edges) => json!({"type": "add_edges", "edges": edges}),
            Self::DeleteEdges(ids) => json!({"type": "delete_edges", "ids": ids}),
        }
    }

    /// The operation as JSON, with its payload moved into the result instead of copied.
    #[must_use]
    pub fn into_value(self) -> Value {
        let (kind, key, payload) = match self {
            Self::AddNodes(nodes) => ("add_nodes", "nodes", objects(nodes)),
            Self::UpdateNodes(updates) => (
                "update_nodes",
                "updates",
                Value::Array(updates.into_iter().map(FieldUpdate::into_value).collect()),
            ),
            Self::DeleteNodes(ids) => ("delete_nodes", "ids", strings(ids)),
            Self::AddEdges(edges) => ("add_edges", "edges", objects(edges)),
            Self::DeleteEdges(ids) => ("delete_edges", "ids", strings(ids)),
        };
        let mut operation = Map::new();
        operation.insert("type".into(), Value::from(kind));
        operation.insert(key.into(), payload);
        Value::Object(operation)
    }
}

fn objects(objects: Vec<Map<String, Value>>) -> Value {
    Value::Array(objects.into_iter().map(Value::Object).collect())
}

fn strings(strings: Vec<String>) -> Value {
    Value::Array(strings.into_iter().map(Value::String).collect())
}

impl TryFrom<Value> for Operation {
    type Error = Error;

    /// Parse one operation. It fails unless the operation has exactly one of
    /// the protocol's shapes.
    fn try_from(operation: Value) -> Result<Self> {
        Self::from_value(operation).map_err(|error| error.into_error("operation"))
    }
}

impl FromValue for Operation {
    fn from_value(value: Value) -> Result<Self, FromValueError> {
        let object = Map::from_value(value)?;
        Ok(match OperationKind::from_map(&object)? {
            OperationKind::AddNodes => Self::AddNodes(payload(object, "nodes")?),
            OperationKind::UpdateNodes => Self::UpdateNodes(payload(object, "updates")?),
            OperationKind::DeleteNodes => Self::DeleteNodes(payload(object, "ids")?),
            OperationKind::AddEdges => Self::AddEdges(payload(object, "edges")?),
            OperationKind::DeleteEdges => Self::DeleteEdges(payload(object, "ids")?),
        })
    }
}

/// The value of an operation's one payload key, read as `T`. The operation
/// may hold only `type` and `key`.
fn payload<T: FromValue>(
    object: Map<String, Value>,
    key: &'static str,
) -> Result<T, FromValueError> {
    let mut payload = None;
    for (name, value) in object {
        match name.as_str() {
            "type" => {}
            _ if name == key => payload = Some(read(value, key)?),
            _ => return Err(unexpected(&name)),
        }
    }
    payload.ok_or_else(|| missing(key))
}

impl FieldUpdate {
    /// The update as JSON. It copies the value; see [`Self::into_value`].
    #[must_use]
    pub fn to_value(&self) -> Value {
        let path = Value::Array(self.path.iter().map(Segment::to_value).collect());
        match &self.change {
            Change::Set(value) => {
                json!({"id": self.id, "path": path, "op": "set_field", "value": value})
            }
            Change::Delete => json!({"id": self.id, "path": path, "op": "delete_field"}),
        }
    }

    /// The update as JSON, with its path and value moved into the result instead of copied.
    #[must_use]
    pub fn into_value(self) -> Value {
        let mut update = Map::new();
        update.insert("id".into(), Value::String(self.id));
        update.insert(
            "path".into(),
            Value::Array(self.path.into_iter().map(Segment::into_value).collect()),
        );
        match self.change {
            Change::Set(value) => {
                update.insert("op".into(), Value::from("set_field"));
                update.insert("value".into(), value);
            }
            Change::Delete => {
                update.insert("op".into(), Value::from("delete_field"));
            }
        }
        Value::Object(update)
    }
}

impl FromValue for FieldUpdate {
    fn from_value(value: Value) -> Result<Self, FromValueError> {
        let object = Map::from_value(value)?;
        let set = match object.get("op") {
            None => return Err(FromValueError::new("op is missing")),
            Some(Value::String(op)) if op == "set_field" => true,
            Some(Value::String(op)) if op == "delete_field" => false,
            Some(_) => {
                return Err(FromValueError::new("must be set_field or delete_field").at_key("op"));
            }
        };
        let mut id: Option<String> = None;
        let mut path: Option<Path> = None;
        let mut written = None;
        for (name, value) in object {
            match name.as_str() {
                "op" => {}
                "id" => id = Some(read(value, "id")?),
                "path" => path = Some(read(value, "path")?),
                "value" if set => written = Some(value),
                _ => return Err(unexpected(&name)),
            }
        }
        let id = id.ok_or_else(|| missing("id"))?;
        if id.is_empty() {
            return Err(FromValueError::new("must not be empty").at_key("id"));
        }
        let path = path.ok_or_else(|| missing("path"))?;
        if path.is_empty() {
            return Err(FromValueError::new("must not be empty").at_key("path"));
        }
        let change = if set {
            Change::Set(written.ok_or_else(|| missing("value"))?)
        } else {
            Change::Delete
        };
        Ok(Self { id, path, change })
    }
}

impl FromValue for Segment {
    fn from_value(value: Value) -> Result<Self, FromValueError> {
        let invalid =
            || FromValueError::new(r#"must be an object key or {"key": ...} with a non-empty key"#);
        match value {
            Value::String(key) => Ok(Self::Key(key)),
            Value::Number(_) => Err(FromValueError::new(
                r#"integer list indexes are not allowed; name a list item with {"key": ...}"#,
            )),
            Value::Object(item) if item.len() == 1 => match item.into_iter().next() {
                Some((name, Value::String(key))) if name == "key" && !key.is_empty() => {
                    Ok(Self::Item(key))
                }
                _ => Err(invalid()),
            },
            _ => Err(invalid()),
        }
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    #[test]
    fn operations_round_trip() {
        for operation in [
            json!({"type": "add_nodes", "nodes": [{"id": "a"}]}),
            json!({"type": "update_nodes", "updates": [
                {"id": "a", "path": ["data", "node", "outputs", {"key": "out"}], "op": "set_field", "value": {"name": "out", "size": 1.0}},
                {"id": "a", "path": ["data", "node", "template", "rows", "value", {"key": "r"}], "op": "delete_field"},
            ]}),
            json!({"type": "delete_nodes", "ids": ["a"]}),
            json!({"type": "add_edges", "edges": [{"id": "e", "source": "a", "target": "b"}]}),
            json!({"type": "delete_edges", "ids": ["e"]}),
        ] {
            let parsed = Operation::try_from(operation.clone()).unwrap();
            assert_eq!(parsed.kind().as_str(), operation["type"]);
            assert_eq!(parsed.to_value(), operation);
            assert_eq!(parsed.into_value(), operation);
        }
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
            json!({"type": "update_metadata", "fields": {"name": "x"}}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x"], "value": 1}]}),
            json!({"type": "update_nodes", "updates": [{"id": "", "op": "delete_field", "path": ["x"]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": []}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x", 0]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": [{"key": ""}]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": [{"id": "r"}]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": [{"id": "r", "key": "k"}]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x"], "expect": {"absent": true}}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"], "value": 1, "from_type": "number"}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"], "value": 1, "template_field": {}}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"], "value": 1, "secret": "literal"}]}), // pragma: allowlist secret
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"], "value": 1, "secrets": [{"path": [], "kind": "literal"}]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "move_field", "path": ["x"]}]}),
        ] {
            let error = Operation::try_from(operation.clone()).unwrap_err();
            assert_eq!(error.code.as_str(), "FLOW_OPERATION_INVALID", "{operation}");
        }
        assert!(Operation::list_from_value(json!({})).is_err());
    }

    #[test]
    fn path_labels_print_paths_as_json() {
        let path = [
            Segment::Key("outputs".into()),
            Segment::Item("text".into()),
            Segment::Key("name".into()),
        ];
        assert_eq!(path_label(&path), r#"["outputs",{"key":"text"},"name"]"#);
    }

    #[test]
    fn errors_say_where_the_operation_is_malformed() {
        for (operations, message) in [
            (json!({}), "operations: must be a list"),
            (json!([{"ids": ["a"]}]), "operations[0]: type is missing"),
            (json!([{"type": 5}]), "operations[0].type: must be a string"),
            (
                json!([{"type": "update_edges"}]),
                "operations[0].type: unsupported operation type 'update_edges'",
            ),
            (
                json!([{"type": "delete_nodes", "ids": ["a"], "extra": 1}]),
                "operations[0]: unexpected key 'extra'",
            ),
            (
                json!([{"type": "delete_nodes", "ids": ["a"]}, {"type": "delete_nodes", "ids": ["b", 5]}]),
                "operations[1].ids[1]: must be a string",
            ),
            (
                json!([{"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x", 0]}]}]),
                "operations[0].updates[0].path[1]: integer list indexes are not allowed; name a list item with {\"key\": ...}",
            ),
        ] {
            let error = Operation::list_from_value(operations).unwrap_err();
            assert_eq!(error.message, message);
        }
    }
}
