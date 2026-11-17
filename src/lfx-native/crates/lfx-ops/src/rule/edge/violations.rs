//! The edge rules broken by the edges that one graph adds, changes or cuts
//! relative to another.

use std::borrow::Cow;

use crate::collection::hash_map::{HashMap, HashSet, IndexMap};
use crate::compare::values_equal;
use crate::flow::model::EntryExt;
use crate::flow::node::NodeRef;
use crate::json::{FlowObj, FlowValue};
use crate::violation::error::{ErrorCode, ErrorKind, Result};
use crate::violation::{PathPart, Violation};

use super::check_edge;
use super::graph::{GraphView, endpoint, list};
use super::handles::{InputKind, edge_changed, read_handles};
use super::index::EdgeIndex;
use super::outputs::index_outputs;

/// The indexes of the edges that `target` adds, changes or cuts relative to `base`.
///
/// A cut edge goes from or into a field or output that `target` removes.
/// Replay deletes that edge, so `target` must not keep it.
pub(crate) fn changed_edges(base: &FlowValue, target: &FlowValue) -> Result<Vec<usize>> {
    let stored: HashMap<&str, &FlowObj> = list(base, "edges")
        .iter()
        .filter_map(FlowValue::as_object)
        .filter_map(|edge| Some((edge.get("id")?.as_str()?, edge)))
        .collect();
    let removed = removed_ends(base, target)?;
    let mut indexes = Vec::new();
    for (index, edge) in list(target, "edges").iter().enumerate() {
        let Some(edge) = edge.as_object() else {
            continue;
        };
        let changed = match stored.get(edge.id()) {
            None => true,
            Some(before) => edge_changed(before, edge)? || is_cut(edge, &removed),
        };
        if changed {
            indexes.push(index);
        }
    }
    Ok(indexes)
}

/// The template fields and outputs a write removes from one node.
#[derive(Debug)]
struct RemovedEnds {
    fields: HashSet<String>,
    outputs: HashSet<String>,
}

/// The template fields and outputs `target` removes from the nodes it keeps, by node id.
fn removed_ends(base: &FlowValue, target: &FlowValue) -> Result<HashMap<String, RemovedEnds>> {
    let stored: HashMap<&str, &FlowObj> = list(base, "nodes")
        .iter()
        .filter_map(FlowValue::as_object)
        .map(|node| (node.id(), node))
        .collect();
    let mut removed = HashMap::default();
    for node in list(target, "nodes")
        .iter()
        .filter_map(FlowValue::as_object)
    {
        let Some(stored) = stored.get(node.id()) else {
            continue;
        };
        let stored = NodeRef::new(stored).map_err(|error| error.into_error("node"))?;
        let node = NodeRef::new(node).map_err(|error| error.into_error("node"))?;
        let fields = removed_fields(stored.template(), node.template());
        let outputs = removed_outputs(stored.body(), node.body(), node.id())?;
        if !fields.is_empty() || !outputs.is_empty() {
            removed.insert(node.id().to_owned(), RemovedEnds { fields, outputs });
        }
    }
    Ok(removed)
}

/// The template keys `before` has and `after` does not.
fn removed_fields(before: &FlowObj, after: &FlowObj) -> HashSet<String> {
    before
        .keys()
        .filter(|key| !after.contains_key(key))
        .map(ToString::to_string)
        .collect()
}

/// The output names `before` has and `after` does not.
fn removed_outputs(before: &FlowObj, after: &FlowObj, node_id: &str) -> Result<HashSet<String>> {
    let Some(outputs_before) = before.get("outputs") else {
        return Ok(HashSet::default());
    };
    let outputs_after = after.get("outputs");
    if let Some(outputs_after) = outputs_after
        && values_equal(outputs_before, outputs_after)?
    {
        return Ok(HashSet::default());
    }
    let kept: HashSet<String> = match outputs_after {
        Some(outputs_after) => index_outputs(Cow::Borrowed(outputs_after), node_id)?
            .names()
            .map(str::to_owned)
            .collect(),
        None => HashSet::default(),
    };
    Ok(index_outputs(Cow::Borrowed(outputs_before), node_id)?
        .names()
        .filter(|name| !kept.contains(*name))
        .map(str::to_owned)
        .collect())
}

/// Whether a kept edge goes from or into a field or output that the write removes.
/// An edge at such a node with handles that do not read also counts.
fn is_cut(edge: &FlowObj, removed: &HashMap<String, RemovedEnds>) -> bool {
    let source = removed.get(endpoint(edge, "source"));
    let target = removed.get(endpoint(edge, "target"));
    if source.is_none() && target.is_none() {
        return false;
    }
    let Ok(handles) = read_handles(edge) else {
        return true;
    };
    if source.is_some_and(|source| source.outputs.contains(&handles.output)) {
        return true;
    }
    target.is_some_and(|target| match handles.input.kind {
        InputKind::Field => target.fields.contains(&handles.input.name),
        InputKind::LoopOutput => target.outputs.contains(&handles.input.name),
    })
}

/// The edge rules broken by the edges `target` adds, changes or cuts relative to `base`.
/// Each violation is reported once, at the edge that breaks the rule.
pub(crate) fn find_edge_violations(base: &FlowValue, target: &FlowValue) -> Result<Vec<Violation>> {
    let indexes = changed_edges(base, target)?;
    if indexes.is_empty() {
        return Ok(Vec::new());
    }
    let view = GraphView::new(target)?;
    let mut edge_index = EdgeIndex::default();
    let edges = list(target, "edges");
    let index_of: HashMap<&str, usize> = edges
        .iter()
        .enumerate()
        .filter_map(|(index, edge)| Some((edge.as_object().map(EntryExt::id)?, index)))
        .collect();
    let mut violations: IndexMap<String, Violation> = IndexMap::default();
    for index in indexes {
        let Some(edge) = edges[index].as_object() else {
            continue;
        };
        let Err(error) = check_edge(&view, &mut edge_index, edge) else {
            continue;
        };
        let (ErrorKind::InvalidOperation, ErrorCode::Violation(code), Some(broken)) =
            (error.kind, error.code, error.edge_id.as_deref())
        else {
            return Err(error);
        };
        if !violations.contains_key(broken) {
            let path = vec![
                "edges".into(),
                index_of.get(broken).copied().unwrap_or(index).into(),
            ];
            violations.insert(
                broken.to_owned(),
                Violation {
                    edge_id: Some(broken.to_owned()),
                    ..Violation::new(code, path, error.message.clone())
                },
            );
        }
    }
    let mut violations: Vec<Violation> = violations.into_values().collect();
    violations.sort_by_key(|violation| match violation.path.get(1) {
        Some(PathPart::Index(index)) => *index,
        _ => 0,
    });
    Ok(violations)
}
