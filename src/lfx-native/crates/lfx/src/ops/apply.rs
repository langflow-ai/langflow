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

use std::borrow::Cow;
use std::collections::HashSet;
use std::fmt;
use std::str::FromStr;

use crate::value::Value;
use indexmap::IndexSet;

use crate::ops::canonical::is_row_position;
use crate::ops::edges::{GraphRead, check_edge, reads_before, removed_endpoints};
use crate::ops::error::{Error, Result, bail, invalid, quoted};
use crate::ops::fields::{self, FieldWrite};
use crate::ops::keyed::{ListIndex, check_position};
use crate::ops::ops::{Change, Edge, FieldUpdate, Node, NodePath, Operation, PathExt, Segment};
use crate::ops::schema::{KeyedList, ListKind, NODE_SCHEMA};
use crate::ops::state::{Graph, GraphState, field_value};

/// How a batch is applied.
#[derive(Debug, Clone, Copy, Default)]
pub struct ApplyOptions {
    /// Return the forward operations.
    pub forward: bool,
    /// Return, for each operation, its backward operations.
    pub backward: bool,
    /// Which rules the batch must pass.
    pub mode: Mode,
}

/// Which rules a batch must pass.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum Mode {
    /// Every rule. A batch that will be saved is always strict.
    #[default]
    Strict,
    /// Apply backward operations to show an earlier revision of the flow, as
    /// the editor's history preview does. They put back a state the flow
    /// already had, whatever rules it broke, and they add and delete every
    /// edge they touch explicitly. So the edge rules, and the cascade delete
    /// of a removed field or output, are both skipped. Never use this for a
    /// batch that will be saved.
    Preview,
}

impl FromStr for Mode {
    type Err = Error;

    /// The mode that `name` names: `strict` or `preview`.
    fn from_str(name: &str) -> Result<Self> {
        match name {
            "strict" => Ok(Self::Strict),
            "preview" => Ok(Self::Preview),
            _ => bail!("unknown apply mode: {}", quoted(name)),
        }
    }
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
    ///   apply them in [`Mode::Preview`]. The flow goes back to a state it already
    ///   had, so the engine skips its edge rules.
    /// - To undo an edit with a new edit, put the lists into one batch, in that
    ///   order, and apply it in [`Mode::Strict`]. The new edit is saved like any
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
        // A batch that panicked, which a binding turns into an exception,
        // left its layers behind. The graph itself is as it was before it.
        self.discard();
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
            if self.graph.has_node(node.id()) {
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
            if !self.graph.has_node(&update.id) {
                bail!("update_nodes: node does not exist: {}", quoted(&update.id));
            }
            if !self.is_base_node(&update.id) {
                bail!(
                    "update_nodes: cannot update node that does not exist in the original flow: {}",
                    quoted(&update.id)
                );
            }
            let before =
                self.apply_field_update(&mut update, context, report.options, backward.as_mut())?;
            if report.options.mode == Mode::Strict
                && let Before::Value(value) = &before
            {
                cascaded.extend(self.edges_at_removed(&update, value.as_ref())?);
            }
            // A delete that found nothing is not recorded.
            let found = matches!(before, Before::Value(_));
            if report.options.forward && (found || !update.is_delete()) {
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
    /// go with them. `before` is what the path held before the write, when
    /// [`removed_endpoints`] reads it.
    fn edges_at_removed(
        &mut self,
        update: &FieldUpdate,
        before: Option<&Value>,
    ) -> Result<IndexSet<String>> {
        let node_id = update.id.as_str();
        let graph = &self.graph;
        let removed = removed_endpoints(
            &update.path,
            update.is_delete(),
            before,
            |keys| graph.node_value(node_id, keys),
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
            if !self.graph.has_node(id) {
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
            if self.graph.has_edge(edge.id()) {
                bail!("add_edges: edge id already exists: {}", quoted(edge.id()));
            }
            if !self.graph.has_node(edge.source()) {
                bail!(
                    "add_edges: source node does not exist: {}",
                    quoted(edge.source())
                );
            }
            if !self.graph.has_node(edge.target()) {
                bail!(
                    "add_edges: target node does not exist: {}",
                    quoted(edge.target())
                );
            }
            if report.options.mode == Mode::Strict {
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
            if !seen.insert(id) || !self.graph.has_edge(id) {
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

    /// Apply one `set_field` or `delete_field` to a node, through the batch's
    /// field layer.
    ///
    /// Returns what the path held before the write. Without `forward`, a
    /// set's value moves into the layer instead of being copied.
    fn apply_field_update(
        &mut self,
        update: &mut FieldUpdate,
        context: UpdatePlace,
        options: ApplyOptions,
        backward: Option<&mut FieldBackward>,
    ) -> Result<Before> {
        let placed = PlacedUpdate { update, context };
        self.copy_natural_list(&placed)?;
        let walk = self.walk(&placed)?;
        if let Some(missing) = walk.missing_at {
            return Err(missing_segment(&placed, missing));
        }
        let (id, path) = (placed.update.id.as_str(), &placed.update.path);
        if let Some(backward) = backward {
            let current = field_value(&self.graph, &mut self.lists, id, path, &context)?;
            let natural = match walk.last_list {
                Some(keyed) if placed.update.is_delete() && keyed.kind == ListKind::Natural => {
                    field_value(
                        &self.graph,
                        &mut self.lists,
                        id,
                        &path[..path.len() - 1],
                        &context,
                    )?
                }
                _ => None,
            };
            let items = natural.as_deref().and_then(Value::as_array);
            backward.record(placed.update, current.as_deref(), items.map(Vec::as_slice));
        }
        let before = if walk.exists && options.mode == Mode::Strict && reads_before(path) {
            field_value(&self.graph, &mut self.lists, id, path, &context)?.map(Cow::into_owned)
        } else {
            None
        };
        let value = match &mut update.change {
            Change::Set(value) if !options.forward => std::mem::take(value),
            Change::Set(value) => value.clone(),
            Change::Delete => Value::Null,
        };
        let placed = PlacedUpdate { update, context };
        self.write_last(&placed, &walk, value)?;
        self.check_list_keys_kept(&placed, &walk)?;
        Ok(if walk.exists {
            Before::Value(before)
        } else {
            Before::Nothing
        })
    }

    /// Check that a write inside a keyed list item left the item's key alone,
    /// and a table row its position.
    fn check_list_keys_kept(&mut self, placed: &PlacedUpdate<'_>, walk: &Walk) -> Result<()> {
        let (id, path, context) = (
            placed.update.id.as_str(),
            &placed.update.path,
            placed.context,
        );
        for item in walk.list_items.iter().rev() {
            let item_path = &path[..=item.segment];
            let value = field_value(&self.graph, &mut self.lists, id, item_path, &context)?;
            let value = value.as_deref();
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

    /// Follow the write's path through the batch's field layer
    /// ([`Graph::walk_field`]), and read what it holds, before anything is
    /// written.
    ///
    /// The value that holds the last segment is inside an entry at an
    /// ancestor (anc.) path of the write's path, or else in the node. A
    /// segment that does not fit the value it reads, such as a key of a list,
    /// is an error rather than a missing value.
    fn walk(&mut self, placed: &PlacedUpdate<'_>) -> Result<Walk> {
        let (id, path, context) = (
            placed.update.id.as_str(),
            &placed.update.path,
            placed.context,
        );
        let last = path.len() - 1;
        let (graph, lists) = (&self.graph, &mut self.lists);
        let stored = graph.is_stored_node(id);
        let mut list_items = Vec::new();
        let mut last_list = None;
        let mut step = fields::step_fn(|value, index, in_entry| match &path[index] {
            Segment::Key(key) => {
                let Value::Object(map) = value else {
                    bail!(
                        "{context}.path[{index}]: {} reads a key of a value that is not an object",
                        quoted(key)
                    );
                };
                Ok(map.get(key))
            }
            Segment::Item(key) => {
                let (keyed, list_path) = keyed_list(graph, placed, index, value)?;
                let items = value.as_array().map(Vec::as_slice).unwrap_or_default();
                // A stored node's lists keep their index between reads. A list
                // inside an entry, or in a node the batch added, is checked again
                // at each read, as building an index checks it.
                let list_context = context.segment(index);
                let slot = if stored && !in_entry {
                    lists
                        .index(id, &list_path, keyed, items, &list_context)?
                        .slot(key)
                } else {
                    ListIndex::build(keyed, items, &list_context)?.slot(key)
                };
                if index == last {
                    last_list = Some(keyed);
                } else {
                    list_items.push(ListItemOnPath {
                        keyed,
                        key: key.clone(),
                        segment: index,
                    });
                }
                Ok(slot.map(|slot| &items[slot]))
            }
        });
        let walked = graph
            .walk_field(id, &path[..last], &mut step)?
            .expect("update_nodes checks that the node exists");
        let Ok(parent) = walked.found else {
            return Ok(Walk {
                write_len: walked.write_len,
                list_items,
                last_list,
                found: false,
                exists: false,
                missing_at: walked.found.err(),
            });
        };
        let found = step(parent, last, walked.write_len.is_some())?.is_some();
        // The item that a write on the way sits at was checked when it was written.
        if let Some(len) = walked.write_len
            && let Segment::Item(key) = &path[len - 1]
        {
            list_items.push(ListItemOnPath {
                keyed: NODE_SCHEMA.listed_at(&path[..len - 1]),
                key: key.clone(),
                segment: len - 1,
            });
            list_items.sort_by_key(|item| item.segment);
        }
        let write_at_path = walked
            .writes
            .and_then(|writes| writes.child_write(&path[last]));
        let exists = match (walked.write_len, write_at_path) {
            (None, Some(write)) => matches!(write, FieldWrite::Set(_)),
            _ => found,
        };
        Ok(Walk {
            write_len: walked.write_len,
            list_items,
            last_list,
            found,
            exists,
            missing_at: None,
        })
    }

    /// Write or delete the last segment of the path: in the value of the
    /// write on the way, or as the write at the path itself.
    fn write_last(&mut self, placed: &PlacedUpdate<'_>, walk: &Walk, value: Value) -> Result<()> {
        let (update, context) = (placed.update, placed.context);
        let (id, path) = (update.id.as_str(), &update.path);
        let last = path.len() - 1;
        if let (Segment::Item(key), false) = (&path[last], update.is_delete()) {
            let keyed = walk.last_list.expect("the walk read the last item's list");
            if keyed.key_of(&value) != Some(key) {
                bail!(
                    "{context}: a list item written at its key must carry the same key: {}",
                    quoted(key)
                );
            }
            check_position(keyed, &value, &context.segment(last))?;
        }
        if update.is_delete() && !walk.exists {
            // A delete that finds nothing writes nothing.
            return Ok(());
        }
        let write = if update.is_delete() {
            FieldWrite::Remove
        } else {
            FieldWrite::Set(value)
        };
        let writes = self.graph.writes_mut(id);
        if let Some(len) = walk.write_len {
            let (_, on_path) = writes
                .write_on_path_mut(&path[..last])
                .expect("the walk found the write on the way");
            let FieldWrite::Set(set) = on_path else {
                unreachable!("the walk found the parent in a set's value")
            };
            let parent = fields::descend_mut(set, &path[..last], len)
                .expect("the walk found the parent in the write");
            fields::make_write(parent, &path[last], &path[..last], write, None);
        } else if matches!(write, FieldWrite::Remove) && !walk.found {
            // The value is only the batch's own write at the path.
            writes.drop_write(path);
        } else {
            writes.set(path, write);
        }
        Ok(())
    }

    /// A write to an item of a natural list, or inside one, is made in a copy
    /// of the whole list, so the list keeps its order. Put that copy as the
    /// write at the list, unless a write on the way already holds the list.
    fn copy_natural_list(&mut self, placed: &PlacedUpdate<'_>) -> Result<()> {
        let (id, path) = (placed.update.id.as_str(), &placed.update.path);
        let Some(item) = (0..path.len()).find(|&index| {
            matches!(path[index], Segment::Item(_))
                && NODE_SCHEMA.natural_list_at(&path[..index]).is_some()
        }) else {
            return Ok(());
        };
        let list_path = &path[..item];
        let step = |value, index: usize, _| {
            Ok(fields::child(value, &list_path[..index], &list_path[index]))
        };
        let walked = self
            .graph
            .walk_field(id, list_path, step)?
            .expect("update_nodes checks that the node exists");
        // A missing list or one that is not a list is the write's own error.
        let (None, Ok(list @ Value::Array(_))) = (walked.write_len, walked.found) else {
            return Ok(());
        };
        let list = list.clone();
        self.graph
            .writes_mut(id)
            .set(list_path, FieldWrite::Set(list));
        Ok(())
    }
}

/// What a field write's path held before the write.
#[derive(Debug)]
enum Before {
    /// Nothing: the write added a value, or a delete found nothing.
    Nothing,
    /// A value. It is kept only for a cascade delete that reads it
    /// ([`reads_before`]).
    Value(Option<Value>),
}

/// A field update, with its place in its `update_nodes` for error messages.
#[derive(Debug)]
struct PlacedUpdate<'w> {
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

/// Where a field update's path leads through the batch's field layer, and what it holds.
#[derive(Debug, Default)]
struct Walk {
    /// The length of the path of the write on the way that holds the value
    /// with the last segment: a write at an ancestor path of the write's
    /// path. `None` when the node itself holds that value.
    write_len: Option<usize>,
    /// The keyed list items the path passes through, before its last segment.
    list_items: Vec<ListItemOnPath>,
    /// The keyed list whose item the last segment names, if it names one.
    last_list: Option<&'static KeyedList>,
    /// Whether the value that holds the last segment has it: inside the
    /// entry, or in the node itself when no entry holds that value.
    found: bool,
    /// Whether the path holds a value as the batch sees it: [`Self::found`],
    /// unless an entry at the path itself says otherwise.
    exists: bool,
    /// The index of the first segment that does not exist.
    missing_at: Option<usize>,
}

/// A keyed list item a path passes through.
#[derive(Debug)]
struct ListItemOnPath {
    keyed: &'static KeyedList,
    key: String,
    /// The index of the path segment that names the item.
    segment: usize,
}

/// The error for the first segment of a path that does not exist.
fn missing_segment(placed: &PlacedUpdate<'_>, missing: usize) -> Error {
    let context = placed.context;
    match &placed.update.path[missing] {
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

/// The keyed list whose item `path[index]` names, and its path as object
/// keys. The schema decides whether a template field's value is a table from
/// the field's keys, read through the batch's writes. Checks that the list
/// is keyed and that `value`, what the path holds there, is a list.
fn keyed_list<'p>(
    graph: &Graph,
    placed: &PlacedUpdate<'p>,
    index: usize,
    value: &Value,
) -> Result<(&'static KeyedList, Vec<&'p str>)> {
    let (id, path, context) = (
        placed.update.id.as_str(),
        &placed.update.path,
        placed.context,
    );
    let list_path = path[..index].to_list();
    let keyed = list_path.as_ref().and_then(|list_path| {
        NODE_SCHEMA.keyed_list_by(list_path, |field_path, key| {
            let mut keys = field_path.to_vec();
            keys.push(key);
            graph.node_value(id, &keys)
        })
    });
    let (Some(keyed), Some(list_path)) = (keyed, list_path) else {
        bail!(
            "{context}.path[{index}]: list item key on a list the node schema does not declare keyed"
        );
    };
    if !value.is_array() {
        bail!("{context}.path[{index}]: list item key on a value that is not a list");
    }
    Ok((keyed, list_path))
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
    /// `current` is what the path holds. `natural_items` is the natural list
    /// that a delete of one of its items removes it from.
    fn record(
        &mut self,
        update: &FieldUpdate,
        current: Option<&Value>,
        natural_items: Option<&[Value]>,
    ) {
        let path = &update.path;
        let last = path.len() - 1;
        if let (Segment::Item(key), Some(items), Some(_)) = (&path[last], natural_items, current) {
            // Removing a natural-list item that is not last cannot be undone by
            // a write at the item's key, which appends; the whole list is written back.
            // A table's order is its rows' positions, so its rows need no such care.
            let keyed = NODE_SCHEMA.listed_at(&path[..last]);
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
                    Value::Array(items.to_vec()),
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
    use crate::json;
    use crate::value::Value;

    use super::*;
    use crate::ops::edges::escape_handle;
    use crate::ops::schema::OUTPUTS_PATH;

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

    fn set(id: &str, path: Value, value: Value) -> Value {
        let mut update = json!({"id": id, "op": "set_field"});
        update["path"] = path;
        update["value"] = value;
        update
    }

    fn delete(id: &str, path: Value) -> Value {
        let mut update = json!({"id": id, "op": "delete_field"});
        update["path"] = path;
        update
    }

    fn updates(updates: Vec<Value>) -> Vec<Operation> {
        let mut operation = json!({"type": "update_nodes"});
        operation["updates"] = Value::Array(updates);
        operations(Value::Array(vec![operation]))
    }

    fn table_node() -> Value {
        let row = |id: &str, pos: u32| json!({"__id__": id, "__pos__": pos, "v": "x"});
        json!({"id": "t", "data": {"node": {"template": {
            "rows": {"type": "table", "value": [row("r1", 1), row("r2", 2), row("r3", 3)]},
            "text": {"type": "str", "value": ""},
        }}}})
    }

    fn rows_path(key: Option<&str>) -> Value {
        let mut path = json!(["data", "node", "template", "rows", "value"]);
        if let Some(key) = key {
            path.as_array_mut().unwrap().push(json!({"key": key}));
        }
        path
    }

    fn cell_path(key: &str) -> Value {
        let mut path = rows_path(Some(key));
        path.as_array_mut().unwrap().push(json!("v"));
        path
    }

    /// Each batch applied to one graph state kept between batches gives what
    /// it gives on a graph loaded fresh.
    fn same_as_fresh(state: &mut GraphState, batch: Vec<Operation>) -> Result<()> {
        let fresh = apply_flow_operations(state.to_value(), batch.clone(), ApplyOptions::default());
        let kept = state.apply(batch, ApplyOptions::default());
        match (fresh, kept) {
            (Ok((graph, _)), Ok(_)) => {
                assert!(crate::ops::canonical::graphs_equal(&state.to_value(), &graph).unwrap());
                Ok(())
            }
            (Err(_), Err(error)) => Err(error),
            (fresh, kept) => panic!("fresh {fresh:?}, kept {kept:?}"),
        }
    }

    #[test]
    fn a_held_table_keeps_its_index_through_writes_and_refused_batches() {
        let mut state = GraphState::new(json!({"nodes": [table_node()], "edges": []})).unwrap();
        let row = |id: &str, pos: f64| json!({"__id__": id, "__pos__": pos, "v": "n"});
        same_as_fresh(
            &mut state,
            updates(vec![set("t", cell_path("r2"), json!("y"))]),
        )
        .unwrap();
        same_as_fresh(
            &mut state,
            updates(vec![delete("t", rows_path(Some("r1")))]),
        )
        .unwrap();
        // Refused after a row is added and a cell written: nothing changes.
        let before = state.to_value();
        let refused = updates(vec![
            set("t", rows_path(Some("r4")), row("r4", 4.0)),
            set("t", cell_path("r3"), json!("z")),
            set("t", cell_path("gone"), json!("z")),
        ]);
        same_as_fresh(&mut state, refused).unwrap_err();
        assert_eq!(state.to_value(), before);
        same_as_fresh(
            &mut state,
            updates(vec![
                set("t", rows_path(Some("r5")), row("r5", 0.5)),
                set("t", cell_path("r5"), json!("w")),
                delete("t", rows_path(Some("r2"))),
                set("t", cell_path("r3"), json!("v3")),
            ]),
        )
        .unwrap();
        same_as_fresh(
            &mut state,
            updates(vec![set("t", cell_path("r5"), json!("again"))]),
        )
        .unwrap();
        let rows = &state.to_value()["nodes"][0]["data"]["node"]["template"]["rows"]["value"];
        let mut cells: Vec<(String, String)> = rows
            .as_array()
            .unwrap()
            .iter()
            .map(|row| {
                (
                    row["__id__"].as_str().unwrap().into(),
                    row["v"].as_str().unwrap().into(),
                )
            })
            .collect();
        cells.sort();
        assert_eq!(
            cells,
            [("r3".into(), "v3".into()), ("r5".into(), "again".into())]
        );
    }

    #[test]
    fn a_field_type_written_in_the_batch_decides_whether_its_value_is_a_table() {
        let node = json!({"id": "t", "data": {"node": {"template": {
            "rows": {"type": "str", "value": [{"__id__": "r1", "__pos__": 1}]},
        }}}});
        let graph = json!({"nodes": [node], "edges": []});
        let row = json!({"__id__": "r2", "__pos__": 2});
        let refused = updates(vec![set("t", rows_path(Some("r2")), row.clone())]);
        let error =
            apply_flow_operations(graph.clone(), refused, ApplyOptions::default()).unwrap_err();
        assert!(
            error.message.contains("does not declare keyed"),
            "{}",
            error.message
        );
        let typed = updates(vec![
            set(
                "t",
                json!(["data", "node", "template", "rows", "type"]),
                json!("table"),
            ),
            set("t", rows_path(Some("r2")), row),
        ]);
        let (graph, _) = apply_flow_operations(graph, typed, ApplyOptions::default()).unwrap();
        assert_eq!(
            graph["nodes"][0]["data"]["node"]["template"]["rows"]["value"]
                .as_array()
                .unwrap()
                .len(),
            2
        );
    }

    #[test]
    fn a_list_written_in_the_batch_is_checked_when_a_write_reads_its_items() {
        let graph = json!({"nodes": [table_node()], "edges": []});
        let update = |update: Value| json!({"type": "update_nodes", "updates": [update]});
        let batch = operations(json!([
            update(set("t", rows_path(None), json!([1, 2]))),
            update(delete("t", rows_path(Some("r1")))),
        ]));
        let error = apply_flow_operations(graph, batch, ApplyOptions::default()).unwrap_err();
        assert!(
            error.message.contains("non-empty string key"),
            "{}",
            error.message
        );
    }

    #[test]
    fn an_output_removed_and_added_again_in_one_batch_goes_last() {
        let output = |name: &str| json!({"name": name});
        let node = json!({"id": "n", "data": {"node": {"template": {},
            "outputs": [output("a"), output("b"), output("c")]}}});
        let outputs = |key: &str| json!(["data", "node", "outputs", {"key": key}]);
        let update = |update: Value| json!({"type": "update_nodes", "updates": [update]});
        let batch = operations(json!([
            update(delete("n", outputs("a"))),
            update(set("n", outputs("d"), output("d"))),
            update(set("n", outputs("a"), output("a"))),
        ]));
        let mut state = GraphState::new(json!({"nodes": [node], "edges": []})).unwrap();
        state.apply(batch, ApplyOptions::default()).unwrap();
        let outputs = state.graph.node_value("n", &OUTPUTS_PATH).unwrap();
        let names: Vec<&str> = outputs
            .as_array()
            .unwrap()
            .iter()
            .map(|output| output["name"].as_str().unwrap())
            .collect();
        assert_eq!(names, ["b", "c", "d", "a"]);
    }

    #[test]
    fn a_node_deleted_and_added_again_takes_the_writes_after_it() {
        let node = json!({"id": "n", "data": {"node": {"template": {"f": {"value": 1}}}}});
        let batch = json!([
            {"type": "delete_nodes", "ids": ["n"]},
            {"type": "add_nodes", "nodes": [{"id": "n", "data": {"node": {"template": {"g": {"value": 2}}}}}]},
            {"type": "update_nodes", "updates": [set("n", json!(["data", "node", "template", "g", "value"]), json!(3))]},
        ]);
        let (graph, _) = apply_flow_operations(
            json!({"nodes": [node], "edges": []}),
            operations(batch),
            ApplyOptions::default(),
        )
        .unwrap();
        assert_eq!(
            graph["nodes"][0]["data"]["node"]["template"],
            json!({"g": {"value": 3}})
        );
    }

    #[test]
    fn an_edge_rule_reads_a_field_written_in_the_batch() {
        let field = json!({"type": "str", "value": ""});
        let graph = json!({
            "nodes": [
                {"id": "S", "data": {"node": {"template": {}, "outputs": [{"name": "out"}]}}},
                {"id": "T", "data": {"node": {"template": {"A": field}}}},
            ],
            "edges": [edge("e1", "A")],
        });
        let second = json!({"type": "add_edges", "edges": [edge("e2", "A")]});
        let error = apply_flow_operations(
            graph.clone(),
            operations(json!([second])),
            ApplyOptions::default(),
        )
        .unwrap_err();
        assert_eq!(
            error.code,
            crate::ops::error::ErrorCode::Violation(
                crate::ops::validate::ViolationCode::EdgeTargetOccupied
            ),
            "{error}"
        );
        let list = set(
            "T",
            json!(["data", "node", "template", "A", "list"]),
            json!(true),
        );
        let batch = json!([{"type": "update_nodes", "updates": [list]}, second]);
        apply_flow_operations(graph, operations(batch), ApplyOptions::default()).unwrap();
    }

    #[test]
    fn a_write_over_earlier_writes_undoes_to_the_graph_before_the_batch() {
        let graph = json!({"nodes": [table_node()], "edges": []});
        let field = json!(["data", "node", "template", "rows"]);
        let batch = updates(vec![
            set("t", cell_path("r1"), json!("y")),
            delete("t", rows_path(Some("r2"))),
            set("t", field, json!({"type": "str", "value": "flat"})),
        ]);
        let mut state = GraphState::new(graph.clone()).unwrap();
        let options = ApplyOptions {
            backward: true,
            ..ApplyOptions::default()
        };
        let applied = state.apply(batch, options).unwrap();
        let preview = ApplyOptions {
            mode: Mode::Preview,
            ..ApplyOptions::default()
        };
        for list in applied.backward.into_iter().rev() {
            state.apply(list, preview).unwrap();
        }
        assert!(crate::ops::canonical::graphs_equal(&state.to_value(), &graph).unwrap());
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
