//! Operation types and their strict parser.
//!
//! Each type reads itself from a parsed JSON value (`FromValue`), so the
//! parser accepts exactly the shapes the operation protocol defines: no
//! unknown keys, no missing fields, no wrong types. A path names a list item
//! by its key, never by its index. An operation that is parsed and printed
//! again reads as it was sent.

use std::collections::HashSet;
use std::ops::Deref;
use std::str::FromStr;

use serde_json::{Map, Value, json};

use crate::ops::entry::EntryExt;
use crate::ops::error::{Error, Result, quoted};
use crate::ops::from_value::{FromValue, FromValueError, missing, read, unexpected};
use crate::ops::schema::NODE_OBJECT_PATHS;
use crate::ops::validate::missing_node_object;

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

/// The path of a field update.
///
/// It is not empty, it does not write the node's `id`, and it is not the
/// whole of `data`, `data.node` or `data.node.template`, which every node
/// keeps and which updates write inside. A `NodePath` cannot be made without
/// these checks, so apply does not make them again, and every node keeps its
/// id and these objects.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct NodePath(Path);

impl NodePath {
    /// The segments, moved out.
    #[must_use]
    pub fn into_segments(self) -> Path {
        self.0
    }

    /// Check that a field update may write `path`. For example, `["id"]`
    /// fails with `cannot change the node's id`.
    fn check(path: &[Segment]) -> Result<(), FromValueError> {
        if path.is_empty() {
            return Err(FromValueError::new("must not be empty"));
        }
        if path[0].as_key() == Some("id") {
            return Err(FromValueError::new("cannot change the node's id"));
        }
        if let Some(object) = NODE_OBJECT_PATHS.iter().find(|object| path.equals(object)) {
            return Err(FromValueError::new(format!(
                "cannot write the whole of {}; write inside it",
                object.join(".")
            )));
        }
        Ok(())
    }
}

impl Deref for NodePath {
    type Target = [Segment];

    fn deref(&self) -> &[Segment] {
        &self.0
    }
}

impl TryFrom<Path> for NodePath {
    type Error = Error;

    /// Check `path`, and keep it as a field update's path.
    fn try_from(path: Path) -> Result<Self> {
        Self::check(&path).map_err(|error| error.into_error("path"))?;
        Ok(Self(path))
    }
}

impl FromValue for NodePath {
    fn from_value(value: Value) -> Result<Self, FromValueError> {
        let path = Path::from_value(value)?;
        Self::check(&path)?;
        Ok(Self(path))
    }
}

/// One `set_field` or `delete_field` on a node.
#[derive(Debug, Clone, PartialEq)]
pub struct FieldUpdate {
    /// The node written.
    pub id: String,
    /// Where it is written.
    pub path: NodePath,
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
    pub fn set(id: &str, path: NodePath, value: Value) -> Self {
        Self {
            id: id.to_owned(),
            path,
            change: Change::Set(value),
        }
    }

    /// A `delete_field` at `path`.
    #[must_use]
    pub fn delete(id: &str, path: NodePath) -> Self {
        Self {
            id: id.to_owned(),
            path,
            change: Change::Delete,
        }
    }
}

/// A node of a flow: one that `add_nodes` adds, or one the flow holds.
///
/// Its `id` is a non-empty string, and its `data`, `data.node` and
/// `data.node.template` are objects. A `Node` cannot be made without these
/// checks, and a field update cannot undo them (see [`NodePath`]), so no
/// reader checks them again.
#[derive(Debug, Clone, PartialEq)]
pub struct Node(Value);

impl Node {
    /// The node's id.
    #[must_use]
    pub fn id(&self) -> &str {
        self.0.id()
    }

    /// The node as a JSON object.
    #[must_use]
    pub fn as_map(&self) -> &Map<String, Value> {
        match &self.0 {
            Value::Object(node) => node,
            _ => unreachable!("a node is a JSON object"),
        }
    }

    /// The node as a JSON object, moved out.
    #[must_use]
    pub fn into_map(self) -> Map<String, Value> {
        match self.0 {
            Value::Object(node) => node,
            _ => unreachable!("a node is a JSON object"),
        }
    }

    /// The node as a JSON value, for reading a path in it.
    pub(crate) fn as_value(&self) -> &Value {
        &self.0
    }

    /// The node as a JSON value, for writing a path in it. A field update's
    /// [`NodePath`] keeps the node's shape.
    pub(crate) fn as_value_mut(&mut self) -> &mut Value {
        &mut self.0
    }

    /// The node as a JSON value, moved out.
    pub(crate) fn into_value(self) -> Value {
        self.0
    }

    /// Check that `node` has the shape of a node. For example, a node without
    /// `data.node` fails with `data.node: must be an object (node 'a')`.
    fn check(node: &Map<String, Value>) -> Result<(), FromValueError> {
        let Some(id) = node.non_empty_str("id") else {
            return Err(FromValueError::new("must be a non-empty string").at_key("id"));
        };
        if let Some(path) = missing_node_object(node) {
            let error = FromValueError::new(format!("must be an object (node {})", quoted(id)));
            // An error takes its innermost key first.
            return Err(path
                .iter()
                .rev()
                .fold(error, |error, key| error.at_key(key)));
        }
        Ok(())
    }
}

impl TryFrom<Map<String, Value>> for Node {
    type Error = Error;

    /// Check `node`, and keep it as a node.
    fn try_from(node: Map<String, Value>) -> Result<Self> {
        Self::check(&node).map_err(|error| error.into_error("node"))?;
        Ok(Self(Value::Object(node)))
    }
}

impl FromValue for Node {
    fn from_value(value: Value) -> Result<Self, FromValueError> {
        let node = Map::from_value(value)?;
        Self::check(&node)?;
        Ok(Self(Value::Object(node)))
    }
}

/// An edge of a flow: one that `add_edges` adds, or one the flow holds.
///
/// Its `id`, `source` and `target` are non-empty strings. An `Edge` cannot be
/// made without these checks, and an edge is never written in place, so no
/// reader checks them again. Whether the nodes and handles it names exist
/// depends on the flow, so apply checks that.
#[derive(Debug, Clone, PartialEq)]
pub struct Edge(Map<String, Value>);

impl Edge {
    /// The edge's id.
    #[must_use]
    pub fn id(&self) -> &str {
        self.0.id()
    }

    /// The id of the node the edge leaves from.
    #[must_use]
    pub fn source(&self) -> &str {
        self.0.non_empty_str("source").unwrap_or_default()
    }

    /// The id of the node the edge goes into.
    #[must_use]
    pub fn target(&self) -> &str {
        self.0.non_empty_str("target").unwrap_or_default()
    }

    /// The edge as a JSON object.
    #[must_use]
    pub fn as_map(&self) -> &Map<String, Value> {
        &self.0
    }

    /// The edge as a JSON object, moved out.
    #[must_use]
    pub fn into_map(self) -> Map<String, Value> {
        self.0
    }

    /// Check that `edge` has the shape of an edge.
    fn check(edge: &Map<String, Value>) -> Result<(), FromValueError> {
        for key in ["id", "source", "target"] {
            if edge.non_empty_str(key).is_none() {
                return Err(FromValueError::new("must be a non-empty string").at_key(key));
            }
        }
        Ok(())
    }
}

impl TryFrom<Map<String, Value>> for Edge {
    type Error = Error;

    /// Check `edge`, and keep it as an edge.
    fn try_from(edge: Map<String, Value>) -> Result<Self> {
        Self::check(&edge).map_err(|error| error.into_error("edge"))?;
        Ok(Self(edge))
    }
}

impl FromValue for Edge {
    fn from_value(value: Value) -> Result<Self, FromValueError> {
        let edge = Map::from_value(value)?;
        Self::check(&edge)?;
        Ok(Self(edge))
    }
}

/// A flow operation.
#[derive(Debug, Clone, PartialEq)]
pub enum Operation {
    /// Add nodes.
    AddNodes(Vec<Node>),
    /// Write fields of existing nodes.
    UpdateNodes(Vec<FieldUpdate>),
    /// Delete nodes, and the edges at them.
    DeleteNodes(Vec<String>),
    /// Add edges. An edge changes by being deleted and added again.
    AddEdges(Vec<Edge>),
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
            Self::AddNodes(nodes) => json!({
                "type": "add_nodes",
                "nodes": nodes.iter().map(Node::as_map).collect::<Vec<_>>(),
            }),
            Self::UpdateNodes(updates) => json!({
                "type": "update_nodes",
                "updates": updates.iter().map(FieldUpdate::to_value).collect::<Vec<_>>(),
            }),
            Self::DeleteNodes(ids) => json!({"type": "delete_nodes", "ids": ids}),
            Self::AddEdges(edges) => json!({
                "type": "add_edges",
                "edges": edges.iter().map(Edge::as_map).collect::<Vec<_>>(),
            }),
            Self::DeleteEdges(ids) => json!({"type": "delete_edges", "ids": ids}),
        }
    }

    /// The operation as JSON, with its payload moved into the result instead of copied.
    #[must_use]
    pub fn into_value(self) -> Value {
        let (kind, key, payload) = match self {
            Self::AddNodes(nodes) => ("add_nodes", "nodes", objects(nodes, Node::into_map)),
            Self::UpdateNodes(updates) => (
                "update_nodes",
                "updates",
                Value::Array(updates.into_iter().map(FieldUpdate::into_value).collect()),
            ),
            Self::DeleteNodes(ids) => ("delete_nodes", "ids", strings(ids)),
            Self::AddEdges(edges) => ("add_edges", "edges", objects(edges, Edge::into_map)),
            Self::DeleteEdges(ids) => ("delete_edges", "ids", strings(ids)),
        };
        let mut operation = Map::new();
        operation.insert("type".into(), Value::from(kind));
        operation.insert(key.into(), payload);
        Value::Object(operation)
    }
}

fn objects<T>(objects: Vec<T>, into_map: fn(T) -> Map<String, Value>) -> Value {
    Value::Array(
        objects
            .into_iter()
            .map(|object| Value::Object(into_map(object)))
            .collect(),
    )
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
            OperationKind::AddNodes => {
                let nodes: Vec<Node> = payload(object, "nodes")?;
                no_repeated_ids(nodes.iter().map(Node::id))
                    .map_err(|error| error.at_key("nodes"))?;
                Self::AddNodes(nodes)
            }
            OperationKind::UpdateNodes => {
                let updates: Vec<FieldUpdate> = payload(object, "updates")?;
                no_repeated_paths(&updates).map_err(|error| error.at_key("updates"))?;
                Self::UpdateNodes(updates)
            }
            OperationKind::DeleteNodes => Self::DeleteNodes(payload(object, "ids")?),
            OperationKind::AddEdges => {
                let edges: Vec<Edge> = payload(object, "edges")?;
                no_repeated_ids(edges.iter().map(Edge::id))
                    .map_err(|error| error.at_key("edges"))?;
                Self::AddEdges(edges)
            }
            OperationKind::DeleteEdges => Self::DeleteEdges(payload(object, "ids")?),
        })
    }
}

/// Fail when an id repeats in one operation. For example, the second of two
/// nodes `a` fails with `[1].id: repeats the id 'a'`.
fn no_repeated_ids<'a>(ids: impl Iterator<Item = &'a str>) -> Result<(), FromValueError> {
    let mut seen = HashSet::new();
    for (index, id) in ids.enumerate() {
        if !seen.insert(id) {
            let error = FromValueError::new(format!("repeats the id {}", quoted(id)));
            return Err(error.at_key("id").at_index(index));
        }
    }
    Ok(())
}

/// Fail when one `update_nodes` writes one path of one node twice, which is a
/// client bug.
fn no_repeated_paths(updates: &[FieldUpdate]) -> Result<(), FromValueError> {
    let mut seen = HashSet::new();
    for (index, update) in updates.iter().enumerate() {
        if !seen.insert((update.id.as_str(), &*update.path)) {
            let message = format!(
                "repeats the path {} of node {}",
                path_label(&update.path),
                quoted(&update.id)
            );
            return Err(FromValueError::new(message).at_index(index));
        }
    }
    Ok(())
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
            Value::Array(
                self.path
                    .into_segments()
                    .into_iter()
                    .map(Segment::into_value)
                    .collect(),
            ),
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
        let mut path: Option<NodePath> = None;
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
            json!({"type": "add_nodes", "nodes": [{"id": "a", "data": {"node": {"template": {}}}}]}),
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
    fn node_paths_refuse_what_a_field_update_may_not_write() {
        let key = |key: &str| Segment::Key(key.into());
        for (path, message) in [
            (vec![], "path: must not be empty"),
            (vec![key("id")], "path: cannot change the node's id"),
            (
                vec![key("data"), key("node")],
                "path: cannot write the whole of data.node; write inside it",
            ),
        ] {
            assert_eq!(NodePath::try_from(path).unwrap_err().message, message);
        }
        let path = vec![key("data"), key("node"), key("outputs")];
        assert_eq!(*NodePath::try_from(path.clone()).unwrap(), path[..]);
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
            (
                json!([{"type": "add_nodes", "nodes": [{"data": {}}]}]),
                "operations[0].nodes[0].id: must be a non-empty string",
            ),
            (
                json!([{"type": "add_nodes", "nodes": [{"id": "a", "data": {}}]}]),
                "operations[0].nodes[0].data.node: must be an object (node 'a')",
            ),
            (
                json!([{"type": "add_nodes", "nodes": [
                    {"id": "a", "data": {"node": {"template": {}}}},
                    {"id": "a", "data": {"node": {"template": {}}}},
                ]}]),
                "operations[0].nodes[1].id: repeats the id 'a'",
            ),
            (
                json!([{"type": "add_edges", "edges": [{"id": "e", "source": "a"}]}]),
                "operations[0].edges[0].target: must be a non-empty string",
            ),
            (
                json!([{"type": "add_edges", "edges": [
                    {"id": "e", "source": "a", "target": "b"},
                    {"id": "e", "source": "b", "target": "a"},
                ]}]),
                "operations[0].edges[1].id: repeats the id 'e'",
            ),
            (
                json!([{"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["id"], "value": "b"}]}]),
                "operations[0].updates[0].path: cannot change the node's id",
            ),
            (
                json!([{"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["data", "node"]}]}]),
                "operations[0].updates[0].path: cannot write the whole of data.node; write inside it",
            ),
            (
                json!([{"type": "update_nodes", "updates": [
                    {"id": "a", "op": "delete_field", "path": ["position"]},
                    {"id": "a", "op": "set_field", "path": ["position"], "value": {}},
                ]}]),
                "operations[0].updates[1]: repeats the path [\"position\"] of node 'a'",
            ),
        ] {
            let error = Operation::list_from_value(operations).unwrap_err();
            assert_eq!(error.message, message);
        }
    }
}
