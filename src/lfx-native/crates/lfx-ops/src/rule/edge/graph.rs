//! Read access to a graph, enough to check edges, and [`GraphView`]: a
//! plain flow graph indexed for that read.

use std::borrow::Cow;

use crate::map::hash::HashMap;
use crate::flow::model::EntryExt;
use crate::flow::node::NodeRef;
use crate::json::{FlowObj, FlowValue};
use crate::violation::error::Result;

/// Read access to an indexed graph, enough to check edges.
pub(crate) trait GraphRead {
    /// Whether the graph has a node with `id`.
    fn has_node(&self, id: &str) -> bool;
    /// The value at the object keys `path` of the node `id`, with the batch's writes.
    fn node_value(&self, id: &str, path: &[&str]) -> Option<Cow<'_, FlowValue>>;
    /// The edge with `id`.
    fn edge(&self, id: &str) -> Option<&FlowObj>;
    /// The ids of the edges at a node.
    fn edge_ids_at(&self, node_id: &str) -> impl Iterator<Item = &str>;
}

/// The source or target of an edge that passed structural validation.
pub(crate) fn endpoint<'e>(edge: &'e FlowObj, end: &str) -> &'e str {
    edge.get(end)
        .and_then(FlowValue::as_str)
        .unwrap_or_default()
}

/// A structurally valid graph, indexed for the edge rules.
#[derive(Debug)]
pub(crate) struct GraphView<'a> {
    nodes: HashMap<&'a str, &'a FlowValue>,
    edges: HashMap<&'a str, &'a FlowObj>,
    edges_at: HashMap<&'a str, Vec<&'a str>>,
}

impl<'a> GraphView<'a> {
    /// Build the indexes of a graph that passed structural validation.
    ///
    /// # Errors
    ///
    /// A node does not have the shape of a node.
    pub fn new(graph: &'a FlowValue) -> Result<Self> {
        let mut view = Self {
            nodes: HashMap::default(),
            edges: HashMap::default(),
            edges_at: HashMap::default(),
        };
        for node in list(graph, "nodes") {
            let Some(map) = node.as_object() else {
                continue;
            };
            view.nodes.insert(
                NodeRef::new(map)
                    .map_err(|error| error.into_error("node"))?
                    .id(),
                node,
            );
        }
        for edge in list(graph, "edges").iter().filter_map(FlowValue::as_object) {
            let id = edge.id();
            view.edges.insert(id, edge);
            let source = endpoint(edge, "source");
            let target = endpoint(edge, "target");
            view.edges_at.entry(source).or_default().push(id);
            if target != source {
                view.edges_at.entry(target).or_default().push(id);
            }
        }
        Ok(view)
    }
}

impl GraphRead for GraphView<'_> {
    fn has_node(&self, id: &str) -> bool {
        self.nodes.contains_key(id)
    }

    fn node_value(&self, id: &str, path: &[&str]) -> Option<Cow<'_, FlowValue>> {
        let node = self.nodes.get(id)?;
        path.iter()
            .try_fold(*node, |value, key| value.get(key))
            .map(Cow::Borrowed)
    }

    fn edge(&self, id: &str) -> Option<&FlowObj> {
        self.edges.get(id).copied()
    }

    fn edge_ids_at(&self, node_id: &str) -> impl Iterator<Item = &str> {
        self.edges_at.get(node_id).into_iter().flatten().copied()
    }
}

pub(crate) fn list<'a>(graph: &'a FlowValue, key: &str) -> &'a [FlowValue] {
    graph
        .get(key)
        .and_then(FlowValue::as_array)
        .unwrap_or_default()
}
