//! Replaying stored operations on a flow.
//!
//! Replay runs no rule. The operations passed the rules when they were
//! applied, and a newer rule must not stop history from replaying. Stored
//! operations list every edge they delete, so replay deletes no edge itself.
//! It fails only when an operation cannot be carried out:
//!
//! - `add_nodes` or `add_edges` adds an id that the flow already has;
//! - `add_edges` names a source or target node that does not exist;
//! - `update_nodes` or `delete_nodes` names a node that does not exist;
//! - an update's path does not exist up to its last segment;
//! - a list item segment before the last one matches no item, or two items.
//!
//! [`apply`](crate::ops::apply) makes the same checks, so its forward
//! operations always replay to the same flow.

use crate::data::maps::IndexSet;
use crate::data::value::AnyValue;
use crate::graph::GraphState;
use crate::models::edges::GraphRead;
use crate::models::error::{Result, bail, quoted};
use crate::models::operation::{Edge, FieldUpdate, Operation};
use crate::ops::place::{
    AddedEdges, FieldBackward, PlacedUpdate, UpdatePlace, require_path, written_value,
};
use crate::ops::{ApplyOptions, ReplayOptions, Replayed, Report};

impl GraphState {
    /// Replay stored operations in order, with no rule. On an error nothing
    /// is replayed. A deleted node keeps its edges unless the operations
    /// delete them.
    ///
    /// # Errors
    ///
    /// An operation cannot be carried out on the flow.
    pub fn replay(
        &mut self,
        operations: Vec<Operation>,
        options: ReplayOptions,
    ) -> Result<Replayed> {
        let mut report = Report::new(ApplyOptions {
            forward: false,
            backward: options.backward,
        });
        self.run_batch(operations, &mut report, Self::replay_operation)?;
        self.commit();
        Ok(Replayed {
            backward: report.into_applied().backward,
        })
    }

    fn replay_operation(&mut self, operation: Operation, report: &mut Report) -> Result<()> {
        match operation {
            Operation::AddNodes(nodes) => self.add_nodes(nodes, report)?,
            Operation::UpdateNodes(updates) => self.replay_update_nodes(updates, report)?,
            Operation::DeleteNodes(ids) => self.replay_delete_nodes(&ids, report)?,
            Operation::AddEdges(edges) => self.replay_add_edges(edges, report)?,
            Operation::DeleteEdges(ids) => self.delete_edges(&ids, report),
        }
        Ok(())
    }

    fn replay_update_nodes(
        &mut self,
        updates: Vec<FieldUpdate>,
        report: &mut Report,
    ) -> Result<()> {
        let mut backward = report.keeps_backward().then(FieldBackward::default);
        for (index, mut update) in updates.into_iter().enumerate() {
            let context = UpdatePlace::new(index);
            self.require_node(&update.id)?;
            let placed = PlacedUpdate {
                update: &update,
                context,
            };
            let walk = self.walk_update(&placed)?;
            require_path(&placed, &walk)?;
            if let Some(backward) = backward.as_mut() {
                self.record_backward(&placed, backward)?;
            }
            // Replay returns no forward operations, so the value moves out.
            let value = written_value(&mut update, false);
            let placed = PlacedUpdate {
                update: &update,
                context,
            };
            self.write_update(&placed, &walk, value);
        }
        if let Some(backward) = backward {
            backward.record(report);
        }
        Ok(())
    }

    /// Delete nodes, each of which must exist. Their edges stay.
    fn replay_delete_nodes(&mut self, ids: &[String], report: &mut Report) -> Result<()> {
        let ids: IndexSet<&str> = ids.iter().map(String::as_str).collect();
        for id in &ids {
            if !self.graph.has_node(id) {
                bail!("delete_nodes: node does not exist: {}", quoted(id));
            }
        }
        self.remove_nodes(&ids, report);
        Ok(())
    }

    fn replay_add_edges(&mut self, edges: Vec<Edge>, report: &mut Report) -> Result<()> {
        let mut added = AddedEdges::default();
        for edge in edges {
            self.require_new_edge(&edge)?;
            self.insert_added_edge(edge, report, &mut added);
        }
        added.record(report);
        Ok(())
    }
}

/// Replay stored operations on a flow graph, with no rule. Loading the flow
/// checks the structural rules ([`GraphState::new`]).
///
/// # Errors
///
/// The flow breaks a structural rule, or an operation cannot be carried out.
pub fn replay_flow_operations(
    base: AnyValue,
    operations: Vec<Operation>,
    options: ReplayOptions,
) -> Result<(AnyValue, Replayed)> {
    let mut state = GraphState::new(base)?;
    let replayed = state.replay(operations, options)?;
    Ok((state.into_value(), replayed))
}

#[cfg(test)]
mod tests {
    use crate::json;

    use super::*;

    #[test]
    fn a_replay_that_deletes_a_node_but_not_its_edges_does_not_refuse() {
        let node = |id: &str| json!({"id": id, "data": {"node": {"template": {"f": {"value": "", "type": "str"}}}}});
        let edge = json!({"id": "e", "source": "a", "target": "b"});
        let flow = json!({"nodes": [node("a"), node("b")], "edges": [edge]});
        let mut state = GraphState::new(flow).unwrap();
        let delete = json!([{"type": "delete_nodes", "ids": ["a"]}]);
        let delete = Operation::list_from_value(delete).unwrap();
        state.replay(delete, ReplayOptions::default()).unwrap();
        assert!(!state.graph.has_node("a"));
        assert!(state.graph.has_edge("e"));
        // The next apply checks only its own batch.
        let write = json!([{"type": "update_nodes", "updates": [
            {"id": "b", "op": "set_field", "path": ["data", "node", "template", "f", "value"], "value": "x"},
        ]}]);
        let write = Operation::list_from_value(write).unwrap();
        state.apply(write, ApplyOptions::default()).unwrap();
    }
}
