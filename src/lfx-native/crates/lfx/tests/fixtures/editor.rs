//! `backward_cases.json` and `editor_cases.json`: what only the editor's engine had.

use lfx::json;
use lfx::ops::canonical::graphs_equal;
use lfx::ops::keyed::{Renumber, append_table_rows, assign_changed_table_row_ids, assign_row_ids};
use lfx::ops::restore::{edge_fixes, fixes_for_edges};
use lfx::ops::{ApplyOptions, GraphState, Operation, ReplayOptions};
use lfx::value::AnyValue;
use libtest_mimic::{Failed, Trial};

use crate::support::{assert_json_matches, cases, compact, load, section_cases};

/// Compare backward operations without the order of what they list: the ids a
/// delete names, and the entries an add lists, are sets keyed by id.
pub fn unordered(operations: &AnyValue) -> AnyValue {
    let mut operations = operations.clone();
    for operation in operations
        .as_array_mut()
        .into_iter()
        .flatten()
        .flat_map(|list| list.as_array_mut().into_iter().flatten())
    {
        let key = match operation["type"].as_str() {
            Some("delete_nodes" | "delete_edges") => "ids",
            Some("add_nodes") => "nodes",
            Some("add_edges") => "edges",
            _ => continue,
        };
        if let Some(items) = operation.get_mut(key).and_then(AnyValue::as_array_mut) {
            items.sort_by_key(|item| {
                item.as_str()
                    .or_else(|| item["id"].as_str())
                    .map(str::to_owned)
            });
        }
    }
    operations
}

fn backward_case(case: &AnyValue) -> Result<(), Failed> {
    let base = &case["base"];
    let mut state = GraphState::new(base.clone()).map_err(|error| error.to_string())?;
    let operations = Operation::list_from_value(case["operations"].clone())
        .map_err(|error| error.to_string())?;
    let options = ApplyOptions {
        backward: true,
        ..ApplyOptions::default()
    };
    let applied = state
        .apply(operations, options)
        .map_err(|error| format!("refused: {error}"))?;
    let backward: AnyValue = applied
        .backward
        .iter()
        .map(|list| AnyValue::Array(list.iter().map(Operation::to_value).collect()))
        .collect();
    assert_json_matches(
        "backward operations",
        &unordered(&backward),
        &unordered(&case["backward"]),
    )?;
    for list in applied.backward.into_iter().rev() {
        state
            .replay(list, ReplayOptions::default())
            .map_err(|error| format!("a backward operation is refused: {error}"))?;
    }
    let restored = state.to_value();
    if graphs_equal(&restored, base).map_err(|error| error.to_string())? {
        return Ok(());
    }
    Err(format!(
        "backward operations do not restore the base: {}",
        compact(&restored)
    )
    .into())
}

/// A user's undo: the backward operation lists, last first, in one batch that is
/// applied under every rule.
fn undo_case(case: &AnyValue) -> Result<(), Failed> {
    let base = &case["base"];
    let mut state = GraphState::new(base.clone()).map_err(|error| error.to_string())?;
    let operations = Operation::list_from_value(case["operations"].clone())
        .map_err(|error| error.to_string())?;
    let options = ApplyOptions {
        backward: true,
        ..ApplyOptions::default()
    };
    let applied = state
        .apply(operations, options)
        .map_err(|error| format!("refused: {error}"))?;
    let undo: Vec<Operation> = applied.backward.into_iter().rev().flatten().collect();
    let shown = AnyValue::Array(undo.iter().map(Operation::to_value).collect());
    assert_json_matches(
        "undo",
        &unordered(&json!([shown])),
        &unordered(&json!([case["undo"]])),
    )?;
    state
        .apply(undo, ApplyOptions::default())
        .map_err(|error| format!("the undo is refused: {error}"))?;
    let restored = state.to_value();
    if graphs_equal(&restored, base).map_err(|error| error.to_string())? {
        return Ok(());
    }
    Err(format!("the undo does not restore the base: {}", compact(&restored)).into())
}

fn rows(case: &AnyValue, key: &str) -> Vec<AnyValue> {
    case[key].as_array().cloned().unwrap_or_default()
}

fn assign(case: &AnyValue) -> Result<(), Failed> {
    let mut assigned = rows(case, "rows");
    assign_row_ids(&mut assigned, case.get("previous"), Renumber::WhenNoRoom)
        .map_err(|error| error.to_string())?;
    assert_json_matches("rows", &AnyValue::Array(assigned), &case["expected"])
}

fn append(case: &AnyValue) -> Result<(), Failed> {
    let mut appended = rows(case, "rows");
    append_table_rows(&mut appended, &rows(case, "new_rows")).map_err(|error| error.to_string())?;
    assert_json_matches("rows", &AnyValue::Array(appended), &case["expected"])
}

fn assign_nodes(case: &AnyValue) -> Result<(), Failed> {
    let mut target = json!({"nodes": case["nodes"]});
    assign_changed_table_row_ids(
        &json!({"nodes": case["previous"]}),
        &mut target,
        Renumber::WhenNoRoom,
    )
    .map_err(|error| error.to_string())?;
    assert_json_matches("nodes", &target["nodes"], &case["expected"])
}

fn fixes(case: &AnyValue) -> Result<(), Failed> {
    let fixes =
        edge_fixes(&rows(case, "read"), &rows(case, "shown")).map_err(|error| error.to_string())?;
    let fixes = AnyValue::Array(fixes.iter().map(Operation::to_value).collect());
    assert_json_matches("fixes", &fixes, &case["fixes"])
}

fn for_edges(case: &AnyValue) -> Result<(), Failed> {
    let all =
        Operation::list_from_value(case["fixes"].clone()).map_err(|error| error.to_string())?;
    let ids: Vec<String> = rows(case, "edge_ids")
        .iter()
        .filter_map(|id| id.as_str().map(str::to_owned))
        .collect();
    let kept = AnyValue::Array(
        fixes_for_edges(&all, &ids)
            .iter()
            .map(Operation::to_value)
            .collect(),
    );
    assert_json_matches("fixes", &kept, &case["expected"])
}

type Check = fn(&AnyValue) -> Result<(), Failed>;

/// Every backward case, undo case and editor case.
pub fn trials() -> Vec<Trial> {
    let backward = load("backward_cases.json");
    let mut trials: Vec<Trial> = cases(&backward)
        .into_iter()
        .map(|(name, case)| {
            Trial::test(format!("backward_cases::{name}"), move || {
                backward_case(&case)
            })
        })
        .collect();
    for (name, case) in section_cases(&backward, "undo") {
        trials.push(Trial::test(
            format!("backward_cases::undo::{name}"),
            move || undo_case(&case),
        ));
    }
    let document = load("editor_cases.json");
    let sections: [(&str, Check); 5] = [
        ("assign", assign),
        ("append", append),
        ("assign_nodes", assign_nodes),
        ("edge_fixes", fixes),
        ("fixes_for_edges", for_edges),
    ];
    for (section, check) in sections {
        for (name, case) in section_cases(&document, section) {
            trials.push(Trial::test(
                format!("editor_cases::{section}::{name}"),
                move || check(&case),
            ));
        }
    }
    trials
}
