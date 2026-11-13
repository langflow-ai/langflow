//! The functions the Python and browser bindings call.
//!
//! Each argument is an [`Input`]: JSON text, or a value that the binding has
//! already read, such as a Python dict. Each result is a value; the browser
//! binding writes it as text with [`json_text`], and the Python binding builds
//! Python objects from it. A number keeps what [`crate::value::Number`] keeps:
//! `1` and `1.0` apart, and the digits of an integer too large for 64 bits.
//! Each function here does no more than read its inputs, call the engine and
//! return its result; the bindings only call these and turn an [`ApiError`]
//! into their language's exception.

use std::fmt;

use crate::json;
use crate::json_out::{self, Ascii};
use crate::value::{AnyMap, AnyValue, FiniteAnyValue};

use crate::ops::apply::{Applied, ApplyOptions, apply_flow_operations};
use crate::ops::canonical;
use crate::ops::diff::derive_flow_operations;
use crate::ops::error::{Error, invalid};
use crate::ops::from_value::FromAnyValue;
use crate::ops::keyed::{self, Renumber};
use crate::ops::ops::Operation;
use crate::ops::plain::GraphPlain;
use crate::ops::repair::{Fix, repair_flow_data};
use crate::ops::replay::{ReplayOptions, Replayed, replay_flow_operations};
use crate::ops::restore;
use crate::ops::state::{GraphSnapshot, GraphState, parse_finite_json, parse_json, parse_problem};
use crate::ops::validate::{Numbers, Violation, find_graph_violations};

/// An error as the bindings receive it: a JSON object with the error's
/// `kind` (the matching Python exception class), `code` and `message`, and
/// what that kind carries (`edge_id`, `violations`, or `graph`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ApiError(pub AnyValue);

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

impl fmt::Display for ApiError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.code(), self.message())
    }
}

impl std::error::Error for ApiError {}

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

/// The result of a call, or the error.
pub type ApiResult<T = AnyValue> = Result<T, ApiError>;

// --- Output --------------------------------------------------------------------------------

/// JSON text as the API returns it: ASCII only, every other character
/// escaped as `\uXXXX`, as Python's `json.dumps` writes by default.
///
/// Every edge handle holds a `œ`. Python keeps a string with one at two bytes
/// per character, and both Python and JavaScript decode an ASCII string
/// fastest, so ASCII text is faster for Python to build and to read. Canonical
/// text ([`canonical_json`]) is not escaped: RFC 8785 writes the characters.
#[must_use]
pub fn json_text(value: &AnyValue) -> String {
    let mut out = Vec::new();
    json_out::write_value(&mut out, value, Ascii::Escape);
    json_out::into_string(out)
}

/// A graph state as JSON text, as [`json_text`] writes it.
#[must_use]
pub fn graph_json(state: &GraphState) -> String {
    json_out::into_string(state.json_text())
}

/// A graph state with its staged batch as JSON text, as [`json_text`] writes
/// it ([`GraphState::staged_json`]), or `None` when no batch is staged.
#[must_use]
pub fn staged_graph_json(state: &GraphState) -> Option<String> {
    state.staged_json_text().map(json_out::into_string)
}

fn violations(violations: &[Violation]) -> AnyValue {
    AnyValue::Array(violations.iter().map(Violation::to_value).collect())
}

/// Operations as JSON. The caller owns them and drops them after, so each
/// one moves its payload into the result.
fn operations_json(operations: Vec<Operation>) -> AnyValue {
    AnyValue::Array(operations.into_iter().map(Operation::into_value).collect())
}

// --- Input ---------------------------------------------------------------------------------

/// An argument: JSON text to parse, or a value a binding has already read,
/// such as a Python dict.
///
/// Text is parsed by what the argument is. Graphs and other data that do not
/// parse are an invalid graph, and operations that do not parse are invalid
/// operations, as when every argument was text.
#[derive(Debug, Clone)]
pub enum Input<'t> {
    /// JSON text.
    Text(&'t str),
    /// A value, already read.
    Value(AnyValue),
}

impl<'t> From<&'t str> for Input<'t> {
    fn from(text: &'t str) -> Self {
        Self::Text(text)
    }
}

impl From<AnyValue> for Input<'_> {
    fn from(value: AnyValue) -> Self {
        Self::Value(value)
    }
}

/// A graph, or any other value the engine reads as data. Validation and
/// repair read a number that is not finite in text, to report it and to
/// replace it.
fn data(input: Input<'_>) -> ApiResult<AnyValue> {
    match input {
        Input::Text(text) => Ok(parse_json(text)?),
        Input::Value(value) => Ok(value),
    }
}

/// A graph that the engine holds or changes: a [`GraphState`], a
/// [`GraphPlain`], and the graph of [`apply`] and [`replay`]. Text with a
/// number that is not finite is refused, as a Python `float` that is not
/// finite is.
fn held(input: Input<'_>) -> ApiResult<AnyValue> {
    match input {
        Input::Text(text) => Ok(parse_finite_json(text)?),
        Input::Value(value) => Ok(value),
    }
}

/// A list of operations. Text with a number that is not finite is refused.
fn operations(input: Input<'_>) -> ApiResult<Vec<Operation>> {
    let value = match input {
        Input::Text(text) => serde_json::from_str(text)
            .map(|FiniteAnyValue(value)| value)
            .map_err(|error| {
                ApiError::from(invalid!(
                    "operations are not valid JSON: {}",
                    parse_problem(&error)
                ))
            })?,
        Input::Value(value) => value,
    };
    Ok(Operation::list_from_value(value)?)
}

fn optional(input: Option<Input<'_>>) -> ApiResult<Option<AnyValue>> {
    input.map(data).transpose()
}

/// A list argument, named in the error when it is not a list or an item
/// has the wrong type: `rows: must be a list`.
fn list<T: FromAnyValue>(input: Input<'_>, name: &str) -> ApiResult<Vec<T>> {
    Ok(Vec::from_value(data(input)?).map_err(|error| error.into_error(name))?)
}

fn renumber(editor: bool) -> Renumber {
    if editor {
        Renumber::WhenNoRoom
    } else {
        Renumber::Never
    }
}

// --- Apply ---------------------------------------------------------------------------------

/// What a batch did, as JSON: the forward operations with `forward`, and the
/// backward operations with `backward`.
#[must_use]
pub fn applied_json(applied: Applied, options: ApplyOptions) -> AnyMap {
    let mut out = AnyMap::new();
    if options.forward {
        out.insert(
            "forward_operations".into(),
            operations_json(applied.forward),
        );
    }
    if options.backward {
        out.insert(
            "backward_operations".into(),
            AnyValue::Array(applied.backward.into_iter().map(operations_json).collect()),
        );
    }
    out
}

/// An operation as [`json_text`] writes it, in place of what `out` held: the
/// text an operation log stores, without a value that the caller would write
/// as JSON again. A caller that writes many reuses `out`, so the text does
/// not grow a new buffer each time.
pub fn write_operation_json(out: &mut Vec<u8>, operation: &Operation) {
    out.clear();
    json_out::write_value(out, &operation.clone().into_value(), Ascii::Escape);
}

/// Apply operations to a graph: `{"flow_data", ...}` and what [`applied_json`] lists.
///
/// # Errors
///
/// The graph or the operations do not parse, or the engine refuses the batch.
pub fn apply(
    flow: Input<'_>,
    operations_in: Input<'_>,
    options: ApplyOptions,
) -> ApiResult<AnyValue> {
    let (flow_data, applied) =
        apply_flow_operations(held(flow)?, operations(operations_in)?, options)?;
    let mut out = applied_json(applied, options);
    out.insert("flow_data".into(), flow_data);
    Ok(AnyValue::Object(out))
}

/// Load a graph into a [`GraphState`], to apply or replay many batches on it.
///
/// # Errors
///
/// The graph does not parse, or breaks a structural rule.
pub fn graph_state(flow: Input<'_>) -> ApiResult<GraphState> {
    Ok(GraphState::new(held(flow)?)?)
}

/// The SHA-256 hex digest of a [`GraphState`]'s canonical form
/// ([`GraphState::graph_hash`]): the committed graph, without a staged batch.
///
/// # Errors
///
/// The graph holds a number that is not finite.
pub fn state_graph_hash(state: &GraphState) -> ApiResult<String> {
    Ok(state.graph_hash()?)
}

/// [`state_graph_hash`] of the graph with its staged batch
/// ([`GraphState::staged_graph_hash`]), or `None` when no batch is staged.
///
/// # Errors
///
/// The graph holds a number that is not finite.
pub fn staged_state_graph_hash(state: &GraphState) -> ApiResult<Option<String>> {
    Ok(state.staged_graph_hash().transpose()?)
}

/// A [`GraphSnapshot`] as JSON text, as [`json_text`] writes it: what
/// [`graph_json`] gave when the snapshot was taken.
#[must_use]
pub fn snapshot_json(snapshot: &GraphSnapshot) -> String {
    json_out::into_string(snapshot.json_text())
}

/// The SHA-256 hex digest of a [`GraphSnapshot`]'s canonical form: what
/// [`state_graph_hash`] gave when the snapshot was taken.
///
/// # Errors
///
/// The graph holds a number that is not finite.
pub fn snapshot_graph_hash(snapshot: &GraphSnapshot) -> ApiResult<String> {
    Ok(snapshot.graph_hash()?)
}

/// Apply a batch to a [`GraphState`]; the result is what [`applied_json`] lists.
///
/// # Errors
///
/// The operations do not parse, or the engine refuses the batch, which then
/// changes nothing.
pub fn apply_to(
    state: &mut GraphState,
    operations_in: Input<'_>,
    options: ApplyOptions,
) -> ApiResult<AnyValue> {
    let applied = apply_to_typed(state, operations_in, options)?;
    Ok(AnyValue::Object(applied_json(applied, options)))
}

/// Stage a batch on a [`GraphState`] ([`GraphState::stage`]); the result is
/// what [`applied_json`] lists, as for [`apply_to`].
///
/// # Errors
///
/// The operations do not parse, or the engine refuses the batch, which then
/// is not staged.
pub fn stage_to(
    state: &mut GraphState,
    operations_in: Input<'_>,
    options: ApplyOptions,
) -> ApiResult<AnyValue> {
    let applied = stage_to_typed(state, operations_in, options)?;
    Ok(AnyValue::Object(applied_json(applied, options)))
}

/// Apply a batch and keep its operation types for a binding's output builder.
///
/// # Errors
///
/// The inputs and rules are the same as [`apply_to`].
pub fn apply_to_typed(
    state: &mut GraphState,
    operations_in: Input<'_>,
    options: ApplyOptions,
) -> ApiResult<Applied> {
    Ok(state.apply(operations(operations_in)?, options)?)
}

/// Stage a batch and keep its operation types for a binding's output builder.
///
/// # Errors
///
/// The inputs and rules are the same as [`stage_to`].
pub fn stage_to_typed(
    state: &mut GraphState,
    operations_in: Input<'_>,
    options: ApplyOptions,
) -> ApiResult<Applied> {
    Ok(state.stage(operations(operations_in)?, options)?)
}

// --- Replay --------------------------------------------------------------------------------

/// What a replay did, as JSON: the backward operations with `backward`.
#[must_use]
pub fn replayed_json(replayed: Replayed, options: ReplayOptions) -> AnyMap {
    let mut out = AnyMap::new();
    if options.backward {
        out.insert(
            "backward_operations".into(),
            AnyValue::Array(replayed.backward.into_iter().map(operations_json).collect()),
        );
    }
    out
}

/// Replay stored operations on a graph, with no rule: `{"flow_data", ...}`
/// and what [`replayed_json`] lists.
///
/// # Errors
///
/// The graph or the operations do not parse, the graph breaks a structural rule,
/// or an operation cannot be carried out.
pub fn replay(
    flow: Input<'_>,
    operations_in: Input<'_>,
    options: ReplayOptions,
) -> ApiResult<AnyValue> {
    let (flow_data, replayed) =
        replay_flow_operations(held(flow)?, operations(operations_in)?, options)?;
    let mut out = replayed_json(replayed, options);
    out.insert("flow_data".into(), flow_data);
    Ok(AnyValue::Object(out))
}

/// Replay stored operations on a [`GraphState`], with no rule; the result
/// is what [`replayed_json`] lists.
///
/// # Errors
///
/// The operations do not parse, or an operation cannot be carried out,
/// which then changes nothing.
pub fn replay_to(
    state: &mut GraphState,
    operations_in: Input<'_>,
    options: ReplayOptions,
) -> ApiResult<AnyValue> {
    let replayed = state.replay(operations(operations_in)?, options)?;
    Ok(AnyValue::Object(replayed_json(replayed, options)))
}

// --- Diff, validation and repair ------------------------------------------------------------

/// The operations that turn `base` into `target`, checked by replay: applied
/// to `base`, they must give `target`, or the diff is refused. So a defect in
/// the diff can never record history that replays to another graph.
///
/// # Errors
///
/// A graph does not parse or breaks the rules, or the operations do not replay.
pub fn ops_diff(base: Input<'_>, target: Input<'_>) -> ApiResult<AnyValue> {
    let derived = derive_flow_operations(data(base)?, &data(target)?)?;
    Ok(operations_json(derived.operations))
}

/// Every rule a graph breaks, against the stored graph a write replaces when given.
///
/// # Errors
///
/// A graph does not parse, or a check fails in a way that is not a violation.
pub fn validate(
    flow: Input<'_>,
    base: Option<Input<'_>>,
    check_values: bool,
) -> ApiResult<AnyValue> {
    let base = optional(base)?;
    let numbers = if check_values {
        Numbers::Check
    } else {
        Numbers::Skip
    };
    Ok(violations(&find_graph_violations(
        &data(flow)?,
        numbers,
        base.as_ref(),
    )?))
}

/// Repair what has one fix: `{"flow_data", "fixes"}`.
///
/// # Errors
///
/// A graph does not parse, or a rule only the client can fix is broken.
pub fn repair(flow: Input<'_>, base: Option<Input<'_>>) -> ApiResult<AnyValue> {
    let base = optional(base)?;
    let repaired = repair_flow_data(&data(flow)?, base.as_ref())?;
    let fixes: Vec<AnyValue> = repaired.fixes.iter().map(Fix::to_value).collect();
    let mut out = AnyMap::new();
    out.insert("flow_data".into(), repaired.flow_data);
    out.insert("fixes".into(), AnyValue::Array(fixes));
    Ok(AnyValue::Object(out))
}

// --- Plain graphs ---------------------------------------------------------------------------

/// Read a graph into a [`GraphPlain`], to run many checks on it. Nothing is
/// checked.
///
/// # Errors
///
/// JSON text that does not parse, or holds a number that is not finite.
pub fn graph_plain(flow: Input<'_>) -> ApiResult<GraphPlain> {
    Ok(GraphPlain::new(held(flow)?))
}

/// [`validate`] on plain graphs.
///
/// # Errors
///
/// A check fails in a way that is not a violation.
pub fn plain_validate(
    flow: &GraphPlain,
    base: Option<&GraphPlain>,
    check_values: bool,
) -> ApiResult<AnyValue> {
    let numbers = if check_values {
        Numbers::Check
    } else {
        Numbers::Skip
    };
    Ok(violations(&flow.violations(base, numbers)?))
}

/// [`repair`] on plain graphs: the repaired graph, and the fixes as JSON.
///
/// # Errors
///
/// A rule only the client can fix is broken.
pub fn plain_repair(
    flow: &GraphPlain,
    base: Option<&GraphPlain>,
) -> ApiResult<(GraphPlain, AnyValue)> {
    let (repaired, fixes) = flow.repair(base)?;
    Ok((
        repaired,
        AnyValue::Array(fixes.iter().map(Fix::to_value).collect()),
    ))
}

/// [`graph_hash`] of a plain graph.
///
/// # Errors
///
/// The graph holds a number that is not finite.
pub fn plain_graph_hash(flow: &GraphPlain) -> ApiResult<String> {
    Ok(flow.graph_hash()?)
}

/// [`graphs_equal`] on plain graphs.
///
/// # Errors
///
/// A graph holds a number that is not finite.
pub fn plain_equals(left: &GraphPlain, right: &GraphPlain) -> ApiResult<bool> {
    Ok(left.equals(right)?)
}

/// [`ops_diff`] on plain graphs.
///
/// # Errors
///
/// A graph breaks the rules, or the operations do not replay.
pub fn plain_ops_diff(base: &GraphPlain, target: &GraphPlain) -> ApiResult<AnyValue> {
    Ok(operations_json(base.ops_diff(target)?.operations))
}

// --- Canonical form -------------------------------------------------------------------------

/// The SHA-256 hex digest of `text`, byte for byte: the hash a checkpoint
/// row stores for its JSON text.
#[must_use]
pub fn text_sha256(text: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    const HEX: &[u8; 16] = b"0123456789abcdef";
    Sha256::digest(text)
        .iter()
        .flat_map(|byte| [HEX[usize::from(byte >> 4)], HEX[usize::from(byte & 0xf)]])
        .map(char::from)
        .collect()
}

/// The SHA-256 hex digest of a graph's canonical form.
///
/// # Errors
///
/// The graph does not parse, or holds a number that is not finite.
pub fn graph_hash(flow: Input<'_>) -> ApiResult<String> {
    Ok(canonical::graph_hash(&data(flow)?)?)
}

/// Whether two graphs are the same graph.
///
/// # Errors
///
/// A graph does not parse, or a compared number is not finite.
pub fn graphs_equal(left: Input<'_>, right: Input<'_>) -> ApiResult<bool> {
    Ok(canonical::graphs_equal(&data(left)?, &data(right)?)?)
}

/// Whether two JSON values are the same value.
///
/// # Errors
///
/// A value does not parse, or a compared number is not finite.
pub fn values_equal(left: Input<'_>, right: Input<'_>) -> ApiResult<bool> {
    Ok(canonical::values_equal(&data(left)?, &data(right)?)?)
}

/// A JSON value in RFC 8785 canonical form, as text.
///
/// # Errors
///
/// The value does not parse, or holds a number that is not finite.
pub fn canonical_json(value: Input<'_>) -> ApiResult<String> {
    Ok(canonical::canonical_json(&data(value)?)?)
}

// --- Restore fixes --------------------------------------------------------------------------

/// A revision with a restore's fixes applied, after checking each one.
///
/// # Errors
///
/// The inputs do not parse, or a fix is not allowed or does not apply.
pub fn apply_restore_fixes(
    revision: Input<'_>,
    stored: Input<'_>,
    fixes: Input<'_>,
) -> ApiResult<AnyValue> {
    Ok(restore::apply_restore_fixes(
        &data(revision)?,
        &data(stored)?,
        operations(fixes)?,
    )?)
}

/// The fixes that turn a revision's edges as read into the edges its preview shows.
///
/// # Errors
///
/// The inputs do not parse, an input is not a list, or a compared handle
/// holds a number that is not finite.
pub fn edge_fixes(read: Input<'_>, shown: Input<'_>) -> ApiResult<AnyValue> {
    let fixes = restore::edge_fixes(&list(read, "read")?, &list(shown, "shown")?)?;
    Ok(operations_json(fixes))
}

/// The part of the fixes that touches the given edges.
///
/// # Errors
///
/// The inputs do not parse, or `edge_ids` is not a list of strings.
pub fn fixes_for_edges(fixes: Input<'_>, edge_ids: Input<'_>) -> ApiResult<AnyValue> {
    let ids: Vec<String> = list(edge_ids, "edge_ids")?;
    Ok(operations_json(restore::fixes_for_edges(
        &operations(fixes)?,
        &ids,
    )))
}

// --- Table rows -----------------------------------------------------------------------------

/// Rows in order and without `__id__` and `__pos__`.
///
/// # Errors
///
/// The rows do not parse.
pub fn strip_row_keys(rows: Input<'_>) -> ApiResult<AnyValue> {
    Ok(keyed::strip_row_keys(&data(rows)?))
}

/// A flow whose top-level tables have their rows in order and without `__id__` and `__pos__`.
///
/// # Errors
///
/// The flow does not parse.
pub fn strip_flow_table_row_keys(flow: Input<'_>) -> ApiResult<AnyValue> {
    let mut flow = data(flow)?;
    keyed::strip_flow_table_row_keys(&mut flow);
    Ok(flow)
}

/// Rows with the ids and positions a write needs. `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The inputs do not parse, `rows` is not a list, or a compared row holds a
/// number that is not finite.
pub fn assign_row_ids(
    rows: Input<'_>,
    previous: Option<Input<'_>>,
    editor: bool,
) -> ApiResult<AnyValue> {
    let mut rows = list(rows, "rows")?;
    keyed::assign_row_ids(&mut rows, optional(previous)?.as_ref(), renumber(editor))?;
    Ok(AnyValue::Array(rows))
}

/// A node being added, with ids on every table. `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The node does not parse, or a compared row holds a number that is not finite.
pub fn assign_table_row_ids(node: Input<'_>, editor: bool) -> ApiResult<AnyValue> {
    let mut node = data(node)?;
    keyed::assign_table_row_ids(&mut node, renumber(editor))?;
    Ok(node)
}

/// `target` with ids on the tables it adds or changes relative to `base`.
/// `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The graphs do not parse, or a compared row holds a number that is not finite.
pub fn assign_changed_table_row_ids(
    base: Input<'_>,
    target: Input<'_>,
    editor: bool,
) -> ApiResult<AnyValue> {
    let mut target = data(target)?;
    keyed::assign_changed_table_row_ids(&data(base)?, &mut target, renumber(editor))?;
    Ok(target)
}

/// Rows with `new_rows` appended, each with a new id one position past the last.
///
/// # Errors
///
/// The inputs do not parse, an input is not a list, or a compared row holds
/// a number that is not finite.
pub fn append_table_rows(rows: Input<'_>, new_rows: Input<'_>) -> ApiResult<AnyValue> {
    let mut rows = list(rows, "rows")?;
    keyed::append_table_rows(&mut rows, &list(new_rows, "new_rows")?)?;
    Ok(AnyValue::Array(rows))
}

/// A node with ids on the tables it adds or changes relative to `previous`,
/// the same node as stored. `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The inputs do not parse, or a compared row holds a number that is not finite.
pub fn assign_changed_node_table_row_ids(
    node: Input<'_>,
    previous: Option<Input<'_>>,
    editor: bool,
) -> ApiResult<AnyValue> {
    let mut node = data(node)?;
    keyed::assign_changed_node_table_row_ids(
        &mut node,
        optional(previous)?.as_ref(),
        renumber(editor),
    )?;
    Ok(node)
}

/// The names of a node's template fields whose value is a table.
///
/// # Errors
///
/// The node does not parse.
pub fn table_fields(node: Input<'_>) -> ApiResult<AnyValue> {
    Ok(json!(keyed::table_fields(&data(node)?)))
}

/// A new random edge id in the editor's format.
#[must_use]
pub fn new_edge_id() -> String {
    crate::ops::ids::new_edge_id()
}

/// A new random table row id in the editor's format.
#[must_use]
pub fn new_table_row_id() -> String {
    crate::ops::ids::new_table_row_id()
}

/// The node schema the engine reads, as JSON text.
#[must_use]
pub fn node_schema() -> &'static str {
    crate::ops::schema::NODE_SCHEMA_JSON
}

/// Rows in order, by `(__pos__, __id__)`, or as stored for a legacy table.
///
/// # Errors
///
/// The rows do not parse, or are not a list.
pub fn ordered_rows(rows: Input<'_>) -> ApiResult<AnyValue> {
    let rows: Vec<AnyValue> = list(rows, "rows")?;
    Ok(AnyValue::Array(
        canonical::ordered_rows(&rows)
            .into_iter()
            .cloned()
            .collect(),
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn refused(result: ApiResult) -> ApiError {
        result.expect_err("a non-list argument must be refused")
    }

    #[test]
    fn held_graphs_and_operations_refuse_a_number_that_is_not_finite() {
        let flow = r#"{"nodes": [], "edges": [], "zoom": 1e400}"#;
        let not_json = "flow data is not valid JSON: NaN and Infinity are not JSON numbers";
        let errors = [
            graph_state(flow.into()).unwrap_err(),
            graph_plain(flow.into()).unwrap_err(),
            apply(flow.into(), "[]".into(), ApplyOptions::default()).unwrap_err(),
            replay(flow.into(), "[]".into(), ReplayOptions::default()).unwrap_err(),
        ];
        for error in errors {
            assert_eq!(
                (error.kind(), error.code()),
                ("FlowDataValidationError", "FLOW_GRAPH_INVALID")
            );
            assert_eq!(error.message(), not_json);
        }
        let empty = r#"{"nodes": [], "edges": []}"#;
        let operations = r#"[{"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["position"], "value": -1e400}]}]"#;
        let error = apply(empty.into(), operations.into(), ApplyOptions::default()).unwrap_err();
        assert_eq!(error.kind(), "FlowOperationValidationError");
        assert_eq!(
            error.message(),
            "operations are not valid JSON: NaN and Infinity are not JSON numbers"
        );
        // Validation and repair read the number, to report it and to replace it.
        let violations = validate(flow.into(), None, true).unwrap();
        assert_eq!(violations[0]["code"], "NON_FINITE_NUMBER");
        assert_eq!(
            repair(flow.into(), None).unwrap()["flow_data"]["zoom"],
            AnyValue::Null
        );
    }

    #[test]
    fn list_arguments_refuse_a_value_that_is_not_a_list() {
        for (error, message) in [
            (
                refused(assign_row_ids(r#"{"a": 1}"#.into(), None, false)),
                "rows: must be a list",
            ),
            (refused(ordered_rows("null".into())), "rows: must be a list"),
            (
                refused(append_table_rows("{}".into(), "[]".into())),
                "rows: must be a list",
            ),
            (
                refused(append_table_rows("[]".into(), r#""row""#.into())),
                "new_rows: must be a list",
            ),
            (
                refused(edge_fixes("{}".into(), "[]".into())),
                "read: must be a list",
            ),
            (
                refused(edge_fixes("[]".into(), "5".into())),
                "shown: must be a list",
            ),
            (
                refused(fixes_for_edges("[]".into(), r#"{"id": "e1"}"#.into())),
                "edge_ids: must be a list",
            ),
            (
                refused(fixes_for_edges("[]".into(), r#"["e1", 5]"#.into())),
                "edge_ids[1]: must be a string",
            ),
        ] {
            assert_eq!(error.kind(), "FlowOperationValidationError");
            assert_eq!(error.code(), "FLOW_OPERATION_INVALID");
            assert_eq!(error.message(), message);
        }
    }

    #[test]
    fn list_arguments_accept_lists() {
        let empty = AnyValue::Array(Vec::new());
        assert_eq!(assign_row_ids("[]".into(), None, false).unwrap(), empty);
        assert_eq!(ordered_rows("[]".into()).unwrap(), empty);
        assert_eq!(append_table_rows("[]".into(), "[]".into()).unwrap(), empty);
        assert_eq!(edge_fixes("[]".into(), "[]".into()).unwrap(), empty);
        assert_eq!(
            fixes_for_edges("[]".into(), r#"["e1"]"#.into()).unwrap(),
            empty
        );
    }

    #[test]
    fn a_value_reads_as_its_text_does() {
        let text = r#"{"nodes": [], "edges": [], "n": 1.0}"#;
        let value: AnyValue = serde_json::from_str(text).unwrap();
        assert_eq!(
            graph_hash(text.into()).unwrap(),
            graph_hash(value.into()).unwrap()
        );
        let error = refused(ops_diff("{".into(), "{}".into()));
        assert_eq!(error.code(), "FLOW_GRAPH_INVALID");
        let state = graph_state(r#"{"nodes": [], "edges": []}"#.into());
        let error = apply_to(&mut state.unwrap(), "[".into(), ApplyOptions::default());
        assert_eq!(refused(error).code(), "FLOW_OPERATION_INVALID");
    }

    #[test]
    fn json_text_is_ascii_and_reads_back_as_written() {
        let text = r#"{"handle":"{œnameœ:œoutœ}","emoji":"😀","quote":"a \"b\"\n","int":12345678901234567890123,"float":1.0}"#;
        let value: AnyValue = serde_json::from_str(text).unwrap();
        let written = json_text(&value);
        assert_eq!(
            written,
            r#"{"handle":"{\u0153name\u0153:\u0153out\u0153}","emoji":"\ud83d\ude00","quote":"a \"b\"\n","int":12345678901234567890123,"float":1.0}"#
        );
        assert_eq!(serde_json::from_str::<AnyValue>(&written).unwrap(), value);
        // A character before, across and after each 16-byte step of the scan.
        for offset in 0..40 {
            let value = AnyValue::from(format!("{}é{}😀", "a".repeat(offset), "b".repeat(offset)));
            let written = json_text(&value);
            assert!(written.is_ascii(), "{written}");
            assert_eq!(serde_json::from_str::<AnyValue>(&written).unwrap(), value);
        }
    }

    #[test]
    fn graph_json_writes_the_graph_as_ascii() {
        let flow = r#"{"nodes":[{"id":"a","data":{"node":{"template":{"t":{"value":"é","type":"str"}}}}}],"edges":[]}"#;
        let state = graph_state(flow.into()).unwrap();
        let written = graph_json(&state);
        assert!(written.is_ascii());
        assert_eq!(
            serde_json::from_str::<AnyValue>(&written).unwrap(),
            serde_json::from_str::<AnyValue>(&state.to_json()).unwrap()
        );
    }
}
