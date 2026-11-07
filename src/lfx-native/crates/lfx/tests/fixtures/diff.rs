//! `diff_cases.json`: the exact operations a whole-flow save records.

use lfx::ops::canonical::graphs_equal;
use lfx::ops::{ApplyOptions, GraphState, Operation, derive_flow_operations, diff_flow_data};
use libtest_mimic::{Failed, Trial};
use serde_json::Value;

use crate::support::{assert_json_eq, cases, compact, load};

/// Every diff case: its operations, its derive check, and replay of its recorded form.
pub fn trials() -> Vec<Trial> {
    let mut trials = Vec::new();
    for (name, case) in cases(&load("diff_cases.json")) {
        let recorded = case.clone();
        trials.push(Trial::test(format!("diff_cases::{name}"), move || {
            diff_case(&case)
        }));
        trials.push(Trial::test(
            format!("diff_cases::{name}::replays_recorded_form"),
            move || replay_recorded(&recorded),
        ));
    }
    trials
}

fn same_graph(what: &str, actual: &Value, expected: &Value) -> Result<(), Failed> {
    if graphs_equal(actual, expected).map_err(|error| error.to_string())? {
        return Ok(());
    }
    Err(format!(
        "{what} differs\n  actual:   {}\n  expected: {}",
        compact(actual),
        compact(expected)
    )
    .into())
}

fn diff_case(case: &Value) -> Result<(), Failed> {
    let (base, target) = (&case["base"], &case["target"]);
    let operations =
        diff_flow_data(base, target).map_err(|error| format!("diff failed: {error}"))?;
    let dumped = Value::Array(operations.iter().map(Operation::to_value).collect());
    assert_json_eq("operations", &dumped, &case["operations"])?;
    let derived = derive_flow_operations(base.clone(), target)
        .map_err(|error| format!("derive failed: {error}"))?;
    same_graph("derived graph", &derived.flow_data, target)
}

/// Applying the recorded operations one at a time from the base gives the target.
fn replay_recorded(case: &Value) -> Result<(), Failed> {
    let operations = Operation::list_from_value(case["operations"].clone())
        .map_err(|error| error.to_string())?;
    let mut state = GraphState::new(case["base"].clone()).map_err(|error| error.to_string())?;
    for operation in operations {
        state
            .apply(vec![operation], ApplyOptions::default())
            .map_err(|error| format!("refused: {error}"))?;
    }
    same_graph("replayed graph", &state.to_value(), &case["target"])
}
