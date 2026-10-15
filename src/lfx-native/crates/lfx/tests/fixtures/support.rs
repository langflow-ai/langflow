//! Loading fixture files and comparing what the engine returns with them.

use std::path::PathBuf;

use libtest_mimic::{Failed, Trial};
use serde_json::Value;

/// The fixture files every runtime runs.
pub const FIXTURE_FILES: [&str; 4] = [
    "apply_cases.json",
    "diff_cases.json",
    "merge_cases.json",
    "property_cases.json",
];

/// The directory that holds the shared fixtures.
pub fn fixtures_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../fixtures")
}

/// Read and parse one fixture file.
pub fn load(name: &str) -> Value {
    let path = fixtures_dir().join(name);
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|error| panic!("cannot read {}: {error}", path.display()));
    serde_json::from_str(&text)
        .unwrap_or_else(|error| panic!("{} is not valid JSON: {error}", path.display()))
}

/// The cases of a fixture file, each with its name.
pub fn cases(document: &Value) -> Vec<(String, Value)> {
    let cases = document
        .get("cases")
        .or_else(|| document.get("sequences"))
        .and_then(Value::as_array)
        .expect("a fixture file lists its cases under \"cases\" or \"sequences\"");
    cases
        .iter()
        .map(|case| {
            let name = case["name"]
                .as_str()
                .expect("every case has a name")
                .to_owned();
            (name, case.clone())
        })
        .collect()
}

/// Fail unless `actual` equals `expected` exactly, as JSON values.
///
/// Objects compare without regard to key order; arrays, strings and the text
/// of numbers compare exactly, so a number keeps the spelling it came in with.
pub fn assert_json_eq(what: &str, actual: &Value, expected: &Value) -> Result<(), Failed> {
    if json_eq(actual, expected) {
        return Ok(());
    }
    Err(format!(
        "{what} differs\n  actual:   {}\n  expected: {}",
        compact(actual),
        compact(expected)
    )
    .into())
}

/// Whether two JSON values are equal: objects in any key order, numbers by their text.
pub fn json_eq(left: &Value, right: &Value) -> bool {
    match (left, right) {
        (Value::Object(left), Value::Object(right)) => {
            left.len() == right.len()
                && left
                    .iter()
                    .all(|(key, value)| right.get(key).is_some_and(|other| json_eq(value, other)))
        }
        (Value::Array(left), Value::Array(right)) => {
            left.len() == right.len() && left.iter().zip(right).all(|(a, b)| json_eq(a, b))
        }
        _ => left == right,
    }
}

/// One line of JSON, for failure messages.
pub fn compact(value: &Value) -> String {
    serde_json::to_string(value).unwrap_or_else(|error| format!("<{error}>"))
}

/// One trial per fixture file: the file parses and every case has a unique name.
/// One more checks the comparison the other runners rely on.
pub fn trials() -> Vec<Trial> {
    let comparison = Trial::test("fixtures::comparison", || {
        let expected = serde_json::json!({"a": 1.0, "b": [1, 2]});
        assert_json_eq(
            "reordered keys",
            &serde_json::json!({"b": [1, 2], "a": 1.0}),
            &expected,
        )?;
        if json_eq(&serde_json::json!({"a": 1, "b": [1, 2]}), &expected) {
            return Err("1 and 1.0 must differ in text".into());
        }
        if json_eq(&serde_json::json!({"a": 1.0, "b": [2, 1]}), &expected) {
            return Err("array order must matter".into());
        }
        Ok(())
    });
    let files = FIXTURE_FILES.iter().map(|&name| {
        Trial::test(format!("fixtures::{name}::loads"), move || {
            let document = load(name);
            let mut names = std::collections::HashSet::new();
            for (case, _) in cases(&document) {
                if !names.insert(case.clone()) {
                    return Err(format!("{name}: two cases are named {case:?}").into());
                }
            }
            Ok(())
        })
    });
    std::iter::once(comparison).chain(files).collect()
}
