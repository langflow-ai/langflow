//! `envelope_cases.json` and `replay_cases.json`: the stored history.

use lfx::ops::Operation;
use lfx::ops::envelope::{
    Corruption, PackedRow, RecordedOperation, RowLimits, StoredRow, decode_row, distinct_actor_ids,
    encode_envelope, pack_rows, request_ids_in_order, sequence,
};
use lfx::ops::replay::{replay, verify_checkpoint};
use libtest_mimic::{Failed, Trial};
use serde_json::{Value, json};

use crate::support::{assert_json_eq, load, section_cases};

fn number(value: &Value) -> u64 {
    value.as_u64().unwrap_or_default()
}

fn stored_row(row: &Value) -> StoredRow {
    StoredRow {
        start_revision: number(&row["start_revision"]),
        end_revision: number(&row["end_revision"]),
        ops: row["ops"].clone(),
    }
}

fn damage(corruption: &Corruption) -> Value {
    json!({"error": {"kind": corruption.damage.as_str(), "revision": corruption.revision}})
}

fn recorded_json(operation: &RecordedOperation) -> Value {
    let mut recorded = json!({
        "revision": operation.revision,
        "actor_user_id": operation.actor_user_id,
        "request_id": operation.request_id,
        "operation": operation.operation.to_json(),
    });
    if let Some(cause) = &operation.cause {
        recorded["cause"] = json!(cause);
    }
    recorded
}

fn packed_json(row: &PackedRow) -> Value {
    json!({
        "start_revision": row.start_revision,
        "end_revision": row.end_revision,
        "ops": row.ops,
        "actor_user_ids": row.actor_user_ids,
        "request_ids": row.request_ids,
    })
}

fn decode(case: &Value) -> Result<(), Failed> {
    let actual = match decode_row(&stored_row(&case["row"])) {
        Ok(decoded) => json!({"decoded": decoded.iter().map(recorded_json).collect::<Vec<_>>()}),
        Err(corruption) => damage(&corruption),
    };
    let expected = match case.get("error") {
        Some(error) => json!({"error": error}),
        None => json!({"decoded": case["decoded"]}),
    };
    assert_json_eq("decoded row", &actual, &expected)
}

fn encode(case: &Value) -> Result<(), Failed> {
    let operations: Vec<RecordedOperation> = case["operations"]
        .as_array()
        .into_iter()
        .flatten()
        .map(|recorded| {
            Ok(RecordedOperation {
                revision: number(&recorded["revision"]),
                actor_user_id: recorded["actor_user_id"]
                    .as_str()
                    .unwrap_or_default()
                    .to_owned(),
                request_id: recorded["request_id"]
                    .as_str()
                    .unwrap_or_default()
                    .to_owned(),
                operation: Operation::from_json(recorded["operation"].clone())
                    .map_err(|error| error.to_string())?,
                cause: recorded
                    .get("cause")
                    .and_then(Value::as_str)
                    .map(str::to_owned),
            })
        })
        .collect::<Result<_, Failed>>()?;
    let actual = json!({
        "envelope": encode_envelope(&operations).map_err(|error| error.to_string())?,
        "actor_user_ids": distinct_actor_ids(&operations),
        "request_ids": request_ids_in_order(&operations),
    });
    let expected = json!({"envelope": case["envelope"], "actor_user_ids": case["actor_user_ids"], "request_ids": case["request_ids"]});
    assert_json_eq("encoded envelope", &actual, &expected)
}

fn pack(case: &Value) -> Result<(), Failed> {
    let operations =
        Operation::list_from_json(case["operations"].clone()).map_err(|error| error.to_string())?;
    let limits = RowLimits {
        ops: usize::try_from(number(&case["limits"]["ops"]))?,
        bytes: usize::try_from(number(&case["limits"]["bytes"]))?,
    };
    let recorded = sequence(
        operations,
        number(&case["latest_revision"]),
        case["actor_user_id"].as_str().unwrap_or_default(),
        case["request_id"].as_str().unwrap_or_default(),
        case.get("cause").and_then(Value::as_str),
        limits.bytes,
    );
    let rows = pack_rows(recorded, limits).map_err(|error| error.to_string())?;
    assert_json_eq(
        "rows",
        &Value::Array(rows.iter().map(packed_json).collect()),
        &case["rows"],
    )
}

fn replay_case(case: &Value) -> Result<(), Failed> {
    let rows: Vec<StoredRow> = case["rows"]
        .as_array()
        .into_iter()
        .flatten()
        .map(stored_row)
        .collect();
    let actual = match replay(
        case["checkpoint"].clone(),
        number(&case["checkpoint_revision"]),
        &rows,
        number(&case["revision"]),
    ) {
        Ok(graph) => json!({"expected": graph}),
        Err(corruption) => damage(&corruption),
    };
    let expected = match case.get("error") {
        Some(error) => json!({"error": error}),
        None => json!({"expected": case["expected"]}),
    };
    assert_json_eq("replayed graph", &actual, &expected)
}

fn verify(case: &Value) -> Result<(), Failed> {
    let actual = match verify_checkpoint(
        &case["graph"],
        case["hash"].as_str().unwrap_or_default(),
        number(&case["revision"]),
    ) {
        Ok(()) => json!({}),
        Err(corruption) => damage(&corruption),
    };
    let expected = case
        .get("error")
        .map_or_else(|| json!({}), |error| json!({"error": error}));
    assert_json_eq("checkpoint verification", &actual, &expected)
}

type Check = fn(&Value) -> Result<(), Failed>;

/// Every envelope and replay case.
pub fn trials() -> Vec<Trial> {
    let mut trials = Vec::new();
    let files: [(&str, &[(&str, Check)]); 2] = [
        (
            "envelope_cases.json",
            &[("decode", decode), ("encode", encode), ("pack", pack)],
        ),
        (
            "replay_cases.json",
            &[("cases", replay_case), ("verify", verify)],
        ),
    ];
    for (file, sections) in files {
        let document = load(file);
        for (section, check) in sections {
            let check = *check;
            for (name, case) in section_cases(&document, section) {
                let stem = file.trim_end_matches(".json");
                trials.push(Trial::test(
                    format!("{stem}::{section}::{name}"),
                    move || check(&case),
                ));
            }
        }
    }
    trials
}
