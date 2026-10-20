//! The Python binding of lfx: the `lfx_native` package.
//!
//! Every function takes JSON as `str` or `bytes`, releases the GIL while the
//! engine works, and returns JSON text. An engine error is raised as
//! [`EngineError`], which carries the error's `kind` (the matching Python
//! exception class of `lfx.services.flow_operations` or
//! `langflow.services.flow_history`), its `code`, and `details`: the whole
//! error as JSON text. The binding holds no rules: each function calls
//! `lfx::ops::api`.

use lfx::ops::ApplyOptions;
use lfx::ops::api::{self, ApiError, ApiResult};
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyString};

create_exception!(
    lfx_native,
    EngineError,
    PyException,
    "An engine error. `kind` names the matching Python exception class, `code` is its stable code, and \
     `details` is the whole error as JSON text."
);

fn engine_error(py: Python<'_>, error: &ApiError) -> PyErr {
    let raised = EngineError::new_err(error.message().to_owned());
    let value = raised.value(py);
    let attributes = [
        ("kind", error.kind().to_owned()),
        ("code", error.code().to_owned()),
        ("details", error.0.to_string()),
    ];
    for (name, attribute) in attributes {
        if let Err(failure) = value.setattr(name, attribute) {
            return failure;
        }
    }
    raised
}

/// JSON text from a `str` or UTF-8 `bytes`.
fn text<'a>(value: &'a Bound<'_, PyAny>) -> PyResult<&'a str> {
    if let Ok(string) = value.cast::<PyString>() {
        return string.to_str();
    }
    if let Ok(bytes) = value.cast::<PyBytes>() {
        return std::str::from_utf8(bytes.as_bytes())
            .map_err(|error| PyValueError::new_err(error.to_string()));
    }
    Err(PyTypeError::new_err("expected JSON text as str or bytes"))
}

fn optional_text<'a>(value: Option<&'a Bound<'_, PyAny>>) -> PyResult<Option<&'a str>> {
    value.filter(|value| !value.is_none()).map(text).transpose()
}

/// Run engine work without the GIL.
fn run<T: Send>(py: Python<'_>, work: impl FnOnce() -> ApiResult<T> + Send) -> PyResult<T> {
    py.detach(work).map_err(|error| engine_error(py, &error))
}

/// A flow graph that the engine keeps loaded, to apply many batches to it.
///
/// Replay, history playback and rebase apply many batches to one graph and
/// read it once. A refused batch changes nothing.
#[pyclass(module = "lfx_native")]
#[derive(Debug)]
struct GraphState {
    state: lfx::ops::GraphState,
}

#[pymethods]
impl GraphState {
    #[new]
    fn new(py: Python<'_>, flow: &Bound<'_, PyAny>) -> PyResult<Self> {
        let flow = text(flow)?;
        Ok(Self {
            state: run(py, || api::graph_state(flow))?,
        })
    }

    /// Apply a batch; returns what it did as JSON.
    #[pyo3(signature = (operations, *, forward = false, inverse = false, restoring = false))]
    fn apply(
        &mut self,
        py: Python<'_>,
        operations: &Bound<'_, PyAny>,
        forward: bool,
        inverse: bool,
        restoring: bool,
    ) -> PyResult<String> {
        let operations = text(operations)?;
        let options = ApplyOptions {
            forward,
            inverse,
            restoring,
        };
        let state = &mut self.state;
        run(py, || api::apply_to(state, operations, options))
    }

    /// The graph as JSON text.
    fn to_json(&self, py: Python<'_>) -> String {
        let state = &self.state;
        py.detach(|| state.to_string())
    }
}

/// Apply operations to a graph; returns `{"flow_data", ...}` as JSON.
#[pyfunction]
#[pyo3(signature = (flow, operations, *, forward = true, inverse = false, restoring = false))]
fn apply(
    py: Python<'_>,
    flow: &Bound<'_, PyAny>,
    operations: &Bound<'_, PyAny>,
    forward: bool,
    inverse: bool,
    restoring: bool,
) -> PyResult<String> {
    let (flow, operations) = (text(flow)?, text(operations)?);
    let options = ApplyOptions {
        forward,
        inverse,
        restoring,
    };
    run(py, || api::apply(flow, operations, options))
}

/// Parse operations and print them as the engine records them.
#[pyfunction]
fn normalize_operations(py: Python<'_>, operations: &Bound<'_, PyAny>) -> PyResult<String> {
    let operations = text(operations)?;
    run(py, || api::normalize_operations(operations))
}

/// The operations that turn `base` into `target`.
#[pyfunction]
fn diff(py: Python<'_>, base: &Bound<'_, PyAny>, target: &Bound<'_, PyAny>) -> PyResult<String> {
    let (base, target) = (text(base)?, text(target)?);
    run(py, || api::diff(base, target))
}

/// The operations that turn `base` into `target`, verified by replay.
#[pyfunction]
fn derive(py: Python<'_>, base: &Bound<'_, PyAny>, target: &Bound<'_, PyAny>) -> PyResult<String> {
    let (base, target) = (text(base)?, text(target)?);
    run(py, || api::derive(base, target))
}

/// Every rule a graph breaks, as a JSON list of violations.
#[pyfunction]
#[pyo3(signature = (flow, base = None, *, check_values = true))]
fn validate(
    py: Python<'_>,
    flow: &Bound<'_, PyAny>,
    base: Option<&Bound<'_, PyAny>>,
    check_values: bool,
) -> PyResult<String> {
    let (flow, base) = (text(flow)?, optional_text(base)?);
    run(py, || api::validate(flow, base, check_values))
}

/// Repair what has one fix; returns `{"flow_data", "fixes"}`.
#[pyfunction]
#[pyo3(signature = (flow, base = None))]
fn repair(
    py: Python<'_>,
    flow: &Bound<'_, PyAny>,
    base: Option<&Bound<'_, PyAny>>,
) -> PyResult<String> {
    let (flow, base) = (text(flow)?, optional_text(base)?);
    run(py, || api::repair(flow, base))
}

/// The SHA-256 hex digest of a graph's canonical form.
#[pyfunction]
fn graph_hash(py: Python<'_>, flow: &Bound<'_, PyAny>) -> PyResult<String> {
    let flow = text(flow)?;
    run(py, || api::graph_hash(flow))
}

/// Whether two graphs are the same graph.
#[pyfunction]
fn graphs_equal(
    py: Python<'_>,
    left: &Bound<'_, PyAny>,
    right: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let (left, right) = (text(left)?, text(right)?);
    run(py, || api::graphs_equal(left, right))
}

/// Whether two JSON values are the same value.
#[pyfunction]
fn values_equal(
    py: Python<'_>,
    left: &Bound<'_, PyAny>,
    right: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let (left, right) = (text(left)?, text(right)?);
    run(py, || api::values_equal(left, right))
}

/// A JSON value in RFC 8785 canonical form.
#[pyfunction]
fn canonical_json(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<String> {
    let value = text(value)?;
    run(py, || api::canonical_json(value))
}

/// The engine's part of a save.
#[pyfunction]
fn prepare_write(
    py: Python<'_>,
    stored: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    options: &Bound<'_, PyAny>,
) -> PyResult<String> {
    let (stored, target, options) = (text(stored)?, text(target)?, text(options)?);
    run(py, || api::prepare_write(stored, target, options))
}

/// A revision with a restore's fixes applied, after checking each one.
#[pyfunction]
fn apply_restore_fixes(
    py: Python<'_>,
    revision: &Bound<'_, PyAny>,
    stored: &Bound<'_, PyAny>,
    fixes: &Bound<'_, PyAny>,
) -> PyResult<String> {
    let (revision, stored, fixes) = (text(revision)?, text(stored)?, text(fixes)?);
    run(py, || api::apply_restore_fixes(revision, stored, fixes))
}

/// The fixes that turn a revision's edges as read into the edges its preview shows.
#[pyfunction]
fn edge_fixes(
    py: Python<'_>,
    read: &Bound<'_, PyAny>,
    shown: &Bound<'_, PyAny>,
) -> PyResult<String> {
    let (read, shown) = (text(read)?, text(shown)?);
    run(py, || api::edge_fixes(read, shown))
}

/// The part of the fixes that touches the given edges.
#[pyfunction]
fn fixes_for_edges(
    py: Python<'_>,
    fixes: &Bound<'_, PyAny>,
    edge_ids: &Bound<'_, PyAny>,
) -> PyResult<String> {
    let (fixes, edge_ids) = (text(fixes)?, text(edge_ids)?);
    run(py, || api::fixes_for_edges(fixes, edge_ids))
}

/// Rows in order and without `__id__` and `__pos__`.
#[pyfunction]
fn strip_row_keys(py: Python<'_>, rows: &Bound<'_, PyAny>) -> PyResult<String> {
    let rows = text(rows)?;
    run(py, || api::strip_row_keys(rows))
}

/// Rows in order, by `(__pos__, __id__)`, or as stored for a legacy table.
#[pyfunction]
fn ordered_rows(py: Python<'_>, rows: &Bound<'_, PyAny>) -> PyResult<String> {
    let rows = text(rows)?;
    run(py, || api::ordered_rows(rows))
}

/// A flow whose top-level tables have their rows in order and without `__id__` and `__pos__`.
#[pyfunction]
fn strip_flow_table_row_keys(py: Python<'_>, flow: &Bound<'_, PyAny>) -> PyResult<String> {
    let flow = text(flow)?;
    run(py, || api::strip_flow_table_row_keys(flow))
}

/// Rows with the ids and positions a write needs.
#[pyfunction]
#[pyo3(signature = (rows, previous = None, *, editor = false))]
fn assign_row_ids(
    py: Python<'_>,
    rows: &Bound<'_, PyAny>,
    previous: Option<&Bound<'_, PyAny>>,
    editor: bool,
) -> PyResult<String> {
    let (rows, previous) = (text(rows)?, optional_text(previous)?);
    run(py, || api::assign_row_ids(rows, previous, editor))
}

/// A node being added, with ids on every table.
#[pyfunction]
#[pyo3(signature = (node, *, editor = false))]
fn assign_table_row_ids(py: Python<'_>, node: &Bound<'_, PyAny>, editor: bool) -> PyResult<String> {
    let node = text(node)?;
    run(py, || api::assign_table_row_ids(node, editor))
}

/// `target` with ids on the tables it adds or changes relative to `base`.
#[pyfunction]
#[pyo3(signature = (base, target, *, editor = false))]
fn assign_changed_table_row_ids(
    py: Python<'_>,
    base: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    editor: bool,
) -> PyResult<String> {
    let (base, target) = (text(base)?, text(target)?);
    run(py, || {
        api::assign_changed_table_row_ids(base, target, editor)
    })
}

/// A node with ids on the tables it adds or changes relative to `previous`.
#[pyfunction]
#[pyo3(signature = (node, previous = None, *, editor = false))]
fn assign_changed_node_table_row_ids(
    py: Python<'_>,
    node: &Bound<'_, PyAny>,
    previous: Option<&Bound<'_, PyAny>>,
    editor: bool,
) -> PyResult<String> {
    let (node, previous) = (text(node)?, optional_text(previous)?);
    run(py, || {
        api::assign_changed_node_table_row_ids(node, previous, editor)
    })
}

/// Rows with `new_rows` appended, each with a new id one position past the last.
#[pyfunction]
fn append_table_rows(
    py: Python<'_>,
    rows: &Bound<'_, PyAny>,
    new_rows: &Bound<'_, PyAny>,
) -> PyResult<String> {
    let (rows, new_rows) = (text(rows)?, text(new_rows)?);
    run(py, || api::append_table_rows(rows, new_rows))
}

/// The names of a node's template fields whose value is a table.
#[pyfunction]
fn table_fields(py: Python<'_>, node: &Bound<'_, PyAny>) -> PyResult<String> {
    let node = text(node)?;
    run(py, || api::table_fields(node))
}

/// A new random edge id in the editor's format.
#[pyfunction]
fn new_edge_id() -> String {
    api::new_edge_id()
}

/// A new random table row id in the editor's format.
#[pyfunction]
fn new_table_row_id() -> String {
    api::new_table_row_id()
}

/// The node schema the engine reads, as JSON text.
#[pyfunction]
fn node_schema() -> &'static str {
    api::node_schema()
}

/// The native part of `lfx_native`.
#[pymodule]
mod _native {
    #[pymodule_export]
    use super::{
        EngineError, GraphState, append_table_rows, apply, apply_restore_fixes,
        assign_changed_node_table_row_ids, assign_changed_table_row_ids, assign_row_ids,
        assign_table_row_ids, canonical_json, derive, diff, edge_fixes, fixes_for_edges,
        graph_hash, graphs_equal, new_edge_id, new_table_row_id, node_schema, normalize_operations,
        ordered_rows, prepare_write, repair, strip_flow_table_row_keys, strip_row_keys,
        table_fields, validate, values_equal,
    };
}
