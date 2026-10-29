//! `apply_cases.json`, `merge_cases.json` and `property_cases.json`: applying operations.

use lfx::ops::canonical::{graph_hash, graphs_equal};
use lfx::ops::schema::NODE_SCHEMA;
use lfx::ops::{ApplyOptions, GraphState, Mode, Operation};
use libtest_mimic::{Failed, Trial};
use serde_json::{Map, Value, json};

use crate::support::{assert_json_eq, cases, compact, load};

/// Every apply case, and the backward round trip of every case that applies.
pub fn trials() -> Vec<Trial> {
    let mut trials = Vec::new();
    for (name, case) in cases(&load("apply_cases.json")) {
        let backward_case = case.clone();
        trials.push(Trial::test(format!("apply_cases::{name}"), move || {
            apply_case(&case)
        }));
        if backward_case.get("error").is_none() {
            trials.push(Trial::test(
                format!("apply_cases::{name}::backward"),
                move || backward_round_trip(&backward_case),
            ));
        }
    }
    let merge = load("merge_cases.json");
    for (name, case) in cases(&merge) {
        let base = merge["base"].clone();
        trials.push(Trial::test(format!("merge_cases::{name}"), move || {
            merge_case(&base, &case)
        }));
    }
    let property = load("property_cases.json");
    for (name, sequence) in cases(&property) {
        let base = property["base"].clone();
        let fresh = (base.clone(), sequence.clone());
        trials.push(Trial::test(format!("property_cases::{name}"), move || {
            property_sequence(&base, &sequence, true)
        }));
        trials.push(Trial::test(
            format!("property_cases::{name}::one_state_per_transaction"),
            move || property_sequence(&fresh.0, &fresh.1, false),
        ));
    }
    trials
}

fn parse(operations: &Value) -> Result<Vec<Operation>, lfx::ops::Error> {
    Operation::list_from_value(operations.clone())
}

fn apply_case(case: &Value) -> Result<(), Failed> {
    let base = &case["base"];
    let options = ApplyOptions {
        forward: true,
        ..ApplyOptions::default()
    };
    let mut state = None;
    let outcome = GraphState::new(base.clone()).and_then(|new| {
        let state = state.insert(new);
        parse(&case["operations"]).and_then(|operations| state.apply(operations, options))
    });
    if let Some(expected_error) = case.get("error") {
        let Err(error) = outcome else {
            return Err("expected the operations to be refused".into());
        };
        let actual = json!({"error": error.kind.class_name(), "code": error.code.as_str()});
        assert_json_eq(
            &format!("error ({error})"),
            &actual,
            &json!({"error": expected_error, "code": case["code"]}),
        )?;
        // A refused batch leaves the state as it was.
        return match state {
            Some(state) => assert_json_eq("state after the refused batch", &state.to_value(), base),
            None => Ok(()),
        };
    }
    let applied = outcome.map_err(|error| format!("refused: {error}"))?;
    let state = state.ok_or("no state")?;
    assert_json_eq(
        "flow data",
        &ignoring_order(&state.to_value()),
        &ignoring_order(&case["expected"]),
    )?;
    // The bindings print the graph with to_json, which must write the text of to_value.
    let printed = state.to_value().to_string();
    if state.to_json() != printed {
        return Err("to_json does not write the text of to_value".into());
    }
    let forward = Value::Array(applied.forward.iter().map(Operation::to_value).collect());
    let expected_forward = case
        .get("forward_operations")
        .unwrap_or(&case["operations"]);
    assert_json_eq(
        "forward operations",
        &ignoring_id_order(&forward),
        &ignoring_id_order(expected_forward),
    )
}

/// Applying a case's backward operations, last first and in preview mode, gives back its base.
fn backward_round_trip(case: &Value) -> Result<(), Failed> {
    let base = &case["base"];
    let mut state =
        GraphState::new(base.clone()).map_err(|error| format!("base does not index: {error}"))?;
    let options = ApplyOptions {
        backward: true,
        ..ApplyOptions::default()
    };
    let applied = state
        .apply(
            parse(&case["operations"]).map_err(|error| error.to_string())?,
            options,
        )
        .map_err(|error| format!("refused: {error}"))?;
    let restore = ApplyOptions {
        mode: Mode::Preview,
        ..ApplyOptions::default()
    };
    for backward in applied.backward.into_iter().rev() {
        let shown = compact(&Value::Array(
            backward.iter().map(Operation::to_value).collect(),
        ));
        state
            .apply(backward, restore)
            .map_err(|error| format!("backward operations {shown} refused: {error}"))?;
    }
    let restored = state.to_value();
    if graphs_equal(&restored, base).map_err(|error| error.to_string())? {
        Ok(())
    } else {
        Err(format!(
            "backward operations do not restore the base\n  actual:   {}\n  expected: {}",
            compact(&restored),
            compact(base)
        )
        .into())
    }
}

fn merge_case(base: &Value, case: &Value) -> Result<(), Failed> {
    let mut state =
        GraphState::new(base.clone()).map_err(|error| format!("base does not index: {error}"))?;
    let mut outcomes = Map::new();
    for name in case["order"].as_array().into_iter().flatten() {
        let name = name.as_str().unwrap_or_default();
        let before = state.to_value();
        let outcome = parse(&case["transactions"][name])
            .and_then(|operations| state.apply(operations, ApplyOptions::default()));
        let recorded = match outcome {
            Ok(_) => json!("applied"),
            Err(error) => {
                assert_json_eq(
                    &format!("state after refusing {name}"),
                    &state.to_value(),
                    &before,
                )?;
                json!({"error": error.kind.class_name(), "code": error.code.as_str()})
            }
        };
        outcomes.insert(name.to_owned(), recorded);
    }
    assert_json_eq("outcomes", &Value::Object(outcomes), &case["outcomes"])?;
    let graph = state.to_value();
    if graphs_equal(&graph, &case["expected"]).map_err(|error| error.to_string())? {
        Ok(())
    } else {
        Err(format!(
            "graph differs\n  actual:   {}\n  expected: {}",
            compact(&graph),
            compact(&case["expected"])
        )
        .into())
    }
}

/// Replay a sequence's transactions: on one state, as a handle does, or on a new state each time.
fn property_sequence(base: &Value, sequence: &Value, one_state: bool) -> Result<(), Failed> {
    let mut state =
        GraphState::new(base.clone()).map_err(|error| format!("base does not index: {error}"))?;
    for (index, transaction) in sequence["transactions"]
        .as_array()
        .into_iter()
        .flatten()
        .enumerate()
    {
        if !one_state {
            state = GraphState::new(state.to_value()).map_err(|error| error.to_string())?;
        }
        state
            .apply(
                parse(transaction).map_err(|error| error.to_string())?,
                ApplyOptions::default(),
            )
            .map_err(|error| format!("transaction {index} refused: {error}"))?;
    }
    let hash = graph_hash(&state.to_value()).map_err(|error| error.to_string())?;
    assert_json_eq("graph hash", &json!(hash), &sequence["graph_hash"])
}

/// Compare the ids a delete names as a set: node and edge order is not state.
fn ignoring_id_order(operations: &Value) -> Value {
    let mut operations = operations.clone();
    for operation in operations.as_array_mut().into_iter().flatten() {
        let deletes = matches!(
            operation["type"].as_str(),
            Some("delete_nodes" | "delete_edges")
        );
        if deletes && let Some(ids) = operation.get_mut("ids").and_then(Value::as_array_mut) {
            ids.sort_by(|a, b| a.as_str().cmp(&b.as_str()));
        }
    }
    operations
}

/// Compare nodes, edges and table rows as collections keyed by id: their array
/// order is not state, and a table's order is its rows' positions.
fn ignoring_order(flow: &Value) -> Value {
    let mut flow = flow.clone();
    for key in ["nodes", "edges"] {
        if let Some(items) = flow.get_mut(key).and_then(Value::as_array_mut) {
            items.sort_by(|a, b| a["id"].as_str().cmp(&b["id"].as_str()));
        }
    }
    for node in flow
        .get_mut("nodes")
        .and_then(Value::as_array_mut)
        .into_iter()
        .flatten()
    {
        let snapshot = node.clone();
        let Some(template) = node
            .pointer_mut("/data/node/template")
            .and_then(Value::as_object_mut)
        else {
            continue;
        };
        for (name, field) in template.iter_mut() {
            let is_table =
                NODE_SCHEMA.is_table_at(&snapshot, &["data", "node", "template", name, "value"]);
            if let (true, Some(rows)) = (
                is_table,
                field.get_mut("value").and_then(Value::as_array_mut),
            ) {
                rows.sort_by(|a, b| a["__id__"].as_str().cmp(&b["__id__"].as_str()));
            }
        }
    }
    flow
}
