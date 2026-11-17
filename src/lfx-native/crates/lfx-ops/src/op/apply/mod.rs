//! Applying an operation batch to a flow.
//!
//! Apply runs every rule. A batch applies in order, all or nothing.
//! [`replay`](crate::op::replay) runs stored operations with the same steps
//! and no rule.
//!
//! Forward operations drop a delete that finds nothing, and add a
//! `delete_edges` for each cascade delete. Backward operations undo each
//! operation. Example: `delete_nodes ["b"]`, where `b` has the edge `e1`,
//! gives forward `delete_nodes ["b"]`, `delete_edges ["e1"]` and backward
//! `add_nodes [b]`, `add_edges [e1]`.

mod field;

use crate::collection::hash_map::IndexSet;
use crate::json::{FlowStr, FlowValue};

use crate::flow::edge::Edge;
use crate::flow::node::Node;
use crate::json::serialize::quoted;
use crate::op::field_update::{AddedEdges, FieldBackward, SeqNum};
use crate::op::operation::{FieldUpdate, Operation};
use crate::op::{Applied, ApplyOptions, OperationStep, Report};
use crate::rule::edge::{GraphRead, check_edge, removed_endpoints};
use crate::state::GraphState;
use crate::violation::error::{Result, bail};

use field::Before;

impl GraphState {
    /// Apply a batch of operations in order, with every rule. On an error
    /// nothing is applied. It checks only what the batch changes.
    ///
    /// # Errors
    ///
    /// An operation is invalid for the flow.
    pub fn apply(&mut self, operations: Vec<Operation>, options: ApplyOptions) -> Result<Applied> {
        let applied = self.apply_pending(operations, options)?;
        self.commit();
        Ok(applied)
    }

    /// Apply a batch as [`Self::apply`] does, but stage it. [`Self::keep`]
    /// commits it, and [`Self::drop_staged`] or the next batch drops it.
    ///
    /// # Errors
    ///
    /// An operation is invalid for the flow.
    pub fn stage(&mut self, operations: Vec<Operation>, options: ApplyOptions) -> Result<Applied> {
        let applied = self.apply_pending(operations, options)?;
        self.set_staged();
        Ok(applied)
    }

    /// Apply a batch as pending changes, without committing them.
    fn apply_pending(
        &mut self,
        operations: Vec<Operation>,
        options: ApplyOptions,
    ) -> Result<Applied> {
        let mut report = Report::new(options);
        self.run_batch(operations, &mut report, Self::apply_operation)?;
        Ok(report.into_applied())
    }

    /// Carry out each operation with `step` as pending changes. On an
    /// error, drop the pending changes. The caller commits them.
    pub(crate) fn run_batch(
        &mut self,
        operations: Vec<Operation>,
        report: &mut Report,
        step: OperationStep,
    ) -> Result<()> {
        // A panicked batch or an unkept staged batch leaves its pending changes behind.
        self.drop_staged();
        self.drop_pending();
        for operation in operations {
            report.begin_operation();
            if let Err(error) = step(self, operation, report) {
                self.drop_pending();
                return Err(error);
            }
        }
        Ok(())
    }

    fn apply_operation(&mut self, operation: Operation, report: &mut Report) -> Result<()> {
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

    /// Add nodes. It refuses an id the flow already has. The parser checked
    /// the rest.
    pub(crate) fn add_nodes(&mut self, nodes: Vec<Node>, report: &mut Report) -> Result<()> {
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
        let mut cascaded = IndexSet::default();
        for (index, mut update) in updates.into_iter().enumerate() {
            let context = SeqNum::new(index);
            self.require_node(&update.id)?;
            if !self.is_base_node(&update.id) {
                bail!(
                    "update_nodes: cannot update node that does not exist in the original flow: {}",
                    quoted(&update.id)
                );
            }
            let before =
                self.apply_field_update(&mut update, context, report.options, backward.as_mut())?;
            if let Before::Value(value) = &before {
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
            backward.record(report);
        }
        self.remove_edges(cascaded.iter().map(String::as_str), report);
        Ok(())
    }

    /// Check that the node an update writes exists.
    pub(crate) fn require_node(&self, id: &str) -> Result<()> {
        if !self.graph.has_node(id) {
            bail!("update_nodes: node does not exist: {}", quoted(id));
        }
        Ok(())
    }

    /// The edges at the endpoints that `update` removed from its node.
    /// `before` is what the path held before the write.
    fn edges_at_removed(
        &mut self,
        update: &FieldUpdate,
        before: Option<&FlowValue>,
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
            return Ok(IndexSet::default());
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
        for id in &ids {
            if !self.is_base_node(id) {
                bail!(
                    "delete_nodes: cannot delete node that does not exist in the original flow: {}",
                    quoted(id)
                );
            }
        }
        let incident = self.remove_nodes(&ids, report);
        self.remove_edges(incident.iter().map(FlowStr::as_str), report);
        Ok(())
    }

    /// Remove the nodes among `ids` that exist. Returns the ids of their
    /// edges, which stay: apply removes them, and replay does not.
    pub(crate) fn remove_nodes(
        &mut self,
        ids: &IndexSet<&str>,
        report: &mut Report,
    ) -> IndexSet<FlowStr> {
        let mut removed = Vec::new();
        let mut changed = false;
        let mut removed_nodes = Vec::new();
        let mut incident = IndexSet::default();
        for &id in ids {
            if !self.graph.has_node(id) {
                continue;
            }
            incident.extend(self.graph.edge_keys_at(id).cloned());
            if report.options.backward {
                removed_nodes.extend(self.node_copy(id));
            }
            self.remove_node(id);
            changed = true;
            if report.options.forward {
                removed.push(id.to_owned());
            }
        }
        if changed {
            report.record(Operation::DeleteNodes(removed));
            report.record_backward(Operation::AddNodes(removed_nodes));
        }
        incident
    }

    // --- Edges -------------------------------------------------------------------------

    /// Add edges. Each edge must pass the edge rules, with the edges before
    /// it added.
    fn add_edges(&mut self, edges: Vec<Edge>, report: &mut Report) -> Result<()> {
        let mut added = AddedEdges::default();
        for edge in edges {
            self.require_new_edge(&edge)?;
            check_edge(&self.graph, &mut self.edge_index, edge.as_map())?;
            self.insert_added_edge(edge, report, &mut added);
        }
        added.record(report);
        Ok(())
    }

    /// Check that the flow has both nodes of `edge`, and not its id.
    pub(crate) fn require_new_edge(&self, edge: &Edge) -> Result<()> {
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
        Ok(())
    }

    /// Add `edge`, which [`Self::require_new_edge`] checked.
    pub(crate) fn insert_added_edge(
        &mut self,
        edge: Edge,
        report: &Report,
        added: &mut AddedEdges,
    ) {
        if report.options.forward {
            added.edges.push(edge.clone());
        }
        if report.options.backward {
            added.ids.push(edge.id().to_owned());
        }
        added.count += 1;
        self.insert_edge(edge);
    }

    /// Delete the edges among `ids` that exist.
    pub(crate) fn delete_edges(&mut self, ids: &[String], report: &mut Report) {
        self.remove_edges(ids.iter().map(String::as_str), report);
    }

    /// Remove the edges among `ids` that exist, each once, and record them as
    /// a `delete_edges`.
    fn remove_edges<'i>(&mut self, ids: impl IntoIterator<Item = &'i str>, report: &mut Report) {
        let mut removed = Vec::new();
        let mut copies = Vec::new();
        let mut changed = false;
        for id in ids {
            if !self.graph.has_edge(id) {
                continue;
            }
            if report.options.backward {
                copies.extend(self.edge_copy(id));
            }
            self.remove_edge(id);
            changed = true;
            if report.options.forward {
                removed.push(id.to_owned());
            }
        }
        if !changed {
            return;
        }
        report.record(Operation::DeleteEdges(removed));
        report.record_backward(Operation::AddEdges(copies));
    }
}

/// Apply operations to a flow graph, with every rule.
///
/// # Errors
///
/// The graph breaks a structural rule, or an operation is invalid for it.
pub fn apply_flow_operations(
    base: FlowValue,
    operations: Vec<Operation>,
    options: ApplyOptions,
) -> Result<(FlowValue, Applied)> {
    let mut state = GraphState::new(base)?;
    let applied = state.apply(operations, options)?;
    Ok((state.into_value(), applied))
}

#[cfg(test)]
mod tests;
