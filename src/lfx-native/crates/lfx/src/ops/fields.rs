//! [`FieldLayer`]: the field writes of a batch, kept apart from the stored nodes.
//!
//! A batch never writes into a stored node. For each node it writes, the
//! layer keeps a tree of path segments with the same shape as the node's
//! JSON ([`PathWrites`]). A tree node holds the batch's write at its path, if
//! any. A read or a write walks the tree and the node's JSON side by side,
//! one segment at a time, and looks at the tree first ([`walk`]): a write on
//! the way holds the value, and otherwise the node does. A batch that
//! succeeds makes its writes in the stored nodes ([`make_writes`]); a batch
//! that fails drops the layer.
//!
//! An ancestor path of a path starts it and is shorter: `template.x` is an
//! ancestor of `template.x.value`, which is a descendant of it. A tree node
//! that holds a write has no children:
//!
//! - a later write at a descendant path changes that write's value;
//! - a later write at an ancestor path replaces the writes below it.
//!
//! So a write copies nothing from the node: a write to one table row keeps
//! only what it wrote. A read of a value with writes below it copies the
//! value and makes those writes in the copy.
//!
//! Only a natural list (outputs, tool actions) has an order that is state.
//! A write to one of its items, or inside one, is made in a copy of the
//! whole list, which is short, so the list keeps its order. Table rows and
//! object keys have no order that is state. The tree keeps its children in
//! the order they were first written, so one batch always gives one result.

use std::borrow::Cow;
use std::collections::HashMap;

use indexmap::IndexMap;
use serde_json::Value;

use crate::ops::error::Result;
use crate::ops::keyed::{ListIndex, find_item, remove_item};
use crate::ops::ops::{Path, PathExt, Segment};
use crate::ops::schema::NODE_SCHEMA;
use crate::ops::state::Lists;

/// The batch's write at a path of a node.
#[derive(Debug, Clone)]
pub(crate) enum FieldWrite {
    /// Set the value at the path: replace the value there, or add it.
    Set(Value),
    /// Remove the value at the path.
    Remove,
}

/// The batch's writes at one path of a node and at its descendant paths: a
/// tree of path segments.
#[derive(Debug, Clone, Default)]
pub(crate) struct PathWrites {
    /// The write at this path. A tree node with a write has no children.
    write: Option<FieldWrite>,
    /// The tree nodes one segment further, in the order they were first written.
    children: IndexMap<Segment, PathWrites>,
}

impl PathWrites {
    fn is_empty(&self) -> bool {
        self.write.is_none() && self.children.is_empty()
    }

    /// The write at the path one `segment` further, if any.
    pub fn child_write(&self, segment: &Segment) -> Option<&FieldWrite> {
        self.children.get(segment)?.write.as_ref()
    }

    /// Make `write` the write at `path` under this tree node, in place of the
    /// writes at its descendant paths. No write may be at an ancestor path of
    /// `path`: a write there takes the new write into its own value.
    pub fn set(&mut self, path: &[Segment], write: FieldWrite) {
        let mut node = self;
        for segment in path {
            debug_assert!(node.write.is_none(), "no write at an ancestor path");
            if !node.children.contains_key(segment) {
                node.children.insert(segment.clone(), Self::default());
            }
            node = node
                .children
                .get_mut(segment)
                .expect("the tree node was just added");
        }
        node.write = Some(write);
        node.children.clear();
    }

    /// Drop the write at `path`: a value the batch added and now removes.
    /// Tree nodes left empty go with it.
    pub fn drop_write(&mut self, path: &[Segment]) {
        let Some((segment, rest)) = path.split_first() else {
            return;
        };
        let Some(child) = self.children.get_mut(segment) else {
            return;
        };
        if rest.is_empty() {
            child.write = None;
        } else {
            child.drop_write(rest);
        }
        if child.is_empty() {
            self.children.swap_remove(segment);
        }
    }

    /// The write on the way to `path`, at `path` or at an ancestor path of
    /// it, with the length of its path, to change its value.
    pub fn write_on_path_mut(&mut self, path: &[Segment]) -> Option<(usize, &mut FieldWrite)> {
        let mut node = self;
        for (index, segment) in path.iter().enumerate() {
            node = node.children.get_mut(segment)?;
            if node.write.is_some() {
                return node.write.as_mut().map(|write| (index + 1, write));
            }
        }
        None
    }
}

/// The field writes of a batch, by node.
#[derive(Debug, Default)]
pub(crate) struct FieldLayer {
    by_node: HashMap<String, PathWrites>,
}

impl FieldLayer {
    /// The writes to node `id`, if the batch wrote it.
    pub fn node(&self, id: &str) -> Option<&PathWrites> {
        self.by_node.get(id)
    }

    /// The writes to node `id`, to add one.
    pub fn node_mut(&mut self, id: &str) -> &mut PathWrites {
        if !self.by_node.contains_key(id) {
            self.by_node.insert(id.to_owned(), PathWrites::default());
        }
        self.by_node
            .get_mut(id)
            .expect("the writes were just added")
    }

    /// Drop the writes to a node the batch deletes.
    pub fn forget_node(&mut self, id: &str) {
        self.by_node.remove(id);
    }

    /// The writes to every node, moved out, which leaves the layer empty.
    pub fn take(&mut self) -> HashMap<String, PathWrites> {
        std::mem::take(&mut self.by_node)
    }

    /// Drop every write.
    pub fn discard(&mut self) {
        self.by_node.clear();
    }
}

/// `step` itself. It gives a closure the signature [`walk`] takes, which
/// ties the value a step returns to the value it reads, for a caller that
/// calls the step again after the walk.
pub(crate) fn step_fn<'v, F>(step: F) -> F
where
    F: FnMut(&'v Value, usize, bool) -> Result<Option<&'v Value>>,
{
    step
}

/// What [`walk`] found along a path.
#[derive(Debug)]
pub(crate) struct Walked<'v> {
    /// The length of the path of the write on the way, at the path or at an
    /// ancestor path, whose value holds what the walk found. `None` when the
    /// node itself holds it.
    pub write_len: Option<usize>,
    /// The value at the path, or the index of the first segment that does not exist.
    pub found: std::result::Result<&'v Value, usize>,
    /// The tree node at the path, when the node itself holds the value: it
    /// holds the writes at the path's descendant paths.
    pub writes: Option<&'v PathWrites>,
}

/// Follow `path` in `node` as the batch sees it, through `writes`, the
/// batch's writes to the node. Every read of a node during a batch goes
/// through here, so none reads the node without the batch's writes.
///
/// At each segment the walk looks at the tree first. A write there holds the
/// value from then on: a set's value, or nothing after a removal. Otherwise
/// `step(value, index, in_write)` reads `path[index]` under `value`, the
/// value at `path[..index]`. `in_write` says whether `value` is inside a
/// write's value, whose lists have no index.
///
/// The value found is right for every read of it, except that writes at
/// descendant paths may change what lies under it; [`read`] makes those
/// writes in a copy.
///
/// # Errors
///
/// `step` fails.
pub(crate) fn walk<'v>(
    node: &'v Value,
    writes: Option<&'v PathWrites>,
    path: &[Segment],
    mut step: impl FnMut(&'v Value, usize, bool) -> Result<Option<&'v Value>>,
) -> Result<Walked<'v>> {
    let mut value = node;
    let mut tree = writes;
    let mut write_len = None;
    for (index, segment) in path.iter().enumerate() {
        if write_len.is_none() {
            tree = tree.and_then(|tree| tree.children.get(segment));
            if let Some(write) = tree.and_then(|tree| tree.write.as_ref()) {
                write_len = Some(index + 1);
                tree = None;
                let FieldWrite::Set(set) = write else {
                    return Ok(Walked {
                        write_len,
                        found: Err(index),
                        writes: None,
                    });
                };
                value = set;
                continue;
            }
        }
        let Some(next) = step(value, index, write_len.is_some())? else {
            return Ok(Walked {
                write_len,
                found: Err(index),
                writes: None,
            });
        };
        value = next;
    }
    Ok(Walked {
        write_len,
        found: Ok(value),
        writes: tree,
    })
}

/// The value at `path` of `node` as the batch sees it, with every write
/// under it: [`walk`], and a copy with the writes made in it when writes are
/// at descendant paths of `path`.
///
/// # Errors
///
/// `step` fails.
pub(crate) fn read<'v>(
    node: &'v Value,
    writes: Option<&'v PathWrites>,
    path: &[Segment],
    step: impl FnMut(&'v Value, usize, bool) -> Result<Option<&'v Value>>,
) -> Result<Option<Cow<'v, Value>>> {
    let walked = walk(node, writes, path, step)?;
    let Ok(value) = walked.found else {
        return Ok(None);
    };
    match walked.writes {
        Some(tree) if !tree.children.is_empty() => {
            let mut copy = value.clone();
            make_writes(&mut copy, tree.clone(), &mut path.to_vec(), None);
            Ok(Some(Cow::Owned(copy)))
        }
        _ => Ok(Some(Cow::Borrowed(value))),
    }
}

/// The value one `segment` under `value`, which is at `parent_path`. An item
/// is found by reading every item of the list.
pub(crate) fn child<'v>(
    value: &'v Value,
    parent_path: &[Segment],
    segment: &Segment,
) -> Option<&'v Value> {
    match segment {
        Segment::Key(key) => value.as_object()?.get(key),
        Segment::Item(key) => {
            let items = value.as_array()?;
            find_item(NODE_SCHEMA.listed_at(parent_path), items, key).map(|slot| &items[slot])
        }
    }
}

/// The value at `path[start..]` under `value`, the value at `path[..start]`,
/// to change it. An item is found by reading every item of the list.
pub(crate) fn descend_mut<'v>(
    value: &'v mut Value,
    path: &[Segment],
    start: usize,
) -> Option<&'v mut Value> {
    (start..path.len()).try_fold(value, |value, index| {
        child_mut(value, &path[..index], &path[index], None)
    })
}

/// The value one `segment` under `value`, which is at `parent_path`, to
/// change it. An item is found through `index`, the list's index, or else by
/// reading every item.
fn child_mut<'v>(
    value: &'v mut Value,
    parent_path: &[Segment],
    segment: &Segment,
    index: Option<&mut ListIndex>,
) -> Option<&'v mut Value> {
    match segment {
        Segment::Key(key) => value.as_object_mut()?.get_mut(key),
        Segment::Item(key) => {
            let items = value.as_array_mut()?;
            let slot = match index {
                Some(index) => index.slot(key),
                None => find_item(NODE_SCHEMA.listed_at(parent_path), items, key),
            }?;
            Some(&mut items[slot])
        }
    }
}

/// The list indexes of the stored node that the fold writes.
pub(crate) struct NodeLists<'l> {
    /// The indexes of every stored node.
    pub lists: &'l mut Lists,
    /// The node the fold writes.
    pub id: &'l str,
}

impl NodeLists<'_> {
    /// The index of the list at `path`, if one is built.
    fn index(&mut self, path: &[Segment]) -> Option<&mut ListIndex> {
        let keys = path.to_list()?;
        self.lists.built(self.id, &keys)
    }
}

/// Make the writes of `tree`, the tree node at `path`, in `value`, the value
/// at `path`, as writes in place would. With `lists`, the value is a stored
/// node at the fold: its list indexes find items and follow the writes, and
/// a write forgets the indexes under its path.
pub(crate) fn make_writes(
    value: &mut Value,
    tree: PathWrites,
    path: &mut Path,
    mut lists: Option<&mut NodeLists<'_>>,
) {
    for (segment, child) in tree.children {
        if let Some(write) = child.write {
            make_write(value, &segment, path, write, lists.as_deref_mut());
            continue;
        }
        let index = lists.as_deref_mut().and_then(|lists| lists.index(path));
        let next =
            child_mut(value, path, &segment, index).expect("the value under a written path exists");
        path.push(segment);
        make_writes(next, child, path, lists.as_deref_mut());
        path.pop();
    }
}

/// Make `write` at `segment` of `parent`, the value at `parent_path`, as a
/// write in place would: a set replaces the value there or adds it last, and
/// a removal of a list item leaves the gap as the list's kind says.
pub(crate) fn make_write(
    parent: &mut Value,
    segment: &Segment,
    parent_path: &[Segment],
    write: FieldWrite,
    mut lists: Option<&mut NodeLists<'_>>,
) {
    let context = "a field write";
    match segment {
        Segment::Key(key) => {
            if let Some(lists) = lists.as_deref_mut()
                && let Some(mut keys) = parent_path.to_list()
            {
                // The write replaces or removes the lists under its path.
                keys.push(key);
                lists.lists.forget_under(lists.id, &keys);
            }
            let object = parent
                .as_object_mut()
                .expect("an object key's parent is an object");
            match write {
                FieldWrite::Set(value) => {
                    object.insert(key.clone(), value);
                }
                FieldWrite::Remove => {
                    object.shift_remove(key);
                }
            }
        }
        Segment::Item(key) => {
            let keyed = NODE_SCHEMA.listed_at(parent_path);
            let items = parent
                .as_array_mut()
                .expect("a list item's parent is a list");
            if let Some(index) = lists.and_then(|lists| lists.index(parent_path)) {
                match (write, index.slot(key)) {
                    (FieldWrite::Set(value), Some(slot)) => {
                        index
                            .replace(items, slot, value, &context)
                            .expect("the write checked the item");
                    }
                    (FieldWrite::Set(value), None) => {
                        index
                            .add(items, value, &context)
                            .expect("the write checked the item");
                    }
                    (FieldWrite::Remove, _) => {
                        index.remove(items, key);
                    }
                }
                return;
            }
            match (write, find_item(keyed, items, key)) {
                (FieldWrite::Set(value), Some(slot)) => items[slot] = value,
                (FieldWrite::Set(value), None) => items.push(value),
                (FieldWrite::Remove, Some(slot)) => {
                    remove_item(keyed, items, slot);
                }
                (FieldWrite::Remove, None) => {}
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    fn path(keys: &[&str]) -> Path {
        keys.iter()
            .map(|key| Segment::Key((*key).to_owned()))
            .collect()
    }

    fn scan<'v>(at: &[Segment]) -> impl FnMut(&'v Value, usize, bool) -> Result<Option<&'v Value>> {
        move |value, index, _| Ok(child(value, &at[..index], &at[index]))
    }

    #[test]
    fn a_write_at_an_ancestor_path_replaces_the_writes_below_it() {
        let mut writes = PathWrites::default();
        writes.set(&path(&["t", "a", "value"]), FieldWrite::Set(json!(1)));
        writes.set(&path(&["t", "b"]), FieldWrite::Set(json!({})));
        writes.set(&path(&["t", "a"]), FieldWrite::Set(json!({"value": 2})));
        let t = &writes.children[&Segment::Key("t".into())];
        assert_eq!(t.children.len(), 2);
        assert!(t.children[&Segment::Key("a".into())].children.is_empty());
        let (len, write) = writes
            .write_on_path_mut(&path(&["t", "a", "value"]))
            .unwrap();
        assert_eq!(len, 2);
        assert!(matches!(write, FieldWrite::Set(value) if *value == json!({"value": 2})));
    }

    #[test]
    fn a_dropped_write_takes_the_tree_nodes_it_leaves_empty() {
        let mut writes = PathWrites::default();
        writes.set(&path(&["t", "a", "value"]), FieldWrite::Set(json!(1)));
        writes.drop_write(&path(&["t", "a", "value"]));
        assert!(writes.is_empty());
    }

    #[test]
    fn a_read_of_a_value_with_writes_below_it_makes_them_in_a_copy() {
        let node = json!({"t": {"a": {"value": 1, "info": "x"}, "b": 2}});
        let mut writes = PathWrites::default();
        writes.set(&path(&["t", "a", "value"]), FieldWrite::Set(json!(5)));
        writes.set(&path(&["t", "c"]), FieldWrite::Set(json!(3)));
        writes.set(&path(&["t", "b"]), FieldWrite::Remove);
        let at = path(&["t"]);
        let read = read(&node, Some(&writes), &at, scan(&at)).unwrap().unwrap();
        assert!(matches!(read, Cow::Owned(_)));
        assert_eq!(*read, json!({"a": {"value": 5, "info": "x"}, "c": 3}));
        assert_eq!(node["t"]["a"]["value"], json!(1));
        let removed = path(&["t", "b", "x"]);
        let walked = walk(&node, Some(&writes), &removed, scan(&removed)).unwrap();
        assert_eq!(walked.found.err(), Some(1));
    }
}
