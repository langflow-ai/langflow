//! [`GraphPlain`]: a parsed flow graph, to run many checks on it.
//!
//! A save validates the graph it receives, may repair it, compares it with
//! the stored graph, diffs the two, and hashes the result. Each of those calls
//! on its own reads its graphs again: a Python dict of a 320-node flow takes
//! about 10 ms to read. A plain graph is read once and kept as it is, with no
//! index and no check, so each call costs only its own work.
//!
//! A plain graph remembers which checks it has passed, and a later call that
//! needs the same check skips it. The graph cannot change, so a check that
//! passed once stays passed.

use std::sync::atomic::{AtomicBool, Ordering};

use crate::value::Value;

use crate::ops::canonical;
use crate::ops::diff::{Derived, derive_checked};
use crate::ops::error::Result;
use crate::ops::repair::{Fix, repair_flow_data};
use crate::ops::state::GraphState;
use crate::ops::validate::{Numbers, Violation, find_graph_violations, validate_flow_data};

/// A parsed flow graph that no rule has been checked on yet.
#[derive(Debug)]
pub struct GraphPlain {
    flow: Value,
    /// The graph has no structural violation.
    structure: AtomicBool,
    /// The graph has no violation at all, numbers that are not finite included.
    full: AtomicBool,
}

impl GraphPlain {
    /// Keep a graph as it is, without checking it.
    #[must_use]
    pub fn new(flow: Value) -> Self {
        Self {
            flow,
            structure: AtomicBool::new(false),
            full: AtomicBool::new(false),
        }
    }

    /// A graph that has passed every check.
    fn checked(flow: Value) -> Self {
        Self {
            flow,
            structure: AtomicBool::new(true),
            full: AtomicBool::new(true),
        }
    }

    /// The graph.
    #[must_use]
    pub fn as_value(&self) -> &Value {
        &self.flow
    }

    /// The graph, without copying it.
    #[must_use]
    pub fn into_value(self) -> Value {
        self.flow
    }

    fn passed(&self, numbers: Numbers) -> bool {
        match numbers {
            Numbers::Check => self.full.load(Ordering::Relaxed),
            Numbers::Skip => self.structure.load(Ordering::Relaxed),
        }
    }

    fn pass(&self, numbers: Numbers) {
        self.structure.store(true, Ordering::Relaxed);
        if numbers == Numbers::Check {
            self.full.store(true, Ordering::Relaxed);
        }
    }

    /// Fail with the graph's violations, unless the check passed before.
    fn require(&self, numbers: Numbers, context: &str) -> Result<()> {
        if !self.passed(numbers) {
            validate_flow_data(&self.flow, numbers, context, None)?;
            self.pass(numbers);
        }
        Ok(())
    }

    /// Every rule the graph breaks, against the stored graph a write replaces
    /// when given: what [`find_graph_violations`] finds.
    ///
    /// # Errors
    ///
    /// What [`find_graph_violations`] fails with.
    pub fn violations(&self, base: Option<&Self>, numbers: Numbers) -> Result<Vec<Violation>> {
        if base.is_none() && self.passed(numbers) {
            return Ok(Vec::new());
        }
        let violations = find_graph_violations(&self.flow, numbers, base.map(Self::as_value))?;
        // The rules against a base include the rules of the graph alone.
        if violations.is_empty() {
            self.pass(numbers);
        }
        Ok(violations)
    }

    /// A copy with every violation that has one fix fixed, and the fixes:
    /// what [`repair_flow_data`] returns.
    ///
    /// # Errors
    ///
    /// What [`repair_flow_data`] fails with.
    pub fn repair(&self, base: Option<&Self>) -> Result<(Self, Vec<Fix>)> {
        let repaired = repair_flow_data(&self.flow, base.map(Self::as_value))?;
        // Repair checks every rule on what it returns.
        Ok((Self::checked(repaired.flow_data), repaired.fixes))
    }

    /// The SHA-256 hex digest of the graph's canonical form.
    ///
    /// # Errors
    ///
    /// A number that is not finite as JavaScript reads it.
    pub fn graph_hash(&self) -> Result<String> {
        canonical::graph_hash(&self.flow)
    }

    /// Whether two graphs are the same graph.
    ///
    /// # Errors
    ///
    /// A number that is not finite as JavaScript reads it, in either graph.
    pub fn equals(&self, other: &Self) -> Result<bool> {
        canonical::graphs_equal(&self.flow, &other.flow)
    }

    /// The operations that turn this graph into `target`, checked by replay,
    /// as [`crate::ops::derive_flow_operations`] derives them.
    ///
    /// # Errors
    ///
    /// A graph breaks the rules, or the operations do not replay to `target`.
    pub fn ops_diff(&self, target: &Self) -> Result<Derived> {
        self.require(Numbers::Skip, "flow.data")?;
        target.require(Numbers::Check, "target flow.data")?;
        derive_checked(self.flow.clone(), &target.flow)
    }

    /// A [`GraphState`] of a copy of the graph, as [`GraphState::new`] loads
    /// it, without checking the structure again when a check passed.
    ///
    /// # Errors
    ///
    /// The graph breaks a structural rule.
    pub fn to_state(&self) -> Result<GraphState> {
        self.require(Numbers::Skip, "flow.data")?;
        GraphState::from_checked(self.flow.clone())
    }

    /// A [`GraphState`] of the graph, without copying it.
    ///
    /// # Errors
    ///
    /// The graph breaks a structural rule.
    pub fn into_state(self) -> Result<GraphState> {
        self.require(Numbers::Skip, "flow.data")?;
        GraphState::from_checked(self.flow)
    }
}

#[cfg(test)]
mod tests {
    use crate::json;

    use super::*;
    use crate::ops::derive_flow_operations;

    /// A graph of one node, with `value` in its one field.
    fn graph(value: &Value) -> Value {
        let template = json!({"t": {"value": value, "type": "str"}});
        json!({"nodes": [{"id": "a", "data": {"node": {"template": template}}}], "edges": []})
    }

    #[test]
    fn calls_answer_as_the_functions_on_the_graph_do() {
        let (base, target) = (graph(&json!("x")), graph(&json!("y")));
        let (plain_base, plain_target) = (
            GraphPlain::new(base.clone()),
            GraphPlain::new(target.clone()),
        );
        assert_eq!(
            plain_base.ops_diff(&plain_target).unwrap(),
            derive_flow_operations(base.clone(), &target).unwrap()
        );
        assert!(!plain_base.equals(&plain_target).unwrap());
        assert!(plain_base.equals(&GraphPlain::new(base.clone())).unwrap());
        assert_eq!(
            plain_target.graph_hash().unwrap(),
            canonical::graph_hash(&target).unwrap()
        );
        assert_eq!(
            plain_base.to_state().unwrap().to_value(),
            GraphState::new(base).unwrap().to_value()
        );
    }

    #[test]
    fn a_check_that_passed_is_not_run_again() {
        let plain = GraphPlain::new(graph(&json!(1)));
        assert!(!plain.passed(Numbers::Skip));
        assert_eq!(plain.violations(None, Numbers::Skip).unwrap(), []);
        assert!(plain.passed(Numbers::Skip) && !plain.passed(Numbers::Check));
        assert_eq!(plain.violations(None, Numbers::Check).unwrap(), []);
        assert!(plain.passed(Numbers::Check));
        plain.to_state().unwrap();
    }

    #[test]
    fn a_graph_that_breaks_a_rule_stays_unchecked() {
        let broken = GraphPlain::new(json!({"nodes": [{"data": {}}], "edges": []}));
        assert_ne!(broken.violations(None, Numbers::Skip).unwrap(), []);
        assert!(!broken.passed(Numbers::Skip));
        assert_eq!(
            broken.to_state().unwrap_err(),
            GraphState::new(broken.as_value().clone()).unwrap_err()
        );
        let (repaired, fixes) = broken.repair(None).unwrap();
        assert_ne!(fixes, []);
        assert!(repaired.passed(Numbers::Check));
        repaired.into_state().unwrap();
    }

    #[test]
    fn a_target_with_a_number_that_is_not_finite_is_refused() {
        let base = GraphPlain::new(graph(&json!(1)));
        let target = GraphPlain::new(graph(&serde_json::from_str("1e400").unwrap()));
        // The structure passes, but a target is checked fully.
        assert_eq!(target.violations(None, Numbers::Skip).unwrap(), []);
        let error = base.ops_diff(&target).unwrap_err();
        assert_eq!(
            error,
            derive_flow_operations(base.as_value().clone(), target.as_value()).unwrap_err()
        );
        assert!(!target.passed(Numbers::Check));
    }
}
