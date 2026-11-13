//! `restore_cases.json` and `write_cases.json`: restore fixes and the engine's part of a save.

use lfx::ops::Operation;
use lfx::ops::restore::apply_restore_fixes;
use lfx::ops::validate::Violation;
use lfx::ops::{WriteError, WriteOptions, prepare_write};
use libtest_mimic::{Failed, Trial};
use serde_json::{Value, json};

use crate::support::{assert_json_eq, assert_json_matches, cases, error_json, load};

fn restore(case: &Value) -> Result<(), Failed> {
    let fixes =
        Operation::list_from_value(case["fixes"].clone()).map_err(|error| error.to_string())?;
    let actual = match apply_restore_fixes(&case["revision"], &case["stored"], fixes) {
        Ok(graph) => json!({"expected": graph}),
        Err(error) => json!({"error": error_json(&error)}),
    };
    let expected = match case.get("error") {
        Some(error) => json!({"error": error}),
        None => json!({"expected": case["expected"]}),
    };
    assert_json_eq("restored revision", &actual, &expected)
}

fn write(case: &Value) -> Result<(), Failed> {
    let options = &case["options"];
    let write_options = WriteOptions {
        started: options["started"].as_bool().unwrap_or_default(),
        repair_invalid_graph: options["repair_invalid_graph"]
            .as_bool()
            .unwrap_or_default(),
    };
    let actual = match prepare_write(
        case["stored"].clone(),
        case["target"].clone(),
        &write_options,
    ) {
        Ok(prepared) => json!({"expected": {
            "base": prepared.base,
            "stored_repaired": prepared.stored_repaired,
            "target": prepared.target,
            "repairs": prepared.repairs_json(),
            "operations": prepared.operations.iter().map(Operation::to_value).collect::<Vec<_>>(),
        }}),
        Err(WriteError::InvalidGraph { role, violations }) => json!({"error": {
            "graph": role.as_str(),
            "violations": violations.iter().map(Violation::to_value).collect::<Vec<_>>(),
        }}),
        Err(WriteError::Engine(error)) => {
            json!({"engine_error": error_json(&error), "message": error.message})
        }
    };
    let expected = match case.get("error") {
        Some(error) => json!({"error": error}),
        None => json!({"expected": case["expected"]}),
    };
    assert_json_matches("prepared write", &actual, &expected)
}

/// Every restore and write case.
pub fn trials() -> Vec<Trial> {
    let mut trials: Vec<Trial> = cases(&load("restore_cases.json"))
        .into_iter()
        .map(|(name, case)| Trial::test(format!("restore_cases::{name}"), move || restore(&case)))
        .collect();
    trials.extend(
        cases(&load("write_cases.json"))
            .into_iter()
            .map(|(name, case)| Trial::test(format!("write_cases::{name}"), move || write(&case))),
    );
    trials
}
