//! Validation: the invariants, which every stored flow follows, and the
//! rules, which apply only to what a write adds or changes relative to the
//! stored graph (`base`). Example: a stored table input without row ids stays
//! valid until a write changes it.

use crate::json::FlowValue;

use crate::invariant::graph::{not_an_object, structure_violations};
use crate::invariant::number::non_finite_violations;
use crate::rule::edge::find_edge_violations;
use crate::rule::list::{find_list_position_violations, find_table_violations};
use crate::violation::error::{Error, Result};
pub use crate::violation::{GraphPath, PathPart, Resolution, Violation, ViolationCode};

/// Whether validation reads every value for numbers that are not finite.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Numbers {
    /// `UpdateTarget` every value. A graph from outside is checked this way.
    Check,
    /// Skip that check. Stored values were checked when they were written.
    Skip,
}

/// Each rule `flow` breaks, in graph order.
///
/// With `base`, it also checks the tables, lists and edges that `flow` adds or
/// changes. For a new flow, pass an empty graph as `base`.
///
/// # Errors
///
/// An edge check fails for a reason that is not a violation.
pub fn find_graph_violations(
    flow: &FlowValue,
    numbers: Numbers,
    base: Option<&FlowValue>,
) -> Result<Vec<Violation>> {
    let FlowValue::Object(graph) = flow else {
        return Ok(vec![not_an_object()]);
    };
    let mut violations = structure_violations(graph);
    if let Some(base) = base
        && graph.get("nodes").is_some_and(FlowValue::is_array)
    {
        let structural = violations.is_empty();
        violations.extend(find_table_violations(base, flow)?);
        violations.extend(find_list_position_violations(base, flow)?);
        if structural {
            violations.extend(find_edge_violations(base, flow)?);
        }
    }
    if numbers == Numbers::Check {
        non_finite_violations(flow, &mut Vec::new(), &mut violations);
    }
    Ok(violations)
}

/// Fail with every violation `flow` has, if it has any.
///
/// # Errors
///
/// The graph has violations, or [`find_graph_violations`] fails.
pub fn validate_flow_data(
    flow: &FlowValue,
    numbers: Numbers,
    context: &str,
    base: Option<&FlowValue>,
) -> Result<()> {
    violations_error(find_graph_violations(flow, numbers, base)?, context)
}

/// Fail with `violations`, if there are any. The message names the first one.
///
/// # Errors
///
/// An invalid graph error listing the violations.
fn violations_error(violations: Vec<Violation>, context: &str) -> Result<()> {
    let Some(first) = violations.first() else {
        return Ok(());
    };
    let location = if first.path.is_empty() {
        "<root>".to_owned()
    } else {
        first
            .path
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join(".")
    };
    let more = if violations.len() > 1 {
        format!(" (and {} more)", violations.len() - 1)
    } else {
        String::new()
    };
    Err(Error::graph(
        format!("{context}: {} at {location}{more}", first.message),
        violations,
    ))
}
