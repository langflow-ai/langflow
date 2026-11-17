//! [`PendingFieldWrites`]: the field writes of a batch, kept apart from the stored nodes.
//!
//! For each node, the pending writes are a tree of path segments ([`PathWrites`])
//! with the shape of the node's JSON. A read follows the tree and the node
//! together, and a write in the tree wins ([`read_through`]). A batch that succeeds
//! makes its writes in the stored nodes ([`make_writes`], or
//! [`IndexedNode::make_writes`] for a node with list indexes). A batch that fails
//! drops the pending writes.
//!
//! A tree node that holds a write has no children. A later write below it
//! changes its value. A later write above it replaces the writes below.
//! The tree keeps children in first-write order, so a batch gives one result.

use std::borrow::Cow;

use crate::collection::hash_map::{HashMap, IndexMap, State};
use crate::collection::pending_map::MAX_RETAINED_BATCH_ENTRIES;
use crate::json::FlowValue;

use crate::flow::list::{ListIndex, find_item, remove_item};
use crate::flow::model::FLOW_MODEL;
use crate::flow::path::{Path, Segment};
use crate::state::Lists;
use crate::violation::error::Result;

/// The batch's write at a path of a node.
#[derive(Debug, Clone)]
pub(crate) enum FieldWrite {
    /// Set the value at the path: replace the value there, or add it.
    Set(FlowValue),
    /// Remove the value at the path.
    Remove,
}

/// The children of a tree node. Most have one child, which needs no hash table.
#[derive(Debug, Clone, Default)]
enum Children {
    #[default]
    Empty,
    One(Box<Child>),
    Many(Box<IndexMap<Segment, PathWrites>>),
}

/// The one child of a tree node.
#[derive(Debug, Clone)]
struct Child {
    segment: Segment,
    writes: PathWrites,
}

impl Children {
    fn is_empty(&self) -> bool {
        matches!(self, Self::Empty)
    }
    fn get(&self, key: &Segment) -> Option<&PathWrites> {
        match self {
            Self::Empty => None,
            Self::One(child) => (child.segment == *key).then_some(&child.writes),
            Self::Many(map) => map.get(key),
        }
    }
    fn get_mut(&mut self, key: &Segment) -> Option<&mut PathWrites> {
        match self {
            Self::Empty => None,
            Self::One(child) => (child.segment == *key).then_some(&mut child.writes),
            Self::Many(map) => map.get_mut(key),
        }
    }
    fn get_or_insert(&mut self, key: &Segment) -> &mut PathWrites {
        if matches!(self, Self::Empty) {
            *self = Self::One(Box::new(Child {
                segment: key.clone(),
                writes: PathWrites::default(),
            }));
        } else if matches!(self, Self::One(child) if child.segment != *key) {
            let Self::One(first) = std::mem::take(self) else {
                unreachable!("one child");
            };
            let mut map = IndexMap::with_capacity_and_hasher(2, State::default());
            map.insert(first.segment, first.writes);
            map.insert(key.clone(), PathWrites::default());
            *self = Self::Many(Box::new(map));
        }
        match self {
            Self::One(child) => &mut child.writes,
            Self::Many(map) => {
                let item_index = match map.get_index_of(key) {
                    Some(item_index) => item_index,
                    None => map.insert_full(key.clone(), PathWrites::default()).0,
                };
                map.get_index_mut(item_index).expect("the child exists").1
            }
            Self::Empty => unreachable!("the child was inserted"),
        }
    }
    fn shift_remove(&mut self, key: &Segment) {
        match self {
            Self::One(child) if child.segment == *key => *self = Self::Empty,
            Self::Many(map) => {
                map.shift_remove(key);
                if map.len() <= 1 {
                    *self = map.pop().map_or(Self::Empty, |(segment, writes)| {
                        Self::One(Box::new(Child { segment, writes }))
                    });
                }
            }
            _ => {}
        }
    }
    fn clear(&mut self) {
        *self = Self::Empty;
    }
    fn into_entries(self) -> impl Iterator<Item = (Segment, PathWrites)> {
        let (one, many) = match self {
            Self::Empty => (None, None),
            Self::One(child) => (Some((child.segment, child.writes)), None),
            Self::Many(map) => (None, Some(*map)),
        };
        one.into_iter().chain(many.into_iter().flatten())
    }
}

/// The batch's writes at one path of a node and at its descendant paths: a
/// tree of path segments.
#[derive(Debug, Clone, Default)]
pub(crate) struct PathWrites {
    /// The write at this path. A tree node with a write has no children.
    write: Option<FieldWrite>,
    /// The tree nodes one segment further, in the order they were first written.
    children: Children,
}

impl PathWrites {
    fn is_empty(&self) -> bool {
        self.write.is_none() && self.children.is_empty()
    }

    /// The write at the path one `segment` further, if any.
    pub fn child_write(&self, segment: &Segment) -> Option<&FieldWrite> {
        self.children.get(segment)?.write.as_ref()
    }

    /// Set `write` at `path`, in place of the writes below it. No write may be
    /// at an ancestor path. The caller changes that write's value instead.
    pub fn set(&mut self, path: &[Segment], write: FieldWrite) {
        let mut node = self;
        for segment in path {
            debug_assert!(node.write.is_none(), "no write at an ancestor path");
            node = node.children.get_or_insert(segment);
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
            self.children.shift_remove(segment);
        }
    }

    /// The write at `path` or at an ancestor path, and the length of its path.
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
pub(crate) struct PendingFieldWrites {
    by_node: HashMap<String, PathWrites>,
}

impl PendingFieldWrites {
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

    /// Move out the writes while retaining the map's allocation for the next batch.
    pub fn drain(&mut self) -> impl Iterator<Item = (String, PathWrites)> + '_ {
        self.by_node.drain()
    }

    /// Do not retain a large allocation after an unusually wide batch.
    pub fn finish(&mut self) {
        if self.by_node.capacity() > MAX_RETAINED_BATCH_ENTRIES {
            self.by_node.shrink_to_fit();
        }
    }

    /// Drop every write.
    pub fn drop_pending(&mut self) {
        self.by_node.clear();
        self.finish();
    }
}

/// What [`read_through`] found along a path.
#[derive(Debug)]
pub(crate) struct ReadThrough<'v> {
    /// The value at the path, or where and why the path ends early.
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
    /// The node. `writes` holds the batch's writes below the path, if any.
    Node { writes: Option<&'v PathWrites> },
    /// The batch's write at the first `path_len` segments of the path.
    /// Example: a write at `["t", "a"]` holds `["t", "a", "value"]` with `path_len` 2.
    Write { path_len: usize },
}

/// Follow `path` in `node` through `writes`, the batch's writes to the node.
/// Every read of a node during a batch goes through here.
///
/// At each segment, a write in the tree holds the value from then on.
/// Otherwise `step(value, index, in_write)` reads `path[index]` under `value`.
/// `in_write` is true inside a write's value, whose lists have no index.
/// Writes below the path are not made. [`read`] makes them in a copy.
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
    for (index, segment) in path.iter().enumerate() {
        if let Holder::Node { writes } = holder {
            let tree = writes.and_then(|tree| tree.children.get(segment));
            holder = Holder::Node { writes: tree };
            if let Some(write) = tree.and_then(|tree| tree.write.as_ref()) {
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

/// The value at `path` of `node`, with every write under it. When writes are
/// below `path`, it is a copy with those writes made.
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
    match reached.holder {
        Holder::Node { writes: Some(tree) } if !tree.children.is_empty() => {
            let mut copy = value.clone();
            make_writes(&mut copy, tree.clone(), &mut path.to_vec());
            Ok(Some(Cow::Owned(copy)))
        }
        _ => Ok(Some(Cow::Borrowed(value))),
    }
}

/// The value one `segment` under `value`, which is at `parent_path`. An item
/// is found by reading every item of the list.
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

/// The value at `path[start..]` under `value`, the value at `path[..start]`,
/// to change it. An item is found by reading every item of the list.
pub(crate) fn descend_mut<'v>(
    value: &'v mut FlowValue,
    path: &[Segment],
    start: usize,
) -> Option<&'v mut FlowValue> {
    (start..path.len()).try_fold(value, |value, index| {
        child_mut(value, &path[..index], &path[index], None)
    })
}

/// The value one `segment` under `value`, which is at `parent_path`, to
/// change it. An item is found through `index`, the list's index, or else by
/// reading every item.
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

/// Make the writes of `tree` in `value`, both at `path`. `value` is a copy
/// or a node with no list index, so an item is found by reading every item.
pub(crate) fn make_writes(value: &mut FlowValue, tree: PathWrites, path: &mut Path) {
    for (segment, child) in tree.children.into_entries() {
        if let Some(write) = child.write {
            make_write(value, &segment, path, write);
            continue;
        }
        let next =
            child_mut(value, path, &segment, None).expect("the value under a written path exists");
        path.push(segment);
        make_writes(next, child, path);
        path.pop();
    }
}

/// Make `write` at `segment` of `parent`, the value at `parent_path`. A set
/// replaces the value or adds it last. A removal leaves the gap as the list's
/// kind says.
pub(crate) fn make_write(
    parent: &mut FlowValue,
    segment: &Segment,
    parent_path: &[Segment],
    write: FieldWrite,
) {
    match segment {
        Segment::Key(key) => {
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
            let keyed = FLOW_MODEL.listed_at(parent_path);
            let items = parent.as_vec_mut().expect("a list item's parent is a list");
            match (write, find_item(keyed, items, key)) {
                (FieldWrite::Set(value), Some(item_index)) => items[item_index] = value,
                (FieldWrite::Set(value), None) => items.push(value),
                (FieldWrite::Remove, Some(item_index)) => {
                    remove_item(keyed, items, item_index);
                }
                (FieldWrite::Remove, None) => {}
            }
        }
    }
}

/// A stored node that the commit writes, with its list indexes. The indexes
/// follow the writes.
pub(crate) struct IndexedNode<'l> {
    /// The indexes of every stored node.
    pub lists: &'l mut Lists,
    /// The node the commit writes.
    pub id: &'l str,
}

impl IndexedNode<'_> {
    /// The index of the list at `path`, if one is built.
    fn index(&mut self, path: &[Segment]) -> Option<&mut ListIndex> {
        self.lists.built(self.id, path)
    }

    /// [`make_writes`] in the node. A list with a built index finds its items
    /// through the index, and the index follows the writes.
    pub(crate) fn make_writes(&mut self, value: &mut FlowValue, tree: PathWrites, path: &mut Path) {
        for (segment, child) in tree.children.into_entries() {
            if let Some(write) = child.write {
                self.make_write(value, &segment, path, write);
                continue;
            }
            let index = self.index(path);
            let next = child_mut(value, path, &segment, index)
                .expect("the value under a written path exists");
            let keyed = FLOW_MODEL.listed_at(path);
            let had_position = keyed.has_position(next);
            path.push(segment);
            self.make_writes(next, child, path);
            let segment = path.pop().expect("the segment was pushed above");
            // The parser refuses a write that changes an item's key.
            // A write can change a row's position.
            if let Segment::Item(key) = &segment
                && let Some(index) = self.index(path)
            {
                debug_assert_eq!(
                    keyed.key_of(next),
                    Some(key.as_str()),
                    "the item keeps its key"
                );
                index.position_changed(had_position, keyed.has_position(next));
            }
        }
    }

    /// [`make_write`] in the node. The indexes follow the write.
    fn make_write(
        &mut self,
        parent: &mut FlowValue,
        segment: &Segment,
        parent_path: &[Segment],
        write: FieldWrite,
    ) {
        match segment {
            Segment::Key(key) => {
                // The write replaces or removes the lists under its path.
                self.lists.forget_under(self.id, parent_path, key);
                make_write(parent, segment, parent_path, write);
            }
            Segment::Item(key) => {
                let Some(index) = self.index(parent_path) else {
                    make_write(parent, segment, parent_path, write);
                    return;
                };
                let items = parent.as_vec_mut().expect("a list item's parent is a list");
                match write {
                    FieldWrite::Set(value) => {
                        // The parser refuses an item with another key.
                        debug_assert_eq!(
                            FLOW_MODEL.listed_at(parent_path).key_of(&value),
                            Some(key.as_str())
                        );
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
        keys.iter()
            .map(|key| Segment::Key((*key).to_owned()))
            .collect()
    }

    fn scan<'v>(
        at: &[Segment],
    ) -> impl FnMut(&'v FlowValue, usize, bool) -> Result<Option<&'v FlowValue>> {
        move |value, index, _| Ok(child(value, &at[..index], &at[index]))
    }

    #[test]
    fn path_children_promote_demote_and_keep_insertion_order() {
        let mut children = Children::default();
        let key = |name: &str| Segment::Key(name.into());
        for name in ["a", "b", "c"] {
            children.get_or_insert(&key(name));
        }
        assert!(matches!(children, Children::Many(_)));
        children.shift_remove(&key("b"));
        let order: Vec<_> = children
            .clone()
            .into_entries()
            .map(|(key, _)| key)
            .collect();
        assert_eq!(order, vec![key("a"), key("c")]);
        children.shift_remove(&key("a"));
        assert!(matches!(children, Children::One(_)));
        assert!(children.get(&key("c")).is_some());
        children.shift_remove(&key("c"));
        assert!(children.is_empty());
    }

    #[test]
    fn dropping_a_branched_write_keeps_other_writes_and_original_values() {
        let mut writes = PathWrites::default();
        let a = vec![Segment::Key("t".into()), Segment::Key("a".into())];
        let b = vec![Segment::Key("t".into()), Segment::Key("b".into())];
        writes.set(&a, FieldWrite::Set(crate::flow_value!(1)));
        writes.set(&b, FieldWrite::Set(crate::flow_value!(2)));
        writes.drop_write(&a);
        let mut value = crate::flow_value!({"t":{"a":0}});
        make_writes(&mut value, writes, &mut Vec::new());
        assert_eq!(value, crate::flow_value!({"t":{"a":0,"b":2}}));
    }

    #[test]
    fn pending_field_writes_reuse_small_maps_and_releases_large_batch_storage() {
        let mut layer = PendingFieldWrites::default();
        layer.node_mut("a");
        drop(layer.drain().collect::<Vec<_>>());
        layer.finish();
        assert!(layer.by_node.capacity() > 0);
        for i in 0..=MAX_RETAINED_BATCH_ENTRIES {
            layer.node_mut(&i.to_string());
        }
        layer.drop_pending();
        assert_eq!(layer.by_node.capacity(), 0);
        for i in 0..=MAX_RETAINED_BATCH_ENTRIES {
            layer.node_mut(&i.to_string());
        }
        drop(layer.drain().collect::<Vec<_>>());
        layer.finish();
        assert_eq!(layer.by_node.capacity(), 0);
    }

    #[test]
    fn a_write_at_an_ancestor_path_replaces_the_writes_below_it() {
        let mut writes = PathWrites::default();
        writes.set(&path(&["t", "a", "value"]), FieldWrite::Set(flow_value!(1)));
        writes.set(&path(&["t", "b"]), FieldWrite::Set(flow_value!({})));
        writes.set(
            &path(&["t", "a"]),
            FieldWrite::Set(flow_value!({"value": 2})),
        );
        let t = writes.children.get(&Segment::Key("t".into())).unwrap();
        assert!(matches!(&t.children, Children::Many(map) if map.len() == 2));
        let a = t.children.get(&Segment::Key("a".into())).unwrap();
        assert!(a.children.is_empty());
        let (len, write) = writes
            .write_on_path_mut(&path(&["t", "a", "value"]))
            .unwrap();
        assert_eq!(len, 2);
        assert!(matches!(write, FieldWrite::Set(value) if *value == flow_value!({"value": 2})));
    }

    #[test]
    fn a_dropped_write_takes_the_tree_nodes_it_leaves_empty() {
        let mut writes = PathWrites::default();
        writes.set(&path(&["t", "a", "value"]), FieldWrite::Set(flow_value!(1)));
        writes.drop_write(&path(&["t", "a", "value"]));
        assert!(writes.is_empty());
    }

    #[test]
    fn a_read_of_a_value_with_writes_below_it_makes_them_in_a_copy() {
        let node = flow_value!({"t": {"a": {"value": 1, "info": "x"}, "b": 2}});
        let mut writes = PathWrites::default();
        writes.set(&path(&["t", "a", "value"]), FieldWrite::Set(flow_value!(5)));
        writes.set(&path(&["t", "c"]), FieldWrite::Set(flow_value!(3)));
        writes.set(&path(&["t", "b"]), FieldWrite::Remove);
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
