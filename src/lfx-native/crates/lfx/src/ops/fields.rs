//! [`FieldLayer`]: the field writes of a batch, kept apart from the stored nodes.
//!
//! For each node, the layer keeps a tree of path segments ([`PathWrites`])
//! with the shape of the node's JSON. A read walks the tree and the node
//! together, and a write in the tree wins ([`walk`]). A batch that succeeds
//! makes its writes in the stored nodes ([`make_writes`]). A batch that fails
//! drops the layer.
//!
//! A tree node that holds a write has no children. A later write below it
//! changes its value. A later write above it replaces the writes below.
//! The tree keeps children in first-write order, so a batch gives one result.

use std::borrow::Cow;

use crate::ops::maps::{HashMap, IndexMap, State};
use crate::value::AnyValue;

use crate::ops::error::Result;
use crate::ops::keyed::{ListIndex, find_item, remove_item};
use crate::ops::ops::{Path, Segment};
use crate::ops::schema::NODE_SCHEMA;
use crate::ops::state::Lists;

/// The batch's write at a path of a node.
#[derive(Debug, Clone)]
pub(crate) enum FieldWrite {
    /// Set the value at the path: replace the value there, or add it.
    Set(AnyValue),
    /// Remove the value at the path.
    Remove,
}

/// The most map entries a layer keeps allocated between batches.
pub(crate) const MAX_RETAINED_BATCH_ENTRIES: usize = 256;

/// The children of a tree node. Most have one child, which needs no hash table.
#[derive(Debug, Clone, Default)]
enum Children {
    #[default]
    Empty,
    One(Box<(Segment, PathWrites)>),
    Many(Box<IndexMap<Segment, PathWrites>>),
}

impl Children {
    fn is_empty(&self) -> bool {
        matches!(self, Self::Empty)
    }
    fn get(&self, key: &Segment) -> Option<&PathWrites> {
        match self {
            Self::Empty => None,
            Self::One(pair) => (pair.0 == *key).then_some(&pair.1),
            Self::Many(map) => map.get(key),
        }
    }
    fn get_mut(&mut self, key: &Segment) -> Option<&mut PathWrites> {
        match self {
            Self::Empty => None,
            Self::One(pair) => (pair.0 == *key).then_some(&mut pair.1),
            Self::Many(map) => map.get_mut(key),
        }
    }
    fn get_or_insert(&mut self, key: &Segment) -> &mut PathWrites {
        if matches!(self, Self::Empty) {
            *self = Self::One(Box::new((key.clone(), PathWrites::default())));
        } else if matches!(self, Self::One(pair) if pair.0 != *key) {
            let Self::One(pair) = std::mem::take(self) else {
                unreachable!("one child");
            };
            let (first, value) = *pair;
            let mut map = IndexMap::with_capacity_and_hasher(2, State::default());
            map.insert(first, value);
            map.insert(key.clone(), PathWrites::default());
            *self = Self::Many(Box::new(map));
        }
        match self {
            Self::One(pair) => &mut pair.1,
            Self::Many(map) => {
                let slot = match map.get_index_of(key) {
                    Some(slot) => slot,
                    None => map.insert_full(key.clone(), PathWrites::default()).0,
                };
                map.get_index_mut(slot).expect("the child exists").1
            }
            Self::Empty => unreachable!("the child was inserted"),
        }
    }
    fn shift_remove(&mut self, key: &Segment) {
        match self {
            Self::One(pair) if pair.0 == *key => *self = Self::Empty,
            Self::Many(map) => {
                map.shift_remove(key);
                if map.len() <= 1 {
                    *self = map
                        .pop()
                        .map_or(Self::Empty, |pair| Self::One(Box::new(pair)));
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
            Self::One(pair) => (Some(*pair), None),
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
    pub fn discard(&mut self) {
        self.by_node.clear();
        self.finish();
    }
}

/// `step` itself, with the signature [`walk`] takes. It ties the returned
/// value to the value read, so a caller can call the step after the walk.
pub(crate) fn step_fn<'v, F>(step: F) -> F
where
    F: FnMut(&'v AnyValue, usize, bool) -> Result<Option<&'v AnyValue>>,
{
    step
}

/// What [`walk`] found along a path.
#[derive(Debug)]
pub(crate) struct Walked<'v> {
    /// The path length of the write that holds the value found. `None` when
    /// the node holds it.
    pub write_len: Option<usize>,
    /// The value at the path, or the index of the first segment that does not exist.
    pub found: std::result::Result<&'v AnyValue, usize>,
    /// The tree node at the path, when the node holds the value. It holds the
    /// writes below the path.
    pub writes: Option<&'v PathWrites>,
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
pub(crate) fn walk<'v>(
    node: &'v AnyValue,
    writes: Option<&'v PathWrites>,
    path: &[Segment],
    mut step: impl FnMut(&'v AnyValue, usize, bool) -> Result<Option<&'v AnyValue>>,
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

/// The value at `path` of `node`, with every write under it. When writes are
/// below `path`, it is a copy with those writes made.
///
/// # Errors
///
/// `step` fails.
pub(crate) fn read<'v>(
    node: &'v AnyValue,
    writes: Option<&'v PathWrites>,
    path: &[Segment],
    step: impl FnMut(&'v AnyValue, usize, bool) -> Result<Option<&'v AnyValue>>,
) -> Result<Option<Cow<'v, AnyValue>>> {
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
    value: &'v AnyValue,
    parent_path: &[Segment],
    segment: &Segment,
) -> Option<&'v AnyValue> {
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
    value: &'v mut AnyValue,
    path: &[Segment],
    start: usize,
) -> Option<&'v mut AnyValue> {
    (start..path.len()).try_fold(value, |value, index| {
        child_mut(value, &path[..index], &path[index], None)
    })
}

/// The value one `segment` under `value`, which is at `parent_path`, to
/// change it. An item is found through `index`, the list's index, or else by
/// reading every item.
fn child_mut<'v>(
    value: &'v mut AnyValue,
    parent_path: &[Segment],
    segment: &Segment,
    index: Option<&mut ListIndex>,
) -> Option<&'v mut AnyValue> {
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
        self.lists.built(self.id, path)
    }
}

/// Make the writes of `tree` in `value`, both at `path`. With `lists`,
/// `value` is a stored node, and its list indexes follow the writes.
pub(crate) fn make_writes(
    value: &mut AnyValue,
    tree: PathWrites,
    path: &mut Path,
    mut lists: Option<&mut NodeLists<'_>>,
) {
    for (segment, child) in tree.children.into_entries() {
        if let Some(write) = child.write {
            make_write(value, &segment, path, write, lists.as_deref_mut());
            continue;
        }
        let index = lists.as_deref_mut().and_then(|lists| lists.index(path));
        let next =
            child_mut(value, path, &segment, index).expect("the value under a written path exists");
        let keyed = NODE_SCHEMA.listed_at(path);
        let had_position = keyed.has_position(next);
        path.push(segment);
        make_writes(next, child, path, lists.as_deref_mut());
        let segment = path.pop().expect("the segment was pushed above");
        // The parser refuses a write that changes an item's key.
        // A write can change a row's position.
        if let (Segment::Item(key), Some(index)) = (
            &segment,
            lists.as_deref_mut().and_then(|lists| lists.index(path)),
        ) {
            debug_assert_eq!(
                keyed.key_of(next),
                Some(key.as_str()),
                "the item keeps its key"
            );
            index.position_changed(had_position, keyed.has_position(next));
        }
    }
}

/// Make `write` at `segment` of `parent`, the value at `parent_path`. A set
/// replaces the value or adds it last. A removal leaves the gap as the list's
/// kind says.
pub(crate) fn make_write(
    parent: &mut AnyValue,
    segment: &Segment,
    parent_path: &[Segment],
    write: FieldWrite,
    mut lists: Option<&mut NodeLists<'_>>,
) {
    match segment {
        Segment::Key(key) => {
            if let Some(lists) = lists.as_deref_mut() {
                // The write replaces or removes the lists under its path.
                lists.lists.forget_under(lists.id, parent_path, key);
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
                match write {
                    FieldWrite::Set(value) => {
                        // The parser refuses an item with another key.
                        debug_assert_eq!(keyed.key_of(&value), Some(key.as_str()));
                        match index.slot(key) {
                            Some(slot) => index.replace(items, slot, value),
                            None => index.add(items, key, value),
                        }
                    }
                    FieldWrite::Remove => {
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
    use crate::json;

    use super::*;

    fn path(keys: &[&str]) -> Path {
        keys.iter()
            .map(|key| Segment::Key((*key).to_owned()))
            .collect()
    }

    fn scan<'v>(
        at: &[Segment],
    ) -> impl FnMut(&'v AnyValue, usize, bool) -> Result<Option<&'v AnyValue>> {
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
        writes.set(&a, FieldWrite::Set(crate::json!(1)));
        writes.set(&b, FieldWrite::Set(crate::json!(2)));
        writes.drop_write(&a);
        let mut value = crate::json!({"t":{"a":0}});
        make_writes(&mut value, writes, &mut Vec::new(), None);
        assert_eq!(value, crate::json!({"t":{"a":0,"b":2}}));
    }

    #[test]
    fn field_layer_reuses_small_maps_and_releases_large_batch_storage() {
        let mut layer = FieldLayer::default();
        layer.node_mut("a");
        drop(layer.drain().collect::<Vec<_>>());
        layer.finish();
        assert!(layer.by_node.capacity() > 0);
        for i in 0..=MAX_RETAINED_BATCH_ENTRIES {
            layer.node_mut(&i.to_string());
        }
        layer.discard();
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
        writes.set(&path(&["t", "a", "value"]), FieldWrite::Set(json!(1)));
        writes.set(&path(&["t", "b"]), FieldWrite::Set(json!({})));
        writes.set(&path(&["t", "a"]), FieldWrite::Set(json!({"value": 2})));
        let t = writes.children.get(&Segment::Key("t".into())).unwrap();
        assert!(matches!(&t.children, Children::Many(map) if map.len() == 2));
        let a = t.children.get(&Segment::Key("a".into())).unwrap();
        assert!(a.children.is_empty());
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
