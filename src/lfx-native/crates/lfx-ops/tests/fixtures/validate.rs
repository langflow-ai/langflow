//! `validation_cases.json`: every rule a graph breaks.

use lfx_ops::flow_value;
use lfx_ops::json::FlowValue;
use lfx_ops::validate::{Numbers, Violation, find_graph_violations};
use libtest_mimic::Trial;

use crate::support::{assert_json_eq, cases, error_json, graph_of, load};

/// Every validation case.
pub fn trials() -> Vec<Trial> {
    cases(&load("validation_cases.json"))
        .into_iter()
        .map(|(name, case)| {
            Trial::test(format!("validation_cases::{name}"), move || {
                let flow = graph_of(&case, "flow");
                let numbers = if case.get("check_values").and_then(FlowValue::as_bool).unwrap_or(true) {
                    Numbers::Check
                } else {
                    Numbers::Skip
                };
                let actual = match find_graph_violations(&flow, numbers, case.get("base")) {
                    Ok(violations) => flow_value!({"violations": violations.iter().map(Violation::to_value).collect::<Vec<_>>()}),
                    Err(error) => flow_value!({"error": error_json(&error)}),
                };
                let expected = match case.get("error") {
                    Some(error) => flow_value!({"error": error}),
                    None => flow_value!({"violations": &case["violations"]}),
                };
                assert_json_eq("violations", &actual, &expected)
            })
        })
        .collect()
}
