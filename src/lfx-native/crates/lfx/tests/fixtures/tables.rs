//! `table_cases.json`: ordering, stripping and assigning table row ids and positions.

use lfx::ops::canonical::ordered_rows;
use lfx::ops::keyed::{
    Renumber, assign_changed_table_row_ids, assign_row_ids, assign_table_row_ids,
    fill_missing_positions, strip_flow_table_row_keys, strip_row_keys,
};
use libtest_mimic::{Failed, Trial};
use serde_json::{Value, json};

use crate::support::{assert_json_matches, load, section_cases};

type Check = fn(&Value) -> Result<(), Failed>;

fn rows(case: &Value, key: &str) -> Vec<Value> {
    case[key].as_array().cloned().unwrap_or_default()
}

fn strip(case: &Value) -> Result<(), Failed> {
    assert_json_matches(
        "stripped rows",
        &strip_row_keys(&case["rows"]),
        &case["expected"],
    )
}

fn ordered(case: &Value) -> Result<(), Failed> {
    let rows = rows(case, "rows");
    let ordered: Vec<Value> = ordered_rows(&rows).into_iter().cloned().collect();
    assert_json_matches("ordered rows", &Value::Array(ordered), &case["expected"])
}

fn fill_positions(case: &Value) -> Result<(), Failed> {
    let mut rows = rows(case, "rows");
    let filled = fill_missing_positions(&mut rows, Renumber::Never);
    assert_json_matches(
        "filled positions",
        &json!({"rows": rows, "filled": filled}),
        &json!({"rows": case["expected"], "filled": case["filled"]}),
    )
}

fn assign(case: &Value) -> Result<(), Failed> {
    let mut rows = rows(case, "rows");
    assign_row_ids(
        &mut rows,
        case.get("previous").filter(|previous| !previous.is_null()),
        Renumber::Never,
    )
    .map_err(|error| error.to_string())?;
    assert_json_matches("assigned rows", &Value::Array(rows), &case["expected"])
}

fn assign_node(case: &Value) -> Result<(), Failed> {
    let mut node = case["node"].clone();
    assign_table_row_ids(&mut node, Renumber::Never).map_err(|error| error.to_string())?;
    assert_json_matches("node", &node, &case["expected"])
}

fn assign_changed(case: &Value) -> Result<(), Failed> {
    let mut target = case["target"].clone();
    assign_changed_table_row_ids(&case["base"], &mut target, Renumber::Never)
        .map_err(|error| error.to_string())?;
    assert_json_matches("target", &target, &case["expected"])
}

fn strip_flow(case: &Value) -> Result<(), Failed> {
    let mut flow = case["flow"].clone();
    strip_flow_table_row_keys(&mut flow);
    assert_json_matches("flow", &flow, &case["expected"])
}

/// Every table case.
pub fn trials() -> Vec<Trial> {
    let document = load("table_cases.json");
    let sections: [(&str, Check); 7] = [
        ("strip", strip),
        ("ordered", ordered),
        ("fill_positions", fill_positions),
        ("assign", assign),
        ("assign_node", assign_node),
        ("assign_changed", assign_changed),
        ("strip_flow", strip_flow),
    ];
    let mut trials = Vec::new();
    for (section, check) in sections {
        for (name, case) in section_cases(&document, section) {
            trials.push(Trial::test(
                format!("table_cases::{section}::{name}"),
                move || check(&case),
            ));
        }
    }
    trials
}
