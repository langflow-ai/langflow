//! [`EdgeIndex`]: each edge's handles and each node's connections, kept
//! between batches.

use crate::flow::model::EntryExt;
use crate::json::FlowObj;
use crate::json::serialize::quoted;
use crate::map::hash::{HashMap, IndexSet};
use crate::map::pending::PendingMap;
use crate::violation::error::{Result, invalid};

use super::graph::{GraphRead, endpoint};
use super::handles::{Handles, Input, read_handles};

/// A node's edges, by the input they enter and the output they leave from.
#[derive(Debug, Clone, Default)]
pub struct Connections {
    /// Edges into each input of the node.
    pub inputs: HashMap<Input, IndexSet<String>>,
    /// Edges out of each output of the node.
    pub outputs: HashMap<String, IndexSet<String>>,
}

impl Connections {
    /// The ids of the edges at `endpoint`. For an output, this includes loop
    /// feedback edges into it.
    pub(crate) fn at(&self, endpoint: &Endpoint) -> impl Iterator<Item = &String> {
        let (input, output) = match endpoint {
            Endpoint::Field(name) => (Input::field(name), None),
            Endpoint::Output(name) => (Input::loop_output(name), self.outputs.get(name)),
        };
        self.inputs.get(&input).into_iter().chain(output).flatten()
    }
}

/// A place on a node that edges attach to.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum Endpoint {
    /// A template field, which edges enter.
    Field(String),
    /// An output, which edges leave and loop feedback edges enter.
    Output(String),
}

/// Each edge's handles and each node's connections, built on first use.
#[derive(Debug)]
pub(crate) struct EdgeIndex {
    handles: PendingMap<Handles>,
    connections: PendingMap<Connections>,
}

impl Default for EdgeIndex {
    fn default() -> Self {
        Self {
            handles: PendingMap::new(),
            connections: PendingMap::new(),
        }
    }
}

impl EdgeIndex {
    /// An edge's handles, read strictly the first time.
    pub fn handles(&mut self, edge: &FlowObj) -> Result<Handles> {
        let id = edge.id();
        if let Some(handles) = self.handles.get(id) {
            return Ok(handles.clone());
        }
        let handles = read_handles(edge)?;
        self.handles.insert(id, handles.clone());
        Ok(handles)
    }

    /// A node's connections, reading the handles of its edges the first time.
    pub fn connections(&mut self, graph: &impl GraphRead, node_id: &str) -> Result<&Connections> {
        if !self.connections.contains(node_id) {
            let mut connections = Connections::default();
            for id in graph.edge_ids_at(node_id) {
                let edge = graph
                    .edge(id)
                    .ok_or_else(|| invalid!("edge {} does not exist", quoted(id)))?;
                let handles = self.handles(edge)?;
                connect(&mut connections, node_id, edge, &handles);
            }
            self.connections.insert(node_id, connections);
        }
        Ok(self
            .connections
            .get(node_id)
            .expect("the connections were just built"))
    }

    /// Index a new edge at the nodes whose connections are built.
    /// If its handles do not read, those nodes are indexed again on next use.
    pub fn insert(&mut self, edge: &FlowObj) {
        let ends = [endpoint(edge, "source"), endpoint(edge, "target")];
        if !ends.iter().any(|end| self.connections.contains(end)) {
            return;
        }
        match self.handles(edge) {
            Ok(handles) => {
                for end in ends {
                    self.connections
                        .update(end, |connections| connect(connections, end, edge, &handles));
                }
            }
            Err(_) => {
                for end in ends {
                    self.connections.remove(end);
                }
            }
        }
    }

    /// Drop an edge from the index, before it is removed.
    pub fn forget(&mut self, edge: &FlowObj) {
        let id = edge.id();
        let Some(handles) = self.handles.get(id).cloned() else {
            return;
        };
        self.handles.remove(id);
        for end in [endpoint(edge, "source"), endpoint(edge, "target")] {
            self.connections.update_if(
                end,
                |connections| is_connected(connections, end, edge, &handles),
                |connections| disconnect(connections, end, edge, &handles),
            );
        }
    }

    /// Whether a node's connections are built.
    #[cfg(test)]
    pub fn has_connections(&self, node_id: &str) -> bool {
        self.connections.contains(node_id)
    }

    /// Drop a node's connections.
    pub fn forget_node(&mut self, node_id: &str) {
        self.connections.remove(node_id);
    }

    /// Make a batch's changes part of the index.
    pub fn commit(&mut self) {
        self.handles.commit();
        self.connections.commit();
    }

    /// Drop a batch's changes.
    pub fn drop_pending(&mut self) {
        self.handles.drop_pending();
        self.connections.drop_pending();
    }
}

fn connect(connections: &mut Connections, node_id: &str, edge: &FlowObj, handles: &Handles) {
    let id = edge.id().to_owned();
    if endpoint(edge, "target") == node_id {
        connections
            .inputs
            .entry(handles.input.clone())
            .or_default()
            .insert(id.clone());
    }
    if endpoint(edge, "source") == node_id {
        connections
            .outputs
            .entry(handles.output.clone())
            .or_default()
            .insert(id);
    }
}

/// Whether [`disconnect`] would remove the edge from `connections`.
fn is_connected(
    connections: &Connections,
    node_id: &str,
    edge: &FlowObj,
    handles: &Handles,
) -> bool {
    let id = edge.id();
    let has = |ids: Option<&IndexSet<String>>| ids.is_some_and(|ids| ids.contains(id));
    (endpoint(edge, "target") == node_id && has(connections.inputs.get(&handles.input)))
        || (endpoint(edge, "source") == node_id && has(connections.outputs.get(&handles.output)))
}

fn disconnect(connections: &mut Connections, node_id: &str, edge: &FlowObj, handles: &Handles) {
    let id = edge.id();
    if endpoint(edge, "target") == node_id
        && let Some(ids) = connections.inputs.get_mut(&handles.input)
    {
        ids.shift_remove(id);
    }
    if endpoint(edge, "source") == node_id
        && let Some(ids) = connections.outputs.get_mut(&handles.output)
    {
        ids.shift_remove(id);
    }
}
