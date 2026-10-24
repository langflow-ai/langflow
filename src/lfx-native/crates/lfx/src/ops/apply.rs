//! Applying an operation batch to a flow.
//!
//! A batch applies in order, and all of it or none of it: on an error the
//! flow is as it was before the batch.
//!
//! Each operation of the batch can give apply two results:
//!
//! - When the caller sets the `forward` option, its forward operations. They
//!   can differ from the operation that was sent: a `delete_edges` or a
//!   `delete_field` that finds nothing is dropped, and the edges that a
//!   delete takes with it (a cascade delete) become a `delete_edges` of
//!   their own. So one operation gives none, one or several.
//! - When the caller sets the `backward` option, its backward operations: a
//!   list of the operations that undo it, read from the values it replaces.
//!
//! For example, `delete_nodes ["b"]`, where node `b` has the edge `e1`,
//! gives the forward operations `delete_nodes ["b"]` and
//! `delete_edges ["e1"]`. Its backward operations are `add_nodes [b]`, then
//! `add_edges [e1]`: the node comes back before the edge that needs it.
//!
//! [`Applied::backward`] says how to apply the backward operations.

use std::collections::HashSet;
use std::fmt;

use indexmap::IndexSet;
use serde_json::Value;

use crate::ops::canonical::is_row_position;
use crate::ops::edges::{check_edge, removed_endpoints};
use crate::ops::error::{Error, Result, bail, invalid, quoted};
use crate::ops::ops::{Change, Edge, FieldUpdate, Node, NodePath, Operation, PathExt, Segment};
use crate::ops::schema::{KeyedList, ListKind, NODE_SCHEMA};
use crate::ops::state::{Graph, GraphState, Lists, resolve, resolve_mut};
use crate::ops::validate::PathPart;

/// How a batch is applied.
#[derive(Debug, Clone, Copy, Default)]
pub struct ApplyOptions {
    /// Return the forward operations.
    pub forward: bool,
    /// Return, for each operation, its backward operations.
    pub backward: bool,
    /// Apply backward operations. They put back a state the flow already had,
    /// whatever rules it broke, and they add and delete every edge they touch
    /// explicitly. So the edge rules, and the cascade delete of a removed
    /// field or output, are both skipped. Never set this for a batch that
    /// will be saved.
    pub restoring: bool,
}

/// What a batch did.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Applied {
    /// When the caller sets the `forward` option: the forward operations.
    pub forward: Vec<Operation>,
    /// When the caller sets the `backward` option: for each operation in the
    /// batch, in the same order, a list of the operations that undo it. An
    /// operation that changed nothing has an empty list.
    ///
    /// To undo the whole batch, undo the last operation first: apply the lists
    /// from last to first, and keep the order inside each list.
    ///
    /// There are two ways to apply them:
    ///
    /// - To show an earlier version of the flow, as the editor's history does,
    ///   set the `restoring` option. The flow goes back to a state it already
    ///   had, so the engine skips its edge rules.
    /// - To undo an edit with a new edit, put the lists into one batch, in that
    ///   order, and apply it without `restoring`. The new edit is saved like any
    ///   other edit, so it must pass the same rules.
    pub backward: Vec<Vec<Operation>>,
}

/// The options of a batch, and what it reports as it applies.
///
/// The report keeps the forward and backward operations for the caller,
/// and only when the options ask for them. A batch that fails needs neither:
/// its changes stay in the batch's layer in `state`, which is dropped.
#[derive(Debug)]
struct Report {
    options: ApplyOptions,
    applied: Applied,
}

impl Report {
    fn new(options: ApplyOptions) -> Self {
        Self {
            options,
            applied: Applied::default(),
        }
    }

    /// Start an operation: its backward operations go into a list of their own.
    fn begin_operation(&mut self) {
        if self.options.backward {
            self.applied.backward.push(Vec::new());
        }
    }

    /// Keep a forward operation. Kept only with `forward`.
    fn record(&mut self, operation: Operation) {
        if self.options.forward {
            self.applied.forward.push(operation);
        }
    }

    /// Record an operation that undoes part of the operation being applied.
    /// Kept only with `backward`.
    fn record_backward(&mut self, operation: Operation) {
        if self.options.backward {
            self.applied
                .backward
                .last_mut()
                .expect("begin_operation started a list")
                .push(operation);
        }
    }
}

impl GraphState {
    /// Apply a batch of operations in order. On an error nothing is applied.
    ///
    /// # Errors
    ///
    /// An operation is invalid for the graph.
    pub fn apply(&mut self, operations: Vec<Operation>, options: ApplyOptions) -> Result<Applied> {
        let mut report = Report::new(options);
        for operation in operations {
            if let Err(error) = self.apply_operation(operation, &mut report) {
                self.discard();
                return Err(error);
            }
        }
        self.commit();
        Ok(report.applied)
    }

    fn apply_operation(&mut self, operation: Operation, report: &mut Report) -> Result<()> {
        report.begin_operation();
        match operation {
            Operation::AddNodes(nodes) => self.add_nodes(nodes, report)?,
            Operation::UpdateNodes(updates) => self.update_nodes(updates, report)?,
            Operation::DeleteNodes(ids) => self.delete_nodes(&ids, report)?,
            Operation::AddEdges(edges) => self.add_edges(edges, report)?,
            Operation::DeleteEdges(ids) => self.delete_edges(&ids, report),
        }
        Ok(())
    }

    // --- Nodes -------------------------------------------------------------------------

    /// Add nodes. The parser checked each node's shape, and that no id
    /// repeats in the operation; an id the flow already has is refused here.
    fn add_nodes(&mut self, nodes: Vec<Node>, report: &mut Report) -> Result<()> {
        if nodes.is_empty() {
            return Ok(());
        }
        let mut added = Vec::new();
        let mut payloads = Vec::new();
        for node in nodes {
            if self.graph.nodes.contains(node.id()) {
                bail!("add_nodes: node id already exists: {}", quoted(node.id()));
            }
            if report.options.forward {
                payloads.push(node.clone());
            }
            if report.options.backward {
                added.push(node.id().to_owned());
            }
            self.insert_node(node);
        }
        report.record(Operation::AddNodes(payloads));
        report.record_backward(Operation::DeleteNodes(added));
        Ok(())
    }

    fn update_nodes(&mut self, updates: Vec<FieldUpdate>, report: &mut Report) -> Result<()> {
        if updates.is_empty() {
            return Ok(());
        }
        let mut backward = report.options.backward.then(FieldBackward::default);
        let mut applied = Vec::new();
        let mut cascaded = IndexSet::new();
        for (index, mut update) in updates.into_iter().enumerate() {
            let context = UpdatePlace::new(index);
            if !self.graph.nodes.contains(&update.id) {
                bail!("update_nodes: node does not exist: {}", quoted(&update.id));
            }
            if !self.is_base_node(&update.id) {
                bail!(
                    "update_nodes: cannot update node that does not exist in the original flow: {}",
                    quoted(&update.id)
                );
            }
            let replaced =
                self.apply_field_update(&mut update, context, report.options, backward.as_mut())?;
            if !report.options.restoring
                && let Some(before) = &replaced
            {
                cascaded.extend(self.edges_at_removed(&update, before)?);
            }
            // A delete that found nothing is not recorded.
            if report.options.forward && (replaced.is_some() || !update.is_delete()) {
                applied.push(update);
            }
        }
        if !applied.is_empty() {
            report.record(Operation::UpdateNodes(applied));
        }
        if let Some(backward) = backward {
            for operation in backward.operations(Operation::UpdateNodes) {
                report.record_backward(operation);
            }
        }
        self.remove_edges(cascaded.iter().map(String::as_str), report);
        Ok(())
    }

    /// The edges at the endpoints that `update` removed from its node, which
    /// go with them. `before` is what the path held before the write.
    fn edges_at_removed(
        &mut self,
        update: &FieldUpdate,
        before: &Value,
    ) -> Result<IndexSet<String>> {
        let node_id = update.id.as_str();
        let node = self
            .graph
            .nodes
            .get(node_id)
            .ok_or_else(|| invalid!("node {} does not exist", quoted(node_id)))?;
        let removed = removed_endpoints(
            &update.path,
            update.is_delete(),
            before,
            node.as_value(),
            node_id,
        )?;
        if removed.is_empty() {
            return Ok(IndexSet::new());
        }
        let connections = self.edge_index.connections(&self.graph, node_id)?;
        Ok(removed
            .iter()
            .flat_map(|endpoint| connections.at(endpoint))
            .cloned()
            .collect())
    }

    fn delete_nodes(&mut self, ids: &[String], report: &mut Report) -> Result<()> {
        let ids: IndexSet<&str> = ids.iter().map(String::as_str).collect();
        if ids.is_empty() {
            return Ok(());
        }
        for id in &ids {
            if !self.is_base_node(id) {
                bail!(
                    "delete_nodes: cannot delete node that does not exist in the original flow: {}",
                    quoted(id)
                );
            }
        }
        let mut removed = Vec::new();
        let mut removed_nodes = Vec::new();
        let mut incident = IndexSet::new();
        for id in ids {
            if !self.graph.nodes.contains(id) {
                continue;
            }
            incident.extend(self.graph.edges_at(id).cloned());
            if report.options.backward {
                removed_nodes.extend(self.node_copy(id));
            }
            self.remove_node(id);
            removed.push(id.to_owned());
        }
        if removed.is_empty() {
            return Ok(());
        }
        report.record(Operation::DeleteNodes(removed));
        report.record_backward(Operation::AddNodes(removed_nodes));
        self.remove_edges(incident.iter().map(String::as_str), report);
        Ok(())
    }

    // --- Edges -------------------------------------------------------------------------

    /// Add edges. The parser checked each edge's shape, and that no id
    /// repeats in the operation; what the edge needs from the flow is checked
    /// here.
    fn add_edges(&mut self, edges: Vec<Edge>, report: &mut Report) -> Result<()> {
        if edges.is_empty() {
            return Ok(());
        }
        let mut added = Vec::new();
        let mut payloads = Vec::new();
        for edge in edges {
            if self.graph.edges.contains(edge.id()) {
                bail!("add_edges: edge id already exists: {}", quoted(edge.id()));
            }
            if !self.graph.nodes.contains(edge.source()) {
                bail!(
                    "add_edges: source node does not exist: {}",
                    quoted(edge.source())
                );
            }
            if !self.graph.nodes.contains(edge.target()) {
                bail!(
                    "add_edges: target node does not exist: {}",
                    quoted(edge.target())
                );
            }
            if !report.options.restoring {
                check_edge(&self.graph, &mut self.edge_index, edge.as_map())?;
            }
            if report.options.forward {
                payloads.push(edge.clone());
            }
            if report.options.backward {
                added.push(edge.id().to_owned());
            }
            self.insert_edge(edge);
        }
        report.record(Operation::AddEdges(payloads));
        report.record_backward(Operation::DeleteEdges(added));
        Ok(())
    }

    fn delete_edges(&mut self, ids: &[String], report: &mut Report) {
        self.remove_edges(ids.iter().map(String::as_str), report);
    }

    /// Remove the edges among `ids` that exist, each once, and record them as
    /// a `delete_edges`. A `delete_edges` and a cascade delete both remove
    /// their edges here.
    fn remove_edges<'i>(&mut self, ids: impl IntoIterator<Item = &'i str>, report: &mut Report) {
        let mut removed = Vec::new();
        let mut copies = Vec::new();
        let mut seen = HashSet::new();
        for id in ids {
            if !seen.insert(id) || !self.graph.edges.contains(id) {
                continue;
            }
            if report.options.backward {
                copies.extend(self.edge_copy(id));
            }
            self.remove_edge(id);
            removed.push(id.to_owned());
        }
        if removed.is_empty() {
            return;
        }
        report.record(Operation::DeleteEdges(removed));
        report.record_backward(Operation::AddEdges(copies));
    }

    // --- Field writes ----------------------------------------------------------------------

    /// Apply one `set_field` or `delete_field` to a node.
    ///
    /// Returns the value the path held before the write, if any. Without
    /// `forward`, a set's value moves into the graph instead of being copied.
    fn apply_field_update(
        &mut self,
        update: &mut FieldUpdate,
        context: UpdatePlace,
        options: ApplyOptions,
        backward: Option<&mut FieldBackward>,
    ) -> Result<Option<Value>> {
        let walk = self.check_field_update(&FieldWrite { update, context }, backward)?;
        let value = match &mut update.change {
            Change::Set(value) if !options.forward => std::mem::take(value),
            Change::Set(value) => value.clone(),
            Change::Delete => Value::Null,
        };
        let write = FieldWrite { update, context };
        let replaced = self.write_last(&write, &walk, value)?;
        self.check_list_keys_kept(&write, &walk)?;
        Ok(replaced)
    }

    /// Check a field update before it writes anything: its path must exist
    /// up to the last segment. Record its backward operation, and return its path as
    /// object keys and array indexes.
    fn check_field_update(
        &mut self,
        write: &FieldWrite<'_>,
        backward: Option<&mut FieldBackward>,
    ) -> Result<Walk> {
        let walk = self.walk(write)?;
        if let Some(missing) = walk.missing_at {
            return Err(missing_segment(write, missing));
        }
        if let Some(backward) = backward {
            let last_step = self.read_last(write, &walk)?;
            let root = written(&self.graph, write);
            let parent = resolve(root, &walk.steps);
            let current = last_step
                .as_ref()
                .and_then(|step| resolve(parent?, std::slice::from_ref(step)));
            backward.record(root, write.update, parent, current);
        }
        Ok(walk)
    }

    /// Check that a write inside a keyed list item left the item's key alone,
    /// and a table row its position.
    fn check_list_keys_kept(&self, write: &FieldWrite<'_>, walk: &Walk) -> Result<()> {
        let context = write.context;
        let root = written(&self.graph, write);
        for item in walk.list_items.iter().rev() {
            let value = resolve(root, &walk.steps[..item.depth]);
            if value.and_then(|value| item.keyed.key_of(value)) != Some(item.key.as_str()) {
                bail!("{context}: cannot change a list item's key");
            }
            if let Some(position) = item.keyed.position.as_deref()
                && !value
                    .and_then(|value| value.get(position))
                    .is_some_and(is_row_position)
            {
                bail!("{context}: a table row's {position} must be a finite number");
            }
        }
        Ok(())
    }

    /// Follow `path[..last]` from the node or edge, once.
    ///
    /// Returns the path as object keys and array indexes, the keyed list items passed through, and
    /// the first segment that does not exist. A segment that does not fit the
    /// value it reads, such as a key of a list, is an error rather than a
    /// missing value.
    fn walk(&mut self, write: &FieldWrite<'_>) -> Result<Walk> {
        let (path, context) = (&write.update.path, write.context);
        let mut walk = Walk::default();
        let root = written(&self.graph, write);
        let mut value = root;
        for (index, part) in path[..path.len() - 1].iter().enumerate() {
            let key = match part {
                Segment::Key(key) => {
                    let Value::Object(map) = value else {
                        bail!(
                            "{context}.path[{index}]: {} reads a key of a value that is not an object",
                            quoted(key)
                        );
                    };
                    let Some(child) = map.get(key) else {
                        walk.missing_at = Some(index);
                        return Ok(walk);
                    };
                    walk.steps.push(PathPart::Key(key.clone()));
                    value = child;
                    continue;
                }
                Segment::Item(key) => key,
            };
            let (keyed, slot) = list_slot(&mut self.lists, write, root, index, value, key)?;
            let Some(slot) = slot else {
                walk.missing_at = Some(index);
                return Ok(walk);
            };
            walk.steps.push(PathPart::Index(slot));
            walk.list_items.push(ListItemOnPath {
                keyed,
                key: key.clone(),
                depth: walk.steps.len(),
            });
            value = &value[slot];
        }
        Ok(walk)
    }

    /// The step from the value holding the last segment to the value the path
    /// names, or `None` when there is none.
    fn read_last(&mut self, write: &FieldWrite<'_>, walk: &Walk) -> Result<Option<PathPart>> {
        let (path, context) = (&write.update.path, write.context);
        let last = path.len() - 1;
        let root = written(&self.graph, write);
        let parent = resolve(root, &walk.steps).expect("the walk resolved these steps");
        let key = match &path[last] {
            Segment::Key(key) => {
                let Value::Object(map) = parent else {
                    bail!(
                        "{context}.path[{last}]: {} reads a key of a value that is not an object",
                        quoted(key)
                    );
                };
                return Ok(map.contains_key(key).then(|| PathPart::Key(key.clone())));
            }
            Segment::Item(key) => key,
        };
        let (_, slot) = list_slot(&mut self.lists, write, root, last, parent, key)?;
        Ok(slot.map(PathPart::Index))
    }

    /// Write or delete the last segment of the path. Returns the value it held, if any.
    fn write_last(
        &mut self,
        write: &FieldWrite<'_>,
        walk: &Walk,
        value: Value,
    ) -> Result<Option<Value>> {
        let (id, path) = (write.update.id.as_str(), &write.update.path);
        let written = match &path[path.len() - 1] {
            Segment::Key(key) => self.write_key(write, walk, key, value)?,
            Segment::Item(key) => self.write_item(write, walk, key, value)?,
        };
        let replaced = match written {
            Written::Nothing => return Ok(None),
            Written::Added => None,
            Written::Replaced(old) => Some(old),
        };
        // A whole value replaced or removed takes the lists indexed under it with it.
        if let Some(keys) = path.to_list() {
            self.lists.forget_under(id, &keys);
        }
        Ok(replaced)
    }

    /// The value that holds the path's last segment, to write it.
    fn parent_mut(&mut self, write: &FieldWrite<'_>, walk: &Walk) -> Option<&mut Value> {
        self.graph
            .nodes
            .get_mut(&write.update.id)
            .and_then(|node| resolve_mut(node.as_value_mut(), &walk.steps))
    }

    /// Write or delete an object key.
    fn write_key(
        &mut self,
        write: &FieldWrite<'_>,
        walk: &Walk,
        key: &str,
        value: Value,
    ) -> Result<Written> {
        let (update, context) = (write.update, write.context);
        let Some(Value::Object(map)) = self.parent_mut(write, walk) else {
            bail!("{context}: path must end at an object property or a keyed list item");
        };
        if update.is_delete() {
            return Ok(map
                .shift_remove(key)
                .map_or(Written::Nothing, Written::Replaced));
        }
        Ok(map
            .insert(key.to_owned(), value)
            .map_or(Written::Added, Written::Replaced))
    }

    /// Write or delete a keyed list item.
    fn write_item(
        &mut self,
        write: &FieldWrite<'_>,
        walk: &Walk,
        key: &str,
        value: Value,
    ) -> Result<Written> {
        let (update, context) = (write.update, write.context);
        let path = &update.path;
        let last = path.len() - 1;
        let (keyed, prefix) = {
            let root = written(&self.graph, write);
            let parent = resolve(root, &walk.steps).expect("the walk resolved these steps");
            keyed_list(root, path, last, parent, context)?
        };
        let list_context = context.segment(last);
        let parent = self
            .graph
            .nodes
            .get_mut(&update.id)
            .and_then(|node| resolve_mut(node.as_value_mut(), &walk.steps));
        let Some(Value::Array(items)) = parent else {
            bail!("{list_context}: list item key on a value that is not a list");
        };
        let index = self
            .lists
            .index(&update.id, &prefix, keyed, items, &list_context)?;
        if update.is_delete() {
            return Ok(index
                .remove(items, key)
                .map_or(Written::Nothing, Written::Replaced));
        }
        let slot = index.slot(key);
        if keyed.key_of(&value) != Some(key) {
            bail!(
                "{context}: a list item written at its key must carry the same key: {}",
                quoted(key)
            );
        }
        if let Some(slot) = slot {
            return Ok(Written::Replaced(
                index.replace(items, slot, value, &context)?,
            ));
        }
        index.add(items, value, &context)?;
        Ok(Written::Added)
    }
}

/// The node a field write goes to. `update_nodes` checks that it exists
/// before it writes.
fn written<'g>(graph: &'g Graph, write: &FieldWrite<'_>) -> &'g Value {
    graph
        .nodes
        .get(&write.update.id)
        .expect("update_nodes checks that the node exists")
        .as_value()
}

/// What a field write did at the last segment of its path.
#[derive(Debug)]
enum Written {
    /// A delete found nothing, so nothing changed.
    Nothing,
    /// A set wrote a key or an item that was not there.
    Added,
    /// A set or a delete replaced or removed this value.
    Replaced(Value),
}

/// One field update on its way into a node.
#[derive(Debug)]
struct FieldWrite<'w> {
    update: &'w FieldUpdate,
    /// Where the update is in its operation, for messages.
    context: UpdatePlace,
}

/// Where a field update is in its `update_nodes`, for error messages:
/// `update_nodes[1]`, or one segment of its path, `update_nodes[1].path[2]`.
/// It is formatted only when an error is, so an update that applies builds
/// no message.
#[derive(Debug, Clone, Copy)]
struct UpdatePlace {
    update: usize,
    segment: Option<usize>,
}

impl UpdatePlace {
    fn new(update: usize) -> Self {
        Self {
            update,
            segment: None,
        }
    }

    /// The place of segment `index` of the update's path.
    fn segment(self, index: usize) -> Self {
        Self {
            segment: Some(index),
            ..self
        }
    }
}

impl fmt::Display for UpdatePlace {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "update_nodes[{}]", self.update)?;
        if let Some(segment) = self.segment {
            write!(f, ".path[{segment}]")?;
        }
        Ok(())
    }
}

/// Where a field update's path leads, as object keys and array indexes, up to its last segment.
#[derive(Debug, Default)]
struct Walk {
    /// The steps to the value that holds the last segment.
    steps: Vec<PathPart>,
    /// The keyed list items the path passes through.
    list_items: Vec<ListItemOnPath>,
    /// The index of the first segment that does not exist.
    missing_at: Option<usize>,
}

/// A keyed list item a path passes through.
#[derive(Debug)]
struct ListItemOnPath {
    keyed: &'static KeyedList,
    key: String,
    /// How many steps lead to the item.
    depth: usize,
}

/// The error for the first segment of a path that does not exist.
fn missing_segment(write: &FieldWrite<'_>, missing: usize) -> Error {
    let context = write.context;
    match &write.update.path[missing] {
        Segment::Key(key) => invalid!(
            "{context}.path[{missing}]: object path part must be an existing string key: {}",
            quoted(key)
        ),
        Segment::Item(key) => invalid!(
            "{context}.path[{missing}]: list item does not exist: {}",
            quoted(key)
        ),
    }
}

/// The keyed list `path[index]` names an item of, and the array index of the item with
/// `key`, or `None` when there is no such item.
fn list_slot(
    lists: &mut Lists,
    write: &FieldWrite<'_>,
    root: &Value,
    index: usize,
    list: &Value,
    key: &str,
) -> Result<(&'static KeyedList, Option<usize>)> {
    let (path, context) = (&write.update.path, write.context);
    let (keyed, prefix) = keyed_list(root, path, index, list, context)?;
    let items = list.as_array().map(Vec::as_slice).unwrap_or_default();
    let slot = lists
        .index(
            &write.update.id,
            &prefix,
            keyed,
            items,
            &context.segment(index),
        )?
        .slot(key);
    Ok((keyed, slot))
}

/// The keyed list whose item `path[index]` names, and its address: the
/// object keys that lead to it. Checks that the list is keyed.
fn keyed_list<'p>(
    node: &Value,
    path: &'p [Segment],
    index: usize,
    value: &Value,
    context: UpdatePlace,
) -> Result<(&'static KeyedList, Vec<&'p str>)> {
    let prefix = path[..index].to_list();
    let Some((keyed, prefix)) = prefix.and_then(|prefix| {
        NODE_SCHEMA
            .keyed_list_at(node, &prefix)
            .map(|keyed| (keyed, prefix))
    }) else {
        bail!(
            "{context}.path[{index}]: list item key on a list the node schema does not declare keyed"
        );
    };
    if !value.is_array() {
        bail!("{context}.path[{index}]: list item key on a value that is not a list");
    }
    Ok((keyed, prefix))
}

// --- Backward operations of field writes ---------------------------------------------------

/// The writes that undo an update batch, read from the state each write
/// replaces. They are undone last first; a path written twice is split into
/// separate operations, since one operation may write a path once.
#[derive(Debug, Default)]
struct FieldBackward {
    entries: Vec<FieldUpdate>,
}

impl FieldBackward {
    /// Record what undoes `update`; called before it is applied.
    ///
    /// `parent` holds the path's last segment, and `current` is what the path holds.
    fn record(
        &mut self,
        root: &Value,
        update: &FieldUpdate,
        parent: Option<&Value>,
        current: Option<&Value>,
    ) {
        let path = &update.path;
        let last = path.len() - 1;
        if update.is_delete()
            && let (Segment::Item(key), Some(Value::Array(items)), Some(_)) =
                (&path[last], parent, current)
            && let Some(keyed) = path[..last]
                .to_list()
                .and_then(|prefix| NODE_SCHEMA.keyed_list_at(root, &prefix))
            && keyed.kind == ListKind::Natural
        {
            // Removing a natural-list item that is not last cannot be undone by
            // a write at the item's key, which appends; the whole list is written back.
            // A table's order is its rows' positions, so its rows need no such care.
            let is_last = items
                .last()
                .is_some_and(|item| keyed.key_of(item) == Some(key.as_str()));
            if !is_last {
                // The prefix is the path of a keyed list the schema declares,
                // such as `data.node.outputs`, which a field update may write.
                let list_path = NodePath::try_from(path[..last].to_vec())
                    .expect("a keyed list's path may be written");
                self.entries.push(FieldUpdate::set(
                    &update.id,
                    list_path,
                    Value::Array(items.clone()),
                ));
                return;
            }
        }
        let Some(current) = current else {
            if !update.is_delete() {
                self.entries
                    .push(FieldUpdate::delete(&update.id, path.clone()));
            }
            return;
        };
        self.entries
            .push(FieldUpdate::set(&update.id, path.clone(), current.clone()));
    }

    fn operations(self, build: fn(Vec<FieldUpdate>) -> Operation) -> Vec<Operation> {
        let mut operations = Vec::new();
        let mut batch: Vec<FieldUpdate> = Vec::new();
        let mut written: HashSet<(String, NodePath)> = HashSet::new();
        for entry in self.entries.into_iter().rev() {
            let key = (entry.id.clone(), entry.path.clone());
            if written.contains(&key) {
                operations.push(build(std::mem::take(&mut batch)));
                written.clear();
            }
            written.insert(key);
            batch.push(entry);
        }
        if !batch.is_empty() {
            operations.push(build(batch));
        }
        operations
    }
}

/// Apply operations to a flow graph and return the result with what the batch did.
///
/// # Errors
///
/// The graph breaks a structural rule, or an operation is invalid for it.
pub fn apply_flow_operations(
    base: Value,
    operations: Vec<Operation>,
    options: ApplyOptions,
) -> Result<(Value, Applied)> {
    let mut state = GraphState::new(base)?;
    let applied = state.apply(operations, options)?;
    Ok((state.into_value(), applied))
}

#[cfg(test)]
mod tests {
    use serde_json::{Value, json};

    use super::*;
    use crate::ops::edges::escape_handle;

    fn target_handle(field: &str) -> Value {
        json!({"fieldName": field, "id": "T", "inputTypes": ["Message"], "type": "str"})
    }

    fn edge(id: &str, field: &str) -> Value {
        let source =
            json!({"dataType": "X", "id": "S", "name": "out", "output_types": ["Message"]});
        json!({
            "id": id, "source": "S", "target": "T",
            "sourceHandle": escape_handle(&source),
            "targetHandle": escape_handle(&target_handle(field)),
            "data": {"sourceHandle": source, "targetHandle": target_handle(field)},
        })
    }

    fn operations(value: Value) -> Vec<Operation> {
        Operation::list_from_value(value).unwrap()
    }

    #[test]
    fn an_update_error_names_the_update_and_the_segment() {
        let graph = json!({
            "nodes": [{"id": "a", "data": {"node": {"template": {"f": {"value": 1}}}}}],
            "edges": [],
        });
        let mut state = GraphState::new(graph).unwrap();
        let write = json!([{"type": "update_nodes", "updates": [
            {"id": "a", "op": "set_field", "path": ["position"], "value": {}},
            {"id": "a", "op": "set_field", "path": ["data", "node", "template", "f", "value", {"key": "r"}], "value": 1},
        ]}]);
        let error = state
            .apply(operations(write), ApplyOptions::default())
            .unwrap_err();
        assert!(
            error.message.starts_with("update_nodes[1].path[5]: "),
            "{}",
            error.message
        );
    }

    #[test]
    fn a_held_state_swaps_two_edges_by_deleting_and_adding_them() {
        let field = json!({"type": "str", "value": ""});
        let graph = json!({
            "nodes": [
                {"id": "S", "data": {"node": {"template": {}, "outputs": [{"name": "out"}]}}},
                {"id": "T", "data": {"node": {"template": {"A": field, "B": field, "C": field}}}},
            ],
            "edges": [edge("e1", "B"), edge("e2", "A")],
        });
        let mut state = GraphState::new(graph).unwrap();
        // This batch indexes the connections of T, which the next batch reuses.
        let add = json!([{"type": "add_edges", "edges": [edge("e3", "C")]}]);
        state
            .apply(operations(add), ApplyOptions::default())
            .unwrap();
        let swap = json!([
            {"type": "delete_edges", "ids": ["e1", "e2"]},
            {"type": "add_edges", "edges": [edge("e1", "A"), edge("e2", "B")]},
        ]);
        state
            .apply(operations(swap), ApplyOptions::default())
            .unwrap();
    }

    #[test]
    fn a_refused_batch_keeps_the_indexes_earlier_batches_built() {
        let field = json!({"type": "str", "value": ""});
        let graph = json!({
            "nodes": [
                {"id": "S", "data": {"node": {"template": {}, "outputs": [{"name": "out"}]}}},
                {"id": "T", "data": {"node": {"template": {"A": field, "B": field}}}},
            ],
            "edges": [edge("e1", "A")],
        });
        let mut state = GraphState::new(graph).unwrap();
        let add = json!([{"type": "add_edges", "edges": [edge("e2", "B")]}]);
        state
            .apply(operations(add), ApplyOptions::default())
            .unwrap();
        assert!(state.edge_index.has_connections("T"));
        // A writes T, then the second edge into A is refused: the batch changes nothing.
        let refused = json!([
            {"type": "update_nodes", "updates": [
                {"id": "T", "op": "set_field", "path": ["data", "node", "template", "A", "value"], "value": "x"},
            ]},
            {"type": "add_edges", "edges": [edge("e3", "A")]},
        ]);
        let before = state.to_value();
        state
            .apply(operations(refused), ApplyOptions::default())
            .unwrap_err();
        assert_eq!(state.to_value(), before);
        assert!(state.edge_index.has_connections("T"));
    }

    #[test]
    fn a_group_sub_flow_node_is_not_selected_by_key() {
        let inner = json!({"id": "lm", "data": {"node": {"template": {"api_key": {"value": ""}}}}});
        let graph = json!({
            "nodes": [{"id": "g", "data": {"node": {
                "template": {},
                "flow": {"data": {"nodes": [inner], "edges": []}},
            }}}],
            "edges": [],
        });
        let path = json!([
            "data", "node", "flow", "data", "nodes", {"key": "lm"},
            "data", "node", "template", "api_key", "value",
        ]);
        let write = json!([{"type": "update_nodes", "updates": [
            {"id": "g", "op": "set_field", "path": path, "value": "x"},
        ]}]);
        let error =
            apply_flow_operations(graph, operations(write), ApplyOptions::default()).unwrap_err();
        assert!(
            error.to_string().contains("does not declare keyed"),
            "{error}"
        );
    }
}
