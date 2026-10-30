//! The functions the Python and browser bindings call.
//!
//! Each argument is an [`Input`]: JSON text, or a value that the binding has
//! already read, such as a Python dict. Each result is a value; the browser
//! binding writes it as text with [`json_text`], and the Python binding builds
//! Python objects from it. Text keeps every number's original text.
//! Each function here does no more than read its inputs, call the engine and
//! return its result; the bindings only call these and turn an [`ApiError`]
//! into their language's exception.

use std::fmt;
use std::io;

use serde::Serialize;
use serde_json::ser::Formatter;
use serde_json::{Map, Value, json};

use crate::ops::apply::{Applied, ApplyOptions, apply_flow_operations};
use crate::ops::canonical;
use crate::ops::diff::{derive_flow_operations, diff_flow_data};
use crate::ops::error::{Error, invalid};
use crate::ops::from_value::FromValue;
use crate::ops::keyed::{self, Renumber};
use crate::ops::ops::Operation;
use crate::ops::repair::{Fix, repair_flow_data};
use crate::ops::restore;
use crate::ops::state::{GraphState, parse_json};
use crate::ops::validate::{Numbers, Violation, find_graph_violations};

/// An error as the bindings receive it: a JSON object with the error's
/// `kind` (the matching Python exception class), `code` and `message`, and
/// what that kind carries (`edge_id`, `violations`, or `graph`).
#[derive(Debug, Clone, PartialEq, Eq)]
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
pub type ApiResult<T = Value> = Result<T, ApiError>;

// --- Output --------------------------------------------------------------------------------

/// JSON text as the API returns it: ASCII only, every other character
/// escaped as `\uXXXX`, as Python's `json.dumps` writes by default.
///
/// Every edge handle holds a `œ`. Python keeps a string with one at two bytes
/// per character, and both Python and JavaScript decode an ASCII string
/// fastest. For a 13.4 MB graph, Python builds the string in 1.4 ms instead
/// of 17 ms, and `json.loads` reads it in 34 ms instead of 52 ms. Canonical
/// text ([`canonical_json`]) is not escaped: RFC 8785 writes the characters.
///
/// # Panics
///
/// A value that `serde_json` cannot write, which the engine never returns:
/// every key is a string.
#[must_use]
pub fn json_text<T: Serialize + ?Sized>(value: &T) -> String {
    let mut out = Vec::new();
    value
        .serialize(&mut serde_json::Serializer::with_formatter(&mut out, Ascii))
        .expect("the engine's JSON has string keys");
    String::from_utf8(out).expect("ASCII is UTF-8")
}

/// A graph state as JSON text, as [`json_text`] writes it.
#[must_use]
pub fn graph_json(state: &GraphState) -> String {
    json_text(&state.json())
}

/// Writes JSON with every character above U+007F escaped.
struct Ascii;

impl Formatter for Ascii {
    fn write_string_fragment<W: ?Sized + io::Write>(
        &mut self,
        writer: &mut W,
        fragment: &str,
    ) -> io::Result<()> {
        let bytes = fragment.as_bytes();
        let mut start = 0;
        while let Some(offset) = bytes[start..].iter().position(|byte| !byte.is_ascii()) {
            let at = start + offset;
            writer.write_all(&bytes[start..at])?;
            let character = fragment[at..]
                .chars()
                .next()
                .expect("a character starts here");
            for unit in character.encode_utf16(&mut [0; 2]) {
                write!(writer, "\\u{unit:04x}")?;
            }
            start = at + character.len_utf8();
        }
        writer.write_all(&bytes[start..])
    }
}

fn violations(violations: &[Violation]) -> Value {
    Value::Array(violations.iter().map(Violation::to_value).collect())
}

/// Operations as JSON. The caller owns them and drops them after, so each
/// one moves its payload into the result.
fn operations_json(operations: Vec<Operation>) -> Value {
    Value::Array(operations.into_iter().map(Operation::into_value).collect())
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
    Value(Value),
}

impl<'t> From<&'t str> for Input<'t> {
    fn from(text: &'t str) -> Self {
        Self::Text(text)
    }
}

impl From<Value> for Input<'_> {
    fn from(value: Value) -> Self {
        Self::Value(value)
    }
}

/// A graph, or any other value the engine reads as data.
fn data(input: Input<'_>) -> ApiResult<Value> {
    match input {
        Input::Text(text) => Ok(parse_json(text)?),
        Input::Value(value) => Ok(value),
    }
}

/// A list of operations.
fn operations(input: Input<'_>) -> ApiResult<Vec<Operation>> {
    let value = match input {
        Input::Text(text) => serde_json::from_str(text)
            .map_err(|error| ApiError::from(invalid!("operations are not valid JSON: {error}")))?,
        Input::Value(value) => value,
    };
    Ok(Operation::list_from_value(value)?)
}

fn optional(input: Option<Input<'_>>) -> ApiResult<Option<Value>> {
    input.map(data).transpose()
}

/// A list argument, named in the error when it is not a list or an item
/// has the wrong type: `rows: must be a list`.
fn list<T: FromValue>(input: Input<'_>, name: &str) -> ApiResult<Vec<T>> {
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
pub fn applied_json(applied: Applied, options: ApplyOptions) -> Map<String, Value> {
    let mut out = Map::new();
    if options.forward {
        out.insert(
            "forward_operations".into(),
            operations_json(applied.forward),
        );
    }
    if options.backward {
        out.insert(
            "backward_operations".into(),
            Value::Array(applied.backward.into_iter().map(operations_json).collect()),
        );
    }
    out
}

/// Apply operations to a graph: `{"flow_data", ...}` and what [`applied_json`] lists.
///
/// # Errors
///
/// The graph or the operations do not parse, or the engine refuses the batch.
pub fn apply(flow: Input<'_>, operations_in: Input<'_>, options: ApplyOptions) -> ApiResult<Value> {
    let (flow_data, applied) =
        apply_flow_operations(data(flow)?, operations(operations_in)?, options)?;
    let mut out = applied_json(applied, options);
    out.insert("flow_data".into(), flow_data);
    Ok(Value::Object(out))
}

/// Load a graph into a [`GraphState`], to apply many batches to it.
///
/// # Errors
///
/// The graph does not parse or breaks a structural rule.
pub fn graph_state(flow: Input<'_>) -> ApiResult<GraphState> {
    Ok(GraphState::new(data(flow)?)?)
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
) -> ApiResult<Value> {
    let applied = state.apply(operations(operations_in)?, options)?;
    Ok(Value::Object(applied_json(applied, options)))
}

/// Parse operations and print them as the engine records them.
///
/// # Errors
///
/// The operations do not parse.
pub fn normalize_operations(operations_in: Input<'_>) -> ApiResult<Value> {
    Ok(operations_json(operations(operations_in)?))
}

// --- Diff, validation and repair ------------------------------------------------------------

/// The operations that turn `base` into `target`.
///
/// # Errors
///
/// A graph does not parse or breaks the rules.
pub fn diff(base: Input<'_>, target: Input<'_>) -> ApiResult<Value> {
    Ok(operations_json(diff_flow_data(
        &data(base)?,
        &data(target)?,
    )?))
}

/// The operations that turn `base` into `target`, verified by replay: `{"operations"}`.
///
/// The replayed graph is the target, which the caller has, so it is not returned.
///
/// # Errors
///
/// A graph does not parse or breaks the rules, or the operations do not replay.
pub fn derive(base: Input<'_>, target: Input<'_>) -> ApiResult<Value> {
    let derived = derive_flow_operations(data(base)?, &data(target)?)?;
    let mut out = Map::new();
    out.insert("operations".into(), operations_json(derived.operations));
    Ok(Value::Object(out))
}

/// Every rule a graph breaks, against the stored graph a write replaces when given.
///
/// # Errors
///
/// A graph does not parse, or a check fails in a way that is not a violation.
pub fn validate(flow: Input<'_>, base: Option<Input<'_>>, check_values: bool) -> ApiResult<Value> {
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
pub fn repair(flow: Input<'_>, base: Option<Input<'_>>) -> ApiResult<Value> {
    let base = optional(base)?;
    let repaired = repair_flow_data(&data(flow)?, base.as_ref())?;
    let fixes: Vec<Value> = repaired.fixes.iter().map(Fix::to_value).collect();
    let mut out = Map::new();
    out.insert("flow_data".into(), repaired.flow_data);
    out.insert("fixes".into(), Value::Array(fixes));
    Ok(Value::Object(out))
}

// --- Canonical form -------------------------------------------------------------------------

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
) -> ApiResult<Value> {
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
pub fn edge_fixes(read: Input<'_>, shown: Input<'_>) -> ApiResult<Value> {
    let fixes = restore::edge_fixes(&list(read, "read")?, &list(shown, "shown")?)?;
    Ok(operations_json(fixes))
}

/// The part of the fixes that touches the given edges.
///
/// # Errors
///
/// The inputs do not parse, or `edge_ids` is not a list of strings.
pub fn fixes_for_edges(fixes: Input<'_>, edge_ids: Input<'_>) -> ApiResult<Value> {
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
pub fn strip_row_keys(rows: Input<'_>) -> ApiResult<Value> {
    Ok(keyed::strip_row_keys(&data(rows)?))
}

/// A flow whose top-level tables have their rows in order and without `__id__` and `__pos__`.
///
/// # Errors
///
/// The flow does not parse.
pub fn strip_flow_table_row_keys(flow: Input<'_>) -> ApiResult<Value> {
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
) -> ApiResult<Value> {
    let mut rows = list(rows, "rows")?;
    keyed::assign_row_ids(&mut rows, optional(previous)?.as_ref(), renumber(editor))?;
    Ok(Value::Array(rows))
}

/// A node being added, with ids on every table. `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The node does not parse, or a compared row holds a number that is not finite.
pub fn assign_table_row_ids(node: Input<'_>, editor: bool) -> ApiResult<Value> {
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
) -> ApiResult<Value> {
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
pub fn append_table_rows(rows: Input<'_>, new_rows: Input<'_>) -> ApiResult<Value> {
    let mut rows = list(rows, "rows")?;
    keyed::append_table_rows(&mut rows, &list(new_rows, "new_rows")?)?;
    Ok(Value::Array(rows))
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
) -> ApiResult<Value> {
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
pub fn table_fields(node: Input<'_>) -> ApiResult<Value> {
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
pub fn ordered_rows(rows: Input<'_>) -> ApiResult<Value> {
    let rows: Vec<Value> = list(rows, "rows")?;
    Ok(Value::Array(
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
        let empty = Value::Array(Vec::new());
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
        let value: Value = serde_json::from_str(text).unwrap();
        assert_eq!(
            graph_hash(text.into()).unwrap(),
            graph_hash(value.into()).unwrap()
        );
        let error = refused(diff("{".into(), "{}".into()));
        assert_eq!(error.code(), "FLOW_GRAPH_INVALID");
        let error = refused(normalize_operations("[".into()));
        assert_eq!(error.code(), "FLOW_OPERATION_INVALID");
    }

    #[test]
    fn json_text_is_ascii_and_reads_back_as_written() {
        let text = r#"{"handle":"{œnameœ:œoutœ}","emoji":"😀","quote":"a \"b\"\n","int":12345678901234567890123,"float":1.0}"#;
        let value: Value = serde_json::from_str(text).unwrap();
        let written = json_text(&value);
        assert_eq!(
            written,
            r#"{"handle":"{\u0153name\u0153:\u0153out\u0153}","emoji":"\ud83d\ude00","quote":"a \"b\"\n","int":12345678901234567890123,"float":1.0}"#
        );
        assert_eq!(serde_json::from_str::<Value>(&written).unwrap(), value);
    }

    #[test]
    fn graph_json_writes_the_graph_as_ascii() {
        let flow = r#"{"nodes":[{"id":"a","data":{"node":{"template":{"t":{"value":"é","type":"str"}}}}}],"edges":[]}"#;
        let state = graph_state(flow.into()).unwrap();
        let written = graph_json(&state);
        assert!(written.is_ascii());
        assert_eq!(
            serde_json::from_str::<Value>(&written).unwrap(),
            serde_json::from_str::<Value>(&state.to_json()).unwrap()
        );
    }
}
