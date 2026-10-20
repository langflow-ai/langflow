//! Loading fixture files and comparing what the engine returns with them.

use std::collections::HashSet;
use std::path::PathBuf;

use libtest_mimic::{Failed, Trial};
use serde_json::{Map, Value};

/// The fixture files every runtime runs.
pub const FIXTURE_FILES: [&str; 13] = [
    "apply_cases.json",
    "canonical_cases.json",
    "diff_cases.json",
    "editor_cases.json",
    "inverse_cases.json",
    "limit_cases.json",
    "merge_cases.json",
    "property_cases.json",
    "repair_cases.json",
    "restore_cases.json",
    "table_cases.json",
    "validation_cases.json",
    "write_cases.json",
];

/// The placeholder for an edge id the engine draws at random.
pub const GENERATED_EDGE_ID: &str = "<generated edge id>";
/// The placeholder for a row id the engine draws at random.
pub const GENERATED_ROW_ID: &str = "<generated row id>";

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
    let section = if document.get("sequences").is_some() {
        "sequences"
    } else {
        "cases"
    };
    section_cases(document, section)
}

/// The cases of one section of a fixture file, each with its name.
pub fn section_cases(document: &Value, section: &str) -> Vec<(String, Value)> {
    let cases = document
        .get(section)
        .and_then(Value::as_array)
        .unwrap_or_else(|| panic!("the fixture file has no section {section:?}"));
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

/// Fail unless `actual` matches `expected`: as [`json_eq`], except that
/// numbers compare as the doubles they are, and a generated-id placeholder
/// matches any id of its shape.
pub fn assert_json_matches(what: &str, actual: &Value, expected: &Value) -> Result<(), Failed> {
    if json_matches(actual, expected) {
        return Ok(());
    }
    Err(format!(
        "{what} differs\n  actual:   {}\n  expected: {}",
        compact(actual),
        compact(expected)
    )
    .into())
}

fn json_matches(actual: &Value, expected: &Value) -> bool {
    match (actual, expected) {
        (Value::String(id), Value::String(placeholder)) if placeholder == GENERATED_EDGE_ID => id
            .strip_prefix("e-")
            .is_some_and(|rest| is_alphanumeric_id(rest, 21)),
        (Value::String(id), Value::String(placeholder)) if placeholder == GENERATED_ROW_ID => {
            is_alphanumeric_id(id, 10)
        }
        (Value::Number(a), Value::Number(b)) => {
            a.as_str().parse::<f64>().ok() == b.as_str().parse::<f64>().ok()
        }
        (Value::Object(a), Value::Object(b)) => {
            a.len() == b.len()
                && a.iter()
                    .all(|(key, value)| b.get(key).is_some_and(|other| json_matches(value, other)))
        }
        (Value::Array(a), Value::Array(b)) => {
            a.len() == b.len() && a.iter().zip(b).all(|(a, b)| json_matches(a, b))
        }
        _ => actual == expected,
    }
}

fn is_alphanumeric_id(id: &str, length: usize) -> bool {
    id.len() == length && id.bytes().all(|byte| byte.is_ascii_alphanumeric())
}

/// A case's graph: its `<key>_json` text when it has one, so number text is exact, or its `<key>`.
pub fn graph_of(case: &Value, key: &str) -> Value {
    match case.get(format!("{key}_json")).and_then(Value::as_str) {
        Some(text) => serde_json::from_str(text)
            .unwrap_or_else(|error| panic!("{key}_json is not JSON: {error}")),
        None => case.get(key).cloned().unwrap_or(Value::Null),
    }
}

/// An engine error as fixtures record it.
pub fn error_json(error: &lfx::ops::Error) -> Value {
    serde_json::json!({"error": error.kind.class_name(), "code": error.code.as_str()})
}

/// One line of JSON, for failure messages.
pub fn compact(value: &Value) -> String {
    serde_json::to_string(value).unwrap_or_else(|error| format!("<{error}>"))
}

/// The rules the fixtures README lists: the first column of its rules table.
pub fn listed_rules() -> HashSet<String> {
    let path = fixtures_dir().join("README.md");
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|error| panic!("cannot read {}: {error}", path.display()));
    text.lines()
        .filter_map(|line| line.strip_prefix("| `")?.split_once('`'))
        .map(|(rule, _)| rule.to_owned())
        .collect()
}

/// The rule each case of a fixture file names, by section and case.
///
/// Every case names the rule it checks, and the README lists that rule.
fn case_rules(name: &str, document: &Map<String, Value>) -> Result<Vec<String>, Failed> {
    let listed = listed_rules();
    let mut rules = Vec::new();
    for (section, cases) in document {
        for (index, case) in cases.as_array().into_iter().flatten().enumerate() {
            let label = case
                .get("name")
                .and_then(Value::as_str)
                .map_or_else(|| format!("#{index}"), |case| format!("{case:?}"));
            let Some(rule) = case.get("rule").and_then(Value::as_str) else {
                return Err(format!("{name}: case {label} in {section} names no rule").into());
            };
            if !listed.contains(rule) {
                return Err(format!(
                    "{name}: case {label} in {section} names the rule {rule:?}, which README.md does not list"
                )
                .into());
            }
            rules.push(rule.to_owned());
        }
    }
    Ok(rules)
}

/// One trial per fixture file: the file parses, every case has a unique name,
/// and every case names a rule the README lists. One more checks that every
/// listed rule has a case, and one checks the comparison the other runners rely on.
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
            let Some(document) = document.as_object() else {
                return Err(format!("{name} is not an object").into());
            };
            for (section, cases) in document {
                let mut names = HashSet::new();
                for case in cases.as_array().into_iter().flatten() {
                    if let Some(case) = case.get("name").and_then(Value::as_str)
                        && !names.insert(case)
                    {
                        return Err(
                            format!("{name}: two cases in {section} are named {case:?}").into()
                        );
                    }
                }
            }
            case_rules(name, document)?;
            Ok(())
        })
    });
    let rules = Trial::test("fixtures::README.md::rules", || {
        let mut used = HashSet::new();
        for name in FIXTURE_FILES {
            if let Some(document) = load(name).as_object() {
                used.extend(case_rules(name, document)?);
            }
        }
        let mut unused: Vec<String> = listed_rules().difference(&used).cloned().collect();
        unused.sort();
        if unused.is_empty() {
            Ok(())
        } else {
            Err(format!("README.md lists rules no case checks: {unused:?}").into())
        }
    });
    std::iter::once(comparison)
        .chain(files)
        .chain(std::iter::once(rules))
        .collect()
}
