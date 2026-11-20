//! [`Graph`]: nodes and edges by id, edges by the nodes they touch, and the batch's field
//! writes. [`Lists`]: the keyed-list indexes of stored nodes.

use std::borrow::Cow;
use std::fmt;

use crate::json::{FlowObj, FlowStr, FlowValue};
use crate::map::hash::{HashMap, IndexSet};
use crate::map::pending::PendingMap;

use crate::flow::edge::Edge;
use crate::flow::list::ListIndex;
use crate::flow::model::{FLOW_MODEL, KeyedList};
use crate::flow::node::Node;
use crate::flow::path::{AsKey, PathExt, Segment};
use crate::rule::edge::GraphRead;
use crate::state::field_write::{self, PendingFieldWrites};
use crate::violation::error::Result;

/// The ids of the edges at each node.
#[derive(Debug)]
pub(crate) struct EdgesAt {
    by_node: PendingMap<IndexSet<FlowStr>>,
}

impl EdgesAt {
    pub(super) fn new() -> Self {
        Self {
            by_node: PendingMap::new(),
        }
    }

    pub(super) fn commit(&mut self) {
        self.by_node.commit();
    }

    pub(super) fn attach(&mut self, id: &str, edge: &Edge) {
        let Some(FlowValue::String(key)) = edge.as_map().get("id") else {
            unreachable!("an edge has a string id");
        };
        debug_assert_eq!(id, key.as_str());
        for end in ends(edge) {
            self.by_node.get_or_insert_with(end, IndexSet::default);
            self.by_node.update(end, |ids| ids.insert(key.clone()));
        }
    }

    pub(super) fn detach(&mut self, id: &str, edge: &Edge) {
        for end in ends(edge) {
            // Remove the last id with its key, without copying the set.
            let kept = self.by_node.update_if(
                end,
                |ids| ids.len() > 1,
                |ids| {
                    ids.shift_remove(id);
                },
            );
            if !kept {
                self.by_node.remove(end);
            }
        }
    }
}

fn ends(edge: &Edge) -> impl Iterator<Item = &str> {
    let source = edge.source();
    let target = edge.target();
    [source, target]
        .into_iter()
        .take(if source == target { 1 } else { 2 })
}

/// Nodes and edges by id, edges by the nodes they touch, and the batch's field writes.
///
/// Its maps are private, so every node read goes through [`field_write::read_through`] and
/// sees the batch's field writes.
#[derive(Debug)]
pub(crate) struct Graph {
    pub(super) nodes: PendingMap<Node>,
    pub(super) edges: PendingMap<Edge>,
    pub(super) edges_at: EdgesAt,
    pub(super) fields: PendingFieldWrites,
}

impl Graph {
    /// The ids of the edges at a node.
    pub fn edges_at(&self, node_id: &str) -> impl Iterator<Item = &str> {
        self.edge_keys_at(node_id).map(FlowStr::as_str)
    }

    /// The shared ids of the edges at a node, in the same order as `edges_at`.
    pub(crate) fn edge_keys_at(&self, node_id: &str) -> impl Iterator<Item = &FlowStr> {
        self.edges_at.by_node.get(node_id).into_iter().flatten()
    }

    /// Whether the graph has an edge with `id`.
    pub fn has_edge(&self, id: &str) -> bool {
        self.edges.contains(id)
    }

    /// Whether node `id` existed when the batch started and the batch did not
    /// replace it. Only a stored node's lists are indexed.
    pub fn is_stored_node(&self, id: &str) -> bool {
        self.nodes.is_based(id) && !self.nodes.is_pending(id)
    }

    /// Follow `path` in node `id` ([`field_write::read_through`]). `None` when there is no
    /// such node.
    ///
    /// # Errors
    ///
    /// `step` fails.
    pub fn read_field<'g>(
        &'g self,
        id: &str,
        path: &[Segment],
        step: impl FnMut(&'g FlowValue, usize, bool) -> Result<Option<&'g FlowValue>>,
    ) -> Result<Option<field_write::ReadThrough<'g>>> {
        let Some(node) = self.nodes.get(id) else {
            return Ok(None);
        };
        field_write::read_through(node.as_value(), self.fields.node(id), path, step).map(Some)
    }

    /// The batch's writes to node `id`, to add one.
    pub fn writes_mut(&mut self, id: &str) -> &mut field_write::PathWrites {
        self.fields.node_mut(id)
    }

    pub(super) fn drop_pending(&mut self) {
        self.nodes.drop_pending();
        self.edges.drop_pending();
        self.edges_at.by_node.drop_pending();
        self.fields.drop_pending();
    }
}

impl GraphRead for Graph {
    fn has_node(&self, id: &str) -> bool {
        self.nodes.contains(id)
    }

    fn node_value(&self, id: &str, path: &[&str]) -> Option<Cow<'_, FlowValue>> {
        let node = self.nodes.get(id)?;
        let writes = self.fields.node(id);
        if writes.is_none() {
            // The batch wrote nothing to the node.
            return path
                .iter()
                .try_fold(node.as_value(), |value, key| value.as_object()?.get(key))
                .map(Cow::Borrowed);
        }
        let path: Vec<Segment> = path
            .iter()
            .map(|key| Segment::Key((*key).to_owned()))
            .collect();
        let step =
            |value, index: usize, _| Ok(field_write::child(value, &path[..index], &path[index]));
        field_write::read(node.as_value(), self.fields.node(id), &path, step)
            .expect("a read of object keys cannot fail")
    }

    fn edge(&self, id: &str) -> Option<&FlowObj> {
        self.edges.get(id).map(Edge::as_map)
    }

    fn edge_ids_at(&self, node_id: &str) -> impl Iterator<Item = &str> {
        self.edges_at(node_id)
    }
}

/// The value at `path` of node `id`, with the batch's field writes. A stored
/// node's list items are found through the list's index. `context` names the
/// read in an error.
///
/// # Errors
///
/// A key that the read looks up names two items of its list.
pub(crate) fn field_value<'g>(
    graph: &'g Graph,
    lists: &mut Lists,
    id: &str,
    path: &[Segment],
    context: &dyn fmt::Display,
) -> Result<Option<Cow<'g, FlowValue>>> {
    let Some(node) = graph.nodes.get(id) else {
        return Ok(None);
    };
    let stored = graph.is_stored_node(id);
    let step = |value: &'g FlowValue, index: usize, in_entry: bool| {
        let parent = &path[..index];
        let segment = &path[index];
        let Segment::Item(key) = segment else {
            return Ok(field_write::child(value, parent, segment));
        };
        if !stored || in_entry || !parent.all_keys() {
            return Ok(field_write::child(value, parent, segment));
        }
        let Some(items) = value.as_array() else {
            return Ok(None);
        };
        let keyed = FLOW_MODEL.listed_at(parent);
        let item_index = lists.index(id, parent, keyed, items).find(key, context)?;
        Ok(item_index.map(|item_index| &items[item_index]))
    };
    field_write::read(node.as_value(), graph.fields.node(id), path, step)
}

/// The keyed lists indexed so far, by node and by the path of the list.
///
/// They index stored nodes only, so a batch that fails leaves them right.
#[derive(Debug, Default)]
pub(crate) struct Lists {
    pub(super) by_node: HashMap<String, Vec<IndexedList>>,
}

/// The index of one list of a node.
#[derive(Debug)]
pub(crate) struct IndexedList {
    /// The object keys that lead to the list.
    path: Vec<String>,
    index: ListIndex,
}

impl Lists {
    /// The index of the list `items` at `path` of a node, built on first use.
    /// Every part of `path` is an object key.
    pub fn index<T: AsKey>(
        &mut self,
        node_id: &str,
        path: &[T],
        keyed: &'static KeyedList,
        items: &[FlowValue],
    ) -> &mut ListIndex {
        let lists = self.by_node.entry(node_id.to_owned()).or_default();
        let position = if let Some(position) = lists.iter().position(|list| path.equals(&list.path))
        {
            position
        } else {
            let owned = path
                .iter()
                .map(|part| {
                    part.as_key()
                        .expect("a list path is object keys")
                        .to_owned()
                })
                .collect();
            lists.push(IndexedList {
                path: owned,
                index: ListIndex::build(keyed, items),
            });
            lists.len() - 1
        };
        &mut lists[position].index
    }

    /// The index of the list at `path` of a node, if one is built. A path
    /// that names a list item has none.
    pub fn built<T: AsKey>(&mut self, node_id: &str, path: &[T]) -> Option<&mut ListIndex> {
        self.by_node
            .get_mut(node_id)?
            .iter_mut()
            .find(|list| path.equals(&list.path))
            .map(|list| &mut list.index)
    }

    /// Forget the indexes of the lists at or below `parent` plus `key`.
    /// A `parent` that names a list item has none.
    pub fn forget_under<T: AsKey>(&mut self, node_id: &str, parent: &[T], key: &str) {
        if let Some(lists) = self.by_node.get_mut(node_id) {
            lists.retain(|list| {
                !(list.path.len() > parent.len()
                    && parent.shares_start(&list.path)
                    && list.path[parent.len()] == key)
            });
        }
    }

    pub(super) fn forget_node(&mut self, node_id: &str) {
        self.by_node.remove(node_id);
    }
}
