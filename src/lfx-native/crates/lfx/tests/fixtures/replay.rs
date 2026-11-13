//! `replay_cases.json`: replaying stored operations with no rule.

use lfx::json;
use lfx::ops::canonical::graphs_equal;
use lfx::ops::{GraphState, Operation, ReplayOptions};
use lfx::value::AnyValue;
use libtest_mimic::{Failed, Trial};

use crate::apply::ignoring_order;
use crate::editor::unordered;
use crate::support::{assert_json_eq, assert_json_matches, cases, compact, load};

/// Every replay case, and the check that one call replays a batch as one
/// call per operation does: for the replay cases, and for the forward
/// operations of every apply case that applies.
pub fn trials() -> Vec<Trial> {
    let mut trials = Vec::new();
    for (name, case) in cases(&load("replay_cases.json")) {
        let batch = case.clone();
        trials.push(Trial::test(format!("replay_cases::{name}"), move || {
            replay_case(&case)
        }));
        if batch.get("error").is_none() {
            trials.push(Trial::test(
                format!("replay_cases::{name}::one_call_per_operation"),
                move || one_call_per_operation(&batch["base"], &batch["operations"]).map(drop),
            ));
        }
    }
    for (name, case) in cases(&load("apply_cases.json")) {
        if case.get("error").is_some() {
            continue;
        }
        trials.push(Trial::test(
            format!("apply_cases::{name}::forward_replay_one_call_per_operation"),
            move || forward_replay(&case),
        ));
    }
    let merge = load("merge_cases.json");
    for (name, case) in cases(&merge) {
        let base = merge["base"].clone();
        let transactions: Vec<AnyValue> = case["order"]
            .as_array()
            .into_iter()
            .flatten()
            .map(|name| case["transactions"][name.as_str().unwrap_or_default()].clone())
            .collect();
        trials.push(Trial::test(
            format!("merge_cases::{name}::forward_replay"),
            move || log_replay(&base, &transactions),
        ));
    }
    let property = load("property_cases.json");
    for (name, sequence) in cases(&property) {
        let base = property["base"].clone();
        let transactions = sequence["transactions"]
            .as_array()
            .cloned()
            .unwrap_or_default();
        trials.push(Trial::test(
            format!("property_cases::{name}::forward_replay"),
            move || log_replay(&base, &transactions),
        ));
    }
    for (name, case) in cases(&load("diff_cases.json")) {
        trials.push(Trial::test(
            format!("diff_cases::{name}::derived_replay"),
            move || derived_replay(&case),
        ));
    }
    trials
}

/// Apply each batch in turn, as the server does, and keep the forward
/// operations of each batch that applies, as the operation log does. Replay
/// the log on the base, one call per batch: every batch replays, and the
/// result is the graph apply gave. A refused batch is not in the log.
fn log_replay(base: &AnyValue, batches: &[AnyValue]) -> Result<(), Failed> {
    let mut applied = GraphState::new(base.clone()).map_err(|error| error.to_string())?;
    let mut replayed = GraphState::new(base.clone()).map_err(|error| error.to_string())?;
    let options = lfx::ops::ApplyOptions {
        forward: true,
        ..lfx::ops::ApplyOptions::default()
    };
    for (index, batch) in batches.iter().enumerate() {
        let operations =
            Operation::list_from_value(batch.clone()).map_err(|error| error.to_string())?;
        let Ok(done) = applied.apply(operations, options) else {
            continue;
        };
        replayed
            .replay(done.forward, ReplayOptions::default())
            .map_err(|error| format!("batch {index} does not replay: {error}"))?;
    }
    let (applied, replayed) = (applied.to_value(), replayed.to_value());
    if graphs_equal(&applied, &replayed).map_err(|error| error.to_string())? {
        return Ok(());
    }
    Err(format!(
        "the replayed log differs from apply\n  apply:  {}\n  replay: {}",
        compact(&applied),
        compact(&replayed)
    )
    .into())
}

/// Derive the operations of a save, as the server does, and replay them on
/// the base: they give the target.
fn derived_replay(case: &AnyValue) -> Result<(), Failed> {
    let derived = lfx::ops::derive_flow_operations(case["base"].clone(), &case["target"])
        .map_err(|error| format!("derive fails: {error}"))?;
    let operations = AnyValue::Array(derived.operations.iter().map(Operation::to_value).collect());
    let replayed = one_call_per_operation(&case["base"], &operations)?;
    if graphs_equal(&replayed, &case["target"]).map_err(|error| error.to_string())? {
        return Ok(());
    }
    Err(format!(
        "the replayed operations do not give the target: {}",
        compact(&replayed)
    )
    .into())
}

/// Replay `operations` on `base` in one call, and again with one call per
/// operation, and require the same graph. A call makes its writes in the
/// stored flow when it ends, so the second way holds nothing between
/// operations. Returns the graph.
fn one_call_per_operation(base: &AnyValue, operations: &AnyValue) -> Result<AnyValue, Failed> {
    let operations =
        Operation::list_from_value(operations.clone()).map_err(|error| error.to_string())?;
    let mut batch = GraphState::new(base.clone()).map_err(|error| error.to_string())?;
    batch
        .replay(operations.clone(), ReplayOptions::default())
        .map_err(|error| format!("the batch fails: {error}"))?;
    let mut single = GraphState::new(base.clone()).map_err(|error| error.to_string())?;
    for (index, operation) in operations.into_iter().enumerate() {
        single
            .replay(vec![operation], ReplayOptions::default())
            .map_err(|error| format!("operation {index} alone fails: {error}"))?;
    }
    let (batch, single) = (batch.to_value(), single.to_value());
    if !graphs_equal(&batch, &single).map_err(|error| error.to_string())? {
        return Err(format!(
            "one call and one call per operation differ\n  one call:      {}\n  per operation: {}",
            compact(&batch),
            compact(&single)
        )
        .into());
    }
    Ok(batch)
}

/// Apply a case, then replay its forward operations on the base: in one
/// call and one call per operation, both give the graph apply gave.
fn forward_replay(case: &AnyValue) -> Result<(), Failed> {
    let base = &case["base"];
    let mut state = GraphState::new(base.clone()).map_err(|error| error.to_string())?;
    let options = lfx::ops::ApplyOptions {
        forward: true,
        ..lfx::ops::ApplyOptions::default()
    };
    let operations = Operation::list_from_value(case["operations"].clone())
        .map_err(|error| error.to_string())?;
    let applied = state
        .apply(operations, options)
        .map_err(|error| format!("refused: {error}"))?;
    let forward = AnyValue::Array(applied.forward.iter().map(Operation::to_value).collect());
    let replayed = one_call_per_operation(base, &forward)?;
    if graphs_equal(&replayed, &state.to_value()).map_err(|error| error.to_string())? {
        return Ok(());
    }
    Err(format!(
        "the replayed forward operations differ from apply: {}",
        compact(&replayed)
    )
    .into())
}

fn replay_case(case: &AnyValue) -> Result<(), Failed> {
    let base = &case["base"];
    let options = ReplayOptions {
        backward: case.get("backward").is_some(),
    };
    let mut state = None;
    let outcome = GraphState::new(base.clone()).and_then(|new| {
        let state = state.insert(new);
        Operation::list_from_value(case["operations"].clone())
            .and_then(|operations| state.replay(operations, options))
    });
    if let Some(expected_error) = case.get("error") {
        let Err(error) = outcome else {
            return Err("expected the replay to fail".into());
        };
        let actual = json!({"error": error.kind.class_name(), "code": error.code.as_str()});
        assert_json_eq(
            &format!("error ({error})"),
            &actual,
            &json!({"error": expected_error, "code": case["code"]}),
        )?;
        // A failed replay leaves the state as it was.
        return match state {
            Some(state) => assert_json_eq("state after the failed replay", &state.to_value(), base),
            None => Ok(()),
        };
    }
    let replayed = outcome.map_err(|error| format!("failed: {error}"))?;
    let mut state = state.ok_or("no state")?;
    assert_json_eq(
        "flow data",
        &ignoring_order(&state.to_value()),
        &ignoring_order(&case["expected"]),
    )?;
    let Some(expected_backward) = case.get("backward") else {
        return Ok(());
    };
    let backward: AnyValue = replayed
        .backward
        .iter()
        .map(|list| AnyValue::Array(list.iter().map(Operation::to_value).collect()))
        .collect();
    assert_json_matches(
        "backward operations",
        &unordered(&backward),
        &unordered(expected_backward),
    )?;
    for list in replayed.backward.into_iter().rev() {
        state
            .replay(list, ReplayOptions::default())
            .map_err(|error| format!("a backward operation fails: {error}"))?;
    }
    let restored = state.to_value();
    if graphs_equal(&restored, base).map_err(|error| error.to_string())? {
        return Ok(());
    }
    Err(format!(
        "backward operations do not restore the base: {}",
        compact(&restored)
    )
    .into())
}
