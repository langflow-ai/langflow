//! `restore_cases.json`: restore fixes.

use lfx_ops::Operation;
use lfx_ops::flow_value;
use lfx_ops::json::FlowValue;
use lfx_ops::restore::apply_restore_fixes;
use libtest_mimic::{Failed, Trial};

use crate::support::{assert_json_eq, cases, error_json, load};

fn restore(case: &FlowValue) -> Result<(), Failed> {
    let fixes =
        Operation::list_from_value(case["fixes"].clone()).map_err(|error| error.to_string())?;
    let actual = match apply_restore_fixes(&case["revision"], &case["stored"], fixes) {
        Ok(graph) => flow_value!({"expected": graph}),
        Err(error) => flow_value!({"error": error_json(&error)}),
    };
    let expected = match case.get("error") {
        Some(error) => flow_value!({"error": error}),
        None => flow_value!({"expected": &case["expected"]}),
    };
    assert_json_eq("restored revision", &actual, &expected)
}

/// Every restore case.
pub fn trials() -> Vec<Trial> {
    cases(&load("restore_cases.json"))
        .into_iter()
        .map(|(name, case)| Trial::test(format!("restore_cases::{name}"), move || restore(&case)))
        .collect()
}
