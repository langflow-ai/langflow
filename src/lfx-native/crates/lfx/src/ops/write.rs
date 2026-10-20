//! The engine's part of a save, in one call.
//!
//! A save checks the graphs, repairs them when the request asks for it,
//! derives the operations, and checks that they replay. [`prepare_write`]
//! does all of that, and returns the violations, the fixes and the
//! operations. The caller owns the storage: it numbers the operations and
//! packs them into rows, and keeps the version check, the lock, the check
//! that the stored graph matches its latest revision, and the inserts.

use std::fmt;

use serde_json::{Map, Value};

use crate::ops::diff::derive_flow_operations;
use crate::ops::error::{Error, ErrorKind};
use crate::ops::ops::Operation;
use crate::ops::repair::{Fix, repair_flow_data};
use crate::ops::validate::{Numbers, Violation, find_graph_violations};

/// Fill in a graph that is missing entirely or lacks its collections.
///
/// A flow created without data, or data without `nodes` or `edges`, is an
/// empty graph rather than a broken one, and saying so loses nothing, so it
/// needs no repair request. Anything else that breaks the rules is left for
/// validation to report.
#[must_use]
pub fn normalize_absent_graph(flow: Value) -> Value {
    match flow {
        Value::Null => serde_json::json!({"nodes": [], "edges": []}),
        Value::Object(mut graph) => {
            for key in ["nodes", "edges"] {
                if graph.get(key).is_none_or(Value::is_null) {
                    graph.insert(key.to_owned(), Value::Array(Vec::new()));
                }
            }
            Value::Object(graph)
        }
        other => other,
    }
}

/// Which graph of a save a violation or a fix is about.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Role {
    /// The graph the flow stores, which the save replaces.
    Stored,
    /// The graph the save asks for.
    Submitted,
}

impl Role {
    /// The role as the API names it.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Stored => "stored",
            Self::Submitted => "submitted",
        }
    }
}

/// What a save asks for, beyond the two graphs.
#[derive(Debug, Clone, Copy)]
pub struct WriteOptions {
    /// Whether the flow already has history. Without it, the stored graph is
    /// checked too, and becomes the revision-0 checkpoint.
    pub started: bool,
    /// Repair what breaks the rules and has one fix, instead of refusing.
    pub repair_invalid_graph: bool,
}

/// What a save stores, before the caller numbers the operations.
#[derive(Debug, Clone, PartialEq)]
pub struct PreparedWrite {
    /// The stored graph the operations start from, repaired when it had no
    /// history and broke the rules. It is the revision-0 checkpoint of a flow
    /// without history.
    pub base: Value,
    /// Whether repair changed the stored graph.
    pub stored_repaired: bool,
    /// The graph to store.
    pub target: Value,
    /// Every fix repair made, and the graph it made it in.
    pub repairs: Vec<(Role, Fix)>,
    /// The operations, as recorded. Empty when nothing changed.
    pub operations: Vec<Operation>,
}

impl PreparedWrite {
    /// The fixes as the API reports them.
    #[must_use]
    pub fn repairs_json(&self) -> Value {
        Value::Array(
            self.repairs
                .iter()
                .map(|(role, fix)| {
                    let mut entry = Map::new();
                    entry.insert("graph".into(), Value::from(role.as_str()));
                    if let Value::Object(fix) = fix.to_value() {
                        entry.extend(fix);
                    }
                    Value::Object(entry)
                })
                .collect(),
        )
    }
}

/// Why a save cannot be prepared.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WriteError {
    /// A graph breaks the rules, and repair was not asked for or cannot fix it.
    InvalidGraph {
        /// The graph that breaks them.
        role: Role,
        /// What it breaks.
        violations: Vec<Violation>,
    },
    /// The engine failed. After both graphs pass the rules, this is a defect
    /// in the diff or the engine.
    Engine(Error),
}

impl fmt::Display for WriteError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidGraph { role, violations } => write!(
                f,
                "The {} flow graph breaks {} flow graph rule(s)",
                role.as_str(),
                violations.len()
            ),
            Self::Engine(error) => error.fmt(f),
        }
    }
}

impl std::error::Error for WriteError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Engine(error) => Some(error),
            Self::InvalidGraph { .. } => None,
        }
    }
}

impl From<Error> for WriteError {
    fn from(error: Error) -> Self {
        Self::Engine(error)
    }
}

/// Check, repair and derive a save of `target` over `stored`.
///
/// # Errors
///
/// A graph breaks the rules ([`WriteError::InvalidGraph`]), or the engine
/// fails.
pub fn prepare_write(
    stored: Value,
    target: Value,
    options: &WriteOptions,
) -> Result<PreparedWrite, WriteError> {
    let mut repairs = Vec::new();
    let mut stored_repaired = false;
    let base = if options.started {
        stored
    } else {
        let base = normalize_absent_graph(stored);
        let violations = find_graph_violations(&base, Numbers::Check, None)?;
        if violations.is_empty() {
            base
        } else if !options.repair_invalid_graph {
            return Err(WriteError::InvalidGraph {
                role: Role::Stored,
                violations,
            });
        } else {
            let repaired =
                repair_flow_data(&base, None).map_err(|error| invalid(Role::Stored, error))?;
            stored_repaired = true;
            repairs.extend(repaired.fixes.into_iter().map(|fix| (Role::Stored, fix)));
            repaired.flow_data
        }
    };

    let mut target = normalize_absent_graph(target);
    // Against the stored graph, so the table and edge rules apply to what this
    // write adds or changes, while what it leaves alone is accepted as stored.
    let violations = find_graph_violations(&target, Numbers::Check, Some(&base))?;
    if !violations.is_empty() {
        if !options.repair_invalid_graph {
            return Err(WriteError::InvalidGraph {
                role: Role::Submitted,
                violations,
            });
        }
        let repaired = repair_flow_data(&target, Some(&base))
            .map_err(|error| invalid(Role::Submitted, error))?;
        repairs.extend(repaired.fixes.into_iter().map(|fix| (Role::Submitted, fix)));
        target = repaired.flow_data;
    }

    let derived = derive_flow_operations(base.clone(), &target)?;
    Ok(PreparedWrite {
        base,
        stored_repaired,
        target,
        repairs,
        operations: derived.operations,
    })
}

/// What repair leaves needs the person's choice, so the client fixes it.
fn invalid(role: Role, error: Error) -> WriteError {
    if error.kind == ErrorKind::InvalidGraph && !error.violations.is_empty() {
        WriteError::InvalidGraph {
            role,
            violations: error.violations,
        }
    } else {
        WriteError::Engine(error)
    }
}
