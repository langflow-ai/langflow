//! Replaying stored operations on a flow.
//!
//! Replay carries out stored operations as they are written, in the order
//! they are written: the forward operations of the operation log, and
//! backward operations to show an earlier revision. It runs no rule, because
//! the operations already passed the rules when they were applied. A rule
//! that was added later must not stop history from replaying.
//!
//! So replay checks no edge rule, no table position, and no other item of a
//! list it writes into. It deletes no edge as a cascade delete either: stored
//! operations list every edge they delete. It fails only when an operation
//! cannot be carried out:
//!
//! - `add_nodes` or `add_edges` adds an id that the flow already has;
//! - `add_edges` names a source or target node that does not exist;
//! - `update_nodes` or `delete_nodes` names a node that does not exist;
//! - an update's path does not exist up to its last segment;
//! - a list item key segment matches no item before the last segment, or
//!   matches two items.
//!
//! Apply makes each of these checks too, with the same code. So the forward
//! operations of apply always replay, and give the flow that apply gave. The
//! fixture runners check this. Replay shares with apply the steps that carry
//! out an operation (see [`apply`](crate::ops::apply)). Only apply calls the
//! rules.

use indexmap::IndexSet;

use crate::ops::apply::{
    AddedEdges, ApplyOptions, FieldBackward, PlacedUpdate, Report, UpdatePlace, require_path,
    written_value,
};
use crate::ops::edges::GraphRead;
use crate::ops::error::{Result, bail, quoted};
use crate::ops::ops::{Edge, FieldUpdate, Operation};
use crate::ops::state::GraphState;
use crate::value::AnyValue;

/// What a replay returns besides the flow.
#[derive(Debug, Clone, Copy, Default)]
pub struct ReplayOptions {
    /// Return, for each operation, its backward operations.
    pub backward: bool,
}

/// What a replay did.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Replayed {
    /// When the caller sets the `backward` option: for each operation, in
    /// the same order, a list of the operations that undo it. They follow
    /// the rules of [`Applied::backward`](crate::ops::apply::Applied::backward).
    pub backward: Vec<Vec<Operation>>,
}

impl GraphState {
    /// Replay stored operations in order, with no rule. On an error nothing
    /// is replayed.
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
        let deleted: Vec<String> = operations
            .iter()
            .filter_map(|operation| match operation {
                Operation::DeleteNodes(ids) => Some(ids.iter().cloned()),
                _ => None,
            })
            .flatten()
            .collect();
        self.run_batch(operations, &mut report, Self::replay_operation)?;
        self.commit();
        // Replay checks no rule. Of the structural rules that apply checks
        // before its first batch, the only one a replay can break is that an
        // edge's nodes exist: replay deletes no edge with its node. Stored
        // operations delete those edges in the same batch, so the graph
        // stays checked unless a node the batch deleted still has edges.
        // Then apply checks the whole graph again, and refuses it.
        if deleted
            .iter()
            .any(|id| !self.graph.has_node(id) && self.graph.edges_at(id).next().is_some())
        {
            self.uncheck_base();
        }
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

    /// Delete nodes, each of which must exist. Their edges stay: the stored
    /// operations delete them.
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

/// Replay stored operations on a flow graph, with no rule, and return the
/// result with what the replay did.
///
/// Loading the flow checks only what the indexes need, so a stored flow that
/// breaks a rule added later still replays.
///
/// # Errors
///
/// The flow cannot be indexed, or an operation cannot be carried out on it.
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
    fn apply_checks_the_flow_again_after_a_replay() {
        let node = |id: &str| json!({"id": id, "data": {"node": {"template": {}}}});
        let edge = json!({"id": "e", "source": "a", "target": "b"});
        let flow = json!({"nodes": [node("a"), node("b")], "edges": [edge]});
        let mut state = GraphState::new(flow).unwrap();
        state.apply(Vec::new(), ApplyOptions::default()).unwrap();
        let delete = json!([{"type": "delete_nodes", "ids": ["a"]}]);
        let delete = Operation::list_from_value(delete).unwrap();
        state.replay(delete, ReplayOptions::default()).unwrap();
        // The replay left edge `e` without its source node.
        let error = state
            .apply(Vec::new(), ApplyOptions::default())
            .unwrap_err();
        assert_eq!(error.code.as_str(), "FLOW_GRAPH_INVALID", "{error}");
    }

    #[test]
    fn the_first_batch_refuses_a_loaded_flow_with_an_edge_without_its_node() {
        let node = |id: &str| json!({"id": id, "data": {"node": {"template": {}}}});
        let flow = json!({
            "nodes": [node("a")],
            "edges": [{"id": "e", "source": "a", "target": "gone"}],
        });
        let expected = crate::ops::validate::validate_flow_data(
            &flow,
            crate::ops::validate::Numbers::Skip,
            "flow.data",
            None,
        )
        .unwrap_err();
        let mut state = GraphState::new(flow).unwrap();
        let error = state
            .apply(Vec::new(), ApplyOptions::default())
            .unwrap_err();
        assert_eq!(error, expected);
        assert!(
            state.needs_check(),
            "a refused check leaves the flow unchecked"
        );
    }

    #[test]
    fn a_replay_that_leaves_every_edge_its_nodes_keeps_the_flow_checked() {
        let node =
            |id: &str| json!({"id": id, "data": {"node": {"template": {"f": {"value": ""}}}}});
        let edge = json!({"id": "e", "source": "a", "target": "b"});
        let flow = json!({"nodes": [node("a"), node("b"), node("c")], "edges": [edge]});
        let mut state = GraphState::new(flow).unwrap();
        assert!(
            state.needs_check(),
            "a loaded flow is checked before its first batch"
        );
        state.apply(Vec::new(), ApplyOptions::default()).unwrap();
        assert!(!state.needs_check());
        let batches = [
            json!([{"type": "update_nodes", "updates": [
                {"id": "a", "op": "set_field", "path": ["data", "node", "template", "f", "value"], "value": "x"},
            ]}]),
            // A stored delete: the node, then its edges.
            json!([{"type": "delete_nodes", "ids": ["a"]}, {"type": "delete_edges", "ids": ["e"]}]),
            json!([{"type": "delete_nodes", "ids": ["c"]}]),
        ];
        for batch in batches {
            let batch = Operation::list_from_value(batch).unwrap();
            state.replay(batch, ReplayOptions::default()).unwrap();
            assert!(!state.needs_check());
        }
    }
}
