//! [`Node`]: a node object that passed its checks, and [`NodeRef`].

use crate::json::{FlowObj, FlowValue};

use crate::flow::deserialize::{DeserializeError, FromFlowValue};
use crate::flow::model::EntryExt;
use crate::flow::model::NODE_OBJECT_PATHS;
use crate::json::serialize::quoted;

/// A node of a flow: one that `add_nodes` adds, or one the flow holds.
///
/// Its `id` is a non-empty string, and its `data`, `data.node` and
/// `data.node.template` are objects. A `Node` cannot be made without these
/// checks, and a field update cannot undo them (see [`NodePath`](crate::NodePath)), so no
/// reader checks them again.
///
/// A node is shared, not copied: a clone of a node, a snapshot of a graph
/// ([`crate::GraphSnapshot`]) and the forward operations of a batch all
/// hold the same objects ([`FlowObj`]). A write copies only the objects on
/// the way to the value it writes, and only while another holder still has
/// them.
#[derive(Debug, Clone, PartialEq)]
pub struct Node(FlowValue);

impl Node {
    /// The node's id.
    #[must_use]
    pub fn id(&self) -> &str {
        self.0.id()
    }

    /// The node as a JSON object.
    #[must_use]
    pub fn as_map(&self) -> &FlowObj {
        match &self.0 {
            FlowValue::Object(node) => node,
            _ => unreachable!("a node is a JSON object"),
        }
    }

    /// The node as a JSON object, moved out.
    #[must_use]
    pub fn into_map(self) -> FlowObj {
        match self.into_value() {
            FlowValue::Object(node) => node,
            _ => unreachable!("a node is a JSON object"),
        }
    }

    /// The node as a JSON value, for reading a path in it.
    pub(crate) fn as_value(&self) -> &FlowValue {
        &self.0
    }

    /// The node as a JSON value, for writing a path in it. A field update's
    /// [`NodePath`](crate::NodePath) keeps the node's shape. Each object on the way to the
    /// value written is copied first while another holder shares it.
    pub(crate) fn as_value_mut(&mut self) -> &mut FlowValue {
        &mut self.0
    }

    /// The node as a JSON value, moved out.
    pub(crate) fn into_value(self) -> FlowValue {
        self.0
    }

    /// Check that `node` has the shape of a node.
    fn check(node: &FlowObj) -> Result<(), DeserializeError> {
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
    node: &'a FlowObj,
    body: &'a FlowObj,
    template: &'a FlowObj,
}

impl<'a> NodeRef<'a> {
    /// Check that `node` has the shape of a node, and borrow it.
    pub(crate) fn new(node: &'a FlowObj) -> Result<Self, DeserializeError> {
        Self::read(node)
    }

    /// Borrow `node` and find its objects. For example, a node without
    /// `data.node` fails with `data.node: must be an object (node 'a')`.
    fn read(node: &'a FlowObj) -> Result<Self, DeserializeError> {
        let Some(id) = node.non_empty_str("id") else {
            return Err(DeserializeError::new("must be a non-empty string").at_key("id"));
        };
        let not_object = |path: &[&'static str]| {
            let error = DeserializeError::new(format!("must be an object (node {})", quoted(id)));
            // An error takes its innermost key first.
            path.iter()
                .rev()
                .fold(error, |error, key| error.at_key(key))
        };
        let [data_path, body_path, template_path] = NODE_OBJECT_PATHS;
        let Some(FlowValue::Object(data)) = node.get("data") else {
            return Err(not_object(data_path));
        };
        let Some(FlowValue::Object(body)) = data.get("node") else {
            return Err(not_object(body_path));
        };
        let Some(FlowValue::Object(template)) = body.get("template") else {
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
    pub(crate) fn body(self) -> &'a FlowObj {
        self.body
    }

    /// The node's `data.node.template`.
    pub(crate) fn template(self) -> &'a FlowObj {
        self.template
    }
}

impl TryFrom<FlowObj> for Node {
    type Error = DeserializeError;

    /// Check `node`, and keep it as a node.
    fn try_from(node: FlowObj) -> Result<Self, DeserializeError> {
        Self::check(&node)?;
        Ok(Self(FlowValue::Object(node)))
    }
}

impl FromFlowValue for Node {
    fn from_value(value: FlowValue) -> Result<Self, DeserializeError> {
        let node = FlowObj::from_value(value)?;
        Self::check(&node)?;
        Ok(Self(FlowValue::Object(node)))
    }
}
