//! JSON in, JSON out: the functions the Python and browser bindings call.
//!
//! Graphs, operations and results pass to and from the bindings as JSON text, so the
//! engine parses each graph once and keeps every number's original text.
//! Each function here does no more than parse its inputs, call the engine and
//! print its result; the bindings only call these and turn an [`ApiError`]
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
use crate::ops::write::{WriteError, WriteOptions};

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

impl From<WriteError> for ApiError {
    fn from(error: WriteError) -> Self {
        let message = error.to_string();
        match error {
            WriteError::InvalidGraph {
                role,
                violations: found,
            } => Self(json!({
                "kind": "FlowGraphInvalidError",
                "code": "FLOW_GRAPH_INVALID",
                "message": message,
                "graph": role.as_str(),
                "violations": violations(&found),
            })),
            WriteError::Engine(error) => error.into(),
        }
    }
}

/// The result of a call: JSON text, or the error.
pub type ApiResult<T = String> = Result<T, ApiError>;

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

/// Parse a JSON input: a graph, or any other value the engine reads as data.
fn parse(text: &str) -> ApiResult<Value> {
    Ok(parse_json(text)?)
}

/// Parse a list of operations.
fn operations(text: &str) -> ApiResult<Vec<Operation>> {
    let value: Value = serde_json::from_str(text)
        .map_err(|error| ApiError::from(invalid!("operations are not valid JSON: {error}")))?;
    Ok(Operation::list_from_value(value)?)
}

fn optional(text: Option<&str>) -> ApiResult<Option<Value>> {
    text.map(parse).transpose()
}

/// Parse a list argument, naming it in the error when it is not a list or
/// an item has the wrong type: `rows: must be a list`.
fn list<T: FromValue>(text: &str, name: &str) -> ApiResult<Vec<T>> {
    Ok(Vec::from_value(parse(text)?).map_err(|error| error.into_error(name))?)
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
pub fn apply(flow: &str, operations_text: &str, options: ApplyOptions) -> ApiResult {
    let (flow_data, applied) =
        apply_flow_operations(parse(flow)?, operations(operations_text)?, options)?;
    let mut out = applied_json(applied, options);
    out.insert("flow_data".into(), flow_data);
    Ok(json_text(&Value::Object(out)))
}

/// Load a graph into a [`GraphState`], to apply many batches to it.
///
/// # Errors
///
/// The graph does not parse or breaks a structural rule.
pub fn graph_state(flow: &str) -> ApiResult<GraphState> {
    Ok(GraphState::new(parse(flow)?)?)
}

/// Apply a batch to a [`GraphState`]; the result is what [`applied_json`] lists.
///
/// # Errors
///
/// The operations do not parse, or the engine refuses the batch, which then
/// changes nothing.
pub fn apply_to(state: &mut GraphState, operations_text: &str, options: ApplyOptions) -> ApiResult {
    let applied = state.apply(operations(operations_text)?, options)?;
    Ok(json_text(&Value::Object(applied_json(applied, options))))
}

/// Parse operations and print them as the engine records them.
///
/// # Errors
///
/// The operations do not parse.
pub fn normalize_operations(operations_text: &str) -> ApiResult {
    Ok(json_text(&operations_json(operations(operations_text)?)))
}

// --- Diff, validation and repair ------------------------------------------------------------

/// The operations that turn `base` into `target`.
///
/// # Errors
///
/// A graph does not parse or breaks the rules.
pub fn diff(base: &str, target: &str) -> ApiResult {
    Ok(json_text(&operations_json(diff_flow_data(
        &parse(base)?,
        &parse(target)?,
    )?)))
}

/// The operations that turn `base` into `target`, verified by replay: `{"operations"}`.
///
/// The replayed graph is the target, which the caller has, so it is not returned.
///
/// # Errors
///
/// A graph does not parse or breaks the rules, or the operations do not replay.
pub fn derive(base: &str, target: &str) -> ApiResult {
    let derived = derive_flow_operations(parse(base)?, &parse(target)?)?;
    let mut out = Map::new();
    out.insert("operations".into(), operations_json(derived.operations));
    Ok(json_text(&Value::Object(out)))
}

/// Every rule a graph breaks, against the stored graph a write replaces when given.
///
/// # Errors
///
/// A graph does not parse, or a check fails in a way that is not a violation.
pub fn validate(flow: &str, base: Option<&str>, check_values: bool) -> ApiResult {
    let base = optional(base)?;
    let numbers = if check_values {
        Numbers::Check
    } else {
        Numbers::Skip
    };
    Ok(json_text(&violations(&find_graph_violations(
        &parse(flow)?,
        numbers,
        base.as_ref(),
    )?)))
}

/// Repair what has one fix: `{"flow_data", "fixes"}`.
///
/// # Errors
///
/// A graph does not parse, or a rule only the client can fix is broken.
pub fn repair(flow: &str, base: Option<&str>) -> ApiResult {
    let base = optional(base)?;
    let repaired = repair_flow_data(&parse(flow)?, base.as_ref())?;
    let fixes: Vec<Value> = repaired.fixes.iter().map(Fix::to_value).collect();
    Ok(json_text(
        &json!({"flow_data": repaired.flow_data, "fixes": fixes}),
    ))
}

// --- Canonical form -------------------------------------------------------------------------

/// The SHA-256 hex digest of a graph's canonical form.
///
/// # Errors
///
/// The graph does not parse, or holds a number that is not finite.
pub fn graph_hash(flow: &str) -> ApiResult {
    Ok(canonical::graph_hash(&parse(flow)?)?)
}

/// Whether two graphs are the same graph.
///
/// # Errors
///
/// A graph does not parse, or a compared number is not finite.
pub fn graphs_equal(left: &str, right: &str) -> ApiResult<bool> {
    Ok(canonical::graphs_equal(&parse(left)?, &parse(right)?)?)
}

/// Whether two JSON values are the same value.
///
/// # Errors
///
/// A value does not parse, or a compared number is not finite.
pub fn values_equal(left: &str, right: &str) -> ApiResult<bool> {
    Ok(canonical::values_equal(&parse(left)?, &parse(right)?)?)
}

/// A JSON value in RFC 8785 canonical form.
///
/// # Errors
///
/// The value does not parse, or holds a number that is not finite.
pub fn canonical_json(value: &str) -> ApiResult {
    Ok(canonical::canonical_json(&parse(value)?)?)
}

// --- Saves ---------------------------------------------------------------------------------

/// A JSON object of named inputs, read strictly: a required key must be
/// present with the right type.
#[derive(Debug)]
struct Fields<'v> {
    object: &'v Value,
    /// What the object is, for messages: `options`.
    name: &'static str,
}

impl<'v> Fields<'v> {
    fn new(object: &'v Value, name: &'static str) -> Self {
        Self { object, name }
    }

    fn boolean(&self, key: &str) -> ApiResult<bool> {
        let name = self.name;
        self.object
            .get(key)
            .and_then(Value::as_bool)
            .ok_or_else(|| invalid!("{name}.{key} must be a boolean").into())
    }
}

/// The engine's part of a save: `{"base"?, "stored_repaired", "target"?, "repairs", "operations"}`.
///
/// `base` and `target` are there only when the save changed the stored or
/// the submitted graph: filled in or repaired. Without them, the base is
/// `stored` and the graph to store is `target`, as given.
///
/// `options` is `{"started", "repair_invalid_graph"}`.
///
/// # Errors
///
/// The inputs do not parse, an option is missing or has the wrong type, a
/// graph breaks the rules, or the engine fails.
pub fn prepare_write(stored: &str, target: &str, options: &str) -> ApiResult {
    let options = parse(options)?;
    let options = Fields::new(&options, "options");
    let write_options = WriteOptions {
        started: options.boolean("started")?,
        repair_invalid_graph: options.boolean("repair_invalid_graph")?,
    };
    let prepared =
        crate::ops::write::prepare_write(parse(stored)?, parse(target)?, &write_options)?;
    let repairs = prepared.repairs_json();
    let mut out = Map::new();
    if let Some(base) = prepared.base {
        out.insert("base".into(), base);
    }
    out.insert("stored_repaired".into(), prepared.stored_repaired.into());
    if let Some(target) = prepared.target {
        out.insert("target".into(), target);
    }
    out.insert("repairs".into(), repairs);
    out.insert("operations".into(), operations_json(prepared.operations));
    Ok(json_text(&Value::Object(out)))
}

// --- Restore fixes --------------------------------------------------------------------------

/// A revision with a restore's fixes applied, after checking each one.
///
/// # Errors
///
/// The inputs do not parse, or a fix is not allowed or does not apply.
pub fn apply_restore_fixes(revision: &str, stored: &str, fixes: &str) -> ApiResult {
    Ok(json_text(&restore::apply_restore_fixes(
        &parse(revision)?,
        &parse(stored)?,
        operations(fixes)?,
    )?))
}

/// The fixes that turn a revision's edges as read into the edges its preview shows.
///
/// # Errors
///
/// The inputs do not parse, an input is not a list, or a compared handle
/// holds a number that is not finite.
pub fn edge_fixes(read: &str, shown: &str) -> ApiResult {
    let fixes = restore::edge_fixes(&list(read, "read")?, &list(shown, "shown")?)?;
    Ok(json_text(&operations_json(fixes)))
}

/// The part of the fixes that touches the given edges.
///
/// # Errors
///
/// The inputs do not parse, or `edge_ids` is not a list of strings.
pub fn fixes_for_edges(fixes: &str, edge_ids: &str) -> ApiResult {
    let ids: Vec<String> = list(edge_ids, "edge_ids")?;
    Ok(json_text(&operations_json(restore::fixes_for_edges(
        &operations(fixes)?,
        &ids,
    ))))
}

// --- Table rows -----------------------------------------------------------------------------

/// Rows in order and without `__id__` and `__pos__`.
///
/// # Errors
///
/// The rows do not parse.
pub fn strip_row_keys(rows: &str) -> ApiResult {
    Ok(json_text(&keyed::strip_row_keys(&parse(rows)?)))
}

/// A flow whose top-level tables have their rows in order and without `__id__` and `__pos__`.
///
/// # Errors
///
/// The flow does not parse.
pub fn strip_flow_table_row_keys(flow: &str) -> ApiResult {
    let mut flow = parse(flow)?;
    keyed::strip_flow_table_row_keys(&mut flow);
    Ok(json_text(&flow))
}

/// Rows with the ids and positions a write needs. `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The inputs do not parse, `rows` is not a list, or a compared row holds a
/// number that is not finite.
pub fn assign_row_ids(rows: &str, previous: Option<&str>, editor: bool) -> ApiResult {
    let mut rows = list(rows, "rows")?;
    keyed::assign_row_ids(&mut rows, optional(previous)?.as_ref(), renumber(editor))?;
    Ok(json_text(&Value::Array(rows)))
}

/// A node being added, with ids on every table. `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The node does not parse, or a compared row holds a number that is not finite.
pub fn assign_table_row_ids(node: &str, editor: bool) -> ApiResult {
    let mut node = parse(node)?;
    keyed::assign_table_row_ids(&mut node, renumber(editor))?;
    Ok(json_text(&node))
}

/// `target` with ids on the tables it adds or changes relative to `base`.
/// `editor` renumbers when a gap has no room left.
///
/// # Errors
///
/// The graphs do not parse, or a compared row holds a number that is not finite.
pub fn assign_changed_table_row_ids(base: &str, target: &str, editor: bool) -> ApiResult {
    let mut target = parse(target)?;
    keyed::assign_changed_table_row_ids(&parse(base)?, &mut target, renumber(editor))?;
    Ok(json_text(&target))
}

/// Rows with `new_rows` appended, each with a new id one position past the last.
///
/// # Errors
///
/// The inputs do not parse, an input is not a list, or a compared row holds
/// a number that is not finite.
pub fn append_table_rows(rows: &str, new_rows: &str) -> ApiResult {
    let mut rows = list(rows, "rows")?;
    keyed::append_table_rows(&mut rows, &list(new_rows, "new_rows")?)?;
    Ok(json_text(&Value::Array(rows)))
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
    let mut node = parse(node)?;
    keyed::assign_changed_node_table_row_ids(
        &mut node,
        optional(previous)?.as_ref(),
        renumber(editor),
    )?;
    Ok(json_text(&node))
}

/// The names of a node's template fields whose value is a table.
///
/// # Errors
///
/// The node does not parse.
pub fn table_fields(node: &str) -> ApiResult {
    Ok(json_text(&json!(keyed::table_fields(&parse(node)?))))
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
pub fn ordered_rows(rows: &str) -> ApiResult {
    let rows: Vec<Value> = list(rows, "rows")?;
    Ok(json_text(&Value::Array(
        canonical::ordered_rows(&rows)
            .into_iter()
            .cloned()
            .collect(),
    )))
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
                refused(assign_row_ids(r#"{"a": 1}"#, None, false)),
                "rows: must be a list",
            ),
            (refused(ordered_rows("null")), "rows: must be a list"),
            (
                refused(append_table_rows("{}", "[]")),
                "rows: must be a list",
            ),
            (
                refused(append_table_rows("[]", r#""row""#)),
                "new_rows: must be a list",
            ),
            (refused(edge_fixes("{}", "[]")), "read: must be a list"),
            (refused(edge_fixes("[]", "5")), "shown: must be a list"),
            (
                refused(fixes_for_edges("[]", r#"{"id": "e1"}"#)),
                "edge_ids: must be a list",
            ),
            (
                refused(fixes_for_edges("[]", r#"["e1", 5]"#)),
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
        assert_eq!(assign_row_ids("[]", None, false).unwrap(), "[]");
        assert_eq!(ordered_rows("[]").unwrap(), "[]");
        assert_eq!(append_table_rows("[]", "[]").unwrap(), "[]");
        assert_eq!(edge_fixes("[]", "[]").unwrap(), "[]");
        assert_eq!(fixes_for_edges("[]", r#"["e1"]"#).unwrap(), "[]");
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
        let state = graph_state(flow).unwrap();
        let written = graph_json(&state);
        assert!(written.is_ascii());
        assert_eq!(
            serde_json::from_str::<Value>(&written).unwrap(),
            serde_json::from_str::<Value>(&state.to_json()).unwrap()
        );
    }
}
