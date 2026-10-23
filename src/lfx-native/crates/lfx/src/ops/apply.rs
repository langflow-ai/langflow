//! Applying operations to a flow graph.
//!
//! A batch applies in order, and all of it or none of it: on an error the
//! state is as it was before the batch. Apply records each operation as the
//! history stores it: a delete that finds nothing is not recorded, and the
//! edges a delete takes with it are recorded as a `delete_edges` of their own.
//!
//! With `inverse`, apply also returns, for each operation, the operations
//! that undo it, read from the state each write replaces. History playback
//! keeps those instead of a graph per revision. Inverses are applied with
//! `restoring`, last operation first.

use std::collections::HashSet;

use indexmap::IndexSet;
use serde_json::{Map, Value};

use crate::ops::canonical::is_row_position;
use crate::ops::edges::{Input, InputKind, check_edge, index_outputs, node_outputs};
use crate::ops::entry::EntryExt;
use crate::ops::error::{Error, Result, bail, invalid, quoted};
use crate::ops::ops::{AsKey, Change, FieldUpdate, Operation, Path, PathExt, Segment, path_label};
use crate::ops::schema::{
    KeyedList, ListKind, NODE_OBJECT_PATHS, NODE_SCHEMA, OUTPUTS_PATH, TEMPLATE_PATH,
};
use crate::ops::state::{Copies, FieldUndo, Graph, GraphState, Lists, resolve, resolve_mut};
use crate::ops::validate::PathPart;
use crate::ops::validate::missing_node_object;

/// How a batch is applied.
#[derive(Debug, Clone, Copy, Default)]
pub struct ApplyOptions {
    /// Return the operations as the engine records them.
    pub forward: bool,
    /// Return, for each operation, the operations that undo it.
    pub inverse: bool,
    /// Apply inverses. Inverses put back a state the history already held,
    /// whatever rules it broke, and they add and delete every edge they touch
    /// explicitly. So the edge rules, and the edges a removed field or output
    /// would take with it, are both skipped. Never set this when applying
    /// operations that will be stored.
    pub restoring: bool,
}

/// What a batch did.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Applied {
    /// The operations as the engine records them, with `forward`.
    pub forward: Vec<Operation>,
    /// With `inverse`: for each operation applied, the operations that undo
    /// it. Undo the last operation first, each list in a call of its own,
    /// with `restoring` set.
    pub inverse: Vec<Vec<Operation>>,
    /// The edges the batch deleted because their node, field or output went away.
    pub deleted_edges: Vec<String>,
    /// The nodes the batch added, removed or wrote.
    pub changed_nodes: Vec<String>,
    /// The edges the batch added, removed or wrote.
    pub changed_edges: Vec<String>,
}

/// The options of a batch, and what it reports as it applies.
///
/// Apply keeps two kinds of record, and they are different things. This
/// report keeps the forward operations and the inverses for the caller, and
/// only when the options ask for them. The undo list in `state` (`undos`) is
/// always kept, inside the engine, to put the graph back when a batch fails.
#[derive(Debug)]
struct Report {
    options: ApplyOptions,
    applied: Applied,
    /// The inverses of the operation being applied, so far.
    inverse: Vec<Operation>,
}

impl Report {
    fn new(options: ApplyOptions) -> Self {
        Self {
            options,
            applied: Applied::default(),
            inverse: Vec::new(),
        }
    }

    /// Keep an operation as the engine records it. Kept only with `forward`.
    fn record(&mut self, operation: Operation) {
        if self.options.forward {
            self.applied.forward.push(operation);
        }
    }

    /// Record an operation that undoes part of the operation being applied.
    /// Kept only with `inverse`.
    fn record_inverse(&mut self, operation: Operation) {
        if self.options.inverse {
            self.inverse.push(operation);
        }
    }

    /// Whether removals keep copies of what they remove, for the inverses.
    fn copies(&self) -> Copies {
        if self.options.inverse {
            Copies::Keep
        } else {
            Copies::Discard
        }
    }

    /// End the operation being applied: its inverses are complete.
    fn end_operation(&mut self) {
        if self.options.inverse {
            self.applied.inverse.push(std::mem::take(&mut self.inverse));
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
        self.begin();
        let mut report = Report::new(options);
        for operation in operations {
            if let Err(error) = self.apply_operation(operation, &mut report) {
                self.rollback();
                return Err(error);
            }
        }
        let mut applied = report.applied;
        applied.changed_nodes = std::mem::take(&mut self.batch.changed_nodes)
            .into_iter()
            .collect();
        applied.changed_edges = std::mem::take(&mut self.batch.changed_edges)
            .into_iter()
            .collect();
        self.begin();
        Ok(applied)
    }

    fn apply_operation(&mut self, operation: Operation, report: &mut Report) -> Result<()> {
        match operation {
            Operation::AddNodes(nodes) => self.add_nodes(nodes, report)?,
            Operation::UpdateNodes(updates) => self.update_nodes(updates, report)?,
            Operation::DeleteNodes(ids) => self.delete_nodes(&ids, report)?,
            Operation::AddEdges(edges) => self.add_edges(edges, report)?,
            Operation::DeleteEdges(ids) => self.delete_edges(&ids, report),
        }
        report.end_operation();
        Ok(())
    }

    // --- Nodes -------------------------------------------------------------------------

    fn add_nodes(&mut self, nodes: Vec<Map<String, Value>>, report: &mut Report) -> Result<()> {
        if nodes.is_empty() {
            return Ok(());
        }
        let mut added = IndexSet::new();
        let mut payloads = Vec::new();
        for (index, node) in nodes.into_iter().enumerate() {
            let context = format!("add_nodes[{index}]");
            let Some(id) = node.non_empty_str("id").map(str::to_owned) else {
                bail!("{context}: node must have a non-empty string id");
            };
            if let Some(path) = missing_node_object(&node) {
                bail!("{context}: node {} must be an object", path.join("."));
            }
            if added.contains(&id) {
                bail!("add_nodes: duplicate node id in request: {}", quoted(&id));
            }
            if self.graph.nodes.contains_key(&id) {
                bail!("add_nodes: node id already exists: {}", quoted(&id));
            }
            added.insert(id.clone());
            if report.options.forward {
                payloads.push(node.clone());
            }
            self.insert_node(id, Value::Object(node));
        }
        report.record(Operation::AddNodes(payloads));
        report.record_inverse(Operation::DeleteNodes(added.into_iter().collect()));
        Ok(())
    }

    fn update_nodes(&mut self, updates: Vec<FieldUpdate>, report: &mut Report) -> Result<()> {
        if updates.is_empty() {
            return Ok(());
        }
        reject_repeated_paths(&updates, "update_nodes")?;
        let mut inverses = report.options.inverse.then(FieldInverses::default);
        let mut applied = Vec::new();
        let mut detached = IndexSet::new();
        for (index, mut update) in updates.into_iter().enumerate() {
            let context = format!("update_nodes[{index}]");
            if !self.graph.nodes.contains_key(&update.id) {
                bail!("update_nodes: node does not exist: {}", quoted(&update.id));
            }
            if !self.is_base_node(&update.id) {
                bail!(
                    "update_nodes: cannot update node that does not exist in the original flow: {}",
                    quoted(&update.id)
                );
            }
            check_node_path(&update.path, &format!("{context}.path"))?;
            let had_value =
                self.apply_field_update(&mut update, &context, report.options, inverses.as_mut())?;
            if !report.options.restoring {
                detached.extend(self.detached_edges(&update, had_value)?);
            }
            // A delete that found nothing is not recorded.
            if report.options.forward && (had_value || !update.is_delete()) {
                applied.push(update);
            }
        }
        if !applied.is_empty() {
            report.record(Operation::UpdateNodes(applied));
        }
        if let Some(inverses) = inverses {
            for operation in inverses.operations(Operation::UpdateNodes) {
                report.record_inverse(operation);
            }
        }
        self.remove_cascaded(detached.iter().map(String::as_str), report);
        Ok(())
    }

    /// The edges a write left without an end: into a removed template field,
    /// or from or into a removed output.
    fn detached_edges(
        &mut self,
        update: &FieldUpdate,
        had_value: bool,
    ) -> Result<IndexSet<String>> {
        let path = &update.path;
        if !had_value {
            return Ok(IndexSet::new());
        }
        let node_id = update.id.as_str();
        if update.is_delete()
            && path.len() == TEMPLATE_PATH.len() + 1
            && path.has_start(&TEMPLATE_PATH)
            && let Segment::Key(field) = &path[TEMPLATE_PATH.len()]
        {
            let input = Input {
                kind: InputKind::Field,
                name: field.clone(),
            };
            let connections = self.edge_index.connections(&self.graph, node_id)?;
            return Ok(connections.inputs.get(&input).cloned().unwrap_or_default());
        }
        if !path.has_start(&OUTPUTS_PATH) {
            return Ok(IndexSet::new());
        }
        let removed: Vec<String> = if path.len() == OUTPUTS_PATH.len() + 1 && update.is_delete() {
            path[OUTPUTS_PATH.len()]
                .as_item()
                .map(str::to_owned)
                .into_iter()
                .collect()
        } else if path.len() == OUTPUTS_PATH.len() {
            // The whole list was replaced or deleted: the outputs it no longer has are gone.
            let after: HashSet<String> = node_outputs(&self.graph, node_id)?
                .map(|outputs| outputs.names().map(str::to_owned).collect())
                .unwrap_or_default();
            let before = self.last_replaced().cloned().unwrap_or(Value::Null);
            let before = index_outputs(&before, node_id)?;
            before
                .names()
                .filter(|name| !after.contains(*name))
                .map(str::to_owned)
                .collect()
        } else {
            return Ok(IndexSet::new());
        };
        if removed.is_empty() {
            return Ok(IndexSet::new());
        }
        let connections = self.edge_index.connections(&self.graph, node_id)?;
        let mut detached = IndexSet::new();
        for name in removed {
            if let Some(ids) = connections.outputs.get(&name) {
                detached.extend(ids.iter().cloned());
            }
            let input = Input {
                kind: InputKind::LoopOutput,
                name,
            };
            if let Some(ids) = connections.inputs.get(&input) {
                detached.extend(ids.iter().cloned());
            }
        }
        Ok(detached)
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
            if !self.graph.nodes.contains_key(id) {
                continue;
            }
            incident.extend(self.graph.edges_at(id).cloned());
            if let Some(node) = self.remove_node(id, report.copies()) {
                removed_nodes.push(node);
            }
            removed.push(id.to_owned());
        }
        if removed.is_empty() {
            return Ok(());
        }
        report.record(Operation::DeleteNodes(removed));
        report.record_inverse(Operation::AddNodes(removed_nodes));
        self.remove_cascaded(incident.iter().map(String::as_str), report);
        Ok(())
    }

    /// Remove the edges an operation took with it, recording them as a `delete_edges`.
    fn remove_cascaded<'i>(&mut self, ids: impl IntoIterator<Item = &'i str>, report: &mut Report) {
        let (removed, edges) = self.remove_edges(ids, report.copies());
        if removed.is_empty() {
            return;
        }
        report.applied.deleted_edges.extend(removed.iter().cloned());
        report.record(Operation::DeleteEdges(removed));
        report.record_inverse(Operation::AddEdges(edges));
    }

    // --- Edges -------------------------------------------------------------------------

    fn add_edges(&mut self, edges: Vec<Map<String, Value>>, report: &mut Report) -> Result<()> {
        if edges.is_empty() {
            return Ok(());
        }
        let mut added = IndexSet::new();
        let mut payloads = Vec::new();
        for (index, edge) in edges.into_iter().enumerate() {
            let context = format!("add_edges[{index}]");
            let field = |key: &str| {
                edge.non_empty_str(key)
                    .map(str::to_owned)
                    .ok_or_else(|| invalid!("{context}: edge must have a non-empty string {key}"))
            };
            let (id, source, target) = (field("id")?, field("source")?, field("target")?);
            if added.contains(&id) {
                bail!("add_edges: duplicate edge id in request: {}", quoted(&id));
            }
            if self.graph.edges.contains_key(&id) {
                bail!("add_edges: edge id already exists: {}", quoted(&id));
            }
            if !self.graph.nodes.contains_key(&source) {
                bail!("add_edges: source node does not exist: {}", quoted(&source));
            }
            if !self.graph.nodes.contains_key(&target) {
                bail!("add_edges: target node does not exist: {}", quoted(&target));
            }
            added.insert(id.clone());
            if !report.options.restoring {
                check_edge(&self.graph, &mut self.edge_index, &edge)?;
            }
            if report.options.forward {
                payloads.push(edge.clone());
            }
            self.insert_edge(id, Value::Object(edge));
        }
        report.record(Operation::AddEdges(payloads));
        report.record_inverse(Operation::DeleteEdges(added.into_iter().collect()));
        Ok(())
    }

    fn delete_edges(&mut self, ids: &[String], report: &mut Report) {
        let (removed, edges) = self.remove_edges(ids.iter().map(String::as_str), report.copies());
        if removed.is_empty() {
            return;
        }
        report.record(Operation::DeleteEdges(removed));
        report.record_inverse(Operation::AddEdges(edges));
    }

    // --- Field writes ----------------------------------------------------------------------

    /// Apply one `set_field` or `delete_field` to a node.
    ///
    /// Returns whether the path held a value before the write. Without
    /// `forward`, a set's value moves into the graph instead of being copied.
    fn apply_field_update(
        &mut self,
        update: &mut FieldUpdate,
        context: &str,
        options: ApplyOptions,
        inverses: Option<&mut FieldInverses>,
    ) -> Result<bool> {
        let walk = self.check_field_update(&FieldWrite { update, context }, inverses)?;
        let value = match &mut update.change {
            Change::Set(value) if !options.forward => std::mem::take(value),
            Change::Set(value) => value.clone(),
            Change::Delete => Value::Null,
        };
        let write = FieldWrite { update, context };
        let had_value = self.write_last(&write, &walk, value)?;
        self.check_list_keys_kept(&write, &walk)?;
        Ok(had_value)
    }

    /// Check a field update before it writes anything: its path must exist
    /// up to the last segment. Record its inverse, and return its path as
    /// object keys and array indexes.
    fn check_field_update(
        &mut self,
        write: &FieldWrite<'_>,
        inverses: Option<&mut FieldInverses>,
    ) -> Result<Walk> {
        let walk = self.walk(write)?;
        if let Some(missing) = walk.missing_at {
            return Err(missing_segment(write, missing));
        }
        if let Some(inverses) = inverses {
            let last_step = self.read_last(write, &walk)?;
            let root = written(&self.graph, write);
            let parent = resolve(root, &walk.steps);
            let current = last_step
                .as_ref()
                .and_then(|step| resolve(parent?, std::slice::from_ref(step)));
            inverses.record(root, write.update, parent, current);
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

    /// Write or delete the last segment of the path. Returns whether it held a value.
    fn write_last(&mut self, write: &FieldWrite<'_>, walk: &Walk, value: Value) -> Result<bool> {
        let (id, path) = (write.update.id.as_str(), &write.update.path);
        let undo = match &path[path.len() - 1] {
            Segment::Key(key) => self.write_key(write, walk, key, value)?,
            Segment::Item(key) => self.write_item(write, walk, key, value)?,
        };
        let Some(undo) = undo else {
            return Ok(false);
        };
        let had_value = !matches!(
            undo,
            FieldUndo::KeySet { old: None, .. } | FieldUndo::ItemAdded
        );
        // A whole value replaced or removed takes the lists indexed under it with it.
        if let Some(keys) = path.to_list() {
            self.lists.forget_under(id, &keys);
        }
        self.record_field(id, walk.steps.clone(), undo);
        Ok(had_value)
    }

    /// The value that holds the path's last segment, to write it.
    fn parent_mut(&mut self, write: &FieldWrite<'_>, walk: &Walk) -> Option<&mut Value> {
        self.graph
            .nodes
            .get_mut(&write.update.id)
            .and_then(|node| resolve_mut(node, &walk.steps))
    }

    /// Write or delete an object key. Returns how to undo it, or `None` for a
    /// delete that found nothing.
    fn write_key(
        &mut self,
        write: &FieldWrite<'_>,
        walk: &Walk,
        key: &str,
        value: Value,
    ) -> Result<Option<FieldUndo>> {
        let (update, context) = (write.update, write.context);
        let Some(Value::Object(map)) = self.parent_mut(write, walk) else {
            bail!("{context}: path must end at an object property or a keyed list item");
        };
        if update.is_delete() {
            let Some(index) = map.keys().position(|existing| existing == key) else {
                return Ok(None);
            };
            let old = map.shift_remove(key).expect("the key was found just above");
            return Ok(Some(FieldUndo::KeyDeleted {
                key: key.to_owned(),
                index,
                old,
            }));
        }
        let old = map.insert(key.to_owned(), value);
        Ok(Some(FieldUndo::KeySet {
            key: key.to_owned(),
            old,
        }))
    }

    /// Write or delete a keyed list item. Returns how to undo it, or `None`
    /// for a delete that found nothing.
    fn write_item(
        &mut self,
        write: &FieldWrite<'_>,
        walk: &Walk,
        key: &str,
        value: Value,
    ) -> Result<Option<FieldUndo>> {
        let (update, context) = (write.update, write.context);
        let path = &update.path;
        let last = path.len() - 1;
        let (keyed, prefix) = {
            let root = written(&self.graph, write);
            let parent = resolve(root, &walk.steps).expect("the walk resolved these steps");
            keyed_list(root, path, last, parent, context)?
        };
        let list_context = format!("{context}.path[{last}]");
        let parent = self
            .graph
            .nodes
            .get_mut(&update.id)
            .and_then(|node| resolve_mut(node, &walk.steps));
        let Some(Value::Array(items)) = parent else {
            bail!("{list_context}: list item key on a value that is not a list");
        };
        let index = self
            .lists
            .index(&update.id, &prefix, keyed, items, &list_context)?;
        if update.is_delete() {
            return Ok(index
                .remove(items, key)
                .map(|(old, removal)| FieldUndo::ItemRemoved { removal, old }));
        }
        let slot = index.slot(key);
        if keyed.key_of(&value) != Some(key) {
            bail!(
                "{context}: a list item written at its key must carry the same key: {}",
                quoted(key)
            );
        }
        if let Some(slot) = slot {
            let old = index.replace(items, slot, value, context)?;
            return Ok(Some(FieldUndo::ItemReplaced { slot, old }));
        }
        index.add(items, value, context)?;
        Ok(Some(FieldUndo::ItemAdded))
    }
}

/// The node a field write goes to. `update_nodes` checks that it exists
/// before it writes.
fn written<'g>(graph: &'g Graph, write: &FieldWrite<'_>) -> &'g Value {
    graph
        .nodes
        .get(&write.update.id)
        .expect("update_nodes checks that the node exists")
}

/// One field update on its way into a node.
#[derive(Debug)]
struct FieldWrite<'w> {
    update: &'w FieldUpdate,
    /// Where the update is in its operation, for messages.
    context: &'w str,
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
            &format!("{context}.path[{index}]"),
        )?
        .slot(key);
    Ok((keyed, slot))
}

/// The keyed list whose item `path[index]` names, and its address: the
/// object keys that lead to it. Checks that the list is keyed.
fn keyed_list<'p>(
    node: &Value,
    path: &'p Path,
    index: usize,
    value: &Value,
    context: &str,
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

fn check_node_path(path: &Path, context: &str) -> Result<()> {
    if path[0].as_key() == Some("id") {
        bail!("{context}: cannot modify node identity");
    }
    // Every node keeps these objects, and operations patch inside them.
    let forbidden = NODE_OBJECT_PATHS
        .iter()
        .any(|object_path| path.equals(object_path));
    if forbidden {
        bail!(
            "{context}: cannot update entire node data objects at path {}; forbidden paths are: data, data.node, data.node.template",
            path_label(path)
        );
    }
    Ok(())
}

/// Refuse an update batch that writes one path of one node or edge twice.
fn reject_repeated_paths(updates: &[FieldUpdate], kind: &str) -> Result<()> {
    let mut seen = HashSet::new();
    for update in updates {
        if !seen.insert((update.id.as_str(), update.path.as_slice())) {
            bail!(
                "{kind}: multiple field updates for one id and path: {} {}",
                quoted(&update.id),
                path_label(&update.path)
            );
        }
    }
    Ok(())
}

// --- Inverses of field writes --------------------------------------------------------------

/// The writes that undo an update batch, read from the state each write
/// replaces. They are undone last first; a path written twice is split into
/// separate operations, since one operation may write a path once.
#[derive(Debug, Default)]
struct FieldInverses {
    entries: Vec<FieldUpdate>,
}

impl FieldInverses {
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
                self.entries.push(FieldUpdate::set(
                    &update.id,
                    path[..last].to_vec(),
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
        let mut written: HashSet<(String, Path)> = HashSet::new();
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
