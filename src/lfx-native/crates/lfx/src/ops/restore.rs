//! The edge fixes a restore takes, from both sides.
//!
//! A revision can hold edges the edge rules refuse, which only the client can
//! fix. The editor's history preview already shows them fixed: it drops the
//! edges whose handles no longer exist and rewrites handles stored in another
//! spelling. A restore refused for such edges is resent with those fixes as
//! operations ([`edge_fixes`], [`fixes_for_edges`]). An edge changes by being
//! deleted and added again, so a rewrite is a `delete_edges` and an `add_edges`.
//!
//! The server checks each fix against the violations the restore would hit
//! ([`check_restore_fixes`]): it must address one of them, in the way that
//! violation's client action allows:
//!
//! - an edge whose handles are invalid or name nothing may be deleted, or
//!   deleted and added again with other handles;
//! - of the edges into an input that takes one, any may be deleted.
//!
//! Anything else is an edit, which takes the save path.

use std::collections::{HashMap, HashSet};

use serde_json::{Map, Value};

use crate::ops::apply::{ApplyOptions, apply_flow_operations};
use crate::ops::canonical::{HANDLE_KEYS, values_equal};
use crate::ops::edges::{endpoint, read_handles};
use crate::ops::entry::EntryExt;
use crate::ops::error::{Error, Result, quoted};
use crate::ops::ops::Operation;
use crate::ops::validate::{Numbers, Resolution, ViolationCode, find_graph_violations};

/// `revision` with `fixes` applied, after checking each one ([`check_restore_fixes`]).
///
/// # Errors
///
/// A fix addresses no violation, or the engine cannot apply it; then the
/// error keeps the engine's code.
pub fn apply_restore_fixes(
    revision: &Value,
    stored: &Value,
    fixes: Vec<Operation>,
) -> Result<Value> {
    check_restore_fixes(revision, stored, &fixes)?;
    apply_flow_operations(revision.clone(), fixes, ApplyOptions::default())
        .map(|(graph, _)| graph)
        .map_err(Error::restore_fix_failed)
}

/// Fail unless every fix addresses a violation restoring `revision` would hit.
///
/// The violations are the ones the save makes: `revision` checked against
/// the `stored` flow it replaces.
///
/// # Errors
///
/// A fix that is not an edge delete or a handle rewrite of an edge a
/// violation allows it for, or a failure finding the violations.
pub fn check_restore_fixes(revision: &Value, stored: &Value, fixes: &[Operation]) -> Result<()> {
    let edges: Vec<&Map<String, Value>> = revision
        .get("edges")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_object)
        .collect();
    let by_id: HashMap<&str, &Map<String, Value>> =
        edges.iter().map(|edge| (edge.id(), *edge)).collect();
    let mut deletable: HashSet<String> = HashSet::new();
    let mut rewritable: HashSet<String> = HashSet::new();
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

    let mut deleted: HashSet<&str> = HashSet::new();
    for fix in fixes {
        match fix {
            Operation::DeleteEdges(ids) => {
                if let Some(id) = ids.iter().find(|id| !deletable.contains(*id)) {
                    return Err(Error::restore_not_allowed(format!(
                        "edge {} breaks no edge rule the client may fix by deleting it",
                        quoted(id)
                    )));
                }
                deleted.extend(ids.iter().map(String::as_str));
            }
            Operation::AddEdges(added) => {
                for edge in added {
                    let id = edge.id();
                    if !rewritable.contains(id) {
                        return Err(Error::restore_not_allowed(format!(
                            "edge {} has no handles the client may rewrite",
                            quoted(id)
                        )));
                    }
                    if !deleted.contains(id) {
                        return Err(Error::restore_not_allowed(format!(
                            "edge {}: a fix adds an edge only after it deletes it",
                            quoted(id)
                        )));
                    }
                    let Some(before) = by_id.get(id) else {
                        return Err(Error::restore_not_allowed(format!(
                            "edge {} does not exist",
                            quoted(id)
                        )));
                    };
                    if !only_handles_differ(before, edge)? {
                        return Err(Error::restore_not_allowed(format!(
                            "edge {}: a fix may only change the edge's handles",
                            quoted(id)
                        )));
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

/// The edges into the input `edge` takes, whose handles are valid since it is occupied.
fn edges_into_the_same_input(
    edges: &[&Map<String, Value>],
    edge: &Map<String, Value>,
) -> Result<HashSet<String>> {
    let taken = read_handles(edge)?.input;
    let target = endpoint(edge, "target");
    Ok(edges
        .iter()
        .filter(|other| endpoint(other, "target") == target)
        // An edge with broken handles takes no input; its own violation says what may fix it.
        .filter(|other| read_handles(other).is_ok_and(|handles| handles.input == taken))
        .map(|other| other.id().to_owned())
        .collect())
}

/// Whether two versions of an edge differ only in their handles, in either
/// form. An edge without a `data` object may gain one that holds only handles.
fn only_handles_differ(before: &Map<String, Value>, after: &Map<String, Value>) -> Result<bool> {
    values_equal(&without_handles(before), &without_handles(after))
}

/// An edge without its handles, and without a `data` that is not an object
/// or holds nothing else.
fn without_handles(edge: &Map<String, Value>) -> Value {
    let mut edge = edge.clone();
    for key in HANDLE_KEYS {
        edge.remove(key);
    }
    let keep_data = match edge.get_mut("data") {
        Some(Value::Object(data)) => {
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
    Value::Object(edge)
}

// --- The editor's side -----------------------------------------------------------------

/// The operations that turn a revision's edges as read (`read`) into the
/// edges its preview shows (`shown`): a `delete_edges` for the edges the
/// preview dropped or whose handles it rewrote, and an `add_edges` that adds
/// the rewritten ones back. Empty when the preview changed no edge.
///
/// # Errors
///
/// A compared handle holds a number that is not finite.
pub fn edge_fixes(read: &[Value], shown: &[Value]) -> Result<Vec<Operation>> {
    let shown_by_id: HashMap<&str, &Map<String, Value>> = shown
        .iter()
        .filter_map(Value::as_object)
        .map(|edge| (edge.id(), edge))
        .collect();
    let mut deleted = Vec::new();
    let mut added = Vec::new();
    for edge in read.iter().filter_map(Value::as_object) {
        let id = edge.id();
        let Some(fixed) = shown_by_id.get(id) else {
            deleted.push(id.to_owned());
            continue;
        };
        let rewritten = with_handles_of(edge, fixed);
        if !values_equal(
            &Value::Object(edge.clone()),
            &Value::Object(rewritten.clone()),
        )? {
            deleted.push(id.to_owned());
            added.push(rewritten);
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

/// `edge` with the handles of `shown`, in both forms. An edge without a
/// `data` object gets one that holds only the handles.
fn with_handles_of(edge: &Map<String, Value>, shown: &Map<String, Value>) -> Map<String, Value> {
    let mut edge = edge.clone();
    let shown_data = shown.get("data").and_then(Value::as_object);
    if !edge.get("data").is_some_and(Value::is_object) {
        edge.insert("data".into(), Value::Object(Map::new()));
    }
    for key in HANDLE_KEYS {
        match shown.get(key) {
            Some(handle) => edge.insert(key.to_owned(), handle.clone()),
            None => edge.remove(key),
        };
        let handle = shown_data.and_then(|data| data.get(key)).cloned();
        if let Some(Value::Object(data)) = edge.get_mut("data") {
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
/// A restore sends fixes only for the edges the server flagged, since the
/// preview also respells handles that break no rule, which the server would
/// refuse as fixes.
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
                let edges: Vec<Map<String, Value>> = edges
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
