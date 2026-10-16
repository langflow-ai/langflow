//! JSON in, JSON out: the surface the Python and browser bindings expose.
//!
//! Graphs, operations and results cross the boundary as JSON text, so the
//! engine parses each graph once and keeps every number's original text.
//! Each function here does no more than parse its inputs, call the engine and
//! print its result; the bindings only call these and turn an [`ApiError`]
//! into their language's exception.

use serde_json::{Map, Value, json};

use crate::ops::apply::{Applied, ApplyOptions, apply_flow_operations};
use crate::ops::canonical;
use crate::ops::diff::{derive_flow_operations, diff_flow_data};
use crate::ops::envelope::{
    Corruption, PackedRow, RecordedOperation, RowLimits, StoredRow, decode_row as decode,
    distinct_actor_ids, encode_envelope as encode, pack_rows, request_ids_in_order, sequence,
};
use crate::ops::error::Error;
use crate::ops::keyed::{self, Renumber};
use crate::ops::ops::Operation;
use crate::ops::repair::{Fix, repair_flow_data};
use crate::ops::replay;
use crate::ops::restore;
use crate::ops::state::FlowState;
use crate::ops::validate::{Violation, find_graph_violations};
use crate::ops::write::{WriteError, WriteOptions};

/// An error as it crosses the boundary: a JSON object with the error's
/// `kind` (the matching Python exception class), `code` and `message`, and
/// what that kind carries (`edge_id`, `violations`, `damage` and `revision`,
/// or `graph`).
#[derive(Debug, Clone, PartialEq)]
pub struct ApiError(pub Value);

impl ApiError {
    /// The error's kind.
    #[must_use]
    pub fn kind(&self) -> &str {
        self.0["kind"].as_str().unwrap_or_default()
    }

    /// The error's code.
    #[must_use]
    pub fn code(&self) -> &str {
        self.0["code"].as_str().unwrap_or_default()
    }

    /// The error's message.
    #[must_use]
    pub fn message(&self) -> &str {
        self.0["message"].as_str().unwrap_or_default()
    }
}

impl From<Error> for ApiError {
    fn from(error: Error) -> Self {
        let mut out = json!({
            "kind": error.kind.class_name(),
            "code": error.code.as_str(),
            "message": error.message,
        });
        if let Some(edge_id) = &error.edge_id {
            out["edge_id"] = json!(edge_id);
        }
        if !error.violations.is_empty() {
            out["violations"] = violations(&error.violations);
        }
        Self(out)
    }
}

impl From<Corruption> for ApiError {
    fn from(corruption: Corruption) -> Self {
        Self(json!({
            "kind": "FlowHistoryCorruptionError",
            "code": "FLOW_HISTORY_CORRUPT",
            "message": corruption.to_string(),
            "damage": corruption.damage.as_str(),
            "revision": corruption.revision,
        }))
    }
}

impl From<WriteError> for ApiError {
    fn from(error: WriteError) -> Self {
        match error {
            WriteError::InvalidGraph {
                role,
                violations: found,
            } => Self(json!({
                "kind": "FlowGraphInvalidError",
                "code": "FLOW_GRAPH_INVALID",
                "message": format!("The {} flow graph breaks {} flow graph rule(s)", role.as_str(), found.len()),
                "graph": role.as_str(),
                "violations": violations(&found),
            })),
            WriteError::Engine(error) => error.into(),
        }
    }
}

/// The result of a call: JSON text, or the error.
pub type ApiResult<T = String> = Result<T, ApiError>;

fn violations(violations: &[Violation]) -> Value {
    Value::Array(violations.iter().map(Violation::to_json).collect())
}

fn operations_json(operations: &[Operation]) -> Value {
    Value::Array(operations.iter().map(Operation::to_json).collect())
}

/// Parse a graph, or any JSON value the engine reads as data.
fn graph(text: &str) -> ApiResult<Value> {
    serde_json::from_str(text).map_err(|error| {
        Error::graph(format!("flow data is not valid JSON: {error}"), Vec::new()).into()
    })
}

/// Parse a list of operations.
fn operations(text: &str) -> ApiResult<Vec<Operation>> {
    let value: Value = serde_json::from_str(text).map_err(|error| {
        ApiError::from(Error::invalid(format!(
            "operations are not valid JSON: {error}"
        )))
    })?;
    Ok(Operation::list_from_json(value)?)
}

fn optional(text: Option<&str>) -> ApiResult<Option<Value>> {
    text.map(graph).transpose()
}

fn rows_of(value: Value) -> Vec<Value> {
    match value {
        Value::Array(rows) => rows,
        _ => Vec::new(),
    }
}

fn renumber(editor: bool) -> Renumber {
    if editor {
        Renumber::WhenNoRoom
    } else {
        Renumber::Never
    }
}

// --- Apply ---------------------------------------------------------------------------------

/// What a batch did, as JSON: the forward operations with `forward`, the
/// inverses with `inverse`, the edges it deleted along the way, and the
/// nodes and edges it changed.
#[must_use]
pub fn applied_json(applied: &Applied, options: ApplyOptions) -> Map<String, Value> {
    let mut out = Map::new();
    if options.forward {
        out.insert(
            "forward_operations".into(),
            operations_json(&applied.forward),
        );
    }
    if options.inverse {
        out.insert(
            "inverse_operations".into(),
            Value::Array(
                applied
                    .inverse
                    .iter()
                    .map(|list| operations_json(list))
                    .collect(),
            ),
        );
    }
    out.insert("deleted_edges".into(), json!(applied.deleted_edges));
    out.insert("changed_nodes".into(), json!(applied.changed_nodes));
    out.insert("changed_edges".into(), json!(applied.changed_edges));
    out
}

/// Apply operations to a graph: `{"flow_data", ...}` and what [`applied_json`] lists.
///
/// # Errors
///
/// The graph or the operations do not parse, or the engine refuses the batch.
pub fn apply(flow: &str, operations_text: &str, options: ApplyOptions) -> ApiResult {
    let (flow_data, applied) =
        apply_flow_operations(graph(flow)?, operations(operations_text)?, options)?;
    let mut out = applied_json(&applied, options);
    out.insert("flow_data".into(), flow_data);
    Ok(Value::Object(out).to_string())
}

/// Index a graph for many batches.
///
/// # Errors
///
/// The graph does not parse or breaks a structural rule.
pub fn flow_state(flow: &str) -> ApiResult<FlowState> {
    Ok(FlowState::new(graph(flow)?)?)
}

/// Apply a batch to a held graph; the result is what [`applied_json`] lists.
///
/// # Errors
///
/// The operations do not parse, or the engine refuses the batch, which then
/// changes nothing.
pub fn apply_to(state: &mut FlowState, operations_text: &str, options: ApplyOptions) -> ApiResult {
    let applied = state.apply(operations(operations_text)?, options)?;
    Ok(Value::Object(applied_json(&applied, options)).to_string())
}

/// Parse operations and print them as the engine records them.
///
/// # Errors
///
/// The operations do not parse.
pub fn normalize_operations(operations_text: &str) -> ApiResult {
    Ok(operations_json(&operations(operations_text)?).to_string())
}

// --- Diff, validation and repair ------------------------------------------------------------

/// The operations that turn `base` into `target`.
///
/// # Errors
///
/// A graph does not parse or breaks the rules.
pub fn diff(base: &str, target: &str) -> ApiResult {
    Ok(operations_json(&diff_flow_data(&graph(base)?, &graph(target)?)?).to_string())
}

/// The operations that turn `base` into `target`, verified by replay: `{"operations", "flow_data"}`.
///
/// # Errors
///
/// A graph does not parse or breaks the rules, or the operations do not replay.
pub fn derive(base: &str, target: &str) -> ApiResult {
    let derived = derive_flow_operations(graph(base)?, &graph(target)?)?;
    Ok(
        json!({"operations": operations_json(&derived.operations), "flow_data": derived.flow_data})
            .to_string(),
    )
}

/// Every rule a graph breaks, against the stored graph a write replaces when given.
///
/// # Errors
///
/// A graph does not parse, or a check fails in a way that is not a violation.
pub fn validate(flow: &str, base: Option<&str>, check_values: bool) -> ApiResult {
    let base = optional(base)?;
    Ok(violations(&find_graph_violations(
        &graph(flow)?,
        check_values,
        base.as_ref(),
    )?)
    .to_string())
}

/// Repair what has one fix: `{"flow_data", "fixes"}`.
///
/// # Errors
///
/// A graph does not parse, or a rule only the client can fix is broken.
pub fn repair(flow: &str, base: Option<&str>) -> ApiResult {
    let base = optional(base)?;
    let repaired = repair_flow_data(&graph(flow)?, base.as_ref())?;
    let fixes: Vec<Value> = repaired.fixes.iter().map(Fix::to_json).collect();
    Ok(json!({"flow_data": repaired.flow_data, "fixes": fixes}).to_string())
}

// --- Canonical form -------------------------------------------------------------------------

/// The SHA-256 hex digest of a graph's canonical form.
///
/// # Errors
///
/// The graph does not parse, or holds a number that is not finite.
pub fn graph_hash(flow: &str) -> ApiResult {
    Ok(canonical::graph_hash(&graph(flow)?)?)
}

/// Whether two graphs are the same graph.
///
/// # Errors
///
/// A graph does not parse, or a compared number is not finite.
pub fn graphs_equal(left: &str, right: &str) -> ApiResult<bool> {
    Ok(canonical::graphs_equal(&graph(left)?, &graph(right)?)?)
}

/// Whether two JSON values are the same value.
///
/// # Errors
///
/// A value does not parse, or a compared number is not finite.
pub fn values_equal(left: &str, right: &str) -> ApiResult<bool> {
    Ok(canonical::values_equal(&graph(left)?, &graph(right)?)?)
}

/// A JSON value in RFC 8785 canonical form.
///
/// # Errors
///
/// The value does not parse, or holds a number that is not finite.
pub fn canonical_json(value: &str) -> ApiResult {
    Ok(canonical::canonical_json(&graph(value)?)?)
}

// --- History --------------------------------------------------------------------------------

fn stored_row(value: &Value) -> StoredRow {
    StoredRow {
        start_revision: value["start_revision"].as_u64().unwrap_or_default(),
        end_revision: value["end_revision"].as_u64().unwrap_or_default(),
        ops: value["ops"].clone(),
    }
}

fn recorded_json(operation: &RecordedOperation) -> Value {
    let mut out = json!({
        "revision": operation.revision,
        "actor_user_id": operation.actor_user_id,
        "request_id": operation.request_id,
        "operation": operation.operation.to_json(),
    });
    if let Some(cause) = &operation.cause {
        out["cause"] = json!(cause);
    }
    out
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

/// Decode a stored row, `{"start_revision", "end_revision", "ops"}`, into its recorded operations.
///
/// # Errors
///
/// The row does not parse, or is damaged.
pub fn decode_row(row: &str) -> ApiResult {
    let decoded = decode(&stored_row(&graph(row)?))?;
    Ok(Value::Array(decoded.iter().map(recorded_json).collect()).to_string())
}

fn recorded(value: &Value) -> ApiResult<RecordedOperation> {
    let text = |key: &str| value[key].as_str().unwrap_or_default().to_owned();
    Ok(RecordedOperation {
        revision: value["revision"].as_u64().unwrap_or_default(),
        actor_user_id: text("actor_user_id"),
        request_id: text("request_id"),
        operation: Operation::from_json(value["operation"].clone())?,
        cause: value
            .get("cause")
            .and_then(Value::as_str)
            .map(str::to_owned),
    })
}

/// Group recorded operations into a row's envelope: `{"envelope", "actor_user_ids", "request_ids"}`.
///
/// # Errors
///
/// The operations do not parse, or a request names two actors.
pub fn encode_envelope(operations_text: &str) -> ApiResult {
    let operations: Vec<RecordedOperation> = rows_of(graph(operations_text)?)
        .iter()
        .map(recorded)
        .collect::<ApiResult<_>>()?;
    Ok(json!({
        "envelope": encode(&operations)?,
        "actor_user_ids": distinct_actor_ids(&operations),
        "request_ids": request_ids_in_order(&operations),
    })
    .to_string())
}

fn limits(value: &Value) -> RowLimits {
    let limit =
        |key: &str| usize::try_from(value[key].as_u64().unwrap_or_default()).unwrap_or(usize::MAX);
    RowLimits {
        ops: limit("ops"),
        bytes: limit("bytes"),
    }
}

/// Number operations from `latest_revision` and pack them into rows.
///
/// `options` is `{"latest_revision", "actor_user_id", "request_id", "cause",
/// "limits": {"ops", "bytes"}}`.
///
/// # Errors
///
/// The inputs do not parse.
pub fn pack(operations_text: &str, options: &str) -> ApiResult {
    let options = graph(options)?;
    let limits = limits(&options["limits"]);
    let recorded = sequence(
        operations(operations_text)?,
        options["latest_revision"].as_u64().unwrap_or_default(),
        options["actor_user_id"].as_str().unwrap_or_default(),
        options["request_id"].as_str().unwrap_or_default(),
        options.get("cause").and_then(Value::as_str),
        limits.bytes,
    );
    let rows = pack_rows(recorded, limits)?;
    Ok(Value::Array(rows.iter().map(packed_json).collect()).to_string())
}

/// The graph at `revision`, replayed from a checkpoint through stored rows.
///
/// # Errors
///
/// The inputs do not parse, or the history is damaged.
pub fn replay(checkpoint: &str, checkpoint_revision: u64, rows: &str, revision: u64) -> ApiResult {
    let rows: Vec<StoredRow> = rows_of(graph(rows)?).iter().map(stored_row).collect();
    Ok(replay::replay(graph(checkpoint)?, checkpoint_revision, &rows, revision)?.to_string())
}

/// Fail unless a checkpoint's graph hashes to its stored hash.
///
/// # Errors
///
/// The graph does not parse, or its hash differs.
pub fn verify_checkpoint(flow: &str, stored_hash: &str, revision: u64) -> ApiResult<()> {
    Ok(replay::verify_checkpoint(
        &graph(flow)?,
        stored_hash,
        revision,
    )?)
}

/// The engine's part of a save: `{"base", "stored_repaired", "target", "repairs", "operations", "rows"}`.
///
/// `options` is `{"started", "repair_invalid_graph", "latest_revision",
/// "actor_user_id", "request_id", "cause", "limits": {"ops", "bytes"}}`.
///
/// # Errors
///
/// The inputs do not parse, a graph breaks the rules, or the engine fails.
pub fn prepare_write(stored: &str, target: &str, options: &str) -> ApiResult {
    let options = graph(options)?;
    let text = |key: &str| options[key].as_str().unwrap_or_default().to_owned();
    let write_options = WriteOptions {
        started: options["started"].as_bool().unwrap_or_default(),
        repair_invalid_graph: options["repair_invalid_graph"]
            .as_bool()
            .unwrap_or_default(),
        latest_revision: options["latest_revision"].as_u64().unwrap_or_default(),
        actor_user_id: text("actor_user_id"),
        request_id: text("request_id"),
        cause: options
            .get("cause")
            .and_then(Value::as_str)
            .map(str::to_owned),
        limits: limits(&options["limits"]),
    };
    let prepared =
        crate::ops::write::prepare_write(graph(stored)?, graph(target)?, &write_options)?;
    Ok(json!({
        "base": prepared.base,
        "stored_repaired": prepared.stored_repaired,
        "target": prepared.target,
        "repairs": prepared.repairs_json(),
        "operations": operations_json(&prepared.operations),
        "rows": prepared.rows.iter().map(packed_json).collect::<Vec<_>>(),
    })
    .to_string())
}

// --- Restore fixes --------------------------------------------------------------------------

/// A revision with a restore's fixes applied, after checking each one.
///
/// # Errors
///
/// The inputs do not parse, or a fix is not allowed or does not apply.
pub fn apply_restore_fixes(revision: &str, stored: &str, fixes: &str) -> ApiResult {
    Ok(
        restore::apply_restore_fixes(&graph(revision)?, &graph(stored)?, operations(fixes)?)?
            .to_string(),
    )
}

/// The fixes that turn a revision's edges as read into the edges its preview shows.
///
/// # Errors
///
/// The inputs do not parse, or a compared handle holds a number that is not finite.
pub fn edge_fixes(read: &str, shown: &str) -> ApiResult {
    let fixes = restore::edge_fixes(&rows_of(graph(read)?), &rows_of(graph(shown)?))?;
    Ok(operations_json(&fixes).to_string())
}

/// The part of the fixes that touches the given edges.
///
/// # Errors
///
/// The inputs do not parse.
pub fn fixes_for_edges(fixes: &str, edge_ids: &str) -> ApiResult {
    let ids: Vec<String> = rows_of(graph(edge_ids)?)
        .into_iter()
        .filter_map(|id| id.as_str().map(str::to_owned))
        .collect();
    Ok(operations_json(&restore::fixes_for_edges(&operations(fixes)?, &ids)).to_string())
}

// --- Table rows -----------------------------------------------------------------------------

/// Rows in order and without `_id` and `_pos`.
///
/// # Errors
///
/// The rows do not parse.
pub fn strip_row_keys(rows: &str) -> ApiResult {
    Ok(keyed::strip_row_keys(&graph(rows)?).to_string())
}

/// A flow with every top-level table ordered and stripped.
///
/// # Errors
///
/// The flow does not parse.
pub fn strip_flow_table_row_keys(flow: &str) -> ApiResult {
    let mut flow = graph(flow)?;
    keyed::strip_flow_table_row_keys(&mut flow);
    Ok(flow.to_string())
}

/// Rows with the ids and positions a write needs. `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The inputs do not parse, or a compared row holds a number that is not finite.
pub fn assign_row_ids(rows: &str, previous: Option<&str>, editor: bool) -> ApiResult {
    let mut rows = rows_of(graph(rows)?);
    keyed::assign_row_ids(&mut rows, optional(previous)?.as_ref(), renumber(editor))?;
    Ok(Value::Array(rows).to_string())
}

/// A node being added, with ids on every table. `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The node does not parse, or a compared row holds a number that is not finite.
pub fn assign_table_row_ids(node: &str, editor: bool) -> ApiResult {
    let mut node = graph(node)?;
    keyed::assign_table_row_ids(&mut node, renumber(editor))?;
    Ok(node.to_string())
}

/// `target` with ids on the tables it adds or changes relative to `base`.
/// `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The graphs do not parse, or a compared row holds a number that is not finite.
pub fn assign_changed_table_row_ids(base: &str, target: &str, editor: bool) -> ApiResult {
    let mut target = graph(target)?;
    keyed::assign_changed_table_row_ids(&graph(base)?, &mut target, renumber(editor))?;
    Ok(target.to_string())
}

/// Rows with `new_rows` appended, each with a new id one position past the last.
///
/// # Errors
///
/// The inputs do not parse, or a compared row holds a number that is not finite.
pub fn append_table_rows(rows: &str, new_rows: &str) -> ApiResult {
    let mut rows = rows_of(graph(rows)?);
    keyed::append_table_rows(&mut rows, &rows_of(graph(new_rows)?))?;
    Ok(Value::Array(rows).to_string())
}

/// A node with ids on the tables it adds or changes relative to `previous`,
/// the same node as stored. `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The inputs do not parse, or a compared row holds a number that is not finite.
pub fn assign_changed_node_table_row_ids(
    node: &str,
    previous: Option<&str>,
    editor: bool,
) -> ApiResult {
    let mut node = graph(node)?;
    keyed::assign_changed_node_table_row_ids(
        &mut node,
        optional(previous)?.as_ref(),
        renumber(editor),
    )?;
    Ok(node.to_string())
}

/// The names of a node's template fields whose value is a table.
///
/// # Errors
///
/// The node does not parse.
pub fn table_fields(node: &str) -> ApiResult {
    Ok(json!(keyed::table_fields(&graph(node)?)).to_string())
}

/// A new opaque edge id in the editor's format.
#[must_use]
pub fn new_edge_id() -> String {
    crate::ops::ids::new_edge_id()
}

/// A new opaque table row id in the editor's format.
#[must_use]
pub fn new_table_row_id() -> String {
    crate::ops::ids::new_table_row_id()
}

/// The node schema the engine reads, as JSON text.
#[must_use]
pub fn node_schema() -> &'static str {
    crate::ops::schema::NODE_SCHEMA_JSON
}

/// Rows in order, by `(_pos, _id)`, or as stored for a legacy table.
///
/// # Errors
///
/// The rows do not parse.
pub fn ordered_rows(rows: &str) -> ApiResult {
    let rows = rows_of(graph(rows)?);
    Ok(Value::Array(
        canonical::ordered_rows(&rows)
            .into_iter()
            .cloned()
            .collect(),
    )
    .to_string())
}
