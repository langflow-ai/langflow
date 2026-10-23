//! `repair_cases.json`: repairing what has one fix, and refusing what the client must fix.

use lfx::ops::repair::{Fix, repair_flow_data};
use lfx::ops::validate::Violation;
use libtest_mimic::Trial;
use serde_json::json;

use crate::support::{assert_json_matches, cases, error_json, graph_of, load};

/// Every repair case.
pub fn trials() -> Vec<Trial> {
    cases(&load("repair_cases.json"))
        .into_iter()
        .map(|(name, case)| {
            Trial::test(format!("repair_cases::{name}"), move || {
                let flow = graph_of(&case, "flow");
                let actual = match repair_flow_data(&flow, case.get("base")) {
                    Ok(repaired) => json!({
                        "expected": repaired.flow_data,
                        "fixes": repaired.fixes.iter().map(Fix::to_value).collect::<Vec<_>>(),
                    }),
                    Err(error) => {
                        let mut recorded = error_json(&error);
                        recorded["violations"] =
                            error.violations.iter().map(Violation::to_value).collect();
                        json!({"error": recorded})
                    }
                };
                let expected = match case.get("error") {
                    Some(error) => json!({"error": error}),
                    None => json!({"expected": case["expected"], "fixes": case["fixes"]}),
                };
                assert_json_matches("repair", &actual, &expected)
            })
        })
        .collect()
}
