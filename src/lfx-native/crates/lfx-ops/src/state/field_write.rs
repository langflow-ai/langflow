//! Read and apply the pending field changes of a node.

use std::borrow::Cow;
use std::sync::OnceLock;

use crate::json::FlowValue;
use crate::map::hash::HashMap;
use crate::map::path_tree::{InvalidPath, Node, NodeValue, drop_path};

use crate::flow::list::{ListIndex, find_item, remove_item};
use crate::flow::model::FLOW_MODEL;
use crate::flow::path::{Path, Segment};
use crate::state::Lists;
use crate::violation::error::Result;

/// The batch's write at a path of a node.
#[derive(Debug, Clone)]
pub(crate) enum FieldWrite {
    /// Set the value at the path: replace the value there, or
    /// add it.
    Set(FlowValue),
    /// Remove the value at the path.
    Remove,
}

impl From<FlowValue> for FieldWrite {
    fn from(value: FlowValue) -> Self {
        Self::Set(value)
    }
}

type FieldTree = Node<Segment, FieldWrite>;
type ObjectWrites = HashMap<Path, OnceLock<FieldWrite>>;

#[derive(Debug, Clone, Default)]
pub(crate) struct PathWrites {
    tree: FieldTree,
    // Object assignment paths and their cached values for
    // staged reads.
    object_writes: ObjectWrites,
}

impl PathWrites {
    pub(crate) fn is_empty(&self) -> bool {
        self.tree.is_empty()
    }

    pub(crate) fn set(&mut self, path: &[Segment], write: FieldWrite) -> Result<(), InvalidPath> {
        let replaces_object = !self.object_writes.is_empty()
            && self
                .node_at(path)
                .is_some_and(|node| matches!(node.value, NodeValue::Children(_)));
        let writes_object = matches!(&write, FieldWrite::Set(FlowValue::Object(_)));
        set_value(&mut self.tree, path, write)?;
        if self.object_writes.remove(path).is_none() && replaces_object {
            self.object_writes
                .retain(|endpoint, _| !endpoint.starts_with(path));
        }
        if writes_object {
            self.object_writes.insert(path.to_vec(), OnceLock::new());
        }
        Ok(())
    }

    pub(crate) fn drop_write(&mut self, path: &[Segment]) {
        self.object_writes.remove(path);
        drop_path(&mut self.tree, path);
    }

    fn node_at(&self, path: &[Segment]) -> Option<&FieldTree> {
        path.iter().try_fold(&self.tree, FieldTree::child)
    }

    /// Find the write at `path` after following its parent in
    /// the patch.
    pub(crate) fn write_at(&self, path: &[Segment]) -> Option<&FieldWrite> {
        self.write_at_node(path, self.node_at(path)?)
    }

    fn write_at_node<'v>(
        &'v self,
        path: &[Segment],
        node: &'v FieldTree,
    ) -> Option<&'v FieldWrite> {
        if let NodeValue::Scalar(write) = &node.value {
            return Some(write);
        }
        Some(object_write(self.object_writes.get(path)?, node))
    }

    /// Change the value inside an earlier assignment at
    /// `path[..path_len]`.
    pub(crate) fn edit(
        &mut self,
        path: &[Segment],
        path_len: usize,
        write: FieldWrite,
    ) -> Result<(), InvalidPath> {
        let endpoint = path.get(..path_len).ok_or(InvalidPath)?;
        let (key, parent_path) = path.split_last().ok_or(InvalidPath)?;
        if let Some((length, leaf)) = self.tree.data_on_path_mut(parent_path) {
            let FieldWrite::Set(value) = leaf else {
                return Err(InvalidPath);
            };
            let parent = descend_mut(value, parent_path, length).ok_or(InvalidPath)?;
            FieldWriter {
                lists: None,
                object_writes: &self.object_writes,
            }
            .make_write(parent, key, parent_path, write);
        } else if matches!(write, FieldWrite::Remove) {
            let parent = self.tree.at_mut(parent_path).ok_or(InvalidPath)?;
            drop_path(parent, std::slice::from_ref(key));
        } else {
            set_at(&mut self.tree, path, write)?;
        }
        if let Some(cached) = self.object_writes.get_mut(endpoint) {
            cached.take();
        }
        Ok(())
    }
}

fn set_value(tree: &mut FieldTree, path: &[Segment], write: FieldWrite) -> Result<(), InvalidPath> {
    let (key, parent_path) = path.split_last().ok_or(InvalidPath)?;
    let mut node = &*tree;
    for (index, segment) in parent_path.iter().enumerate() {
        let Some(child) = node.child(segment) else {
            // Build the rest of the pending path before
            // attaching it.
            let mut subtree = FieldTree::default();
            set_at(&mut subtree, std::slice::from_ref(key), write)?;
            for segment in parent_path[index + 1..].iter().rev() {
                let mut parent = FieldTree::default();
                parent.attach(std::slice::from_ref(segment), subtree)?;
                subtree = parent;
            }
            return tree.attach(&path[..=index], subtree);
        };
        node = child;
    }
    set_at(tree, path, write)
}

fn set_at(tree: &mut FieldTree, path: &[Segment], write: FieldWrite) -> Result<(), InvalidPath> {
    match write {
        FieldWrite::Set(value @ FlowValue::Object(_)) => tree.attach(path, FieldTree::from(value)),
        _ => tree.set(path, write),
    }
}

fn object_write<'v>(cached: &'v OnceLock<FieldWrite>, node: &FieldTree) -> &'v FieldWrite {
    cached.get_or_init(|| FieldWrite::Set(object_value(node)))
}

fn object_value(node: &FieldTree) -> FlowValue {
    let NodeValue::Children(children) = &node.value else {
        unreachable!("an object holds child nodes");
    };
    let entries = children.iter().map(|(segment, child)| {
        let Segment::Key(key) = segment else {
            unreachable!("an object holds string keys");
        };
        let value = match &child.value {
            NodeValue::Scalar(FieldWrite::Set(value)) => value.clone(),
            NodeValue::Scalar(FieldWrite::Remove) => unreachable!("an object holds values"),
            NodeValue::Children(_) => object_value(child),
        };
        (key.clone(), value)
    });
    FlowValue::Object(entries.collect())
}

/// What [`read_through`] found along a path.
#[derive(Debug)]
pub(crate) struct ReadThrough<'v> {
    /// The value at the path, or where and why the path ends
    /// early.
    pub found: std::result::Result<&'v FlowValue, Missing>,
    /// What holds the value read last.
    pub holder: Holder<'v>,
}

/// The first segment of a path that has no value.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct Missing {
    /// The index of the segment.
    pub at: usize,
    pub kind: MissingKind,
}

/// Why a segment has no value.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum MissingKind {
    /// The value never had it. Example: key `b` of `{"a": 1}`.
    Absent,
    /// The batch removed it with a [`FieldWrite::Remove`].
    Removed,
}

/// What holds the value that [`read_through`] read last.
#[derive(Debug, Clone, Copy)]
pub(crate) enum Holder<'v> {
    /// The node. `writes` is its pending patch when the patch
    /// reaches this path.
    Node { writes: Option<&'v PathWrites> },
    /// The batch's write at the first `path_len` segments of
    /// the path. Example: a write at `["t", "a"]` holds
    /// `["t", "a", "value"]` with `path_len` 2.
    Write { path_len: usize },
}

/// Follow `path` in `node` through `writes`, the batch's writes
/// to the node. Every read of a node during a batch goes
/// through here.
///
/// At each segment, a write in the tree holds the value from
/// then on. Otherwise `step(value, index, in_write)` reads
/// `path[index]` under `value`. `in_write` is true inside a
/// write's value, whose lists have no index. Writes below the
/// path are not made. [`read`] makes them in a copy.
///
/// # Errors
///
/// `step` fails.
pub(crate) fn read_through<'v>(
    node: &'v FlowValue,
    writes: Option<&'v PathWrites>,
    path: &[Segment],
    mut step: impl FnMut(&'v FlowValue, usize, bool) -> Result<Option<&'v FlowValue>>,
) -> Result<ReadThrough<'v>> {
    let mut value = node;
    let mut holder = Holder::Node { writes };
    let mut branch = writes.map(|writes| &writes.tree);
    for (index, segment) in path.iter().enumerate() {
        if let Holder::Node {
            writes: Some(writes),
        } = holder
        {
            branch = branch.and_then(|node| node.child(segment));
            holder = Holder::Node {
                writes: branch.map(|_| writes),
            };
            if let Some(write) = branch.and_then(|node| writes.write_at_node(&path[..=index], node))
            {
                holder = Holder::Write {
                    path_len: index + 1,
                };
                let FieldWrite::Set(set) = write else {
                    return Ok(ReadThrough {
                        found: Err(Missing {
                            at: index,
                            kind: MissingKind::Removed,
                        }),
                        holder,
                    });
                };
                value = set;
                continue;
            }
        }
        let in_write = matches!(holder, Holder::Write { .. });
        let Some(next) = step(value, index, in_write)? else {
            return Ok(ReadThrough {
                found: Err(Missing {
                    at: index,
                    kind: MissingKind::Absent,
                }),
                holder,
            });
        };
        value = next;
    }
    Ok(ReadThrough {
        found: Ok(value),
        holder,
    })
}

/// The value at `path` of `node`, with every write under it.
/// When writes are below `path`, it is a copy with those writes
/// made.
///
/// # Errors
///
/// `step` fails.
pub(crate) fn read<'v>(
    node: &'v FlowValue,
    writes: Option<&'v PathWrites>,
    path: &[Segment],
    step: impl FnMut(&'v FlowValue, usize, bool) -> Result<Option<&'v FlowValue>>,
) -> Result<Option<Cow<'v, FlowValue>>> {
    let reached = read_through(node, writes, path, step)?;
    let Ok(value) = reached.found else {
        return Ok(None);
    };
    let Holder::Node {
        writes: Some(writes),
    } = reached.holder
    else {
        return Ok(Some(Cow::Borrowed(value)));
    };
    let Some(branch) = writes.node_at(path).filter(|node| !node.is_empty()) else {
        return Ok(Some(Cow::Borrowed(value)));
    };

    let mut copy = value.clone();
    let mut path = path.to_vec();
    FieldWriter {
        lists: None,
        object_writes: &writes.object_writes,
    }
    .make_writes(&mut copy, branch.clone(), &mut path);
    Ok(Some(Cow::Owned(copy)))
}

/// The value one `segment` under `value`, which is at
/// `parent_path`. An item is found by reading every item of the
/// list.
pub(crate) fn child<'v>(
    value: &'v FlowValue,
    parent_path: &[Segment],
    segment: &Segment,
) -> Option<&'v FlowValue> {
    match segment {
        Segment::Key(key) => value.as_object()?.get(key),
        Segment::Item(key) => {
            let items = value.as_array()?;
            find_item(FLOW_MODEL.listed_at(parent_path), items, key)
                .map(|item_index| &items[item_index])
        }
    }
}

/// The value at `path[start..]` under `value`, the value at
/// `path[..start]`, to change it. An item is found by reading
/// every item of the list.
fn descend_mut<'v>(
    mut value: &'v mut FlowValue,
    path: &[Segment],
    start: usize,
) -> Option<&'v mut FlowValue> {
    for (index, segment) in path.iter().enumerate().skip(start) {
        value = child_mut(value, &path[..index], segment, None)?;
    }
    Some(value)
}

/// The value one `segment` under `value`, which is at
/// `parent_path`, to change it. An item is found through
/// `index`, the list's index, or else by reading every item.
fn child_mut<'v>(
    value: &'v mut FlowValue,
    parent_path: &[Segment],
    segment: &Segment,
    index: Option<&mut ListIndex>,
) -> Option<&'v mut FlowValue> {
    match segment {
        Segment::Key(key) => value.as_object_mut()?.get_mut(key),
        Segment::Item(key) => {
            let items = value.as_array_mut()?;
            let item_index = match index {
                Some(index) => index.item_index(key),
                None => find_item(FLOW_MODEL.listed_at(parent_path), items, key),
            }?;
            Some(&mut items[item_index])
        }
    }
}

/// Apply a subtree at `path`, updating any stored list indexes.
pub(crate) fn make_writes(
    value: &mut FlowValue,
    writes: PathWrites,
    path: &mut Path,
    lists: Option<(&mut Lists, &str)>,
) {
    FieldWriter {
        lists,
        object_writes: &writes.object_writes,
    }
    .make_writes(value, writes.tree, path);
}

struct FieldWriter<'a> {
    lists: Option<(&'a mut Lists, &'a str)>,
    object_writes: &'a ObjectWrites,
}

impl FieldWriter<'_> {
    fn index(&mut self, path: &[Segment]) -> Option<&mut ListIndex> {
        let (lists, id) = self.lists.as_mut()?;
        lists.built(id, path)
    }

    /// [`make_writes`] in the node. A list with a built index
    /// finds its items through the index, and the index follows
    /// the writes.
    fn make_writes(&mut self, value: &mut FlowValue, writes: FieldTree, path: &mut Path) {
        for (segment, child) in writes.into_children() {
            if let NodeValue::Scalar(write) = child.value {
                self.make_write(value, &segment, path, write);
                continue;
            }
            if !self.object_writes.is_empty() {
                path.push(segment.clone());
                let object = self.object_writes.get(path.as_slice());
                path.pop();
                if let Some(cached) = object {
                    let write = object_write(cached, &child).clone();
                    self.make_write(value, &segment, path, write);
                    continue;
                }
            }
            let index = if matches!(segment, Segment::Item(_)) {
                self.index(path)
            } else {
                None
            };
            let indexed = index.is_some();
            let next = child_mut(value, path, &segment, index)
                .expect("the value under a written path exists");
            let keyed = FLOW_MODEL.listed_at(path);
            let had_position = indexed && keyed.has_position(next);
            path.push(segment);
            self.make_writes(next, child, path);
            let segment = path.pop().expect("the segment was pushed above");

            // The parser refuses a write that changes an item's
            // key. A write can change a row's position.
            let Segment::Item(key) = segment else {
                continue;
            };
            let Some(index) = self.index(path) else {
                continue;
            };
            debug_assert_eq!(
                keyed.key_of(next),
                Some(key.as_str()),
                "the item keeps its key"
            );
            index.position_changed(had_position, keyed.has_position(next));
        }
    }

    /// [`make_write`] in the node. The indexes follow the
    /// write.
    fn make_write(
        &mut self,
        parent: &mut FlowValue,
        segment: &Segment,
        parent_path: &[Segment],
        write: FieldWrite,
    ) {
        match segment {
            Segment::Key(key) => {
                // The write replaces or removes the lists under
                // its path.
                if let Some((lists, id)) = &mut self.lists {
                    lists.forget_under(id, parent_path, key);
                }
                let object = parent
                    .as_object_mut()
                    .expect("an object key's parent is an object");
                match write {
                    FieldWrite::Set(value) => {
                        object.insert_shared(key.clone(), value);
                    }
                    FieldWrite::Remove => {
                        object.shift_remove(key);
                    }
                }
            }
            Segment::Item(key) => {
                let keyed = FLOW_MODEL.listed_at(parent_path);
                let items = parent.as_vec_mut().expect("a list item's parent is a list");
                let Some(index) = self.index(parent_path) else {
                    match (write, find_item(keyed, items, key)) {
                        (FieldWrite::Set(value), Some(item_index)) => items[item_index] = value,
                        (FieldWrite::Set(value), None) => items.push(value),
                        (FieldWrite::Remove, Some(item_index)) => {
                            remove_item(keyed, items, item_index);
                        }
                        (FieldWrite::Remove, None) => {}
                    }
                    return;
                };
                match write {
                    FieldWrite::Set(value) => {
                        // The parser refuses an item with
                        // another key.
                        debug_assert_eq!(keyed.key_of(&value), Some(key.as_str()));
                        match index.item_index(key) {
                            Some(item_index) => index.replace(items, item_index, value),
                            None => index.add(items, key, value),
                        }
                    }
                    FieldWrite::Remove => {
                        index.remove(items, key);
                    }
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::flow_value;

    use super::*;

    fn path(keys: &[&str]) -> Path {
        keys.iter().map(|key| Segment::Key((*key).into())).collect()
    }

    fn scan<'v>(
        at: &[Segment],
    ) -> impl FnMut(&'v FlowValue, usize, bool) -> Result<Option<&'v FlowValue>> {
        move |value, index, _| Ok(child(value, &at[..index], &at[index]))
    }

    #[test]
    fn dropping_a_branched_write_keeps_other_writes_and_original_values() {
        let mut writes = PathWrites::default();
        let a = vec![Segment::Key("t".into()), Segment::Key("a".into())];
        let b = vec![Segment::Key("t".into()), Segment::Key("b".into())];
        writes
            .set(&a, FieldWrite::Set(crate::flow_value!(1)))
            .unwrap();
        writes
            .set(&b, FieldWrite::Set(crate::flow_value!(2)))
            .unwrap();
        writes.drop_write(&a);
        let mut value = crate::flow_value!({"t":{"a":0}});
        make_writes(&mut value, writes, &mut Vec::new(), None);
        assert_eq!(value, crate::flow_value!({"t":{"a":0,"b":2}}));
    }

    #[test]
    fn a_write_at_an_ancestor_path_replaces_the_writes_below_it() {
        let mut writes = PathWrites::default();
        writes
            .set(&path(&["t", "a", "value"]), FieldWrite::Set(flow_value!(1)))
            .unwrap();
        writes
            .set(&path(&["t", "b"]), FieldWrite::Set(flow_value!({})))
            .unwrap();
        writes
            .set(
                &path(&["t", "a"]),
                FieldWrite::Set(flow_value!({"value": 2})),
            )
            .unwrap();
        let t = writes.tree.child(&Segment::Key("t".into())).unwrap();
        let a = t.child(&Segment::Key("a".into())).unwrap();
        assert!(a.child(&Segment::Key("value".into())).is_some());
        let write = writes.write_at(&path(&["t", "a"])).unwrap();
        assert!(matches!(write, FieldWrite::Set(value) if *value == flow_value!({"value": 2})));

        writes
            .edit(&path(&["t", "a", "value"]), 2, FieldWrite::Remove)
            .unwrap();
        let mut node = flow_value!({"t": {"a": {"old": 0}}});
        make_writes(&mut node, writes, &mut Vec::new(), None);
        assert_eq!(node, flow_value!({"t": {"a": {}, "b": {}}}));
    }

    #[test]
    fn a_dropped_write_takes_the_tree_nodes_it_leaves_empty() {
        let mut writes = PathWrites::default();
        writes
            .set(&path(&["t", "a", "value"]), FieldWrite::Set(flow_value!(1)))
            .unwrap();
        writes.drop_write(&path(&["t", "a", "value"]));
        assert!(writes.is_empty());
    }

    #[test]
    fn path_siblings_keep_order_and_distinguish_segment_kinds() {
        use std::slice::from_ref;

        let key = Segment::Key("row".into());
        let item = Segment::Item("row".into());
        let mut writes = PathWrites::default();
        writes
            .set(from_ref(&key), FieldWrite::Set(flow_value!(1)))
            .unwrap();
        writes
            .set(from_ref(&item), FieldWrite::Set(flow_value!(2)))
            .unwrap();
        writes.drop_write(from_ref(&key));
        assert!(writes.write_at(from_ref(&key)).is_none());
        assert!(
            matches!(writes.write_at(from_ref(&item)), Some(FieldWrite::Set(value)) if *value == flow_value!(2))
        );
        writes
            .set(from_ref(&key), FieldWrite::Set(flow_value!(3)))
            .unwrap();
        assert_eq!(
            writes
                .tree
                .into_children()
                .map(|(segment, _)| segment)
                .collect::<Vec<_>>(),
            [item, key],
        );
    }

    #[test]
    fn a_read_of_a_value_with_writes_below_it_makes_them_in_a_copy() {
        let node = flow_value!({"t": {"a": {"value": 1, "info": "x"}, "b": 2}});
        let mut writes = PathWrites::default();
        writes
            .set(&path(&["t", "a", "value"]), FieldWrite::Set(flow_value!(5)))
            .unwrap();
        writes
            .set(&path(&["t", "c"]), FieldWrite::Set(flow_value!(3)))
            .unwrap();
        writes.set(&path(&["t", "b"]), FieldWrite::Remove).unwrap();
        let at = path(&["t"]);
        let read = read(&node, Some(&writes), &at, scan(&at)).unwrap().unwrap();
        assert!(matches!(read, Cow::Owned(_)));
        assert_eq!(*read, flow_value!({"a": {"value": 5, "info": "x"}, "c": 3}));
        assert_eq!(node["t"]["a"]["value"], flow_value!(1));
        let removed = path(&["t", "b", "x"]);
        let reached = read_through(&node, Some(&writes), &removed, scan(&removed)).unwrap();
        assert_eq!(
            reached.found.err(),
            Some(Missing {
                at: 1,
                kind: MissingKind::Removed
            })
        );
    }
}
