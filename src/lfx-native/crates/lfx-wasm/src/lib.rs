//! The browser binding of lfx: the `lfx-native` npm package.
//!
//! Every function takes JSON text and returns JSON text. An engine error is
//! thrown as an `Error` whose `kind` names the matching Python exception class,
//! whose `code` is its stable code, and whose `details` is the whole error as
//! JSON text. The binding holds no rules: each function calls `lfx::ops::api`.

use js_sys::{Error, Reflect};
use lfx::ops::ApplyOptions;
use lfx::ops::api::{self, ApiError, ApiResult};
use wasm_bindgen::prelude::*;

fn thrown(error: &ApiError) -> JsValue {
    let raised = Error::new(error.message());
    for (name, value) in [
        ("kind", error.kind().to_owned()),
        ("code", error.code().to_owned()),
        ("details", error.0.to_string()),
    ] {
        // Setting a property on a fresh Error cannot fail.
        let _ = Reflect::set(
            &raised,
            &JsValue::from_str(name),
            &JsValue::from_str(&value),
        );
    }
    raised.into()
}

fn run<T>(result: ApiResult<T>) -> Result<T, JsValue> {
    result.map_err(|error| thrown(&error))
}

/// Read the apply switches from an options object: `{forward, inverse, restoring}`.
fn apply_options(options: &JsValue, forward_by_default: bool) -> ApplyOptions {
    let flag = |name: &str| {
        Reflect::get(options, &JsValue::from_str(name))
            .ok()
            .and_then(|value| value.as_bool())
    };
    ApplyOptions {
        forward: flag("forward").unwrap_or(forward_by_default),
        inverse: flag("inverse").unwrap_or(false),
        restoring: flag("restoring").unwrap_or(false),
    }
}

/// A flow graph that the engine keeps loaded, to apply many batches to it.
///
/// History playback and rebase apply many batches to one graph and read it
/// once. A refused batch changes nothing.
#[wasm_bindgen]
#[derive(Debug)]
pub struct GraphState {
    state: lfx::ops::GraphState,
}

#[wasm_bindgen]
impl GraphState {
    /// Load a graph given as JSON text.
    ///
    /// # Errors
    ///
    /// The graph does not parse or breaks a structural rule.
    #[wasm_bindgen(constructor)]
    pub fn new(flow: &str) -> Result<GraphState, JsValue> {
        Ok(Self {
            state: run(api::graph_state(flow))?,
        })
    }

    /// Apply a batch; returns what it did as JSON. `options` is
    /// `{forward, inverse, restoring}`, each false by default.
    ///
    /// # Errors
    ///
    /// The operations do not parse, or the engine refuses the batch.
    pub fn apply(&mut self, operations: &str, options: &JsValue) -> Result<String, JsValue> {
        run(api::apply_to(
            &mut self.state,
            operations,
            apply_options(options, false),
        ))
    }

    /// The graph as JSON text.
    #[wasm_bindgen(js_name = toJson)]
    #[must_use]
    pub fn to_json(&self) -> String {
        self.state.to_string()
    }
}

/// Apply operations to a graph; returns `{"flow_data", ...}` as JSON.
/// `options` is `{forward, inverse, restoring}`; `forward` is true by default.
///
/// # Errors
///
/// The graph or the operations do not parse, or the engine refuses the batch.
#[wasm_bindgen]
pub fn apply(flow: &str, operations: &str, options: &JsValue) -> Result<String, JsValue> {
    run(api::apply(flow, operations, apply_options(options, true)))
}

/// Parse operations and print them as the engine records them.
///
/// # Errors
///
/// The operations do not parse.
#[wasm_bindgen(js_name = normalizeOperations)]
pub fn normalize_operations(operations: &str) -> Result<String, JsValue> {
    run(api::normalize_operations(operations))
}

/// The operations that turn `base` into `target`.
///
/// # Errors
///
/// A graph does not parse or breaks the rules.
#[wasm_bindgen]
pub fn diff(base: &str, target: &str) -> Result<String, JsValue> {
    run(api::diff(base, target))
}

/// The operations that turn `base` into `target`, verified by replay.
///
/// # Errors
///
/// A graph does not parse or breaks the rules, or the operations do not replay.
#[wasm_bindgen]
pub fn derive(base: &str, target: &str) -> Result<String, JsValue> {
    run(api::derive(base, target))
}

/// Every rule a graph breaks, as a JSON list of violations.
///
/// # Errors
///
/// A graph does not parse, or a check fails in a way that is not a violation.
#[wasm_bindgen]
#[expect(
    clippy::needless_pass_by_value,
    reason = "wasm-bindgen passes an optional string by value"
)]
pub fn validate(
    flow: &str,
    base: Option<String>,
    check_values: Option<bool>,
) -> Result<String, JsValue> {
    run(api::validate(
        flow,
        base.as_deref(),
        check_values.unwrap_or(true),
    ))
}

/// Repair what has one fix; returns `{"flow_data", "fixes"}`.
///
/// # Errors
///
/// A graph does not parse, or a rule only the client can fix is broken.
#[wasm_bindgen]
#[expect(
    clippy::needless_pass_by_value,
    reason = "wasm-bindgen passes an optional string by value"
)]
pub fn repair(flow: &str, base: Option<String>) -> Result<String, JsValue> {
    run(api::repair(flow, base.as_deref()))
}

/// The SHA-256 hex digest of a graph's canonical form.
///
/// # Errors
///
/// The graph does not parse, or holds a number that is not finite.
#[wasm_bindgen(js_name = graphHash)]
pub fn graph_hash(flow: &str) -> Result<String, JsValue> {
    run(api::graph_hash(flow))
}

/// Whether two graphs are the same graph.
///
/// # Errors
///
/// A graph does not parse, or a compared number is not finite.
#[wasm_bindgen(js_name = graphsEqual)]
pub fn graphs_equal(left: &str, right: &str) -> Result<bool, JsValue> {
    run(api::graphs_equal(left, right))
}

/// Whether two JSON values are the same value.
///
/// # Errors
///
/// A value does not parse, or a compared number is not finite.
#[wasm_bindgen(js_name = valuesEqual)]
pub fn values_equal(left: &str, right: &str) -> Result<bool, JsValue> {
    run(api::values_equal(left, right))
}

/// A JSON value in RFC 8785 canonical form.
///
/// # Errors
///
/// The value does not parse, or holds a number that is not finite.
#[wasm_bindgen(js_name = canonicalJson)]
pub fn canonical_json(value: &str) -> Result<String, JsValue> {
    run(api::canonical_json(value))
}

/// The engine's part of a save.
///
/// # Errors
///
/// The inputs do not parse, a graph breaks the rules, or the engine fails.
#[wasm_bindgen(js_name = prepareWrite)]
pub fn prepare_write(stored: &str, target: &str, options: &str) -> Result<String, JsValue> {
    run(api::prepare_write(stored, target, options))
}

/// A revision with a restore's fixes applied, after checking each one.
///
/// # Errors
///
/// The inputs do not parse, or a fix is not allowed or does not apply.
#[wasm_bindgen(js_name = applyRestoreFixes)]
pub fn apply_restore_fixes(
    revision_graph: &str,
    stored: &str,
    fixes: &str,
) -> Result<String, JsValue> {
    run(api::apply_restore_fixes(revision_graph, stored, fixes))
}

/// The fixes that turn a revision's edges as read into the edges its preview shows.
///
/// # Errors
///
/// The inputs do not parse.
#[wasm_bindgen(js_name = edgeFixes)]
pub fn edge_fixes(read: &str, shown: &str) -> Result<String, JsValue> {
    run(api::edge_fixes(read, shown))
}

/// The part of the fixes that touches the given edges.
///
/// # Errors
///
/// The inputs do not parse.
#[wasm_bindgen(js_name = fixesForEdges)]
pub fn fixes_for_edges(fixes: &str, edge_ids: &str) -> Result<String, JsValue> {
    run(api::fixes_for_edges(fixes, edge_ids))
}

/// Rows in order, by `(__pos__, __id__)`, or as stored for a legacy table.
///
/// # Errors
///
/// The rows do not parse.
#[wasm_bindgen(js_name = orderedRows)]
pub fn ordered_rows(rows: &str) -> Result<String, JsValue> {
    run(api::ordered_rows(rows))
}

/// Rows in order and without `__id__` and `__pos__`.
///
/// # Errors
///
/// The rows do not parse.
#[wasm_bindgen(js_name = stripRowKeys)]
pub fn strip_row_keys(rows: &str) -> Result<String, JsValue> {
    run(api::strip_row_keys(rows))
}

/// A flow whose top-level tables have their rows in order and without `__id__` and `__pos__`.
///
/// # Errors
///
/// The flow does not parse.
#[wasm_bindgen(js_name = stripFlowTableRowKeys)]
pub fn strip_flow_table_row_keys(flow: &str) -> Result<String, JsValue> {
    run(api::strip_flow_table_row_keys(flow))
}

/// Rows with the ids and positions a write needs. With `editor`, a gap with
/// no room left renumbers the table.
///
/// # Errors
///
/// The inputs do not parse.
#[wasm_bindgen(js_name = assignRowIds)]
#[expect(
    clippy::needless_pass_by_value,
    reason = "wasm-bindgen passes an optional string by value"
)]
pub fn assign_row_ids(
    rows: &str,
    previous: Option<String>,
    editor: Option<bool>,
) -> Result<String, JsValue> {
    run(api::assign_row_ids(
        rows,
        previous.as_deref(),
        editor.unwrap_or(true),
    ))
}

/// A node being added, with ids on every table.
///
/// # Errors
///
/// The node does not parse.
#[wasm_bindgen(js_name = assignTableRowIds)]
pub fn assign_table_row_ids(node: &str, editor: Option<bool>) -> Result<String, JsValue> {
    run(api::assign_table_row_ids(node, editor.unwrap_or(true)))
}

/// `target` with ids on the tables it adds or changes relative to `base`.
///
/// # Errors
///
/// The graphs do not parse.
#[wasm_bindgen(js_name = assignChangedTableRowIds)]
pub fn assign_changed_table_row_ids(
    base: &str,
    target: &str,
    editor: Option<bool>,
) -> Result<String, JsValue> {
    run(api::assign_changed_table_row_ids(
        base,
        target,
        editor.unwrap_or(true),
    ))
}

/// A node with ids on the tables it adds or changes relative to `previous`.
///
/// # Errors
///
/// The inputs do not parse.
#[wasm_bindgen(js_name = assignChangedNodeTableRowIds)]
#[expect(
    clippy::needless_pass_by_value,
    reason = "wasm-bindgen passes an optional string by value"
)]
pub fn assign_changed_node_table_row_ids(
    node: &str,
    previous: Option<String>,
    editor: Option<bool>,
) -> Result<String, JsValue> {
    run(api::assign_changed_node_table_row_ids(
        node,
        previous.as_deref(),
        editor.unwrap_or(true),
    ))
}

/// Rows with `new_rows` appended, each with a new id one position past the last.
///
/// # Errors
///
/// The inputs do not parse.
#[wasm_bindgen(js_name = appendTableRows)]
pub fn append_table_rows(rows: &str, new_rows: &str) -> Result<String, JsValue> {
    run(api::append_table_rows(rows, new_rows))
}

/// The names of a node's template fields whose value is a table.
///
/// # Errors
///
/// The node does not parse.
#[wasm_bindgen(js_name = tableFields)]
pub fn table_fields(node: &str) -> Result<String, JsValue> {
    run(api::table_fields(node))
}

/// A new random edge id in the editor's format.
#[wasm_bindgen(js_name = newEdgeId)]
#[must_use]
pub fn new_edge_id() -> String {
    api::new_edge_id()
}

/// A new random table row id in the editor's format.
#[wasm_bindgen(js_name = newTableRowId)]
#[must_use]
pub fn new_table_row_id() -> String {
    api::new_table_row_id()
}

/// The node schema the engine reads, as JSON text.
#[wasm_bindgen(js_name = nodeSchema)]
#[must_use]
pub fn node_schema() -> String {
    api::node_schema().to_owned()
}
