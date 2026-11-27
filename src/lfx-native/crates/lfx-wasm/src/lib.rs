//! The browser binding of lfx: the `lfx-native` npm package.
//!
//! Every function takes JSON text and returns ASCII JSON text. `JSON.parse`
//! reads text faster than the binding builds JavaScript objects.
//!
//! An engine error throws an `Error`. Its `kind` names the matching Python
//! exception class, `code` is its stable code, and `details` is the whole
//! error as JSON text.

use js_sys::{Error, Reflect};
use lfx_ops::bindings::{self, BindingError, BindingResult, Input};
use lfx_ops::{ApplyOptions, ReplayOptions};
use wasm_bindgen::prelude::*;

fn thrown(error: &BindingError) -> JsValue {
    let raised = Error::new(error.message());
    for (name, value) in [
        ("kind", error.kind().to_owned()),
        ("code", error.code().to_owned()),
        ("details", bindings::json_text(&error.details())),
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

fn run<T>(result: BindingResult<T>) -> Result<T, JsValue> {
    result.map_err(|error| thrown(&error))
}

/// A result as JSON text, written as ASCII.
fn text(result: BindingResult) -> Result<String, JsValue> {
    run(result).map(|value| bindings::json_text(&value))
}

/// A boolean option of an options object, or `None` when it is not a boolean.
fn flag(options: &JsValue, name: &str) -> Option<bool> {
    Reflect::get(options, &JsValue::from_str(name))
        .ok()
        .and_then(|value| value.as_bool())
}

/// Read the apply options from an options object: `{forward, backward}`.
fn apply_options(options: &JsValue, forward_by_default: bool) -> ApplyOptions {
    ApplyOptions {
        forward: flag(options, "forward").unwrap_or(forward_by_default),
        backward: flag(options, "backward").unwrap_or(false),
    }
}

/// Read the replay options from an options object: `{backward}`.
fn replay_options(options: &JsValue) -> ReplayOptions {
    ReplayOptions {
        backward: flag(options, "backward").unwrap_or(false),
    }
}

/// A flow graph that the engine keeps loaded, to apply or replay many
/// batches on it. A refused batch changes nothing.
#[wasm_bindgen]
#[derive(Debug)]
pub struct GraphState {
    state: lfx_ops::GraphState,
}

#[wasm_bindgen]
impl GraphState {
    /// Load a graph given as JSON text.
    ///
    /// # Errors
    ///
    /// The graph does not parse, or breaks a structural rule.
    #[wasm_bindgen(constructor)]
    pub fn new(flow: &str) -> Result<GraphState, JsValue> {
        Ok(Self {
            state: run(bindings::graph_state(flow.into()))?,
        })
    }

    /// Apply a batch, with every rule. Returns what it did as JSON.
    /// `options` is `{forward, backward}`, both false by default.
    ///
    /// # Errors
    ///
    /// The operations do not parse, or the engine refuses the batch.
    pub fn apply(&mut self, operations: &str, options: &JsValue) -> Result<String, JsValue> {
        text(bindings::apply_to(
            &mut self.state,
            operations.into(),
            apply_options(options, false),
        ))
    }

    /// Replay stored operations, with no rule. Returns what it did as JSON.
    /// `options` is `{backward}`, false by default.
    ///
    /// # Errors
    ///
    /// The operations do not parse, or an operation cannot be carried out.
    pub fn replay(&mut self, operations: &str, options: &JsValue) -> Result<String, JsValue> {
        text(bindings::replay_to(
            &mut self.state,
            operations.into(),
            replay_options(options),
        ))
    }

    /// The graph as JSON text.
    #[wasm_bindgen(js_name = toJson)]
    #[must_use]
    pub fn to_json(&self) -> String {
        self.state.to_json()
    }
}

/// Apply operations to a graph, with every rule. Returns `{"flow_data", ...}`
/// as JSON. `options` is `{forward, backward}`, and `forward` is true by default.
///
/// # Errors
///
/// The graph or the operations do not parse, or the engine refuses the batch.
#[wasm_bindgen]
pub fn apply(flow: &str, operations: &str, options: &JsValue) -> Result<String, JsValue> {
    text(bindings::apply(
        flow.into(),
        operations.into(),
        apply_options(options, true),
    ))
}

/// Replay stored operations on a graph, with no rule. Returns
/// `{"flow_data", ...}` as JSON. `options` is `{backward}`, false by default.
///
/// # Errors
///
/// The input does not parse, the graph breaks a structural rule, or an operation fails.
#[wasm_bindgen]
pub fn replay(flow: &str, operations: &str, options: &JsValue) -> Result<String, JsValue> {
    text(bindings::replay(
        flow.into(),
        operations.into(),
        replay_options(options),
    ))
}

/// Functions that run one engine call on JSON text.
/// In `fn name as jsName(a, b [c]; flag = true)`, `a` and `b` are JSON text,
/// `c` is optional, and `flag` is an optional boolean with its default. With
/// `-> T`, a function returns the `T`. Without it, it returns ASCII JSON text
/// ([`text`]). Each throws when its text does not parse or the engine refuses.
macro_rules! engine_functions {
    (@type) => { String };
    (@type $ret:ty) => { $ret };
    (@run $job:expr) => { text($job) };
    (@run $job:expr, $ret:ty) => { run::<$ret>($job) };
    ($(
        $(#[$attr:meta])*
        fn $name:ident as $js:ident(
            $($arg:ident),+ $([$($opt:ident),+])? $(; $($flag:ident = $default:expr),+)?
        ) $(-> $ret:ty)? => $body:expr;
    )*) => {$(
        $(#[$attr])*
        #[wasm_bindgen(js_name = $js)]
        #[allow(clippy::missing_errors_doc, reason = "the macro's documentation says when each throws")]
        #[allow(clippy::needless_pass_by_value, reason = "wasm-bindgen passes an optional string by value")]
        pub fn $name(
            $($arg: &str,)+
            $($($opt: Option<String>,)+)?
            $($($flag: Option<bool>,)+)?
        ) -> Result<engine_functions!(@type $($ret)?), JsValue> {
            $(let $arg = Input::from($arg);)+
            $($(let $opt = $opt.as_deref().map(Input::from);)+)?
            $($(let $flag = $flag.unwrap_or($default);)+)?
            engine_functions!(@run $body $(, $ret)?)
        }
    )*};
}

engine_functions! {
    /// The operations that turn `base` into `target`, checked by replay.
    fn ops_diff as opsDiff(base, target) => bindings::ops_diff(base, target);

    /// Every rule a graph breaks, as a JSON list of violations.
    fn validate as validate(flow [base]; check_values = true) =>
        bindings::validate(flow, base, check_values);

    /// Repair what has one fix. Returns `{"flow_data", "fixes"}`. It throws
    /// when a rule only the client can fix is broken.
    fn repair as repair(flow [base]) => bindings::repair(flow, base);

    /// The SHA-256 hex digest of a graph's canonical form.
    fn graph_hash as graphHash(flow) -> String => bindings::graph_hash(flow);

    /// Whether two graphs are the same graph.
    fn graphs_equal as graphsEqual(left, right) -> bool => bindings::graphs_equal(left, right);

    /// Whether two JSON values are the same value.
    fn values_equal as valuesEqual(left, right) -> bool => bindings::values_equal(left, right);

    /// A JSON value in RFC 8785 canonical form.
    fn canonical_json as canonicalJson(value) -> String => bindings::canonical_json(value);

    /// A revision with a restore's fixes applied, after checking each one.
    fn apply_restore_fixes as applyRestoreFixes(revision_graph, stored, fixes) =>
        bindings::apply_restore_fixes(revision_graph, stored, fixes);

    /// The fixes that turn a revision's edges as read into the edges its preview shows.
    fn edge_fixes as edgeFixes(read, shown) => bindings::edge_fixes(read, shown);

    /// The part of the fixes that touches the given edges.
    fn fixes_for_edges as fixesForEdges(fixes, edge_ids) => bindings::fixes_for_edges(fixes, edge_ids);

    /// Rows in order, by `(__pos__, __id__)`, or as stored for a legacy table.
    fn ordered_rows as orderedRows(rows) => bindings::ordered_rows(rows);

    /// Rows in order and without `__id__` and `__pos__`.
    fn strip_row_keys as stripRowKeys(rows) => bindings::strip_row_keys(rows);

    /// A flow whose top-level tables have their rows in order and without `__id__` and `__pos__`.
    fn strip_flow_table_row_keys as stripFlowTableRowKeys(flow) =>
        bindings::strip_flow_table_row_keys(flow);

    /// Rows with the ids and positions a write needs. With `editor`, a gap with
    /// no room left renumbers the table.
    fn assign_row_ids as assignRowIds(rows [previous]; editor = true) =>
        bindings::assign_row_ids(rows, previous, editor);

    /// A node being added, with ids on every table.
    fn assign_table_row_ids as assignTableRowIds(node; editor = true) =>
        bindings::assign_table_row_ids(node, editor);

    /// `target` with ids on the tables it adds or changes relative to `base`.
    fn assign_changed_table_row_ids as assignChangedTableRowIds(base, target; editor = true) =>
        bindings::assign_changed_table_row_ids(base, target, editor);

    /// A node with ids on the tables it adds or changes relative to `previous`.
    fn assign_changed_node_table_row_ids as assignChangedNodeTableRowIds(
        node [previous]; editor = true
    ) => bindings::assign_changed_node_table_row_ids(node, previous, editor);

    /// Rows with `new_rows` appended, each with a new id one position past the last.
    fn append_table_rows as appendTableRows(rows, new_rows) =>
        bindings::append_table_rows(rows, new_rows);

    /// The names of a node's template fields whose value is a table.
    fn table_fields as tableFields(node) => bindings::table_fields(node);
}

/// A new random edge id in the editor's format.
#[wasm_bindgen(js_name = newEdgeId)]
#[must_use]
pub fn new_edge_id() -> String {
    lfx_ops::flow::id::new_edge_id()
}

/// A new random table row id in the editor's format.
#[wasm_bindgen(js_name = newTableRowId)]
#[must_use]
pub fn new_table_row_id() -> String {
    lfx_ops::flow::id::new_table_row_id()
}

/// The node schema the engine reads, as JSON text.
#[wasm_bindgen(js_name = nodeSchema)]
#[must_use]
pub fn node_schema() -> String {
    lfx_ops::flow::model::FLOW_MODEL_JSON.to_owned()
}
