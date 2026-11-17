//! The rules for an edge that a write adds.
//!
//! An edge goes from an output of its source (`sourceHandle.name`) to a
//! template field of its target (`targetHandle.fieldName`). A loop feedback
//! edge goes into an output with `allows_loop` (`targetHandle.name`).
//!
//! An edge holds each handle twice: as an object in `data`, and as a string
//! where `œ` stands for `"`. The two forms must agree.
//!
//! When a write removes a field or an output, it also removes the edges there.
//! The rules check only the edges a write adds or changes, and the edges it cuts.

mod endpoints;
mod graph;
mod handles;
mod index;
mod outputs;
mod violations;

use std::fmt;

use crate::flow::model::{EntryExt, TEMPLATE_PATH};
use crate::json::serialize::quoted;
use crate::json::{FlowObj, FlowValue};
use crate::violation::ViolationCode;
use crate::violation::error::{Error, ErrorCode, Result, bail};

pub(crate) use endpoints::{reads_before, removed_endpoints};
pub(crate) use graph::{GraphRead, endpoint, list};
pub(crate) use handles::{edge_changed, read_handles};
pub(crate) use index::EdgeIndex;
pub(crate) use violations::find_edge_violations;

use handles::{Handles, InputKind};
use outputs::node_outputs;

/// The type of a note node.
pub const NOTE_NODE_TYPE: &str = "noteNode";

/// Check an edge that a write adds, and return its handles.
///
/// # Errors
///
/// The edge rule this edge, or an edge it is checked against, breaks.
pub(crate) fn check_edge(
    graph: &impl GraphRead,
    index: &mut EdgeIndex,
    edge: &FlowObj,
) -> Result<Handles> {
    check_no_note(graph, edge)?;
    let handles = index.handles(edge)?;
    check_source_output(graph, edge, &handles)?;
    if check_target_input(graph, edge, &handles)? == Takes::One {
        check_input_free(graph, index, edge, &handles)?;
    }
    Ok(handles)
}

/// How many edges an input takes.
#[derive(Debug, PartialEq, Eq)]
enum Takes {
    One,
    Many,
}

/// The edge has no note at either end, because a note has no handles.
fn check_no_note(graph: &impl GraphRead, edge: &FlowObj) -> Result<()> {
    for end in ["source", "target"] {
        let node_id = endpoint(edge, end);
        if !graph.has_node(node_id) {
            bail!("edge {}: {end} node does not exist", quoted(edge.id()));
        }
        let node_type = graph.node_value(node_id, &["type"]);
        if node_type.as_deref().and_then(FlowValue::as_str) == Some(NOTE_NODE_TYPE) {
            return Err(error(
                edge,
                ViolationCode::EdgeTouchesNote,
                format!(
                    "its {end} {} is a note, which has no handles",
                    quoted(node_id)
                ),
            ));
        }
    }
    Ok(())
}

/// The source node has the output the edge leaves from.
fn check_source_output(graph: &impl GraphRead, edge: &FlowObj, handles: &Handles) -> Result<()> {
    let source = endpoint(edge, "source");
    let found =
        node_outputs(graph, source)?.is_some_and(|outputs| outputs.get(&handles.output).is_some());
    if found {
        return Ok(());
    }
    Err(not_found(
        edge,
        format!(
            "source node {} has no output {}",
            quoted(source),
            quoted(&handles.output)
        ),
    ))
}

/// The target node has the input the edge enters. Returns how many edges it accepts.
fn check_target_input(graph: &impl GraphRead, edge: &FlowObj, handles: &Handles) -> Result<Takes> {
    let target = endpoint(edge, "target");
    let name = &handles.input.name;
    match handles.input.kind {
        InputKind::Field => {
            let [data, body, template] = TEMPLATE_PATH;
            let field = graph.node_value(target, &[data, body, template, name]);
            let Some(field) = field.as_deref().and_then(FlowValue::as_object) else {
                return Err(not_found(
                    edge,
                    format!(
                        "target node {} has no field {}",
                        quoted(target),
                        quoted(name)
                    ),
                ));
            };
            Ok(if field.get("list") == Some(&FlowValue::Bool(true)) {
                Takes::Many
            } else {
                Takes::One
            })
        }
        InputKind::LoopOutput => {
            let allows_loop = node_outputs(graph, target)?.and_then(|outputs| {
                outputs
                    .get(name)
                    .map(|output| output.get("allows_loop") == Some(&FlowValue::Bool(true)))
            });
            if allows_loop == Some(true) {
                return Ok(Takes::One);
            }
            Err(not_found(
                edge,
                format!(
                    "target node {} has no loop output {}",
                    quoted(target),
                    quoted(name)
                ),
            ))
        }
    }
}

/// An input that accepts only one edge has no other edge yet.
fn check_input_free(
    graph: &impl GraphRead,
    index: &mut EdgeIndex,
    edge: &FlowObj,
    handles: &Handles,
) -> Result<()> {
    let id = edge.id();
    let target = endpoint(edge, "target");
    let taken = index
        .connections(graph, target)?
        .inputs
        .get(&handles.input)
        .and_then(|ids| ids.iter().filter(|other| *other != id).min());
    let Some(other) = taken else {
        return Ok(());
    };
    let kind = match handles.input.kind {
        InputKind::Field => "field",
        InputKind::LoopOutput => "output",
    };
    Err(error(
        edge,
        ViolationCode::EdgeTargetOccupied,
        format!(
            "{kind} {} of node {} takes one connection and already has {}",
            quoted(&handles.input.name),
            quoted(target),
            quoted(other)
        ),
    ))
}

fn error(edge: &FlowObj, code: ViolationCode, reason: impl std::fmt::Display) -> Error {
    Error::edge(edge.id(), code, reason)
}

fn invalid(edge: &FlowObj, reason: impl std::fmt::Display) -> Error {
    error(edge, ViolationCode::EdgeHandleInvalid, reason)
}

fn not_found(edge: &FlowObj, reason: impl std::fmt::Display) -> Error {
    error(edge, ViolationCode::EdgeHandleNotFound, reason)
}

impl Error {
    /// An edge rule broken by the edge `edge_id`.
    pub fn edge(edge_id: &str, code: ViolationCode, reason: impl fmt::Display) -> Self {
        Self {
            edge_id: Some(edge_id.to_owned()),
            ..Self::invalid_with(
                ErrorCode::Violation(code),
                format!("edge {}: {reason}", quoted(edge_id)),
            )
        }
    }
}
