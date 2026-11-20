//! Operation types and their strict parser.

use std::ops::Deref;

use crate::json::{FlowObj, FlowValue};

use crate::flow::deserialize::{DeserializeError, FromFlowValue};
use crate::flow::edge::Edge;
use crate::flow::model::NODE_OBJECT_PATHS;
use crate::flow::node::Node;
use crate::flow::path::{AsKey, Path, PathExt, Segment};
use crate::violation::error::{Error, Result};

/// What a field update does at its path.
#[derive(Debug, Clone, PartialEq)]
pub enum Change {
    /// Write this value.
    Set(FlowValue),
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

    fn match_node_object<P: PathExt + ?Sized>(path: &P) -> Option<&&[&str]> {
        NODE_OBJECT_PATHS.iter().find(|np| path.equals(np))
    }

    /// Check that a field update may write `path`. For example, `["id"]`
    /// fails with `cannot change the node's id`. It reads only object keys,
    /// so it works on built segments and on the JSON list they come from.
    fn check<T: AsKey>(path: &[T]) -> Result<(), DeserializeError> {
        if path.is_empty() {
            return Err(DeserializeError::new("must not be empty"));
        }
        if path[0].as_key() == Some("id") {
            return Err(DeserializeError::new("cannot change the node's id"));
        }
        if let Some(nop) = Self::match_node_object(path) {
            return Err(DeserializeError::new(format!(
                "cannot write the whole of {}; write inside it",
                nop.join(".")
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
    pub fn set(id: &str, path: NodePath, value: FlowValue) -> Self {
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
    pub(crate) fn from_map(object: &FlowObj) -> Result<Self, DeserializeError> {
        match object.get("type") {
            None => Err(DeserializeError::new("type is missing")),
            Some(FlowValue::String(name)) => name.parse(),
            _ => Err(DeserializeError::new("must be a string").at_key("type")),
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
}

impl TryFrom<Path> for NodePath {
    type Error = Error;

    /// Check `path`, and keep it as a field update's path.
    fn try_from(path: Path) -> Result<Self> {
        Self::check(&path).map_err(|error| error.into_error("path"))?;
        Ok(Self(path))
    }
}

impl FromFlowValue for NodePath {
    /// Check the JSON list first, so an invalid path builds no segments.
    fn from_value(value: FlowValue) -> Result<Self, DeserializeError> {
        let items = value
            .as_array()
            .ok_or_else(|| DeserializeError::new("must be a list"))?;
        Self::check(items)?;
        Ok(Self(Path::from_value(value)?))
    }
}

#[cfg(test)]
mod tests {
    use crate::flow_value;

    use super::*;

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
    fn node_path_checks_read_string_lists_and_json_lists() {
        let message = |error: DeserializeError| error.into_error("path").message;
        let strings: Vec<String> = vec!["data".into(), "node".into()];
        assert_eq!(
            message(NodePath::check(&strings).unwrap_err()),
            "path: cannot write the whole of data.node; write inside it"
        );
        assert_eq!(
            message(NodePath::check(&["id"]).unwrap_err()),
            "path: cannot change the node's id"
        );
        assert!(NodePath::check(&["data", "node", "outputs"]).is_ok());
        assert_eq!(
            message(NodePath::check::<&str>(&[]).unwrap_err()),
            "path: must not be empty"
        );
        let FlowValue::Array(items) = flow_value!(["data", {"key": "node"}]) else {
            unreachable!()
        };
        assert!(NodePath::check(&items).is_ok());
        assert_eq!(
            NodePath::from_value(flow_value!(["data", "node", "template"]))
                .unwrap_err()
                .into_error("path")
                .message,
            "path: cannot write the whole of data.node.template; write inside it"
        );
    }
}
