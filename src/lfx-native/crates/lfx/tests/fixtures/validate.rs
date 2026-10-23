//! `validation_cases.json`: every rule a graph breaks.

use lfx::ops::validate::{Numbers, Violation, find_graph_violations};
use libtest_mimic::Trial;
use serde_json::{Value, json};

use crate::support::{assert_json_eq, cases, error_json, graph_of, load};

/// Every validation case.
pub fn trials() -> Vec<Trial> {
    cases(&load("validation_cases.json"))
        .into_iter()
        .map(|(name, case)| {
            Trial::test(format!("validation_cases::{name}"), move || {
                let flow = graph_of(&case, "flow");
                let numbers = if case.get("check_values").and_then(Value::as_bool).unwrap_or(true) {
                    Numbers::Check
                } else {
                    Numbers::Skip
                };
                let actual = match find_graph_violations(&flow, numbers, case.get("base")) {
                    Ok(violations) => json!({"violations": violations.iter().map(Violation::to_value).collect::<Vec<_>>()}),
                    Err(error) => json!({"error": error_json(&error)}),
                };
                let expected = match case.get("error") {
                    Some(error) => json!({"error": error}),
                    None => json!({"violations": case["violations"]}),
                };
                assert_json_eq("violations", &actual, &expected)
            })
        })
        .collect()
}
