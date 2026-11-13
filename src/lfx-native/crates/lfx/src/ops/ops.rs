//! Operation types and their strict parser.
//!
//! Each type reads itself from a parsed JSON value (`FromAnyValue`), so the
//! parser accepts exactly the shapes the operation protocol defines: no
//! unknown keys, no missing fields, no wrong types. A path names a list item
//! by its key, never by its index. An operation that is parsed and printed
//! again reads as it was sent.

use std::ops::Deref;
use std::str::FromStr;

use crate::json;
use crate::ops::maps::HashSet;
use crate::value::{AnyMap, AnyValue};

use crate::ops::entry::EntryExt;
use crate::ops::error::{Error, Result, quoted};
use crate::ops::from_value::{FromAnyValue, FromAnyValueError, missing, read, unexpected};
use crate::ops::schema::{KeyWrite, NODE_OBJECT_PATHS, NODE_SCHEMA};

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
    fn to_value(&self) -> AnyValue {
        match self {
            Self::Key(key) => AnyValue::from(key.as_str()),
            Self::Item(key) => json!({"key": key}),
        }
    }

    /// The same JSON as [`Self::to_value`], but it moves the key into the
    /// value instead of copying it.
    fn into_value(self) -> AnyValue {
        match self {
            Self::Key(key) => AnyValue::from(key),
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
    AnyValue::Array(path.iter().map(Segment::to_value).collect()).to_string()
}

/// What a field update does at its path.
#[derive(Debug, Clone, PartialEq)]
pub enum Change {
    /// Write this value.
    Set(AnyValue),
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
    fn check(path: &[Segment]) -> Result<(), FromAnyValueError> {
        if path.is_empty() {
            return Err(FromAnyValueError::new("must not be empty"));
        }
        if path[0].as_key() == Some("id") {
            return Err(FromAnyValueError::new("cannot change the node's id"));
        }
        if let Some(object) = NODE_OBJECT_PATHS.iter().find(|object| path.equals(object)) {
            return Err(FromAnyValueError::new(format!(
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

impl FromAnyValue for NodePath {
    fn from_value(value: AnyValue) -> Result<Self, FromAnyValueError> {
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
    pub fn set(id: &str, path: NodePath, value: AnyValue) -> Self {
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
///
/// A node is shared, not copied: a clone of a node, a snapshot of a graph
/// ([`crate::ops::GraphSnapshot`]) and the forward operations of a batch all
/// hold the same objects ([`AnyMap`]). A write copies only the objects on
/// the way to the value it writes, and only while another holder still has
/// them.
#[derive(Debug, Clone, PartialEq)]
pub struct Node(AnyValue);

impl Node {
    /// The node's id.
    #[must_use]
    pub fn id(&self) -> &str {
        self.0.id()
    }

    /// The node as a JSON object.
    #[must_use]
    pub fn as_map(&self) -> &AnyMap {
        match &self.0 {
            AnyValue::Object(node) => node,
            _ => unreachable!("a node is a JSON object"),
        }
    }

    /// The node as a JSON object, moved out.
    #[must_use]
    pub fn into_map(self) -> AnyMap {
        match self.into_value() {
            AnyValue::Object(node) => node,
            _ => unreachable!("a node is a JSON object"),
        }
    }

    /// The node as a JSON value, for reading a path in it.
    pub(crate) fn as_value(&self) -> &AnyValue {
        &self.0
    }

    /// The node as a JSON value, for writing a path in it. A field update's
    /// [`NodePath`] keeps the node's shape. Each object on the way to the
    /// value written is copied first while another holder shares it.
    pub(crate) fn as_value_mut(&mut self) -> &mut AnyValue {
        &mut self.0
    }

    /// The node as a JSON value, moved out.
    pub(crate) fn into_value(self) -> AnyValue {
        self.0
    }

    /// Check that `node` has the shape of a node.
    fn check(node: &AnyMap) -> Result<(), FromAnyValueError> {
        NodeRef::read(node).map(|_| ())
    }
}

/// A borrowed node with the shape of a [`Node`], and its `data.node` and
/// `data.node.template` objects, found once.
///
/// [`Node`] checks its shape through it, and validation reads the nodes it
/// compares through it, so neither checks a node's shape twice.
#[derive(Debug, Clone, Copy)]
pub(crate) struct NodeRef<'a> {
    node: &'a AnyMap,
    body: &'a AnyMap,
    template: &'a AnyMap,
}

impl<'a> NodeRef<'a> {
    /// Check that `node` has the shape of a node, and borrow it.
    pub(crate) fn new(node: &'a AnyMap) -> Result<Self> {
        Self::read(node).map_err(|error| error.into_error("node"))
    }

    /// Borrow `node` and find its objects. For example, a node without
    /// `data.node` fails with `data.node: must be an object (node 'a')`.
    fn read(node: &'a AnyMap) -> Result<Self, FromAnyValueError> {
        let Some(id) = node.non_empty_str("id") else {
            return Err(FromAnyValueError::new("must be a non-empty string").at_key("id"));
        };
        let not_object = |path: &[&'static str]| {
            let error = FromAnyValueError::new(format!("must be an object (node {})", quoted(id)));
            // An error takes its innermost key first.
            path.iter()
                .rev()
                .fold(error, |error, key| error.at_key(key))
        };
        let [data_path, body_path, template_path] = NODE_OBJECT_PATHS;
        let Some(AnyValue::Object(data)) = node.get("data") else {
            return Err(not_object(data_path));
        };
        let Some(AnyValue::Object(body)) = data.get("node") else {
            return Err(not_object(body_path));
        };
        let Some(AnyValue::Object(template)) = body.get("template") else {
            return Err(not_object(template_path));
        };
        Ok(Self {
            node,
            body,
            template,
        })
    }

    /// The node's id.
    pub(crate) fn id(self) -> &'a str {
        self.node.id()
    }

    /// The node's `data.node`.
    pub(crate) fn body(self) -> &'a AnyMap {
        self.body
    }

    /// The node's `data.node.template`.
    pub(crate) fn template(self) -> &'a AnyMap {
        self.template
    }
}

impl TryFrom<AnyMap> for Node {
    type Error = Error;

    /// Check `node`, and keep it as a node.
    fn try_from(node: AnyMap) -> Result<Self> {
        Self::check(&node).map_err(|error| error.into_error("node"))?;
        Ok(Self(AnyValue::Object(node)))
    }
}

impl FromAnyValue for Node {
    fn from_value(value: AnyValue) -> Result<Self, FromAnyValueError> {
        let node = AnyMap::from_value(value)?;
        Self::check(&node)?;
        Ok(Self(AnyValue::Object(node)))
    }
}

/// An edge of a flow: one that `add_edges` adds, or one the flow holds.
///
/// Its `id`, `source` and `target` are non-empty strings. An `Edge` cannot be
/// made without these checks, and an edge is never written in place, so no
/// reader checks them again. Whether the nodes and handles it names exist
/// depends on the flow, so apply checks that. Like a [`Node`], an edge is
/// shared, not copied.
#[derive(Debug, Clone, PartialEq)]
pub struct Edge(AnyMap);

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
    pub fn as_map(&self) -> &AnyMap {
        &self.0
    }

    /// The edge as a JSON object, moved out.
    #[must_use]
    pub fn into_map(self) -> AnyMap {
        self.0
    }

    /// Check that `edge` has the shape of an edge.
    fn check(edge: &AnyMap) -> Result<(), FromAnyValueError> {
        for key in ["id", "source", "target"] {
            if edge.non_empty_str(key).is_none() {
                return Err(FromAnyValueError::new("must be a non-empty string").at_key(key));
            }
        }
        Ok(())
    }
}

impl TryFrom<AnyMap> for Edge {
    type Error = Error;

    /// Check `edge`, and keep it as an edge.
    fn try_from(edge: AnyMap) -> Result<Self> {
        Self::check(&edge).map_err(|error| error.into_error("edge"))?;
        Ok(Self(edge))
    }
}

impl FromAnyValue for Edge {
    fn from_value(value: AnyValue) -> Result<Self, FromAnyValueError> {
        let edge = AnyMap::from_value(value)?;
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
    fn from_map(object: &AnyMap) -> Result<Self, FromAnyValueError> {
        match object.get("type") {
            None => Err(FromAnyValueError::new("type is missing")),
            Some(AnyValue::String(name)) => name.parse(),
            _ => Err(FromAnyValueError::new("must be a string").at_key("type")),
        }
    }
}

impl FromStr for OperationKind {
    type Err = FromAnyValueError;

    /// The kind that a `type` names.
    fn from_str(name: &str) -> Result<Self, FromAnyValueError> {
        match name {
            "add_nodes" => Ok(Self::AddNodes),
            "update_nodes" => Ok(Self::UpdateNodes),
            "delete_nodes" => Ok(Self::DeleteNodes),
            "add_edges" => Ok(Self::AddEdges),
            "delete_edges" => Ok(Self::DeleteEdges),
            _ => {
                let message = format!("unsupported operation type {}", quoted(name));
                Err(FromAnyValueError::new(message).at_key("type"))
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
    pub fn list_from_value(operations: AnyValue) -> Result<Vec<Self>> {
        Vec::from_value(operations).map_err(|error| error.into_error("operations"))
    }

    /// The operation as JSON. It copies every payload; a caller that owns
    /// the operation and drops it after printing uses [`Self::into_value`].
    #[must_use]
    pub fn to_value(&self) -> AnyValue {
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
    pub fn into_value(self) -> AnyValue {
        let (kind, key, payload) = match self {
            Self::AddNodes(nodes) => ("add_nodes", "nodes", objects(nodes, Node::into_map)),
            Self::UpdateNodes(updates) => (
                "update_nodes",
                "updates",
                AnyValue::Array(updates.into_iter().map(FieldUpdate::into_value).collect()),
            ),
            Self::DeleteNodes(ids) => ("delete_nodes", "ids", strings(ids)),
            Self::AddEdges(edges) => ("add_edges", "edges", objects(edges, Edge::into_map)),
            Self::DeleteEdges(ids) => ("delete_edges", "ids", strings(ids)),
        };
        let mut operation = AnyMap::new();
        operation.insert("type".into(), AnyValue::from(kind));
        operation.insert(key.into(), payload);
        AnyValue::Object(operation)
    }
}

fn objects<T>(objects: Vec<T>, into_map: fn(T) -> AnyMap) -> AnyValue {
    AnyValue::Array(
        objects
            .into_iter()
            .map(|object| AnyValue::Object(into_map(object)))
            .collect(),
    )
}

fn strings(strings: Vec<String>) -> AnyValue {
    AnyValue::Array(strings.into_iter().map(AnyValue::from).collect())
}

impl TryFrom<AnyValue> for Operation {
    type Error = Error;

    /// Parse one operation. It fails unless the operation has exactly one of
    /// the protocol's shapes.
    fn try_from(operation: AnyValue) -> Result<Self> {
        Self::from_value(operation).map_err(|error| error.into_error("operation"))
    }
}

impl FromAnyValue for Operation {
    fn from_value(value: AnyValue) -> Result<Self, FromAnyValueError> {
        let object = AnyMap::from_value(value)?;
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
fn no_repeated_ids<'a>(ids: impl Iterator<Item = &'a str>) -> Result<(), FromAnyValueError> {
    let mut seen = HashSet::default();
    for (index, id) in ids.enumerate() {
        if !seen.insert(id) {
            let error = FromAnyValueError::new(format!("repeats the id {}", quoted(id)));
            return Err(error.at_key("id").at_index(index));
        }
    }
    Ok(())
}

/// Fail when one `update_nodes` writes one path of one node twice, which is a
/// client bug.
fn no_repeated_paths(updates: &[FieldUpdate]) -> Result<(), FromAnyValueError> {
    let mut seen = HashSet::default();
    for (index, update) in updates.iter().enumerate() {
        if !seen.insert((update.id.as_str(), &*update.path)) {
            let message = format!(
                "repeats the path {} of node {}",
                path_label(&update.path),
                quoted(&update.id)
            );
            return Err(FromAnyValueError::new(message).at_index(index));
        }
    }
    Ok(())
}

/// The value of an operation's one payload key, read as `T`. The operation
/// may hold only `type` and `key`.
fn payload<T: FromAnyValue>(object: AnyMap, key: &'static str) -> Result<T, FromAnyValueError> {
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
    pub fn to_value(&self) -> AnyValue {
        let path = AnyValue::Array(self.path.iter().map(Segment::to_value).collect());
        match &self.change {
            Change::Set(value) => {
                json!({"id": self.id, "path": path, "op": "set_field", "value": value})
            }
            Change::Delete => json!({"id": self.id, "path": path, "op": "delete_field"}),
        }
    }

    /// The update as JSON, with its path and value moved into the result instead of copied.
    #[must_use]
    pub fn into_value(self) -> AnyValue {
        let mut update = AnyMap::new();
        update.insert("id".into(), AnyValue::from(self.id));
        update.insert(
            "path".into(),
            AnyValue::Array(
                self.path
                    .into_segments()
                    .into_iter()
                    .map(Segment::into_value)
                    .collect(),
            ),
        );
        match self.change {
            Change::Set(value) => {
                update.insert("op".into(), AnyValue::from("set_field"));
                update.insert("value".into(), value);
            }
            Change::Delete => {
                update.insert("op".into(), AnyValue::from("delete_field"));
            }
        }
        AnyValue::Object(update)
    }
}

impl FromAnyValue for FieldUpdate {
    fn from_value(value: AnyValue) -> Result<Self, FromAnyValueError> {
        let object = AnyMap::from_value(value)?;
        let set = match object.get("op") {
            None => return Err(FromAnyValueError::new("op is missing")),
            Some(AnyValue::String(op)) if op == "set_field" => true,
            Some(AnyValue::String(op)) if op == "delete_field" => false,
            Some(_) => {
                return Err(
                    FromAnyValueError::new("must be set_field or delete_field").at_key("op")
                );
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
            return Err(FromAnyValueError::new("must not be empty").at_key("id"));
        }
        let path = path.ok_or_else(|| missing("path"))?;
        let change = if set {
            Change::Set(written.ok_or_else(|| missing("value"))?)
        } else {
            Change::Delete
        };
        let update = Self { id, path, change };
        update.check_keys_kept()?;
        Ok(update)
    }
}

impl FieldUpdate {
    /// Check that the update keeps the key of every list item on its path. An
    /// item's key is its id, so no write may change it, as no write may change
    /// a node's `id`. To give an item another key, delete it and add it again.
    fn check_keys_kept(&self) -> Result<(), FromAnyValueError> {
        for (index, segment) in self.path.iter().enumerate() {
            let Segment::Item(key) = segment else {
                continue;
            };
            let inner = &self.path[index + 1..];
            let keyed = NODE_SCHEMA.listed_at(&self.path[..index]);
            match keyed.key_after_write(inner, &self.change) {
                KeyWrite::Untouched => {}
                KeyWrite::Key(after) if after == key => {}
                _ if inner.is_empty() => {
                    let message = format!(
                        "a list item written at its key must carry the same key: {}",
                        quoted(key)
                    );
                    return Err(FromAnyValueError::new(message).at_key("value"));
                }
                _ => {
                    return Err(
                        FromAnyValueError::new("cannot change a list item's key").at_key("path")
                    );
                }
            }
        }
        Ok(())
    }
}

impl FromAnyValue for Segment {
    fn from_value(value: AnyValue) -> Result<Self, FromAnyValueError> {
        let invalid = || {
            FromAnyValueError::new(r#"must be an object key or {"key": ...} with a non-empty key"#)
        };
        match value {
            AnyValue::String(key) => Ok(Self::Key(key.to_string())),
            AnyValue::Number(_) => Err(FromAnyValueError::new(
                r#"integer list indexes are not allowed; name a list item with {"key": ...}"#,
            )),
            AnyValue::Object(item) if item.len() == 1 => match item.into_iter().next() {
                Some((name, AnyValue::String(key))) if name == "key" && !key.is_empty() => {
                    Ok(Self::Item(key.to_string()))
                }
                _ => Err(invalid()),
            },
            _ => Err(invalid()),
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::json;

    use super::*;

    #[test]
    fn text_reads_and_writes_as_the_general_way_does() {
        let general = |text: &str| {
            let value: crate::value::FiniteAnyValue = serde_json::from_str(text).unwrap();
            Operation::list_from_value(value.0)
        };
        for text in [
            r#"[{"type":"add_nodes","nodes":[{"id":"a","data":{"node":{"template":{"t":{"value":"é 😀","n":1.5}}}}}]}]"#,
            r#"[{"type":"update_nodes","updates":[{"op":"set_field","id":"a","path":["data","node","outputs",{"key":"out"}],"value":{"name":"out","size":1}},{"id":"a","path":["data","node","template","rows","value",{"key":"r"}],"op":"delete_field"}]}]"#,
            r#"[{"type":"delete_nodes","ids":["a","b"]},{"type":"delete_edges","ids":["e"]}]"#,
            r#"[{"type":"add_edges","edges":[{"id":"e","source":"a","target":"b","data":{"x":[1,2]}}]}]"#,
            "[]",
        ] {
            assert_eq!(
                operations_from_text(text),
                Some(general(text).unwrap()),
                "{text}"
            );
            for operation in general(text).unwrap() {
                let mut written = Vec::new();
                operation.write_json(&mut written, crate::json_out::Ascii::Escape);
                let expected = crate::ops::api::json_text(&operation.to_value());
                assert_eq!(String::from_utf8(written).unwrap(), expected);
            }
        }
        // Other shapes, and text that breaks a rule, are left to the general reader.
        for text in [
            r#"[{"ids":["a"],"type":"delete_nodes"}]"#,
            r#"[{"type":"delete_nodes","ids":["a"],"ids":["b"]}]"#,
            r#"[{"type":"delete_nodes","ids":[1]}]"#,
            r#"[{"type":"update_nodes","updates":[{"op":"set_field","id":"a","path":["id"],"value":"b"}]}]"#,
            r#"[{"type":"update_nodes","updates":[{"op":"delete_field","id":"a","path":["x"],"value":1}]}]"#,
            r#"[{"type":"add_nodes","nodes":[{"id":"a"},{"id":"a"}]}]"#,
            r#"{"type":"delete_nodes","ids":["a"]}"#,
            r#"[{"type":"delete_nodes","ids":["a"]}] x"#,
        ] {
            assert_eq!(operations_from_text(text), None, "{text}");
        }
    }

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

// --- Writing and reading operation text without a JSON value ---------------------------------

impl Operation {
    /// Write the operation as JSON text, as [`crate::json_out::write_value`]
    /// writes [`Self::to_value`], without building that value.
    pub(crate) fn write_json(&self, out: &mut Vec<u8>, ascii: crate::json_out::Ascii) {
        use crate::json_out::{write_map, write_seq, write_str};
        out.extend_from_slice(b"{\"type\":");
        write_str(out, self.kind().as_str(), ascii);
        match self {
            Self::AddNodes(nodes) => {
                out.extend_from_slice(b",\"nodes\":");
                write_seq(out, nodes, |out, node| write_map(out, node.as_map(), ascii));
            }
            Self::UpdateNodes(updates) => {
                out.extend_from_slice(b",\"updates\":");
                write_seq(out, updates, |out, update| update.write_json(out, ascii));
            }
            Self::DeleteNodes(ids) | Self::DeleteEdges(ids) => {
                out.extend_from_slice(b",\"ids\":");
                write_seq(out, ids, |out, id| write_str(out, id, ascii));
            }
            Self::AddEdges(edges) => {
                out.extend_from_slice(b",\"edges\":");
                write_seq(out, edges, |out, edge| write_map(out, edge.as_map(), ascii));
            }
        }
        out.push(b'}');
    }
}

impl FieldUpdate {
    fn write_json(&self, out: &mut Vec<u8>, ascii: crate::json_out::Ascii) {
        use crate::json_out::{write_seq, write_str, write_value};
        out.extend_from_slice(b"{\"id\":");
        write_str(out, &self.id, ascii);
        out.extend_from_slice(b",\"path\":");
        write_seq(out, self.path.iter(), |out, segment| match segment {
            Segment::Key(key) => write_str(out, key, ascii),
            Segment::Item(key) => {
                out.extend_from_slice(b"{\"key\":");
                write_str(out, key, ascii);
                out.push(b'}');
            }
        });
        match &self.change {
            Change::Set(value) => {
                out.extend_from_slice(b",\"op\":\"set_field\",\"value\":");
                write_value(out, value, ascii);
            }
            Change::Delete => out.extend_from_slice(b",\"op\":\"delete_field\""),
        }
        out.push(b'}');
    }
}

/// Read operations from JSON text straight into their types, without a JSON
/// value for the whole batch. It reads only text in the common shape: an
/// operation with its `type` first, and no repeated key. For any other text,
/// or text that breaks a rule, it returns `None`, and the caller reads the
/// text the general way, which gives the same operations or the exact error.
pub(crate) fn operations_from_text(text: &str) -> Option<Vec<Operation>> {
    let mut builder = crate::value::Builder::<true>::default();
    let mut deserializer = serde_json::Deserializer::from_str(text);
    let operations =
        serde::de::DeserializeSeed::deserialize(text::Operations(&mut builder), &mut deserializer)
            .ok()?;
    deserializer.end().ok()?;
    Some(operations)
}

mod text {
    use std::fmt;

    use serde::de::{
        self, DeserializeSeed, Deserializer, IgnoredAny, MapAccess, SeqAccess, Visitor,
    };

    use super::{
        Change, Edge, FieldUpdate, Node, NodePath, Operation, OperationKind, Segment,
        no_repeated_ids, no_repeated_paths,
    };
    use crate::ops::from_value::FromAnyValue;
    use crate::value::{AnyValue, Builder, FiniteSeed};

    /// Any failure: the caller reads the text the general way.
    fn bail<E: de::Error>() -> E {
        E::custom("not in the common shape")
    }

    /// A key of an operation or a field update, read without allocating.
    #[derive(PartialEq, Eq)]
    enum Key {
        Type,
        Nodes,
        Updates,
        Ids,
        Edges,
        Op,
        Id,
        Path,
        Value,
        Other,
    }

    struct KeySeed;
    impl<'de> DeserializeSeed<'de> for KeySeed {
        type Value = Key;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Key, D::Error> {
            d.deserialize_str(self)
        }
    }
    impl Visitor<'_> for KeySeed {
        type Value = Key;
        fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("a key")
        }
        fn visit_str<E: de::Error>(self, key: &str) -> Result<Key, E> {
            Ok(match key {
                "type" => Key::Type,
                "nodes" => Key::Nodes,
                "updates" => Key::Updates,
                "ids" => Key::Ids,
                "edges" => Key::Edges,
                "op" => Key::Op,
                "id" => Key::Id,
                "path" => Key::Path,
                "value" => Key::Value,
                _ => Key::Other,
            })
        }
    }

    /// A string, as an owned `String`.
    struct Text;
    impl<'de> DeserializeSeed<'de> for Text {
        type Value = String;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<String, D::Error> {
            d.deserialize_str(self)
        }
    }
    impl Visitor<'_> for Text {
        type Value = String;
        fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("a string")
        }
        fn visit_str<E: de::Error>(self, text: &str) -> Result<String, E> {
            Ok(text.to_owned())
        }
    }

    /// A list, each item read by `item`.
    struct List<F>(F);
    impl<'de, T, F: FnMut(&mut dyn ItemReader<'de>) -> Option<T>> Visitor<'de> for List<F> {
        type Value = Vec<T>;
        fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("a list")
        }
        fn visit_seq<A: SeqAccess<'de>>(mut self, mut seq: A) -> Result<Vec<T>, A::Error> {
            let mut items = Vec::with_capacity(seq.size_hint().unwrap_or(0));
            loop {
                let mut reader = Reader::<A> {
                    seq: &mut seq,
                    done: false,
                    failed: false,
                };
                let item = (self.0)(&mut reader);
                if reader.failed {
                    return Err(bail());
                }
                if reader.done {
                    return Ok(items);
                }
                items.push(item.ok_or_else(bail)?);
            }
        }
    }

    /// Reads the next item of a list with a seed, without naming the access type.
    trait ItemReader<'de> {
        fn ops(&mut self, builder: &mut Builder<true>) -> Option<Operation>;
        fn value(&mut self, builder: &mut Builder<true>) -> Option<AnyValue>;
        fn text(&mut self) -> Option<String>;
        fn segment(&mut self) -> Option<Segment>;
        fn update(&mut self, builder: &mut Builder<true>) -> Option<FieldUpdate>;
    }

    struct Reader<'s, A> {
        seq: &'s mut A,
        done: bool,
        failed: bool,
    }

    impl<'de, A: SeqAccess<'de>> Reader<'_, A> {
        fn next<S: DeserializeSeed<'de>>(&mut self, seed: S) -> Option<S::Value> {
            match self.seq.next_element_seed(seed) {
                Ok(Some(item)) => Some(item),
                Ok(None) => {
                    self.done = true;
                    None
                }
                Err(_) => {
                    self.failed = true;
                    None
                }
            }
        }
    }

    impl<'de, A: SeqAccess<'de>> ItemReader<'de> for Reader<'_, A> {
        fn ops(&mut self, builder: &mut Builder<true>) -> Option<Operation> {
            self.next(OperationSeed(builder))
        }
        fn value(&mut self, builder: &mut Builder<true>) -> Option<AnyValue> {
            self.next(FiniteSeed(builder))
        }
        fn text(&mut self) -> Option<String> {
            self.next(Text)
        }
        fn segment(&mut self) -> Option<Segment> {
            self.next(SegmentSeed)
        }
        fn update(&mut self, builder: &mut Builder<true>) -> Option<FieldUpdate> {
            self.next(UpdateSeed(builder))
        }
    }

    /// The batch: a list of operations.
    pub(super) struct Operations<'b>(pub(super) &'b mut Builder<true>);
    impl<'de> DeserializeSeed<'de> for Operations<'_> {
        type Value = Vec<Operation>;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Vec<Operation>, D::Error> {
            let builder = self.0;
            d.deserialize_seq(List(|reader: &mut dyn ItemReader<'de>| reader.ops(builder)))
        }
    }

    struct OperationSeed<'b>(&'b mut Builder<true>);
    impl<'de> DeserializeSeed<'de> for OperationSeed<'_> {
        type Value = Operation;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Operation, D::Error> {
            d.deserialize_map(self)
        }
    }
    impl<'de> Visitor<'de> for OperationSeed<'_> {
        type Value = Operation;
        fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("an operation")
        }
        fn visit_map<M: MapAccess<'de>>(self, mut map: M) -> Result<Operation, M::Error> {
            let builder = self.0;
            if map.next_key_seed(KeySeed)? != Some(Key::Type) {
                return Err(bail());
            }
            let kind: OperationKind = map.next_value_seed(Text)?.parse().map_err(|_| bail())?;
            let expected = match kind {
                OperationKind::AddNodes => Key::Nodes,
                OperationKind::UpdateNodes => Key::Updates,
                OperationKind::DeleteNodes | OperationKind::DeleteEdges => Key::Ids,
                OperationKind::AddEdges => Key::Edges,
            };
            if map.next_key_seed(KeySeed)? != Some(expected) {
                return Err(bail());
            }
            let operation = match kind {
                OperationKind::AddNodes => {
                    let values = map.next_value_seed(Values(builder))?;
                    let nodes = values
                        .into_iter()
                        .map(Node::from_value)
                        .collect::<Result<Vec<_>, _>>()
                        .map_err(|_| bail())?;
                    no_repeated_ids(nodes.iter().map(Node::id)).map_err(|_| bail())?;
                    Operation::AddNodes(nodes)
                }
                OperationKind::AddEdges => {
                    let values = map.next_value_seed(Values(builder))?;
                    let edges = values
                        .into_iter()
                        .map(Edge::from_value)
                        .collect::<Result<Vec<_>, _>>()
                        .map_err(|_| bail())?;
                    no_repeated_ids(edges.iter().map(Edge::id)).map_err(|_| bail())?;
                    Operation::AddEdges(edges)
                }
                OperationKind::UpdateNodes => {
                    let updates = map.next_value_seed(Updates(builder))?;
                    no_repeated_paths(&updates).map_err(|_| bail())?;
                    Operation::UpdateNodes(updates)
                }
                OperationKind::DeleteNodes => Operation::DeleteNodes(map.next_value_seed(Ids)?),
                OperationKind::DeleteEdges => Operation::DeleteEdges(map.next_value_seed(Ids)?),
            };
            if map.next_key_seed(KeySeed)?.is_some() {
                return Err(bail());
            }
            Ok(operation)
        }
    }

    struct Values<'b>(&'b mut Builder<true>);
    impl<'de> DeserializeSeed<'de> for Values<'_> {
        type Value = Vec<AnyValue>;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Vec<AnyValue>, D::Error> {
            let builder = self.0;
            d.deserialize_seq(List(|reader: &mut dyn ItemReader<'de>| {
                reader.value(builder)
            }))
        }
    }

    struct Ids;
    impl<'de> DeserializeSeed<'de> for Ids {
        type Value = Vec<String>;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Vec<String>, D::Error> {
            d.deserialize_seq(List(|reader: &mut dyn ItemReader<'de>| reader.text()))
        }
    }

    struct Updates<'b>(&'b mut Builder<true>);
    impl<'de> DeserializeSeed<'de> for Updates<'_> {
        type Value = Vec<FieldUpdate>;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Vec<FieldUpdate>, D::Error> {
            let builder = self.0;
            d.deserialize_seq(List(|reader: &mut dyn ItemReader<'de>| {
                reader.update(builder)
            }))
        }
    }

    struct Path;
    impl<'de> DeserializeSeed<'de> for Path {
        type Value = Vec<Segment>;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Vec<Segment>, D::Error> {
            d.deserialize_seq(List(|reader: &mut dyn ItemReader<'de>| reader.segment()))
        }
    }

    /// A path segment: a string, or `{"key": ...}` with a non-empty key.
    struct SegmentSeed;
    impl<'de> DeserializeSeed<'de> for SegmentSeed {
        type Value = Segment;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Segment, D::Error> {
            d.deserialize_any(self)
        }
    }
    impl<'de> Visitor<'de> for SegmentSeed {
        type Value = Segment;
        fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("a path segment")
        }
        fn visit_str<E: de::Error>(self, key: &str) -> Result<Segment, E> {
            Ok(Segment::Key(key.to_owned()))
        }
        fn visit_map<M: MapAccess<'de>>(self, mut map: M) -> Result<Segment, M::Error> {
            let Some(name) = map.next_key_seed(Text)? else {
                return Err(bail());
            };
            if name != "key" {
                return Err(bail());
            }
            let key = map.next_value_seed(Text)?;
            if key.is_empty() || map.next_key::<IgnoredAny>()?.is_some() {
                return Err(bail());
            }
            Ok(Segment::Item(key))
        }
    }

    struct UpdateSeed<'b>(&'b mut Builder<true>);
    impl<'de> DeserializeSeed<'de> for UpdateSeed<'_> {
        type Value = FieldUpdate;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<FieldUpdate, D::Error> {
            d.deserialize_map(self)
        }
    }
    impl<'de> Visitor<'de> for UpdateSeed<'_> {
        type Value = FieldUpdate;
        fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("a field update")
        }
        fn visit_map<M: MapAccess<'de>>(self, mut map: M) -> Result<FieldUpdate, M::Error> {
            let (mut op, mut id, mut path, mut value) = (None, None, None, None);
            while let Some(key) = map.next_key_seed(KeySeed)? {
                match key {
                    Key::Op if op.is_none() => op = Some(map.next_value_seed(Text)?),
                    Key::Id if id.is_none() => id = Some(map.next_value_seed(Text)?),
                    Key::Path if path.is_none() => path = Some(map.next_value_seed(Path)?),
                    Key::Value if value.is_none() => {
                        value = Some(map.next_value_seed(FiniteSeed(&mut *self.0))?);
                    }
                    _ => return Err(bail()),
                }
            }
            let id = id.filter(|id: &String| !id.is_empty()).ok_or_else(bail)?;
            let path = NodePath::try_from(path.ok_or_else(bail)?).map_err(|_| bail())?;
            let change = match (op.as_deref(), value) {
                (Some("set_field"), Some(value)) => Change::Set(value),
                (Some("delete_field"), None) => Change::Delete,
                _ => return Err(bail()),
            };
            let update = FieldUpdate { id, path, change };
            update.check_keys_kept().map_err(|_| bail())?;
            Ok(update)
        }
    }
}
