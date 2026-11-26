//! A tree with siblings
//! sorted in insertion order.
//!
//! Paths are relative to
//! the starting node.
//! An empty path refers to that node.

use std::hash::Hash;

use super::ordered::OrderedMap;
use crate::types::{FlowStr, FlowValue};

/// A tree node. It's `value` is
/// either a scalar or a collection
/// of descendants. The parameter
/// `K` describes the unique key
/// (string-like), that identifies
/// its children. `D` represents
/// the scalar value that nodes can have.
#[derive(Debug, Clone)]
pub(crate) struct Node<K, D> {
    pub(crate) value: NodeValue<K, D>,
}
/// The possible types
/// inside [`Node::value`].
/// `Scalar(D)` describes
/// a flat value of type `D`,
/// typically a string, boolean, or integer.
/// `Children(OrderedMap<Node<K, D>, K>)`
/// describes a nested value, i.e., an object
/// where each key of type `K`
/// identifies a child node.
///
/// The value of a JSON key
/// can be flat scalar type
/// or a nested object,
/// This enum enforces the xor aspect.
#[derive(Debug, Clone)]
pub(crate) enum NodeValue<K, D> {
    Scalar(D),
    Children(OrderedMap<Node<K, D>, K>),
}

/// The requested write cannot be made at this path.
#[derive(Debug)]
pub(crate) struct InvalidPath;

impl<K, D> Default for Node<K, D> {
    fn default() -> Self {
        Self {
            value: NodeValue::Children(OrderedMap::new()),
        }
    }
}

impl<K: Eq + Hash + From<FlowStr>, D: From<FlowValue>> From<FlowValue> for Node<K, D> {
    /// Build a subtree, preserving object key order.
    fn from(value: FlowValue) -> Self {
        let FlowValue::Object(object) = value else {
            return Self {
                value: NodeValue::Scalar(D::from(value)),
            };
        };
        let mut children = OrderedMap::new();
        for (key, value) in object {
            children.insert(K::from(key), Self::from(value));
        }
        Self {
            value: NodeValue::Children(children),
        }
    }
}

impl<K, D> Node<K, D> {
    /// false if the node has >=1
    /// child or a scalar value
    pub(crate) fn is_empty(&self) -> bool {
        matches!(&self.value, NodeValue::Children(children) if children.is_empty())
    }

    pub(crate) fn into_children(self) -> impl Iterator<Item = (K, Self)> {
        let children = match self.value {
            NodeValue::Children(children) => Some(children),
            NodeValue::Scalar(_) => None,
        };
        children.into_iter().flat_map(OrderedMap::into_entries)
    }
}

impl<K: Clone + Eq + Hash, D> Node<K, D> {
    pub(crate) fn child(&self, key: &K) -> Option<&Self> {
        let NodeValue::Children(children) = &self.value else {
            return None;
        };
        children.get(key)
    }

    /// Get the node at `path` by mutable reference.
    pub(crate) fn at_mut(&mut self, path: &[K]) -> Option<&mut Self> {
        let mut node = self;
        for key in path {
            let NodeValue::Children(children) = &mut node.value else {
                return None;
            };
            node = children.get_mut(key)?;
        }
        Some(node)
    }

    /// Set the scalar at `path`.
    ///
    /// # Errors
    ///
    /// An ancestor is missing or holds a scalar.
    pub(crate) fn set(&mut self, path: &[K], data: D) -> Result<(), InvalidPath> {
        self.attach(
            path,
            Self {
                value: NodeValue::Scalar(data),
            },
        )
    }

    /// Put the subtree at `path`, or replace `self` when `path`
    /// is empty.
    ///
    /// # Errors
    ///
    /// An ancestor is missing or holds a scalar.
    pub(crate) fn attach(&mut self, path: &[K], subtree: Self) -> Result<(), InvalidPath> {
        let Some((key, parent_path)) = path.split_last() else {
            *self = subtree;
            return Ok(());
        };
        let parent = self.at_mut(parent_path).ok_or(InvalidPath)?;
        let NodeValue::Children(children) = &mut parent.value else {
            return Err(InvalidPath);
        };
        children.insert(key.clone(), subtree);
        Ok(())
    }

    /// Find the first scalar along `path`, with the length of
    /// its path.
    pub(crate) fn data_on_path_mut(&mut self, path: &[K]) -> Option<(usize, &mut D)> {
        let mut node = self;
        let mut keys = path.iter();
        loop {
            match &mut node.value {
                NodeValue::Scalar(data) => return Some((path.len() - keys.len(), data)),
                NodeValue::Children(children) => node = children.get_mut(keys.next()?)?,
            }
        }
    }
}

/// Remove the node obtained
/// by traversing `path`
/// and prune the stale
/// trailing segment
/// of nodes that no longer
/// have descendants nor data.
/// An empty `path` does not
/// drop any node.
pub(crate) fn drop_path<K: Hash + Eq, D>(node: &mut Node<K, D>, path: &[K]) {
    // node has no data nor descendants
    if node.is_empty() {
        return;
    }
    // path is empty
    let Some((next_key, rest)) = path.split_first() else {
        return;
    };
    // we have not walked
    // the whole path
    // but there is no subtree
    // left to traverse any further
    // thus: path is not in the tree
    let NodeValue::Children(children) = &mut node.value else {
        return;
    };

    // reached the node to delete
    if rest.is_empty() {
        children.remove(next_key);
        return;
    }

    let Some(next) = children.get_mut(next_key) else {
        return;
    };
    // continue search
    drop_path(next, rest);

    // prune child if no longer holds data
    if next.is_empty() {
        children.remove(next_key);
    }
}

#[cfg(test)]
mod tests {
    use super::{InvalidPath, Node, NodeValue};

    #[test]
    fn attach_leaves_the_tree_unchanged_when_the_parent_cannot_hold_children() {
        let mut tree = Node::<&str, i32>::default();
        assert!(matches!(
            tree.attach(&["missing", "leaf"], Node::default()),
            Err(InvalidPath)
        ));
        assert!(tree.is_empty());

        tree.set(&["scalar"], 1).unwrap();
        assert!(matches!(
            tree.attach(&["scalar", "leaf"], Node::default()),
            Err(InvalidPath)
        ));
        assert!(matches!(
            tree.child(&"scalar").unwrap().value,
            NodeValue::Scalar(1)
        ));
    }
}
