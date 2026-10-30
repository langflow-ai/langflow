//! The Python binding of lfx: the `lfx_native` package.
//!
//! Every function takes Python values and returns Python values. An argument
//! that is `bytes` is UTF-8 JSON text, which the engine parses without the
//! GIL; any other argument is read as the JSON value it is: `dict`, `list`,
//! `tuple`, `str`, `int`, `float`, `bool` or `None`. A `str` is a JSON string,
//! never text to parse, so a string value cannot be mistaken for a graph.
//! Reading Python objects is about four times cheaper than `json.dumps` and a
//! parse, and building them about three times cheaper than writing JSON and
//! `json.loads`.
//!
//! An engine error is raised as [`EngineError`], which carries the error's
//! `kind` (the matching Python exception class of
//! `lfx.services.flow_operations` or `langflow.services.flow_history`), its
//! `code`, and `details`: the whole error as a dict. The binding holds no
//! rules: each function calls `lfx::ops::api`.

use lfx::ops::api::{self, ApiError, ApiResult, Input};
use lfx::ops::{ApplyOptions, Entry, Error};
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyBytes, PyDict, PyFloat, PyInt, PyList, PyString, PyTuple};
use serde_json::{Map, Number, Value};

create_exception!(
    lfx_native,
    EngineError,
    PyException,
    "An engine error. `kind` names the matching Python exception class, `code` is its stable code, and \
     `details` is the whole error as a dict."
);

fn engine_error(py: Python<'_>, error: &ApiError) -> PyErr {
    let raised = EngineError::new_err(error.message().to_owned());
    match describe(py, &raised, error) {
        Ok(()) => raised,
        Err(failure) => failure,
    }
}

/// Set the error's `kind`, `code` and `details`.
fn describe(py: Python<'_>, raised: &PyErr, error: &ApiError) -> PyResult<()> {
    let value = raised.value(py);
    value.setattr("kind", error.kind())?;
    value.setattr("code", error.code())?;
    value.setattr("details", to_python(py, &error.0)?)
}

// --- Arguments ------------------------------------------------------------------------------

/// The deepest nesting the engine reads: the depth the JSON parser allows.
const MAX_DEPTH: usize = 127;

/// An argument: JSON text from UTF-8 `bytes`, or a Python value.
fn input<'a>(object: &'a Bound<'_, PyAny>) -> PyResult<Input<'a>> {
    if let Ok(bytes) = object.cast::<PyBytes>() {
        return std::str::from_utf8(bytes.as_bytes())
            .map(Input::Text)
            .map_err(|error| PyValueError::new_err(error.to_string()));
    }
    Ok(Input::Value(read(object, 0)?))
}

fn optional_input<'a>(object: Option<&'a Bound<'_, PyAny>>) -> PyResult<Option<Input<'a>>> {
    object
        .filter(|object| !object.is_none())
        .map(input)
        .transpose()
}

/// A value the JSON parser would refuse: the same engine error as text that
/// does not parse.
fn not_json(object: &Bound<'_, PyAny>, why: &str) -> PyErr {
    let error = Error::graph_message(format!("flow data is not valid JSON: {why}"));
    engine_error(object.py(), &error.into())
}

/// Read a Python value as JSON, with the rules of the JSON parser: nesting
/// at most 127 levels deep, no lone surrogate in a string, and finite
/// numbers. A key that is not a `str`, or a value of another type, is a
/// `TypeError`.
fn read(object: &Bound<'_, PyAny>, depth: usize) -> PyResult<Value> {
    if let Ok(string) = object.cast::<PyString>() {
        return Ok(Value::String(text_of(string)?.to_owned()));
    }
    if let Ok(dict) = object.cast::<PyDict>() {
        nested(object, depth)?;
        let mut map = Map::with_capacity(dict.len());
        for (key, item) in dict.iter() {
            let key = key
                .cast::<PyString>()
                .map_err(|_| PyTypeError::new_err("a JSON object's keys must be str"))?;
            map.insert(text_of(key)?.to_owned(), read(&item, depth + 1)?);
        }
        return Ok(Value::Object(map));
    }
    if let Ok(list) = object.cast::<PyList>() {
        nested(object, depth)?;
        return list
            .iter()
            .map(|item| read(&item, depth + 1))
            .collect::<PyResult<_>>()
            .map(Value::Array);
    }
    if object.is_none() {
        return Ok(Value::Null);
    }
    // `bool` is a subclass of `int`, so it is read first.
    if let Ok(flag) = object.cast::<PyBool>() {
        return Ok(Value::Bool(flag.is_true()));
    }
    if object.cast::<PyInt>().is_ok() {
        if let Ok(int) = object.extract::<i64>() {
            return Ok(Value::Number(int.into()));
        }
        // An int too large for 64 bits keeps its digits, as JSON text does.
        let digits = object.str()?;
        return serde_json::from_str::<Number>(digits.to_str()?)
            .map(Value::Number)
            .map_err(|error| PyValueError::new_err(error.to_string()));
    }
    if let Ok(float) = object.cast::<PyFloat>() {
        return Number::from_f64(float.value())
            .map(Value::Number)
            .ok_or_else(|| not_json(object, "NaN and Infinity are not JSON numbers"));
    }
    if let Ok(tuple) = object.cast::<PyTuple>() {
        nested(object, depth)?;
        return tuple
            .iter()
            .map(|item| read(&item, depth + 1))
            .collect::<PyResult<_>>()
            .map(Value::Array);
    }
    Err(PyTypeError::new_err(format!(
        "{} is not a JSON value",
        object.get_type().name()?
    )))
}

/// Refuse a container nested deeper than the parser reads.
fn nested(object: &Bound<'_, PyAny>, depth: usize) -> PyResult<()> {
    if depth >= MAX_DEPTH {
        return Err(not_json(object, "nested more than 127 levels deep"));
    }
    Ok(())
}

/// A string's text, refusing a lone surrogate as the JSON parser does.
fn text_of<'a>(string: &'a Bound<'_, PyString>) -> PyResult<&'a str> {
    string
        .to_str()
        .map_err(|_| not_json(string.as_any(), "a string holds a lone surrogate"))
}

// --- Results --------------------------------------------------------------------------------

/// A JSON value as Python objects: numbers as `int` or `float`, as
/// `json.loads` reads their text.
fn to_python<'py>(py: Python<'py>, value: &Value) -> PyResult<Bound<'py, PyAny>> {
    Ok(match value {
        Value::Null => py.None().into_bound(py),
        Value::Bool(flag) => PyBool::new(py, *flag).to_owned().into_any(),
        Value::Number(number) => number_to_python(py, number)?,
        Value::String(text) => PyString::new(py, text).into_any(),
        Value::Array(items) => list_to_python(py, items)?.into_any(),
        Value::Object(map) => map_to_python(py, map)?.into_any(),
    })
}

fn number_to_python<'py>(py: Python<'py>, number: &Number) -> PyResult<Bound<'py, PyAny>> {
    if let Some(int) = number.as_i64() {
        return Ok(int.into_pyobject(py)?.into_any());
    }
    if let Some(int) = number.as_u64() {
        return Ok(int.into_pyobject(py)?.into_any());
    }
    let text = number.to_string();
    if text.contains(['.', 'e', 'E']) {
        let float = number
            .as_f64()
            .ok_or_else(|| PyValueError::new_err("a number is not finite"))?;
        Ok(PyFloat::new(py, float).into_any())
    } else {
        py.get_type::<PyInt>().call1((text,))
    }
}

fn list_to_python<'py>(py: Python<'py>, items: &[Value]) -> PyResult<Bound<'py, PyList>> {
    let list = PyList::empty(py);
    for item in items {
        list.append(to_python(py, item)?)?;
    }
    Ok(list)
}

fn map_to_python<'py>(py: Python<'py>, map: &Map<String, Value>) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    for (key, item) in map {
        dict.set_item(key, to_python(py, item)?)?;
    }
    Ok(dict)
}

/// Run engine work without the GIL.
fn run<T: Send>(py: Python<'_>, work: impl FnOnce() -> ApiResult<T> + Send) -> PyResult<T> {
    py.detach(work).map_err(|error| engine_error(py, &error))
}

/// Run engine work without the GIL, and return its result as Python objects.
/// The result is dropped without the GIL too: freeing a large graph takes time.
fn call(py: Python<'_>, work: impl FnOnce() -> ApiResult + Send) -> PyResult<Bound<'_, PyAny>> {
    let value = run(py, work)?;
    let result = to_python(py, &value);
    py.detach(move || drop(value));
    result
}

/// The apply options; `mode` is `strict` or `preview`.
fn apply_options(
    py: Python<'_>,
    forward: bool,
    backward: bool,
    mode: &str,
) -> PyResult<ApplyOptions> {
    let mode = mode
        .parse()
        .map_err(|error: Error| engine_error(py, &error.into()))?;
    Ok(ApplyOptions {
        forward,
        backward,
        mode,
    })
}

// --- The engine -----------------------------------------------------------------------------

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
        let flow = input(flow)?;
        Ok(Self {
            state: run(py, || api::graph_state(flow))?,
        })
    }

    /// Apply a batch; returns what it did.
    #[pyo3(signature = (operations, *, forward = false, backward = false, mode = "strict"))]
    fn apply<'py>(
        &mut self,
        py: Python<'py>,
        operations: &Bound<'_, PyAny>,
        forward: bool,
        backward: bool,
        mode: &str,
    ) -> PyResult<Bound<'py, PyAny>> {
        let operations = input(operations)?;
        let options = apply_options(py, forward, backward, mode)?;
        let state = &mut self.state;
        call(py, || api::apply_to(state, operations, options))
    }

    /// The graph as JSON text.
    fn to_json(&self, py: Python<'_>) -> String {
        let state = &self.state;
        py.detach(|| api::graph_json(state))
    }

    /// The graph as a dict, built from the loaded graph without a copy.
    fn to_dict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let graph = PyDict::new(py);
        for (key, entry) in self.state.entries() {
            let value = match entry {
                Entry::Value(value) => to_python(py, value)?,
                Entry::Nodes(nodes) => {
                    let list = PyList::empty(py);
                    for node in nodes.iter() {
                        list.append(to_python(py, node)?)?;
                    }
                    list.into_any()
                }
                Entry::Edges(edges) => {
                    let list = PyList::empty(py);
                    for edge in edges.iter() {
                        list.append(map_to_python(py, edge)?)?;
                    }
                    list.into_any()
                }
            };
            graph.set_item(key, value)?;
        }
        Ok(graph)
    }
}

/// Apply operations to a graph; returns `{"flow_data", ...}`.
#[pyfunction]
#[pyo3(signature = (flow, operations, *, forward = true, backward = false, mode = "strict"))]
fn apply<'py>(
    py: Python<'py>,
    flow: &Bound<'_, PyAny>,
    operations: &Bound<'_, PyAny>,
    forward: bool,
    backward: bool,
    mode: &str,
) -> PyResult<Bound<'py, PyAny>> {
    let (flow, operations) = (input(flow)?, input(operations)?);
    let options = apply_options(py, forward, backward, mode)?;
    call(py, || api::apply(flow, operations, options))
}

/// Parse operations and return them as the engine records them.
#[pyfunction]
fn normalize_operations<'py>(
    py: Python<'py>,
    operations: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let operations = input(operations)?;
    call(py, || api::normalize_operations(operations))
}

/// The operations that turn `base` into `target`.
#[pyfunction]
fn diff<'py>(
    py: Python<'py>,
    base: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let (base, target) = (input(base)?, input(target)?);
    call(py, || api::diff(base, target))
}

/// The operations that turn `base` into `target`, verified by replay: `{"operations"}`.
#[pyfunction]
fn derive<'py>(
    py: Python<'py>,
    base: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let (base, target) = (input(base)?, input(target)?);
    call(py, || api::derive(base, target))
}

/// Every rule a graph breaks, as a list of violations.
#[pyfunction]
#[pyo3(signature = (flow, base = None, *, check_values = true))]
fn validate<'py>(
    py: Python<'py>,
    flow: &Bound<'_, PyAny>,
    base: Option<&Bound<'_, PyAny>>,
    check_values: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let (flow, base) = (input(flow)?, optional_input(base)?);
    call(py, || api::validate(flow, base, check_values))
}

/// Repair what has one fix; returns `{"flow_data", "fixes"}`.
#[pyfunction]
#[pyo3(signature = (flow, base = None))]
fn repair<'py>(
    py: Python<'py>,
    flow: &Bound<'_, PyAny>,
    base: Option<&Bound<'_, PyAny>>,
) -> PyResult<Bound<'py, PyAny>> {
    let (flow, base) = (input(flow)?, optional_input(base)?);
    call(py, || api::repair(flow, base))
}

/// The SHA-256 hex digest of a graph's canonical form.
#[pyfunction]
fn graph_hash(py: Python<'_>, flow: &Bound<'_, PyAny>) -> PyResult<String> {
    let flow = input(flow)?;
    run(py, || api::graph_hash(flow))
}

/// Whether two graphs are the same graph.
#[pyfunction]
fn graphs_equal(
    py: Python<'_>,
    left: &Bound<'_, PyAny>,
    right: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let (left, right) = (input(left)?, input(right)?);
    run(py, || api::graphs_equal(left, right))
}

/// Whether two JSON values are the same value.
#[pyfunction]
fn values_equal(
    py: Python<'_>,
    left: &Bound<'_, PyAny>,
    right: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let (left, right) = (input(left)?, input(right)?);
    run(py, || api::values_equal(left, right))
}

/// A JSON value in RFC 8785 canonical form, as text.
#[pyfunction]
fn canonical_json(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<String> {
    let value = input(value)?;
    run(py, || api::canonical_json(value))
}

/// The engine's part of a save.
#[pyfunction]
fn prepare_write<'py>(
    py: Python<'py>,
    stored: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    options: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let (stored, target, options) = (input(stored)?, input(target)?, input(options)?);
    call(py, || api::prepare_write(stored, target, options))
}

/// A revision with a restore's fixes applied, after checking each one.
#[pyfunction]
fn apply_restore_fixes<'py>(
    py: Python<'py>,
    revision: &Bound<'_, PyAny>,
    stored: &Bound<'_, PyAny>,
    fixes: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let (revision, stored, fixes) = (input(revision)?, input(stored)?, input(fixes)?);
    call(py, || api::apply_restore_fixes(revision, stored, fixes))
}

/// The fixes that turn a revision's edges as read into the edges its preview shows.
#[pyfunction]
fn edge_fixes<'py>(
    py: Python<'py>,
    read: &Bound<'_, PyAny>,
    shown: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let (read, shown) = (input(read)?, input(shown)?);
    call(py, || api::edge_fixes(read, shown))
}

/// The part of the fixes that touches the given edges.
#[pyfunction]
fn fixes_for_edges<'py>(
    py: Python<'py>,
    fixes: &Bound<'_, PyAny>,
    edge_ids: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let (fixes, edge_ids) = (input(fixes)?, input(edge_ids)?);
    call(py, || api::fixes_for_edges(fixes, edge_ids))
}

/// Rows in order and without `__id__` and `__pos__`.
#[pyfunction]
fn strip_row_keys<'py>(py: Python<'py>, rows: &Bound<'_, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let rows = input(rows)?;
    call(py, || api::strip_row_keys(rows))
}

/// Rows in order, by `(__pos__, __id__)`, or as stored for a legacy table.
#[pyfunction]
fn ordered_rows<'py>(py: Python<'py>, rows: &Bound<'_, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let rows = input(rows)?;
    call(py, || api::ordered_rows(rows))
}

/// A flow whose top-level tables have their rows in order and without `__id__` and `__pos__`.
#[pyfunction]
fn strip_flow_table_row_keys<'py>(
    py: Python<'py>,
    flow: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let flow = input(flow)?;
    call(py, || api::strip_flow_table_row_keys(flow))
}

/// Rows with the ids and positions a write needs.
#[pyfunction]
#[pyo3(signature = (rows, previous = None, *, editor = false))]
fn assign_row_ids<'py>(
    py: Python<'py>,
    rows: &Bound<'_, PyAny>,
    previous: Option<&Bound<'_, PyAny>>,
    editor: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let (rows, previous) = (input(rows)?, optional_input(previous)?);
    call(py, || api::assign_row_ids(rows, previous, editor))
}

/// A node being added, with ids on every table.
#[pyfunction]
#[pyo3(signature = (node, *, editor = false))]
fn assign_table_row_ids<'py>(
    py: Python<'py>,
    node: &Bound<'_, PyAny>,
    editor: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let node = input(node)?;
    call(py, || api::assign_table_row_ids(node, editor))
}

/// `target` with ids on the tables it adds or changes relative to `base`.
#[pyfunction]
#[pyo3(signature = (base, target, *, editor = false))]
fn assign_changed_table_row_ids<'py>(
    py: Python<'py>,
    base: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
    editor: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let (base, target) = (input(base)?, input(target)?);
    call(py, || {
        api::assign_changed_table_row_ids(base, target, editor)
    })
}

/// A node with ids on the tables it adds or changes relative to `previous`.
#[pyfunction]
#[pyo3(signature = (node, previous = None, *, editor = false))]
fn assign_changed_node_table_row_ids<'py>(
    py: Python<'py>,
    node: &Bound<'_, PyAny>,
    previous: Option<&Bound<'_, PyAny>>,
    editor: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let (node, previous) = (input(node)?, optional_input(previous)?);
    call(py, || {
        api::assign_changed_node_table_row_ids(node, previous, editor)
    })
}

/// Rows with `new_rows` appended, each with a new id one position past the last.
#[pyfunction]
fn append_table_rows<'py>(
    py: Python<'py>,
    rows: &Bound<'_, PyAny>,
    new_rows: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let (rows, new_rows) = (input(rows)?, input(new_rows)?);
    call(py, || api::append_table_rows(rows, new_rows))
}

/// The names of a node's template fields whose value is a table.
#[pyfunction]
fn table_fields<'py>(py: Python<'py>, node: &Bound<'_, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let node = input(node)?;
    call(py, || api::table_fields(node))
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
