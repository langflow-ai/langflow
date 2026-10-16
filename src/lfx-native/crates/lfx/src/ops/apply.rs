//! Applying operations to a flow graph.
//!
//! A batch applies in order, and all of it or none of it: on an error the
//! state is as it was before the batch. Each operation is normalized as it
//! applies: a delete that finds nothing is not recorded, and the edges a
//! delete takes with it are recorded as a `delete_edges` of their own.
//!
//! With `inverse`, apply also returns, for each operation, the operations
//! that undo it, read from the state each write replaces. History playback
//! keeps those instead of a graph per revision. Inverses are applied with
//! `restoring`, last operation first.

use std::collections::HashSet;

use indexmap::{IndexMap, IndexSet};
use serde_json::{Map, Value};

use crate::ops::canonical::{is_row_position, json_type, values_equal};
use crate::ops::edges::{
    Input, InputKind, OUTPUTS_PATH, check_edge, handle_forms, index_outputs, node_outputs,
};
use crate::ops::error::{Error, ErrorCode, Result, quoted};
use crate::ops::ops::{Change, Expect, FieldUpdate, Operation, Path, Segment, path_label};
use crate::ops::schema::{KeyedList, ListKind, NODE_SCHEMA};
use crate::ops::state::{FieldUndo, FlowState, Owner, Step, resolve, resolve_mut};
use crate::ops::validate::missing_node_object;

/// How a batch is applied.
#[derive(Debug, Clone, Copy, Default)]
#[expect(clippy::struct_excessive_bools, reason = "four independent switches")]
pub struct ApplyOptions {
    /// Return the operations as the engine normalized them.
    pub forward: bool,
    /// Return, for each operation, the operations that undo it.
    pub inverse: bool,
    /// Apply inverses. Inverses put back a state the history already held,
    /// whatever rules it broke, and they add and delete every edge they touch
    /// explicitly. So the edge rules, and the edges a removed field or output
    /// would take with it, are both skipped. Never set this when applying
    /// operations that will be stored.
    pub restoring: bool,
    /// Skip the `from_type` checks. History readers get secret values
    /// redacted to null, so in a redacted graph a value's JSON type says
    /// nothing. Never set this when applying operations that will be stored.
    pub redacted: bool,
}

/// What a batch did.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Applied {
    /// The operations as the engine normalized them, with `forward`.
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

/// The node paths a write may not replace whole: every node keeps its
/// `data`, `data.node` and `data.node.template` objects, and operations patch
/// inside them.
const FORBIDDEN_NODE_PATHS: [&[&str]; 3] =
    [&["data"], &["data", "node"], &["data", "node", "template"]];
/// An edge's endpoints are its identity: connecting other nodes is another edge.
const FORBIDDEN_EDGE_ROOTS: [&str; 3] = ["id", "source", "target"];
/// Writes under these edge keys can change which output or input the edge connects.
const EDGE_HANDLE_ROOTS: [&str; 3] = ["sourceHandle", "targetHandle", "data"];
const TEMPLATE_PATH: [&str; 3] = ["data", "node", "template"];

impl FlowState {
    /// Apply a batch of operations in order. On an error nothing is applied.
    ///
    /// # Errors
    ///
    /// An operation is invalid for the graph, or an expectation fails.
    pub fn apply(&mut self, operations: Vec<Operation>, options: ApplyOptions) -> Result<Applied> {
        self.begin();
        let mut applied = Applied::default();
        for operation in operations {
            if let Err(error) = self.apply_operation(operation, options, &mut applied) {
                self.rollback();
                return Err(error);
            }
        }
        applied.changed_nodes = std::mem::take(&mut self.batch.changed_nodes)
            .into_iter()
            .collect();
        applied.changed_edges = std::mem::take(&mut self.batch.changed_edges)
            .into_iter()
            .collect();
        self.begin();
        Ok(applied)
    }

    fn apply_operation(
        &mut self,
        operation: Operation,
        options: ApplyOptions,
        out: &mut Applied,
    ) -> Result<()> {
        let mut inverse = Vec::new();
        match operation {
            Operation::AddNodes(nodes) => self.add_nodes(nodes, options, out, &mut inverse)?,
            Operation::UpdateNodes(updates) => {
                self.update_nodes(updates, options, out, &mut inverse)?;
            }
            Operation::DeleteNodes(ids) => self.delete_nodes(&ids, options, out, &mut inverse)?,
            Operation::AddEdges(edges) => self.add_edges(edges, options, out, &mut inverse)?,
            Operation::UpdateEdges(updates) => {
                self.update_edges(updates, options, out, &mut inverse)?;
            }
            Operation::DeleteEdges(ids) => self.delete_edges(&ids, options, out, &mut inverse),
            Operation::UpdateMetadata {
                fields,
                delete_keys,
            } => {
                self.update_metadata(fields, &delete_keys, options, out, &mut inverse)?;
            }
        }
        if options.inverse {
            out.inverse.push(inverse);
        }
        Ok(())
    }

    // --- Nodes -------------------------------------------------------------------------

    fn add_nodes(
        &mut self,
        nodes: Vec<Map<String, Value>>,
        options: ApplyOptions,
        out: &mut Applied,
        inverse: &mut Vec<Operation>,
    ) -> Result<()> {
        if nodes.is_empty() {
            return Ok(());
        }
        let mut seen = IndexSet::new();
        let mut payloads = Vec::new();
        for (index, node) in nodes.into_iter().enumerate() {
            let context = format!("add_nodes[{index}]");
            let Some(id) = non_empty_id(&node, "id") else {
                return Err(Error::invalid(format!(
                    "{context}: node must have a non-empty string id"
                )));
            };
            if let Some(path) = missing_node_object(&node) {
                return Err(Error::invalid(format!(
                    "{context}: node {} must be an object",
                    path.join(".")
                )));
            }
            if seen.contains(&id) {
                return Err(Error::invalid(format!(
                    "add_nodes: duplicate node id in request: {}",
                    quoted(&id)
                )));
            }
            if self.graph.nodes.contains_key(&id) {
                return Err(Error::invalid(format!(
                    "add_nodes: node id already exists: {}",
                    quoted(&id)
                )));
            }
            seen.insert(id.clone());
            if options.forward {
                payloads.push(node.clone());
            }
            self.insert_node(id, Value::Object(node));
        }
        if options.forward {
            out.forward.push(Operation::AddNodes(payloads));
        }
        inverse.push(Operation::DeleteNodes(seen.into_iter().collect()));
        Ok(())
    }

    fn update_nodes(
        &mut self,
        updates: Vec<FieldUpdate>,
        options: ApplyOptions,
        out: &mut Applied,
        inverse: &mut Vec<Operation>,
    ) -> Result<()> {
        if updates.is_empty() {
            return Ok(());
        }
        reject_repeated_paths(&updates, "update_nodes")?;
        let mut inverses = options.inverse.then(FieldInverses::default);
        let mut applied = Vec::new();
        let mut detached = IndexSet::new();
        for (index, mut update) in updates.into_iter().enumerate() {
            let context = format!("update_nodes[{index}]");
            if !self.graph.nodes.contains_key(&update.id) {
                return Err(Error::invalid(format!(
                    "update_nodes: node does not exist: {}",
                    quoted(&update.id)
                )));
            }
            if !self.is_base_node(&update.id) {
                return Err(Error::invalid(format!(
                    "update_nodes: cannot update node that does not exist in the original flow: {}",
                    quoted(&update.id)
                )));
            }
            check_node_path(&update.path, &format!("{context}.path"))?;
            let existed = self.apply_field_update(
                Owner::Node,
                &mut update,
                &context,
                options,
                inverses.as_mut(),
            )?;
            if !options.restoring {
                detached.extend(self.detached_edges(&update, existed)?);
            }
            if options.forward && (existed || !update.is_delete()) {
                applied.push(update);
            }
        }
        if options.forward && !applied.is_empty() {
            out.forward.push(Operation::UpdateNodes(applied));
        }
        if let Some(inverses) = inverses {
            inverse.extend(inverses.operations(Operation::UpdateNodes));
        }
        self.remove_cascaded(detached.iter().map(String::as_str), options, out, inverse);
        Ok(())
    }

    /// The edges a write left without an end: into a removed template field,
    /// or from or into a removed output.
    fn detached_edges(&mut self, update: &FieldUpdate, existed: bool) -> Result<IndexSet<String>> {
        let path = &update.path;
        if !existed {
            return Ok(IndexSet::new());
        }
        let node_id = update.id.as_str();
        if update.is_delete()
            && path.len() == TEMPLATE_PATH.len() + 1
            && starts_with(path, &TEMPLATE_PATH)
        {
            let input = Input {
                kind: InputKind::Field,
                name: path[TEMPLATE_PATH.len()]
                    .as_key()
                    .unwrap_or_default()
                    .to_owned(),
            };
            let connections = self.edge_index.connections(&self.graph, node_id)?;
            return Ok(connections.inputs.get(&input).cloned().unwrap_or_default());
        }
        if !starts_with(path, &OUTPUTS_PATH) {
            return Ok(IndexSet::new());
        }
        let removed: Vec<String> = if path.len() == OUTPUTS_PATH.len() + 1 && update.is_delete() {
            path[OUTPUTS_PATH.len()]
                .selector_key()
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
                kind: InputKind::Output,
                name,
            };
            if let Some(ids) = connections.inputs.get(&input) {
                detached.extend(ids.iter().cloned());
            }
        }
        Ok(detached)
    }

    fn delete_nodes(
        &mut self,
        ids: &[String],
        options: ApplyOptions,
        out: &mut Applied,
        inverse: &mut Vec<Operation>,
    ) -> Result<()> {
        let ids: IndexSet<&str> = ids.iter().map(String::as_str).collect();
        if ids.is_empty() {
            return Ok(());
        }
        for id in &ids {
            if !self.is_base_node(id) {
                return Err(Error::invalid(format!(
                    "delete_nodes: cannot delete node that does not exist in the original flow: {}",
                    quoted(id)
                )));
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
            let node = self.remove_node(id);
            if options.inverse
                && let Some(Value::Object(node)) = node
            {
                removed_nodes.push(node.clone());
            }
            removed.push(id.to_owned());
        }
        if removed.is_empty() {
            return Ok(());
        }
        if options.forward {
            out.forward.push(Operation::DeleteNodes(removed));
        }
        inverse.push(Operation::AddNodes(removed_nodes));
        self.remove_cascaded(incident.iter().map(String::as_str), options, out, inverse);
        Ok(())
    }

    /// Remove the edges an operation took with it, recording them as a `delete_edges`.
    fn remove_cascaded<'i>(
        &mut self,
        ids: impl IntoIterator<Item = &'i str>,
        options: ApplyOptions,
        out: &mut Applied,
        inverse: &mut Vec<Operation>,
    ) {
        let (removed, edges) = self.remove_edges(ids, options.inverse);
        if removed.is_empty() {
            return;
        }
        out.deleted_edges.extend(removed.iter().cloned());
        if options.forward {
            out.forward.push(Operation::DeleteEdges(removed));
        }
        inverse.push(Operation::AddEdges(edges));
    }

    // --- Edges -------------------------------------------------------------------------

    fn add_edges(
        &mut self,
        edges: Vec<Map<String, Value>>,
        options: ApplyOptions,
        out: &mut Applied,
        inverse: &mut Vec<Operation>,
    ) -> Result<()> {
        if edges.is_empty() {
            return Ok(());
        }
        let mut seen = IndexSet::new();
        let mut payloads = Vec::new();
        for (index, edge) in edges.into_iter().enumerate() {
            let context = format!("add_edges[{index}]");
            let field = |key: &str| {
                non_empty_id(&edge, key).ok_or_else(|| {
                    Error::invalid(format!(
                        "{context}: edge must have a non-empty string {key}"
                    ))
                })
            };
            let (id, source, target) = (field("id")?, field("source")?, field("target")?);
            if seen.contains(&id) {
                return Err(Error::invalid(format!(
                    "add_edges: duplicate edge id in request: {}",
                    quoted(&id)
                )));
            }
            if self.graph.edges.contains_key(&id) {
                return Err(Error::invalid(format!(
                    "add_edges: edge id already exists: {}",
                    quoted(&id)
                )));
            }
            if !self.graph.nodes.contains_key(&source) {
                return Err(Error::invalid(format!(
                    "add_edges: source node does not exist: {}",
                    quoted(&source)
                )));
            }
            if !self.graph.nodes.contains_key(&target) {
                return Err(Error::invalid(format!(
                    "add_edges: target node does not exist: {}",
                    quoted(&target)
                )));
            }
            seen.insert(id.clone());
            if !options.restoring {
                check_edge(&self.graph, &mut self.edge_index, &edge)?;
            }
            if options.forward {
                payloads.push(edge.clone());
            }
            self.insert_edge(id, Value::Object(edge));
        }
        if options.forward {
            out.forward.push(Operation::AddEdges(payloads));
        }
        inverse.push(Operation::DeleteEdges(seen.into_iter().collect()));
        Ok(())
    }

    fn update_edges(
        &mut self,
        updates: Vec<FieldUpdate>,
        options: ApplyOptions,
        out: &mut Applied,
        inverse: &mut Vec<Operation>,
    ) -> Result<()> {
        if updates.is_empty() {
            return Ok(());
        }
        reject_repeated_paths(&updates, "update_edges")?;
        let mut inverses = options.inverse.then(FieldInverses::default);
        let mut applied = Vec::new();
        // The handles of each edge the batch writes under a handle key, as they were before.
        let mut handles_before: IndexMap<String, Value> = IndexMap::new();
        for (index, mut update) in updates.into_iter().enumerate() {
            let context = format!("update_edges[{index}]");
            let Some(edge) = self.graph.edges.get(&update.id) else {
                return Err(Error::invalid(format!(
                    "update_edges: edge does not exist: {}",
                    quoted(&update.id)
                )));
            };
            if !self.is_base_edge(&update.id) {
                return Err(Error::invalid(format!(
                    "update_edges: cannot update edge that does not exist in the original flow: {}",
                    quoted(&update.id)
                )));
            }
            let root = update.path[0].as_key();
            if let Some(root) = root.filter(|root| FORBIDDEN_EDGE_ROOTS.contains(root)) {
                return Err(Error::invalid(format!(
                    "{context}.path: cannot modify an edge's {root}; connecting different nodes is a different edge, so delete it and add another"
                )));
            }
            if root.is_some_and(|root| EDGE_HANDLE_ROOTS.contains(&root))
                && !handles_before.contains_key(&update.id)
                && let Some(edge) = edge.as_object()
            {
                handles_before.insert(update.id.clone(), handle_forms(edge));
            }
            let existed = self.apply_field_update(
                Owner::Edge,
                &mut update,
                &context,
                options,
                inverses.as_mut(),
            )?;
            if options.forward && (existed || !update.is_delete()) {
                applied.push(update);
            }
        }
        // An edge whose handles the batch changed is rewired, so it is checked like a new one.
        for (id, before) in handles_before {
            let Some(edge) = self.graph.edges.get(&id).and_then(Value::as_object) else {
                continue;
            };
            if values_equal(&handle_forms(edge), &before)? {
                continue;
            }
            self.edge_index.forget(edge);
            if !options.restoring {
                check_edge(&self.graph, &mut self.edge_index, edge)?;
            }
            self.edge_index.insert(edge);
        }
        if options.forward && !applied.is_empty() {
            out.forward.push(Operation::UpdateEdges(applied));
        }
        if let Some(inverses) = inverses {
            inverse.extend(inverses.operations(Operation::UpdateEdges));
        }
        Ok(())
    }

    fn delete_edges(
        &mut self,
        ids: &[String],
        options: ApplyOptions,
        out: &mut Applied,
        inverse: &mut Vec<Operation>,
    ) {
        let (removed, edges) = self.remove_edges(ids.iter().map(String::as_str), options.inverse);
        if removed.is_empty() {
            return;
        }
        if options.forward {
            out.forward.push(Operation::DeleteEdges(removed));
        }
        inverse.push(Operation::AddEdges(edges));
    }

    // --- Metadata ------------------------------------------------------------------------

    fn update_metadata(
        &mut self,
        fields: Map<String, Value>,
        delete_keys: &[String],
        options: ApplyOptions,
        out: &mut Applied,
        inverse: &mut Vec<Operation>,
    ) -> Result<()> {
        for key in fields.keys() {
            if is_collection_key(key) {
                return Err(Error::invalid(format!(
                    "update_metadata: cannot set graph collection key {}",
                    quoted(key)
                )));
            }
        }
        for key in delete_keys {
            if is_collection_key(key) {
                return Err(Error::invalid(format!(
                    "update_metadata: cannot delete graph collection key {}",
                    quoted(key)
                )));
            }
        }
        let delete_keys: Vec<String> = delete_keys
            .iter()
            .cloned()
            .collect::<IndexSet<_>>()
            .into_iter()
            .collect();
        if fields.is_empty() && delete_keys.is_empty() {
            return Ok(());
        }
        if options.inverse {
            let mut restore = Map::new();
            let mut remove = Vec::new();
            let keys: IndexSet<&String> = fields.keys().chain(&delete_keys).collect();
            for key in keys {
                match self.root().get(key) {
                    Some(value) => {
                        restore.insert(key.clone(), value.clone());
                    }
                    None => remove.push(key.clone()),
                }
            }
            inverse.push(Operation::UpdateMetadata {
                fields: restore,
                delete_keys: remove,
            });
        }
        let forward = options.forward.then(|| fields.clone());
        for (key, value) in fields {
            self.set_root(&key, value);
        }
        for key in &delete_keys {
            self.delete_root(key);
        }
        if let Some(fields) = forward {
            out.forward.push(Operation::UpdateMetadata {
                fields,
                delete_keys,
            });
        }
        Ok(())
    }

    // --- Field writes ----------------------------------------------------------------------

    /// Apply one `set_field` or `delete_field` to a node or an edge.
    ///
    /// Returns whether the path held a value before the write. Without
    /// `forward`, a set's value moves into the graph instead of being copied.
    fn apply_field_update(
        &mut self,
        owner: Owner,
        update: &mut FieldUpdate,
        context: &str,
        options: ApplyOptions,
        inverses: Option<&mut FieldInverses>,
    ) -> Result<bool> {
        let walk = self.walk(owner, update, context)?;
        let last_step = match walk.missing_at {
            Some(_) => None,
            None => self.read_last(owner, update, &walk, context)?,
        };
        {
            let root = self.graph.owner(owner, &update.id).unwrap_or(&Value::Null);
            let parent = resolve(root, &walk.physical);
            let current = last_step
                .as_ref()
                .and_then(|step| resolve(parent?, std::slice::from_ref(step)));
            check_expectation(update, current, context)?;
            if let Some(missing) = walk.missing_at {
                return Err(Error::invalid(match &update.path[missing] {
                    Segment::Key(key) => format!(
                        "{context}.path[{missing}]: object path part must be an existing string key: {}",
                        quoted(key)
                    ),
                    selector => format!(
                        "{context}.path[{missing}]: list item does not exist: {}",
                        quoted(selector.selector_key().unwrap_or_default())
                    ),
                }));
            }
            if let Some(inverses) = inverses {
                inverses.record(root, update, parent, current);
            }
        }

        let value = match &mut update.change {
            Change::Set { value, .. } if !options.forward => std::mem::take(value),
            Change::Set { value, .. } => value.clone(),
            Change::Delete => Value::Null,
        };
        let existed = self.write_last(owner, update, &walk, value, context, options)?;

        // A write inside a keyed list item must leave its key alone, and a table row its position.
        let root = self.graph.owner(owner, &update.id).unwrap_or(&Value::Null);
        for step in walk.items.iter().rev() {
            let item = resolve(root, &walk.physical[..step.depth]).unwrap_or(&Value::Null);
            if step.keyed.key_of(item) != Some(step.key.as_str()) {
                return Err(Error::invalid(format!(
                    "{context}: cannot change a list item's {}",
                    step.keyed.selector_name()
                )));
            }
            if step.keyed.kind == ListKind::Table {
                let position = step.keyed.position.as_deref().unwrap_or_default();
                if !item.get(position).is_some_and(is_row_position) {
                    return Err(Error::invalid(format!(
                        "{context}: a table row's {position} must be a finite number"
                    )));
                }
            }
        }
        Ok(existed)
    }

    /// Follow `path[..last]` from the node or edge, once.
    ///
    /// Returns the resolved steps, the keyed list items passed through, and
    /// the first segment that does not exist. A segment that does not fit the
    /// value it reads, such as a key of a list, is an error rather than a
    /// missing value.
    fn walk(&mut self, owner: Owner, update: &FieldUpdate, context: &str) -> Result<Walk> {
        let path = &update.path;
        let mut walk = Walk::default();
        let root = self.graph.owner(owner, &update.id).unwrap_or(&Value::Null);
        let mut value = root;
        for (index, part) in path[..path.len() - 1].iter().enumerate() {
            if let Segment::Key(key) = part {
                let Value::Object(map) = value else {
                    return Err(Error::invalid(format!(
                        "{context}.path[{index}]: {} reads a key of a value that is not an object",
                        quoted(key)
                    )));
                };
                let Some(child) = map.get(key) else {
                    walk.missing_at = Some(index);
                    return Ok(walk);
                };
                walk.physical.push(Step::Key(key.clone()));
                value = child;
                continue;
            }
            let keyed = keyed_list(owner, root, path, index, value, context)?;
            let items = value.as_array().map_or(&[][..], Vec::as_slice);
            let key = part.selector_key().unwrap_or_default();
            let slot = self
                .lists
                .index(
                    &update.id,
                    &string_prefix(path, index),
                    keyed,
                    items,
                    &format!("{context}.path[{index}]"),
                )?
                .slot(key);
            let Some(slot) = slot else {
                walk.missing_at = Some(index);
                return Ok(walk);
            };
            walk.physical.push(Step::Index(slot));
            walk.items.push(ItemStep {
                keyed,
                key: key.to_owned(),
                depth: walk.physical.len(),
            });
            value = &items[slot];
        }
        Ok(walk)
    }

    /// The step from the value holding the last segment to the value the path
    /// names, or `None` when there is none.
    fn read_last(
        &mut self,
        owner: Owner,
        update: &FieldUpdate,
        walk: &Walk,
        context: &str,
    ) -> Result<Option<Step>> {
        let path = &update.path;
        let last = path.len() - 1;
        let root = self.graph.owner(owner, &update.id).unwrap_or(&Value::Null);
        let parent = resolve(root, &walk.physical).unwrap_or(&Value::Null);
        match &path[last] {
            Segment::Key(key) => {
                let Value::Object(map) = parent else {
                    return Err(Error::invalid(format!(
                        "{context}.path[{last}]: {} reads a key of a value that is not an object",
                        quoted(key)
                    )));
                };
                Ok(map.contains_key(key).then(|| Step::Key(key.clone())))
            }
            selector => {
                let keyed = keyed_list(owner, root, path, last, parent, context)?;
                let items = parent.as_array().map_or(&[][..], Vec::as_slice);
                let slot = self
                    .lists
                    .index(
                        &update.id,
                        &string_prefix(path, last),
                        keyed,
                        items,
                        &format!("{context}.path[{last}]"),
                    )?
                    .slot(selector.selector_key().unwrap_or_default());
                Ok(slot.map(Step::Index))
            }
        }
    }

    /// Write or delete the last segment of the path. Returns whether it held a value.
    fn write_last(
        &mut self,
        owner: Owner,
        update: &FieldUpdate,
        walk: &Walk,
        value: Value,
        context: &str,
        options: ApplyOptions,
    ) -> Result<bool> {
        let path = &update.path;
        let id = update.id.as_str();
        let undo = match &path[path.len() - 1] {
            Segment::Key(key) => {
                self.write_key(owner, update, walk, key, value, context, options)?
            }
            selector => {
                let key = selector.selector_key().unwrap_or_default();
                self.write_item(owner, update, walk, key, value, context, options)?
            }
        };
        let Some(undo) = undo else {
            return Ok(false);
        };
        let existed = !matches!(
            undo,
            FieldUndo::KeySet { old: None, .. } | FieldUndo::ItemAdded
        );
        // A whole value replaced or removed takes the lists indexed under it with it.
        if owner == Owner::Node
            && let Some(keys) = path
                .iter()
                .map(Segment::as_key)
                .collect::<Option<Vec<&str>>>()
        {
            self.lists.forget_under(id, &keys);
        }
        self.record_field(owner, id, walk.physical.clone(), undo);
        Ok(existed)
    }

    /// The object the path's last segment is a key of, to write it.
    fn parent_mut(
        &mut self,
        owner: Owner,
        id: &str,
        walk: &Walk,
        context: &str,
    ) -> Result<&mut Value> {
        self.graph
            .owner_mut(owner, id)
            .and_then(|root| resolve_mut(root, &walk.physical))
            .ok_or_else(|| {
                Error::invalid(format!(
                    "{context}: path must end at an object property or a keyed list item"
                ))
            })
    }

    /// Write or delete an object key. Returns how to undo it, or `None` for a
    /// delete that found nothing.
    #[expect(
        clippy::too_many_arguments,
        reason = "one write's inputs, passed through from write_last"
    )]
    fn write_key(
        &mut self,
        owner: Owner,
        update: &FieldUpdate,
        walk: &Walk,
        key: &str,
        value: Value,
        context: &str,
        options: ApplyOptions,
    ) -> Result<Option<FieldUndo>> {
        let Value::Object(map) = self.parent_mut(owner, &update.id, walk, context)? else {
            return Err(Error::invalid(format!(
                "{context}: path must end at an object property or a keyed list item"
            )));
        };
        if update.is_delete() {
            let Some(index) = map.keys().position(|existing| existing == key) else {
                return Ok(None);
            };
            let old = map.shift_remove(key).unwrap_or_default();
            return Ok(Some(FieldUndo::KeyDeleted {
                key: key.to_owned(),
                index,
                old,
            }));
        }
        check_type_change(map.get(key), update, &value, context, options)?;
        let old = map.insert(key.to_owned(), value);
        Ok(Some(FieldUndo::KeySet {
            key: key.to_owned(),
            old,
        }))
    }

    /// Write or delete a keyed list item. Returns how to undo it, or `None`
    /// for a delete that found nothing.
    #[expect(
        clippy::too_many_arguments,
        reason = "one write's inputs, passed through from write_last"
    )]
    fn write_item(
        &mut self,
        owner: Owner,
        update: &FieldUpdate,
        walk: &Walk,
        key: &str,
        value: Value,
        context: &str,
        options: ApplyOptions,
    ) -> Result<Option<FieldUndo>> {
        let path = &update.path;
        let last = path.len() - 1;
        let id = update.id.as_str();
        let keyed = {
            let root = self.graph.owner(owner, id).unwrap_or(&Value::Null);
            let parent = resolve(root, &walk.physical).unwrap_or(&Value::Null);
            keyed_list(owner, root, path, last, parent, context)?
        };
        let list_context = format!("{context}.path[{last}]");
        let parent = self
            .graph
            .owner_mut(owner, id)
            .and_then(|root| resolve_mut(root, &walk.physical));
        let Some(Value::Array(items)) = parent else {
            return Err(Error::invalid(format!(
                "{list_context}: selector on a value that is not a list"
            )));
        };
        let index =
            self.lists
                .index(id, &string_prefix(path, last), keyed, items, &list_context)?;
        let slot = index.slot(key);
        if update.is_delete() {
            if slot.is_none() {
                return Ok(None);
            }
            let (old, removal) = index.remove(items, key);
            return Ok(Some(FieldUndo::ItemRemoved { removal, old }));
        }
        if keyed.key_of(&value) != Some(key) {
            return Err(Error::invalid(format!(
                "{context}: a list item written at a selector must carry the same key: {}",
                quoted(key)
            )));
        }
        check_type_change(
            slot.map(|slot| &items[slot]),
            update,
            &value,
            context,
            options,
        )?;
        if let Some(slot) = slot {
            let old = index.replace(items, key, value, context)?;
            return Ok(Some(FieldUndo::ItemReplaced { slot, old }));
        }
        index.add(items, value, context)?;
        Ok(Some(FieldUndo::ItemAdded))
    }
}

/// The keyed list items a path passes through, and where the path leads.
#[derive(Debug, Default)]
struct Walk {
    /// The resolved steps to the value holding the last segment.
    physical: Vec<Step>,
    /// The keyed list items passed through.
    items: Vec<ItemStep>,
    /// The index of the first segment that does not exist.
    missing_at: Option<usize>,
}

/// A keyed list item a path passes through.
#[derive(Debug)]
struct ItemStep {
    keyed: &'static KeyedList,
    key: String,
    /// How many resolved steps lead to the item.
    depth: usize,
}

/// The keyed list `path[index]` selects from, checking that the selector fits it.
fn keyed_list(
    owner: Owner,
    node: &Value,
    path: &Path,
    index: usize,
    value: &Value,
    context: &str,
) -> Result<&'static KeyedList> {
    let prefix: Option<Vec<&str>> = path[..index].iter().map(Segment::as_key).collect();
    let keyed = match (owner, prefix) {
        (Owner::Node, Some(prefix)) => NODE_SCHEMA.keyed_list_at(node, &prefix),
        _ => None,
    };
    let Some(keyed) = keyed else {
        return Err(Error::invalid(format!(
            "{context}.path[{index}]: selector on a list the node schema does not declare keyed"
        )));
    };
    let fits = matches!(
        (keyed.kind, &path[index]),
        (ListKind::Table, Segment::ById(_)) | (ListKind::Natural, Segment::ByKey(_))
    );
    if !fits {
        return Err(Error::invalid(format!(
            "{context}.path[{index}]: items of this list are selected with {{{}: ...}}",
            quoted(keyed.selector_name())
        )));
    }
    if !value.is_array() {
        return Err(Error::invalid(format!(
            "{context}.path[{index}]: selector on a value that is not a list"
        )));
    }
    Ok(keyed)
}

/// The object keys of `path[..index]`, which a keyed list's address is.
fn string_prefix(path: &Path, index: usize) -> Vec<String> {
    path[..index]
        .iter()
        .filter_map(Segment::as_key)
        .map(str::to_owned)
        .collect()
}

fn starts_with(path: &Path, prefix: &[&str]) -> bool {
    path.len() >= prefix.len()
        && path
            .iter()
            .zip(prefix)
            .all(|(segment, key)| segment.as_key() == Some(*key))
}

fn non_empty_id(object: &Map<String, Value>, key: &str) -> Option<String> {
    object
        .get(key)
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .map(str::to_owned)
}

fn is_collection_key(key: &str) -> bool {
    key == "nodes" || key == "edges"
}

fn check_node_path(path: &Path, context: &str) -> Result<()> {
    if path[0].as_key() == Some("id") {
        return Err(Error::invalid(format!(
            "{context}: cannot modify node identity"
        )));
    }
    let forbidden = FORBIDDEN_NODE_PATHS
        .iter()
        .any(|forbidden| path.len() == forbidden.len() && starts_with(path, forbidden));
    if forbidden {
        return Err(Error::invalid(format!(
            "{context}: cannot update entire node data objects at path {}; forbidden paths are: data, data.node, data.node.template",
            path_label(path)
        )));
    }
    Ok(())
}

/// Refuse an update batch that writes one path of one node or edge twice.
fn reject_repeated_paths(updates: &[FieldUpdate], kind: &str) -> Result<()> {
    let mut seen = HashSet::new();
    for update in updates {
        if !seen.insert((update.id.as_str(), update.path.as_slice())) {
            return Err(Error::invalid(format!(
                "{kind}: multiple field updates for one id and path: {} {}",
                quoted(&update.id),
                path_label(&update.path)
            )));
        }
    }
    Ok(())
}

fn check_expectation(update: &FieldUpdate, current: Option<&Value>, context: &str) -> Result<()> {
    let exists = current.is_some();
    match &update.expect {
        Some(Expect::Absent) if exists => Err(Error::precondition(format!(
            "{context}: expected {} to be absent, but it exists",
            path_label(&update.path)
        ))),
        None | Some(Expect::Absent) => Ok(()),
        Some(Expect::Value(expected)) => {
            let holds = match current {
                Some(current) => values_equal(current, expected)?,
                None => false,
            };
            if holds {
                Ok(())
            } else {
                Err(Error::precondition(format!(
                    "{context}: expected {} to hold the given value, but found {}",
                    path_label(&update.path),
                    if exists {
                        "a different value"
                    } else {
                        "nothing"
                    }
                )))
            }
        }
    }
}

/// Refuse a `set_field` that silently changes a value's JSON type.
///
/// A type change must be declared with `from_type` naming the type being
/// replaced, which also makes it a precondition: the write only applies to
/// the value it was derived from.
fn check_type_change(
    current: Option<&Value>,
    update: &FieldUpdate,
    value: &Value,
    context: &str,
    options: ApplyOptions,
) -> Result<()> {
    if options.redacted {
        return Ok(());
    }
    let Change::Set { from_type, .. } = &update.change else {
        return Ok(());
    };
    match (from_type, current) {
        (None, Some(current)) if json_type(current) != json_type(value) => {
            Err(Error::invalid_with(
                ErrorCode::FieldTypeChangeUndeclared,
                format!(
                    "{context}: set_field changes a {} to a {} without declaring from_type",
                    json_type(current).as_str(),
                    json_type(value).as_str()
                ),
            ))
        }
        (None, _) => Ok(()),
        (Some(from_type), Some(current)) if json_type(current) == *from_type => Ok(()),
        (Some(from_type), current) => Err(Error::invalid_with(
            ErrorCode::FieldTypePreconditionFailed,
            format!(
                "{context}: set_field expected to replace a {} but found {}",
                from_type.as_str(),
                current.map_or("nothing", |current| json_type(current).as_str())
            ),
        )),
    }
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
            && let (Segment::ByKey(key), Some(Value::Array(items)), Some(_)) =
                (&path[last], parent, current)
        {
            // Removing a natural-list item that is not last cannot be undone by
            // a selector write, which appends; the whole list is written back.
            // A table's order is its rows' positions, so its rows need no such care.
            let prefix = string_prefix(path, last);
            let keyed = NODE_SCHEMA.keyed_list_at(root, &prefix);
            let is_last = items.last().is_some_and(|item| {
                keyed.and_then(|keyed| keyed.key_of(item)) == Some(key.as_str())
            });
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
        let mut entry = FieldUpdate::set(&update.id, path.clone(), current.clone());
        if let (Change::Set { value, .. }, Change::Set { from_type, .. }) =
            (&update.change, &mut entry.change)
            && json_type(current) != json_type(value)
        {
            *from_type = Some(json_type(value));
        }
        self.entries.push(entry);
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
/// The graph breaks a structural rule, an operation is invalid for it, or an
/// expectation fails.
pub fn apply_flow_operations(
    base: Value,
    operations: Vec<Operation>,
    options: ApplyOptions,
) -> Result<(Value, Applied)> {
    let mut state = FlowState::new(base)?;
    let applied = state.apply(operations, options)?;
    Ok((state.into_value(), applied))
}
