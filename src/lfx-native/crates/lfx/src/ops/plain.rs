//! [`GraphPlain`]: a parsed flow graph, to run many checks on it.
//!
//! A save validates the graph it receives, may repair it, compares it with
//! the stored graph, diffs the two, and hashes the result. Each of those calls
//! on its own reads its graphs again, and reading a large Python dict is
//! not cheap. A plain graph is read once and kept as it is, with no
//! index and no check, so each call costs only its own work.
//!
//! A plain graph remembers which checks it has passed, and a later call that
//! needs the same check skips it. The graph cannot change, so a check that
//! passed once stays passed. Full checks against one base keep a separate
//! lifetime token for that base, so repair can reuse a successful check
//! without retaining the base graph or confusing it with a later allocation.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, PoisonError};

use crate::value::AnyValue;

use crate::ops::canonical;
use crate::ops::diff::{Derived, derive_checked};
use crate::ops::error::Result;
use crate::ops::repair::{Fix, repair_flow_data};
use crate::ops::validate::{Numbers, Violation, find_graph_violations, validate_flow_data};

/// A parsed flow graph that no rule has been checked on yet.
#[derive(Debug)]
pub struct GraphPlain {
    flow: AnyValue,
    /// The graph has no structural violation.
    structure: AtomicBool,
    /// The graph has no violation at all, numbers that are not finite included.
    full: AtomicBool,
    /// A lifetime token for this immutable value and its checked copies.
    identity: Arc<()>,
    /// The one base against which every rule passed. This retains only its
    /// token, never its graph. Holding the token prevents address reuse.
    clean_against: Mutex<Option<Arc<()>>>,
}

impl GraphPlain {
    /// Keep a graph as it is, without checking it.
    #[must_use]
    pub fn new(flow: AnyValue) -> Self {
        Self {
            flow,
            structure: AtomicBool::new(false),
            full: AtomicBool::new(false),
            identity: Arc::new(()),
            clean_against: Mutex::new(None),
        }
    }

    /// A graph that has passed every check, including those against `base`.
    fn checked(flow: AnyValue, base: Option<&Self>) -> Self {
        Self {
            flow,
            structure: AtomicBool::new(true),
            full: AtomicBool::new(true),
            identity: Arc::new(()),
            clean_against: Mutex::new(base.map(|base| Arc::clone(&base.identity))),
        }
    }

    /// A checked handle to this same immutable value. Base checks depend on
    /// the value, so its aliases may share their identity without allocating.
    fn checked_copy(&self, base: Option<&Self>) -> Self {
        Self {
            flow: self.flow.clone(),
            structure: AtomicBool::new(true),
            full: AtomicBool::new(true),
            identity: Arc::clone(&self.identity),
            clean_against: Mutex::new(base.map(|base| Arc::clone(&base.identity))),
        }
    }

    /// The graph.
    #[must_use]
    pub fn as_value(&self) -> &AnyValue {
        &self.flow
    }

    /// The graph, without copying it.
    #[must_use]
    pub fn into_value(self) -> AnyValue {
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

    /// Only a full check against this exact immutable base permits repair
    /// to return the graph unchanged. Other checks still run their own rules.
    fn passed_against(&self, base: Option<&Self>) -> bool {
        let Some(base) = base else {
            return self.passed(Numbers::Check);
        };
        self.clean_against
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .as_ref()
            .is_some_and(|identity| Arc::ptr_eq(identity, &base.identity))
    }

    fn pass_against(&self, base: &Self) {
        *self
            .clean_against
            .lock()
            .unwrap_or_else(PoisonError::into_inner) = Some(Arc::clone(&base.identity));
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
        if (base.is_none() && self.passed(numbers))
            || (numbers == Numbers::Check && self.passed_against(base))
        {
            return Ok(Vec::new());
        }
        let violations = find_graph_violations(&self.flow, numbers, base.map(Self::as_value))?;
        // The rules against a base include the rules of the graph alone.
        if violations.is_empty() {
            self.pass(numbers);
            if numbers == Numbers::Check
                && let Some(base) = base
            {
                self.pass_against(base);
            }
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
        if self.passed_against(base) {
            return Ok((self.checked_copy(base), Vec::new()));
        }
        let repaired = repair_flow_data(&self.flow, base.map(Self::as_value))?;
        // Repair checks every rule on what it returns.
        Ok((Self::checked(repaired.flow_data, base), repaired.fixes))
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
}

#[cfg(test)]
mod tests {
    use crate::json;

    use super::*;
    use crate::ops::derive_flow_operations;

    /// A graph of one node, with `value` in its one field.
    fn graph(value: &AnyValue) -> AnyValue {
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
    }

    #[test]
    fn a_check_that_passed_is_not_run_again() {
        let plain = GraphPlain::new(graph(&json!(1)));
        assert!(!plain.passed(Numbers::Skip));
        assert_eq!(plain.violations(None, Numbers::Skip).unwrap(), []);
        assert!(plain.passed(Numbers::Skip) && !plain.passed(Numbers::Check));
        assert_eq!(plain.violations(None, Numbers::Check).unwrap(), []);
        assert!(plain.passed(Numbers::Check));
    }

    #[test]
    fn a_graph_that_breaks_a_rule_stays_unchecked() {
        let broken = GraphPlain::new(json!({"nodes": [{"data": {}}], "edges": []}));
        assert_ne!(broken.violations(None, Numbers::Skip).unwrap(), []);
        assert!(!broken.passed(Numbers::Skip));
        let (repaired, fixes) = broken.repair(None).unwrap();
        assert_ne!(fixes, []);
        assert!(repaired.passed(Numbers::Check));
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

    fn legacy_table() -> AnyValue {
        json!({"nodes":[{"id":"n","data":{"node":{"template":{"t":{
            "type":"table", "_input_type":"TableInput", "value":[{"v":1}]
        }}}}}],"edges":[]})
    }

    fn reserved_columns() -> AnyValue {
        let mut value = legacy_table();
        value["nodes"][0]["data"]["node"]["template"]["t"]["value"] =
            json!([{"__id__":"row", "__pos__":1, "v":1}]);
        value["nodes"][0]["data"]["node"]["template"]["t"]["table_schema"] =
            json!([{"name":"__pos__"}, {"name":"__id__"}]);
        value
    }

    #[test]
    fn full_validation_against_the_same_base_makes_repair_a_shared_copy() {
        let base = GraphPlain::new(graph(&json!(0)));
        let target = GraphPlain::new(graph(&json!(1)));
        assert_eq!(target.violations(Some(&base), Numbers::Check).unwrap(), []);
        assert!(target.passed_against(Some(&base)));
        let (repaired, fixes) = target.repair(Some(&base)).unwrap();
        assert_eq!(fixes, []);
        assert!(std::ptr::eq(
            target.as_value().get("nodes").unwrap(),
            repaired.as_value().get("nodes").unwrap(),
        ));
        assert_eq!(target.violations(Some(&base), Numbers::Check).unwrap(), []);
    }

    #[test]
    fn a_different_base_still_checks_and_repairs_new_table_rows() {
        let value = legacy_table();
        let unchanged = GraphPlain::new(value.clone());
        let added = GraphPlain::new(json!({"nodes":[], "edges":[]}));
        let target = GraphPlain::new(value);
        assert_eq!(
            target.violations(Some(&unchanged), Numbers::Check).unwrap(),
            []
        );
        assert_ne!(target.violations(Some(&added), Numbers::Check).unwrap(), []);
        assert!(!target.passed_against(Some(&added)));
        let (repaired, fixes) = target.repair(Some(&added)).unwrap();
        assert_eq!(fixes.len(), 2);
        assert!(
            repaired.as_value()["nodes"][0]["data"]["node"]["template"]["t"]["value"][0]["__id__"]
                .is_string()
        );
        // Repair neither changes the original nor invalidates its proof for the other base.
        assert!(
            target.as_value()["nodes"][0]["data"]["node"]["template"]["t"]["value"][0]["__id__"]
                .is_null()
        );
        assert!(target.passed_against(Some(&unchanged)));
    }

    #[test]
    fn a_structural_check_does_not_authorize_full_repair() {
        let base = GraphPlain::new(graph(&json!(1)));
        let value = graph(&serde_json::from_str("1e400").unwrap());
        let target = GraphPlain::new(value);
        assert_eq!(target.violations(Some(&base), Numbers::Skip).unwrap(), []);
        assert!(!target.passed_against(Some(&base)));
        let (repaired, fixes) = target.repair(Some(&base)).unwrap();
        assert_eq!(fixes.len(), 1);
        assert_eq!(
            repaired.as_value()["nodes"][0]["data"]["node"]["template"]["t"]["value"],
            AnyValue::Null
        );
    }

    #[test]
    fn a_standalone_check_does_not_authorize_a_base_specific_repair() {
        let target = GraphPlain::new(legacy_table());
        let added = GraphPlain::new(json!({"nodes":[], "edges":[]}));
        assert_eq!(target.violations(None, Numbers::Check).unwrap(), []);
        assert!(!target.passed_against(Some(&added)));
        assert_eq!(target.repair(Some(&added)).unwrap().1.len(), 2);
    }

    #[test]
    fn an_invalid_graph_never_gets_a_base_success_token() {
        let base = GraphPlain::new(json!({"nodes":[], "edges":[]}));
        let target = GraphPlain::new(json!({"nodes":[{"data":{}}], "edges":[]}));
        assert_ne!(target.violations(Some(&base), Numbers::Check).unwrap(), []);
        assert!(!target.passed_against(Some(&base)));
        assert_ne!(target.repair(Some(&base)).unwrap().1, []);
        assert!(!target.passed_against(Some(&base)));
    }

    #[test]
    fn cached_validation_keeps_manual_error_order_for_another_base() {
        let value = reserved_columns();
        let same = GraphPlain::new(value.clone());
        let added = GraphPlain::new(json!({"nodes":[], "edges":[]}));
        let target = GraphPlain::new(value);
        assert_eq!(target.violations(Some(&same), Numbers::Check).unwrap(), []);
        let expected = repair_flow_data(target.as_value(), Some(added.as_value())).unwrap_err();
        let actual = target.repair(Some(&added)).unwrap_err();
        assert_eq!(actual, expected);
        assert_eq!(actual.violations.len(), 2);
    }

    #[test]
    fn base_tokens_do_not_retain_graphs_or_alias_later_bases() {
        let target = GraphPlain::new(legacy_table());
        let base = Arc::new(GraphPlain::new(legacy_table()));
        let weak_graph = Arc::downgrade(&base);
        let weak_token = Arc::downgrade(&base.identity);
        assert_eq!(target.violations(Some(&base), Numbers::Check).unwrap(), []);
        drop(base);
        assert!(weak_graph.upgrade().is_none());
        // The cached token keeps its allocation alive after its graph is gone.
        let old_token = weak_token.upgrade().unwrap();
        let new_base = GraphPlain::new(json!({"nodes":[], "edges":[]}));
        assert!(!Arc::ptr_eq(&old_token, &new_base.identity));
        drop(old_token);
        assert!(!target.passed_against(Some(&new_base)));
        assert_eq!(target.repair(Some(&new_base)).unwrap().1.len(), 2);
        let replacement = GraphPlain::new(legacy_table());
        assert_eq!(
            target
                .violations(Some(&replacement), Numbers::Check)
                .unwrap(),
            []
        );
        // One replacement drops the prior token. The cache cannot grow with old bases.
        assert!(weak_token.upgrade().is_none());
    }

    #[test]
    fn concurrent_base_checks_cannot_authorize_a_different_base() {
        let target = GraphPlain::new(reserved_columns());
        let a = GraphPlain::new(reserved_columns());
        let mut changed_view = reserved_columns();
        changed_view["zoom"] = json!(2);
        let c = GraphPlain::new(changed_view);
        let invalid = GraphPlain::new(json!({"nodes":[], "edges":[]}));
        let barrier = std::sync::Barrier::new(3);
        std::thread::scope(|scope| {
            for base in [&a, &c] {
                let target = &target;
                let barrier = &barrier;
                scope.spawn(move || {
                    barrier.wait();
                    for _ in 0..100 {
                        assert_eq!(target.violations(Some(base), Numbers::Check).unwrap(), []);
                        assert_eq!(target.repair(Some(base)).unwrap().1, []);
                    }
                });
            }
            scope.spawn(|| {
                barrier.wait();
                for _ in 0..100 {
                    assert_ne!(
                        target.violations(Some(&invalid), Numbers::Check).unwrap(),
                        []
                    );
                    assert_eq!(
                        target.repair(Some(&invalid)).unwrap_err().violations.len(),
                        2
                    );
                }
            });
        });
        assert!(!target.passed_against(Some(&invalid)));
    }

    #[test]
    fn a_returned_clean_graph_keeps_its_base_proof_without_retaining_the_base_graph() {
        let target = GraphPlain::new(reserved_columns());
        let base = Arc::new(GraphPlain::new(reserved_columns()));
        let weak_graph = Arc::downgrade(&base);
        assert_eq!(target.violations(Some(&base), Numbers::Check).unwrap(), []);
        let (repaired, fixes) = target.repair(Some(&base)).unwrap();
        assert_eq!(fixes, []);
        assert!(repaired.passed_against(Some(&base)));
        assert_eq!(
            repaired.violations(Some(&base), Numbers::Check).unwrap(),
            []
        );
        let (again, fixes) = repaired.repair(Some(&base)).unwrap();
        assert_eq!(fixes, []);
        assert!(std::ptr::eq(
            repaired.as_value().get("nodes").unwrap(),
            again.as_value().get("nodes").unwrap()
        ));
        let other = GraphPlain::new(json!({"nodes":[], "edges":[]}));
        assert!(!repaired.passed_against(Some(&other)));
        assert_eq!(
            repaired.repair(Some(&other)).unwrap_err().violations.len(),
            2
        );
        drop(base);
        assert!(weak_graph.upgrade().is_none());
    }

    #[test]
    fn a_changed_repair_keeps_the_proof_for_its_repaired_value() {
        let target = GraphPlain::new(legacy_table());
        let base = GraphPlain::new(json!({"nodes":[], "edges":[]}));
        assert_ne!(target.violations(Some(&base), Numbers::Check).unwrap(), []);
        let (repaired, fixes) = target.repair(Some(&base)).unwrap();
        assert_eq!(fixes.len(), 2);
        assert!(!Arc::ptr_eq(&target.identity, &repaired.identity));
        assert!(!target.passed_against(Some(&base)));
        assert!(repaired.passed_against(Some(&base)));
        assert_eq!(
            repaired.violations(Some(&base), Numbers::Check).unwrap(),
            []
        );
        let (again, fixes) = repaired.repair(Some(&base)).unwrap();
        assert_eq!(fixes, []);
        assert!(std::ptr::eq(
            repaired.as_value().get("nodes").unwrap(),
            again.as_value().get("nodes").unwrap()
        ));
        let other = GraphPlain::new(json!({"nodes":[], "edges":[]}));
        assert!(!repaired.passed_against(Some(&other)));
    }

    #[test]
    fn checked_copies_are_safe_aliases_when_used_as_a_base() {
        let base = Arc::new(GraphPlain::new(legacy_table()));
        let weak_graph = Arc::downgrade(&base);
        assert_eq!(base.violations(None, Numbers::Check).unwrap(), []);
        let (alias, fixes) = base.repair(None).unwrap();
        assert_eq!(fixes, []);
        let (second_alias, fixes) = alias.repair(None).unwrap();
        assert_eq!(fixes, []);
        assert!(Arc::ptr_eq(&base.identity, &alias.identity));
        assert!(Arc::ptr_eq(&base.identity, &second_alias.identity));
        let target = GraphPlain::new(legacy_table());
        assert_eq!(target.violations(Some(&base), Numbers::Check).unwrap(), []);
        assert!(target.passed_against(Some(&alias)));
        assert!(target.passed_against(Some(&second_alias)));
        assert_eq!(target.repair(Some(&alias)).unwrap().1, []);
        drop(base);
        assert!(weak_graph.upgrade().is_none());
        assert_eq!(target.repair(Some(&second_alias)).unwrap().1, []);
        drop(alias);
        drop(second_alias);
        let different = GraphPlain::new(json!({"nodes":[], "edges":[]}));
        assert!(!target.passed_against(Some(&different)));
        assert_eq!(target.repair(Some(&different)).unwrap().1.len(), 2);
    }

    #[test]
    fn consuming_a_base_alias_does_not_transfer_its_identity_to_mutable_values() {
        let base = Arc::new(GraphPlain::new(legacy_table()));
        let weak_graph = Arc::downgrade(&base);
        assert_eq!(base.violations(None, Numbers::Check).unwrap(), []);
        let target = GraphPlain::new(legacy_table());
        assert_eq!(target.violations(Some(&base), Numbers::Check).unwrap(), []);
        let (alias, _) = base.repair(None).unwrap();
        let mut value = alias.into_value();
        value["nodes"][0]["data"]["node"]["template"]["t"]["value"][0]["v"] = json!(2);
        // A live original is protected by copy-on-write.
        assert_eq!(
            base.as_value()["nodes"][0]["data"]["node"]["template"]["t"]["value"][0]["v"],
            json!(1)
        );
        let changed = GraphPlain::new(value);
        assert!(!Arc::ptr_eq(&base.identity, &changed.identity));
        assert!(!target.passed_against(Some(&changed)));
        assert_eq!(target.repair(Some(&changed)).unwrap().1.len(), 2);
        let (last_alias, _) = base.repair(None).unwrap();
        drop(base);
        assert!(weak_graph.upgrade().is_none());
        // Even when the consumed alias was the last owner of its value, a
        // new mutable value must enter through a new GraphPlain identity.
        let mut value = last_alias.into_value();
        value["nodes"][0]["data"]["node"]["template"]["t"]["value"][0]["v"] = json!(3);
        let replacement = GraphPlain::new(value);
        assert!(!target.passed_against(Some(&replacement)));
        assert_eq!(target.repair(Some(&replacement)).unwrap().1.len(), 2);
    }
}
