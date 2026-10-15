//! The edge fixes a restore takes, from both sides.
//!
//! A revision can hold edges the edge rules refuse, which only the client can
//! fix. The editor's history preview already shows them fixed: it drops the
//! edges whose handles no longer exist and rewrites handles stored in another
//! spelling. A restore refused for such edges is resent with those fixes as
//! operations ([`edge_fixes`], [`fixes_for_edges`]).
//!
//! The server checks each fix against the violations the restore would hit
//! ([`check_restore_fixes`]): it must address one of them, in the way that
//! violation's client action allows:
//!
//! - an edge whose handles are invalid or name nothing may be deleted, or
//!   have its handles rewritten;
//! - of the edges into an input that takes one, any may be deleted.
//!
//! Anything else is an edit, which takes the save path.

use std::collections::{HashMap, HashSet};

use serde_json::{Map, Value};

use crate::ops::apply::{ApplyOptions, apply_flow_operations};
use crate::ops::canonical::{HANDLE_KEYS, values_equal};
use crate::ops::edges::{edge_id, endpoint, read_handles};
use crate::ops::error::{Error, ErrorCode, ErrorKind, Result, quoted};
use crate::ops::ops::{Change, FieldUpdate, Operation, Segment};
use crate::ops::validate::{Resolution, ViolationCode, find_graph_violations};

fn not_allowed(message: impl Into<String>) -> Error {
    Error {
        kind: ErrorKind::RestoreFixNotAllowed,
        ..Error::invalid_with(ErrorCode::RestoreFixNotAllowed, message)
    }
}

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
        .map_err(|error| Error {
            kind: ErrorKind::RestoreFixNotAllowed,
            message: format!("A fix cannot be applied: {}", error.message),
            ..error
        })
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
        edges.iter().map(|edge| (edge_id(edge), *edge)).collect();
    let mut deletable: HashSet<String> = HashSet::new();
    let mut rewritable: HashSet<String> = HashSet::new();
    for violation in find_graph_violations(revision, true, Some(stored))? {
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

    for fix in fixes {
        match fix {
            Operation::DeleteEdges(ids) => {
                if let Some(id) = ids.iter().find(|id| !deletable.contains(*id)) {
                    return Err(not_allowed(format!(
                        "edge {} breaks no edge rule the client may fix by deleting it",
                        quoted(id)
                    )));
                }
            }
            Operation::UpdateEdges(updates) => {
                for update in updates {
                    if !rewritable.contains(&update.id) {
                        return Err(not_allowed(format!(
                            "edge {} has no handles the client may rewrite",
                            quoted(&update.id)
                        )));
                    }
                    if !by_id
                        .get(update.id.as_str())
                        .is_some_and(|edge| rewrites_handles(update, edge))
                    {
                        return Err(not_allowed(format!(
                            "edge {}: a fix may only set the edge's handles",
                            quoted(&update.id)
                        )));
                    }
                }
            }
            other => {
                return Err(not_allowed(format!(
                    "a fix may only delete edges or rewrite their handles, not {}",
                    other.type_name()
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
        .map(|other| edge_id(other).to_owned())
        .collect())
}

/// Whether `update` sets one of the edge's handles, or its whole `data` when it has none.
fn rewrites_handles(update: &FieldUpdate, edge: &Map<String, Value>) -> bool {
    let Change::Set { value, .. } = &update.change else {
        return false;
    };
    let keys: Option<Vec<&str>> = update.path.iter().map(Segment::as_key).collect();
    match keys.as_deref() {
        Some([key]) if HANDLE_KEYS.contains(key) => true,
        Some(["data", key]) if HANDLE_KEYS.contains(key) => true,
        Some(["data"]) => {
            !edge.get("data").is_some_and(Value::is_object)
                && value.as_object().is_some_and(|value| {
                    value.keys().all(|key| HANDLE_KEYS.contains(&key.as_str()))
                })
        }
        _ => false,
    }
}

// --- The editor's side -----------------------------------------------------------------

/// The operations that turn a revision's edges as read (`read`) into the
/// edges its preview shows (`shown`): a `delete_edges` for the edges the
/// preview dropped, and an `update_edges` for the handles it rewrote. Empty
/// when the preview changed no edge.
///
/// # Errors
///
/// A compared handle holds a number that is not finite.
pub fn edge_fixes(read: &[Value], shown: &[Value]) -> Result<Vec<Operation>> {
    let shown_by_id: HashMap<&str, &Map<String, Value>> = shown
        .iter()
        .filter_map(Value::as_object)
        .map(|edge| (edge_id(edge), edge))
        .collect();
    let mut dropped = Vec::new();
    let mut updates = Vec::new();
    for edge in read.iter().filter_map(Value::as_object) {
        let id = edge_id(edge);
        let Some(fixed) = shown_by_id.get(id) else {
            dropped.push(id.to_owned());
            continue;
        };
        for key in HANDLE_KEYS {
            let (before, after) = (
                edge.get(key).unwrap_or(&Value::Null),
                fixed.get(key).unwrap_or(&Value::Null),
            );
            if !values_equal(before, after)? {
                updates.push(FieldUpdate::set(
                    id,
                    vec![Segment::Key(key.to_owned())],
                    after.clone(),
                ));
            }
        }
        let fixed_data = fixed.get("data").and_then(Value::as_object);
        let handles: Map<String, Value> = HANDLE_KEYS
            .iter()
            .filter_map(|key| Some(((*key).to_owned(), fixed_data?.get(*key)?.clone())))
            .collect();
        let Some(Value::Object(data)) = edge.get("data") else {
            updates.push(FieldUpdate::set(
                id,
                vec![Segment::Key("data".into())],
                Value::Object(handles),
            ));
            continue;
        };
        for key in HANDLE_KEYS {
            let (before, after) = (
                data.get(key).unwrap_or(&Value::Null),
                handles.get(key).unwrap_or(&Value::Null),
            );
            if !values_equal(before, after)? {
                let path = vec![Segment::Key("data".into()), Segment::Key(key.to_owned())];
                updates.push(FieldUpdate::set(id, path, after.clone()));
            }
        }
    }
    let mut fixes = Vec::new();
    if !dropped.is_empty() {
        fixes.push(Operation::DeleteEdges(dropped));
    }
    if !updates.is_empty() {
        fixes.push(Operation::UpdateEdges(updates));
    }
    Ok(fixes)
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
            Operation::UpdateEdges(updates) => {
                let updates: Vec<FieldUpdate> = updates
                    .iter()
                    .filter(|update| edge_ids.contains(update.id.as_str()))
                    .cloned()
                    .collect();
                if !updates.is_empty() {
                    kept.push(Operation::UpdateEdges(updates));
                }
            }
            _ => {}
        }
    }
    kept
}
