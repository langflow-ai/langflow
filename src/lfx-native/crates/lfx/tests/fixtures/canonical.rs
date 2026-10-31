//! `canonical_cases.json`: canonical text, value equality, graph equality and handles.

use lfx::ops::canonical::{canonical_json, graph_hash, graphs_equal, parse_handle, values_equal};
use libtest_mimic::{Failed, Trial};
use serde_json::{Value, json};

use crate::support::{assert_json_eq, error_json, load, section_cases};

fn parse(text: &str) -> Result<Value, Failed> {
    serde_json::from_str(text).map_err(|error| format!("not JSON: {error}").into())
}

/// Every canonical case.
pub fn trials() -> Vec<Trial> {
    let document = load("canonical_cases.json");
    let mut trials = limit_trials();
    for section in ["numbers", "values"] {
        for (name, case) in section_cases(&document, section) {
            trials.push(Trial::test(
                format!("canonical_cases::{section}::{name}"),
                move || {
                    let value = parse(case["json"].as_str().unwrap_or_default())?;
                    let actual = match canonical_json(&value) {
                        Ok(text) => json!({"canonical": text}),
                        Err(error) => json!({"error": error_json(&error)}),
                    };
                    let expected = match case.get("error") {
                        Some(error) => json!({"error": error}),
                        None => json!({"canonical": case["canonical"]}),
                    };
                    assert_json_eq("canonical form", &actual, &expected)
                },
            ));
        }
    }
    let samples = document["equality_samples"].clone();
    trials.push(Trial::test(
        "canonical_cases::equality_samples",
        move || {
            let samples: Vec<(Value, &str)> = samples
                .as_array()
                .into_iter()
                .flatten()
                .map(|sample| {
                    Ok((
                        parse(sample["json"].as_str().unwrap_or_default())?,
                        sample["canonical"].as_str().unwrap_or_default(),
                    ))
                })
                .collect::<Result<_, Failed>>()?;
            for (left, left_canonical) in &samples {
                for (right, right_canonical) in &samples {
                    let equal = values_equal(left, right).map_err(|error| error.to_string())?;
                    if equal != (left_canonical == right_canonical) {
                        return Err(format!("values_equal({left}, {right}) is {equal}").into());
                    }
                }
            }
            Ok(())
        },
    ));
    for (name, case) in section_cases(&document, "graphs") {
        trials.push(Trial::test(format!("canonical_cases::graphs::{name}"), move || {
            let (left, right) = (&case["left"], &case["right"]);
            let actual = json!({
                "equal": graphs_equal(left, right).map_err(|error| error.to_string())?,
                "left_hash": graph_hash(left).map_err(|error| error.to_string())?,
                "right_hash": graph_hash(right).map_err(|error| error.to_string())?,
            });
            let expected = json!({"equal": case["equal"], "left_hash": case["left_hash"], "right_hash": case["right_hash"]});
            assert_json_eq("graph comparison", &actual, &expected)
        }));
    }
    for (name, case) in section_cases(&document, "handles") {
        trials.push(Trial::test(
            format!("canonical_cases::handles::{name}"),
            move || {
                let parsed = parse_handle(&case["handle"]).map_or(Value::Null, Value::Object);
                assert_json_eq("parsed handle", &parsed, &case["parsed"])
            },
        ));
    }
    trials
}

/// `limit_cases.json`: JSON text the engine refuses or accepts as it reads it.
fn limit_trials() -> Vec<Trial> {
    let document = load("limit_cases.json");
    let mut trials = Vec::new();
    for section in ["refused", "accepted"] {
        for (name, case) in section_cases(&document, section) {
            trials.push(Trial::test(
                format!("limit_cases::{section}::{name}"),
                move || {
                    let actual = match lfx::ops::api::canonical_json(
                        case["json"].as_str().unwrap_or_default(),
                    ) {
                        Ok(text) => json!({"canonical": text}),
                        Err(error) => {
                            json!({"error": {"error": error.kind(), "code": error.code()}})
                        }
                    };
                    let expected = match case.get("error") {
                        Some(error) => json!({"error": error}),
                        None => json!({"canonical": case["canonical"]}),
                    };
                    assert_json_eq("reading the text", &actual, &expected)
                },
            ));
        }
    }
    trials
}
