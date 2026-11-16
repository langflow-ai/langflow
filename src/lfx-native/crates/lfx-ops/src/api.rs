//! The functions the Python and browser bindings call.
//!
//! Each function reads its [`Input`]s, calls the engine and returns a value.
//! The bindings turn an [`ApiError`] into their language's exception.

use std::fmt;

use crate::json;
use crate::json::serialize::{self, Ascii};
use crate::json::{FiniteFlowValue, FlowObj, FlowValue, NonFinite};

use crate::compare;
use crate::flow::deserialize::FromFlowValue;
use crate::flow::list::Renumber;
use crate::node_input::table_input;
use crate::op::apply::apply_flow_operations;
use crate::op::diff::derive_flow_operations;
use crate::op::operation::Operation;
use crate::op::repair::{Fix, repair_flow_data};
use crate::op::replay::replay_flow_operations;
use crate::op::restore;
use crate::op::{Applied, ApplyOptions, ReplayOptions, Replayed};
use crate::state::GraphState;
use crate::state::plain::GraphPlain;
use crate::validate::{Numbers, Violation, find_graph_violations};
use crate::violation::error::{Error, invalid};

/// An error as a JSON object with `kind`, `code`, `message`, and
/// `edge_id` or `violations` when it has them.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ApiError(pub FlowValue);

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

impl From<NonFinite> for ApiError {
    fn from(error: NonFinite) -> Self {
        Self::from(Error::from(error))
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

/// The result of a call, or the error.
pub type ApiResult<T = FlowValue> = Result<T, ApiError>;

// --- Output --------------------------------------------------------------------------------

/// JSON text with every non-ASCII character escaped as `\uXXXX`, as
/// Python's `json.dumps` writes it.
///
/// Every edge handle holds a `œ`, and Python and JavaScript decode ASCII
/// text fastest.
#[must_use]
pub fn json_text(value: &FlowValue) -> String {
    let mut out = Vec::new();
    serialize::write_value(&mut out, value, Ascii::Escape);
    serialize::into_string(out)
}

fn violations(violations: &[Violation]) -> FlowValue {
    FlowValue::Array(violations.iter().map(Violation::to_value).collect())
}

/// Operations as JSON. Each one moves its payload into the result.
fn operations_json(operations: Vec<Operation>) -> FlowValue {
    FlowValue::Array(operations.into_iter().map(Operation::into_value).collect())
}

// --- Input ---------------------------------------------------------------------------------

/// An argument: JSON text to parse, or a value a binding has already read,
/// such as a Python dict.
#[derive(Debug, Clone)]
pub enum Input<'t> {
    /// JSON text.
    Text(&'t str),
    /// A value, already read.
    Value(FlowValue),
}

impl<'t> From<&'t str> for Input<'t> {
    fn from(text: &'t str) -> Self {
        Self::Text(text)
    }
}

impl From<FlowValue> for Input<'_> {
    fn from(value: FlowValue) -> Self {
        Self::Value(value)
    }
}

/// A graph, or any other value the engine reads as data. Text may hold a
/// non-finite number, so validation can report it and repair can replace it.
fn data(input: Input<'_>) -> ApiResult<FlowValue> {
    match input {
        Input::Text(text) => Ok(parse_json(text)?),
        Input::Value(value) => Ok(value),
    }
}

/// A graph that the engine keeps or changes. Text with a non-finite number
/// is refused.
fn value(input: Input<'_>) -> ApiResult<FlowValue> {
    match input {
        Input::Text(text) => Ok(parse_finite_json(text)?),
        Input::Value(value) => Ok(value),
    }
}

/// A list of operations. Text with a number that is not finite is refused.
///
/// # Errors
///
/// The operations do not parse.
pub fn operations(input: Input<'_>) -> ApiResult<Vec<Operation>> {
    if let Input::Text(text) = input
        && let Some(operations) = crate::op::deserialize::operations_from_text(text)
    {
        return Ok(operations);
    }
    let value = match input {
        Input::Text(text) => serde_json::from_str(text)
            .map(|FiniteFlowValue(value)| value)
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

fn optional(input: Option<Input<'_>>) -> ApiResult<Option<FlowValue>> {
    input.map(data).transpose()
}

/// A list argument, named in the error when it is not a list or an item
/// has the wrong type: `rows: must be a list`.
fn list<T: FromFlowValue>(input: Input<'_>, name: &str) -> ApiResult<Vec<T>> {
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
pub fn applied_json(applied: Applied, options: ApplyOptions) -> FlowObj {
    let mut out = FlowObj::new();
    if options.forward {
        out.insert(
            "forward_operations".into(),
            operations_json(applied.forward),
        );
    }
    if options.backward {
        out.insert(
            "backward_operations".into(),
            FlowValue::Array(applied.backward.into_iter().map(operations_json).collect()),
        );
    }
    out
}

/// Write an operation into `out` as [`json_text`] writes it, replacing what
/// `out` holds. A caller reuses `out` for many operations.
pub fn write_operation_json(out: &mut Vec<u8>, operation: &Operation) {
    out.clear();
    operation.write_json(out, Ascii::Escape);
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
) -> ApiResult<FlowValue> {
    let (flow_data, applied) =
        apply_flow_operations(value(flow)?, operations(operations_in)?, options)?;
    let mut out = applied_json(applied, options);
    out.insert("flow_data".into(), flow_data);
    Ok(FlowValue::Object(out))
}

/// Load a graph into a [`GraphState`], to apply or replay many batches on it.
///
/// # Errors
///
/// The graph does not parse, or breaks a structural rule.
pub fn graph_state(flow: Input<'_>) -> ApiResult<GraphState> {
    Ok(GraphState::new(value(flow)?)?)
}

/// Apply a batch to a [`GraphState`]. The result is what [`applied_json`] lists.
///
/// # Errors
///
/// The operations do not parse, or the engine refuses the batch.
pub fn apply_to(
    state: &mut GraphState,
    operations_in: Input<'_>,
    options: ApplyOptions,
) -> ApiResult<FlowValue> {
    let applied = state.apply(operations(operations_in)?, options)?;
    Ok(FlowValue::Object(applied_json(applied, options)))
}

// --- Replay --------------------------------------------------------------------------------

/// What a replay did, as JSON: the backward operations with `backward`.
#[must_use]
pub fn replayed_json(replayed: Replayed, options: ReplayOptions) -> FlowObj {
    let mut out = FlowObj::new();
    if options.backward {
        out.insert(
            "backward_operations".into(),
            FlowValue::Array(replayed.backward.into_iter().map(operations_json).collect()),
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
) -> ApiResult<FlowValue> {
    let (flow_data, replayed) =
        replay_flow_operations(value(flow)?, operations(operations_in)?, options)?;
    let mut out = replayed_json(replayed, options);
    out.insert("flow_data".into(), flow_data);
    Ok(FlowValue::Object(out))
}

/// Replay stored operations on a [`GraphState`], with no rule. The result
/// is what [`replayed_json`] lists.
///
/// # Errors
///
/// The operations do not parse, or an operation cannot be carried out.
pub fn replay_to(
    state: &mut GraphState,
    operations_in: Input<'_>,
    options: ReplayOptions,
) -> ApiResult<FlowValue> {
    let replayed = state.replay(operations(operations_in)?, options)?;
    Ok(FlowValue::Object(replayed_json(replayed, options)))
}

// --- Diff, validation and repair ------------------------------------------------------------

/// The operations that turn `base` into `target`. A replay checks that they
/// give `target`.
///
/// # Errors
///
/// A graph does not parse or breaks the rules, or the operations do not replay.
pub fn ops_diff(base: Input<'_>, target: Input<'_>) -> ApiResult<FlowValue> {
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
) -> ApiResult<FlowValue> {
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
pub fn repair(flow: Input<'_>, base: Option<Input<'_>>) -> ApiResult<FlowValue> {
    let base = optional(base)?;
    let repaired = repair_flow_data(&data(flow)?, base.as_ref())?;
    let fixes: Vec<FlowValue> = repaired.fixes.iter().map(Fix::to_value).collect();
    let mut out = FlowObj::new();
    out.insert("flow_data".into(), repaired.flow_data);
    out.insert("fixes".into(), FlowValue::Array(fixes));
    Ok(FlowValue::Object(out))
}

// --- Plain graphs ---------------------------------------------------------------------------

/// Read a graph into a [`GraphPlain`], to run many checks on it.
///
/// # Errors
///
/// JSON text that does not parse, or holds a number that is not finite.
pub fn graph_plain(flow: Input<'_>) -> ApiResult<GraphPlain> {
    Ok(GraphPlain::new(value(flow)?))
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
) -> ApiResult<FlowValue> {
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
) -> ApiResult<(GraphPlain, FlowValue)> {
    let (repaired, fixes) = flow.repair(base)?;
    Ok((
        repaired,
        FlowValue::Array(fixes.iter().map(Fix::to_value).collect()),
    ))
}

/// [`ops_diff`] on plain graphs.
///
/// # Errors
///
/// A graph breaks the rules, or the operations do not replay.
pub fn plain_ops_diff(base: &GraphPlain, target: &GraphPlain) -> ApiResult<FlowValue> {
    Ok(operations_json(base.ops_diff(target)?.operations))
}

// --- Canonical form -------------------------------------------------------------------------

/// The SHA-256 hex digest of `text`, as a checkpoint row stores it.
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
    Ok(compare::graph_hash(&data(flow)?)?)
}

/// Whether two graphs are the same graph.
///
/// # Errors
///
/// A graph does not parse, or a compared number is not finite.
pub fn graphs_equal(left: Input<'_>, right: Input<'_>) -> ApiResult<bool> {
    Ok(compare::graphs_equal(&data(left)?, &data(right)?)?)
}

/// Whether two JSON values are the same value.
///
/// # Errors
///
/// A value does not parse, or a compared number is not finite.
pub fn values_equal(left: Input<'_>, right: Input<'_>) -> ApiResult<bool> {
    Ok(compare::values_equal(&data(left)?, &data(right)?)?)
}

/// A JSON value in RFC 8785 canonical form, as text.
///
/// # Errors
///
/// The value does not parse, or holds a number that is not finite.
pub fn canonical_json(value: Input<'_>) -> ApiResult<String> {
    Ok(compare::canonical_json(&data(value)?)?)
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
) -> ApiResult<FlowValue> {
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
/// The inputs do not parse, an input is not a list, or a handle holds a non-finite number.
pub fn edge_fixes(read: Input<'_>, shown: Input<'_>) -> ApiResult<FlowValue> {
    let fixes = restore::edge_fixes(&list(read, "read")?, &list(shown, "shown")?)?;
    Ok(operations_json(fixes))
}

/// The part of the fixes that touches the given edges.
///
/// # Errors
///
/// The inputs do not parse, or `edge_ids` is not a list of strings.
pub fn fixes_for_edges(fixes: Input<'_>, edge_ids: Input<'_>) -> ApiResult<FlowValue> {
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
pub fn strip_row_keys(rows: Input<'_>) -> ApiResult<FlowValue> {
    Ok(table_input::strip_row_keys(&data(rows)?))
}

/// A flow whose top-level tables have their rows in order and without `__id__` and `__pos__`.
///
/// # Errors
///
/// The flow does not parse.
pub fn strip_flow_table_row_keys(flow: Input<'_>) -> ApiResult<FlowValue> {
    let mut flow = data(flow)?;
    table_input::strip_flow_table_row_keys(&mut flow);
    Ok(flow)
}

/// Rows with the ids and positions a write needs. `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The inputs do not parse, `rows` is not a list, or a row holds a non-finite number.
pub fn assign_row_ids(
    rows: Input<'_>,
    previous: Option<Input<'_>>,
    editor: bool,
) -> ApiResult<FlowValue> {
    let mut rows = list(rows, "rows")?;
    table_input::assign_row_ids(&mut rows, optional(previous)?.as_ref(), renumber(editor))?;
    Ok(FlowValue::Array(rows))
}

/// A node being added, with ids on every table. `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The node does not parse, or a compared row holds a number that is not finite.
pub fn assign_table_row_ids(node: Input<'_>, editor: bool) -> ApiResult<FlowValue> {
    let mut node = data(node)?;
    table_input::assign_table_row_ids(&mut node, renumber(editor))?;
    Ok(node)
}

/// `target` with ids on the tables it adds or changes relative to `base`.
///
/// # Errors
///
/// The graphs do not parse, or a compared row holds a number that is not finite.
pub fn assign_changed_table_row_ids(
    base: Input<'_>,
    target: Input<'_>,
    editor: bool,
) -> ApiResult<FlowValue> {
    let mut target = data(target)?;
    table_input::assign_changed_table_row_ids(&data(base)?, &mut target, renumber(editor))?;
    Ok(target)
}

/// Rows with `new_rows` appended, each with a new id one position past the last.
///
/// # Errors
///
/// The inputs do not parse, an input is not a list, or a row holds a non-finite number.
pub fn append_table_rows(rows: Input<'_>, new_rows: Input<'_>) -> ApiResult<FlowValue> {
    let mut rows = list(rows, "rows")?;
    table_input::append_table_rows(&mut rows, &list(new_rows, "new_rows")?)?;
    Ok(FlowValue::Array(rows))
}

/// A node with ids on the tables it adds or changes relative to `previous`,
/// the same node as stored.
///
/// # Errors
///
/// The inputs do not parse, or a compared row holds a number that is not finite.
pub fn assign_changed_node_table_row_ids(
    node: Input<'_>,
    previous: Option<Input<'_>>,
    editor: bool,
) -> ApiResult<FlowValue> {
    let mut node = data(node)?;
    table_input::assign_changed_node_table_row_ids(
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
pub fn table_fields(node: Input<'_>) -> ApiResult<FlowValue> {
    Ok(json!(table_input::table_fields(&data(node)?)))
}

/// Rows in order, by `(__pos__, __id__)`, or as stored for a legacy table.
///
/// # Errors
///
/// The rows do not parse, or are not a list.
pub fn ordered_rows(rows: Input<'_>) -> ApiResult<FlowValue> {
    let rows: Vec<FlowValue> = list(rows, "rows")?;
    Ok(FlowValue::Array(
        table_input::ordered_rows(&rows)
            .into_iter()
            .cloned()
            .collect(),
    ))
}

/// Parse JSON text, reporting a parse failure as an invalid graph.
fn parse_json(text: &str) -> Result<FlowValue, Error> {
    serde_json::from_str(text).map_err(|error| graph_not_json(&error))
}

/// [`parse_json`], but it refuses a number that is not finite as a double
/// ([`FiniteFlowValue`]).
fn parse_finite_json(text: &str) -> Result<FlowValue, Error> {
    serde_json::from_str(text)
        .map(|FiniteFlowValue(value)| value)
        .map_err(|error| graph_not_json(&error))
}

fn graph_not_json(error: &serde_json::Error) -> Error {
    Error::graph_message(format!(
        "flow data is not valid JSON: {}",
        parse_problem(error)
    ))
}

/// Why JSON text does not parse. A refused value, such as `1e400`, is named
/// without its place in the text, as Python names it.
fn parse_problem(error: &serde_json::Error) -> String {
    let text = error.to_string();
    if error.is_data()
        && let Some((problem, _)) = text.rsplit_once(" at line ")
    {
        return problem.to_owned();
    }
    text
}

#[cfg(test)]
mod tests {
    use super::*;

    fn refused(result: ApiResult) -> ApiError {
        result.expect_err("a non-list argument must be refused")
    }

    #[test]
    fn kept_graphs_and_operations_refuse_a_number_that_is_not_finite() {
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
            FlowValue::Null
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
        let empty = FlowValue::Array(Vec::new());
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
        let value: FlowValue = serde_json::from_str(text).unwrap();
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
        let value: FlowValue = serde_json::from_str(text).unwrap();
        let written = json_text(&value);
        assert_eq!(
            written,
            r#"{"handle":"{\u0153name\u0153:\u0153out\u0153}","emoji":"\ud83d\ude00","quote":"a \"b\"\n","int":12345678901234567890123,"float":1.0}"#
        );
        assert_eq!(serde_json::from_str::<FlowValue>(&written).unwrap(), value);
        // A character before, across and after each 16-byte step of the scan.
        for offset in 0..40 {
            let value = FlowValue::from(format!("{}é{}😀", "a".repeat(offset), "b".repeat(offset)));
            let written = json_text(&value);
            assert!(written.is_ascii(), "{written}");
            assert_eq!(serde_json::from_str::<FlowValue>(&written).unwrap(), value);
        }
    }

    #[test]
    fn graph_json_writes_the_graph_as_ascii() {
        let flow = r#"{"nodes":[{"id":"a","data":{"node":{"template":{"t":{"value":"é","type":"str"}}}}}],"edges":[]}"#;
        let state = graph_state(flow.into()).unwrap();
        let written = state.to_json();
        assert!(written.is_ascii());
        assert_eq!(
            serde_json::from_str::<FlowValue>(&written).unwrap(),
            state.to_value()
        );
    }
}
