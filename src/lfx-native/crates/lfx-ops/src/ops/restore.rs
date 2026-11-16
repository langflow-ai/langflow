//! Edge fixes for a restore: the client makes them, and the server checks them.
//!
//! A fix may delete an edge whose handles are invalid or name nothing, or add it
//! back with other handles. It may also delete any edge into an input that
//! accepts only one edge.

use crate::data::maps::{HashMap, HashSet};
use crate::data::value::{AnyMap, AnyValue};

use crate::models::canonical::values_equal;
use crate::models::edges::{endpoint, read_handles};
use crate::models::entry::EntryExt;
use crate::models::error::{Error, Result, quoted};
use crate::models::handle::HANDLE_KEYS;
use crate::models::operation::{Edge, Operation};
use crate::models::validate::{Numbers, Resolution, ViolationCode, find_graph_violations};
use crate::ops::ApplyOptions;
use crate::ops::apply::apply_flow_operations;

/// `revision` with `fixes` applied, after checking each one ([`check_restore_fixes`]).
///
/// # Errors
///
/// A fix addresses no violation, or the engine cannot apply it.
pub fn apply_restore_fixes(
    revision: &AnyValue,
    stored: &AnyValue,
    fixes: Vec<Operation>,
) -> Result<AnyValue> {
    check_restore_fixes(revision, stored, &fixes)?;
    apply_flow_operations(revision.clone(), fixes, ApplyOptions::default())
        .map(|(graph, _)| graph)
        .map_err(Error::restore_fix_failed)
}

/// Fail unless each fix addresses a violation of `revision` against `stored`.
///
/// # Errors
///
/// A fix addresses no violation, or the violations cannot be found.
pub fn check_restore_fixes(
    revision: &AnyValue,
    stored: &AnyValue,
    fixes: &[Operation],
) -> Result<()> {
    let edges: Vec<&AnyMap> = revision
        .get("edges")
        .and_then(AnyValue::as_array)
        .into_iter()
        .flatten()
        .filter_map(AnyValue::as_object)
        .collect();
    let by_id: HashMap<&str, &AnyMap> = edges.iter().map(|edge| (edge.id(), *edge)).collect();
    let mut deletable: HashSet<String> = HashSet::default();
    let mut rewritable: HashSet<String> = HashSet::default();
    for violation in find_graph_violations(revision, Numbers::Check, Some(stored))? {
        let Some(id) = violation.edge_id.as_deref() else {
            continue;
        };
        if violation.code.resolution() != Resolution::Manual {
            continue;
        }
        deletable.insert(id.to_owned());
        match violation.code {
            ViolationCode::EdgeHandleInvalid | ViolationCode::EdgeHandleNotFound => {
                rewritable.insert(id.to_owned());
            }
            ViolationCode::EdgeTargetOccupied => {
                if let Some(edge) = by_id.get(id) {
                    deletable.extend(edges_into_the_same_input(&edges, edge)?);
                }
            }
            _ => {}
        }
    }

    let refused =
        |id: &str, why: &str| Error::restore_not_allowed(format!("edge {}{why}", quoted(id)));
    let mut deleted: HashSet<&str> = HashSet::default();
    for fix in fixes {
        match fix {
            Operation::DeleteEdges(ids) => {
                if let Some(id) = ids.iter().find(|id| !deletable.contains(*id)) {
                    return Err(refused(
                        id,
                        " breaks no edge rule the client may fix by deleting it",
                    ));
                }
                deleted.extend(ids.iter().map(String::as_str));
            }
            Operation::AddEdges(added) => {
                for edge in added {
                    let id = edge.id();
                    if !rewritable.contains(id) {
                        return Err(refused(id, " has no handles the client may rewrite"));
                    }
                    if !deleted.contains(id) {
                        return Err(refused(id, ": a fix adds an edge only after it deletes it"));
                    }
                    let Some(before) = by_id.get(id) else {
                        return Err(refused(id, " does not exist"));
                    };
                    if !only_handles_differ(before, edge.as_map())? {
                        return Err(refused(id, ": a fix may only change the edge's handles"));
                    }
                }
            }
            other => {
                return Err(Error::restore_not_allowed(format!(
                    "a fix may only delete edges, or add back an edge it deleted with other handles, not {}",
                    other.kind().as_str()
                )));
            }
        }
    }
    Ok(())
}

/// The ids of the edges into the same input as `edge`.
fn edges_into_the_same_input(edges: &[&AnyMap], edge: &AnyMap) -> Result<HashSet<String>> {
    let taken = read_handles(edge)?.input;
    let target = endpoint(edge, "target");
    Ok(edges
        .iter()
        .filter(|other| endpoint(other, "target") == target)
        // An edge with broken handles goes into no input. Its own violation covers it.
        .filter(|other| read_handles(other).is_ok_and(|handles| handles.input == taken))
        .map(|other| other.id().to_owned())
        .collect())
}

/// Whether two versions of an edge differ only in their handles.
fn only_handles_differ(before: &AnyMap, after: &AnyMap) -> Result<bool> {
    values_equal(&without_handles(before), &without_handles(after))
}

/// An edge without its handles, and without a `data` that is not an object
/// or holds nothing else.
fn without_handles(edge: &AnyMap) -> AnyValue {
    let mut edge = edge.clone();
    for key in HANDLE_KEYS {
        edge.remove(key);
    }
    let keep_data = match edge.get_mut("data") {
        Some(AnyValue::Object(data)) => {
            for key in HANDLE_KEYS {
                data.remove(key);
            }
            !data.is_empty()
        }
        _ => false,
    };
    if !keep_data {
        edge.remove("data");
    }
    AnyValue::Object(edge)
}

// --- The editor's side -----------------------------------------------------------------

/// The operations that change the `read` edges into the `shown` edges.
/// A rewritten edge is deleted and added back.
///
/// # Errors
///
/// A handle holds a number that is not finite, or a rewritten edge is invalid.
pub fn edge_fixes(read: &[AnyValue], shown: &[AnyValue]) -> Result<Vec<Operation>> {
    let shown_by_id: HashMap<&str, &AnyMap> = shown
        .iter()
        .filter_map(AnyValue::as_object)
        .map(|edge| (edge.id(), edge))
        .collect();
    let mut deleted = Vec::new();
    let mut added = Vec::new();
    for edge in read.iter().filter_map(AnyValue::as_object) {
        let id = edge.id();
        let Some(fixed) = shown_by_id.get(id) else {
            deleted.push(id.to_owned());
            continue;
        };
        let rewritten = with_handles_of(edge, fixed);
        if !values_equal(
            &AnyValue::Object(edge.clone()),
            &AnyValue::Object(rewritten.clone()),
        )? {
            deleted.push(id.to_owned());
            added.push(Edge::try_from(rewritten)?);
        }
    }
    let mut fixes = Vec::new();
    if !deleted.is_empty() {
        fixes.push(Operation::DeleteEdges(deleted));
    }
    if !added.is_empty() {
        fixes.push(Operation::AddEdges(added));
    }
    Ok(fixes)
}

/// `edge` with the handles of `shown`, at the top level and in `data`.
fn with_handles_of(edge: &AnyMap, shown: &AnyMap) -> AnyMap {
    let mut edge = edge.clone();
    let shown_data = shown.get("data").and_then(AnyValue::as_object);
    if !edge.get("data").is_some_and(AnyValue::is_object) {
        edge.insert("data".into(), AnyValue::Object(AnyMap::new()));
    }
    for key in HANDLE_KEYS {
        match shown.get(key) {
            Some(handle) => edge.insert(key.to_owned(), handle.clone()),
            None => edge.remove(key),
        };
        let handle = shown_data.and_then(|data| data.get(key)).cloned();
        if let Some(AnyValue::Object(data)) = edge.get_mut("data") {
            match handle {
                Some(handle) => data.insert(key.to_owned(), handle),
                None => data.remove(key),
            };
        }
    }
    edge
}

/// The part of `fixes` that touches the given edges.
///
/// The preview also respells valid handles. The server refuses those as fixes.
#[must_use]
pub fn fixes_for_edges(fixes: &[Operation], edge_ids: &[String]) -> Vec<Operation> {
    let edge_ids: HashSet<&str> = edge_ids.iter().map(String::as_str).collect();
    let mut kept = Vec::new();
    for fix in fixes {
        match fix {
            Operation::DeleteEdges(ids) => {
                let ids: Vec<String> = ids
                    .iter()
                    .filter(|id| edge_ids.contains(id.as_str()))
                    .cloned()
                    .collect();
                if !ids.is_empty() {
                    kept.push(Operation::DeleteEdges(ids));
                }
            }
            Operation::AddEdges(edges) => {
                let edges: Vec<Edge> = edges
                    .iter()
                    .filter(|edge| edge_ids.contains(edge.id()))
                    .cloned()
                    .collect();
                if !edges.is_empty() {
                    kept.push(Operation::AddEdges(edges));
                }
            }
            _ => {}
        }
    }
    kept
}
