//! The Python binding of lfx: the `lfx_native` package.
//!
//! A `bytes` argument is UTF-8 JSON text. Any other argument is
//! a JSON value: `dict`, `list`, `tuple`, `str`, `int`,
//! `float`, `bool` or `None`. A `str` is a JSON string, never
//! text to parse. Reading Python objects is about 4 times
//! faster than `json.dumps` and a parse. Building them is about
//! 3 times faster than writing JSON and `json.loads`.
//!
//! An engine error raises [`EngineError`]. Each function calls
//! `lfx_ops::bindings`. Only large work releases the GIL. See
//! `HELD_VALUES`.

use std::collections::HashMap;
use std::sync::mpsc::{SyncSender, TrySendError, sync_channel};
use std::sync::{LazyLock, PoisonError, RwLock, RwLockWriteGuard, TryLockError};

use lfx_ops::bindings::{self, BindingError, BindingResult, Input};
use lfx_ops::json::{FlowObj, FlowValue, Number, StringPool};
use lfx_ops::{
    Applied, ApplyOptions, Change, Entry, Error, FieldUpdate, Operation, ReplayOptions, Segment,
};
use pyo3::IntoPyObjectExt;
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::sync::RwLockExt;
use pyo3::types::{PyBool, PyBytes, PyDict, PyFloat, PyInt, PyList, PyString, PyTuple};

create_exception!(
    lfx_native,
    EngineError,
    PyException,
    "An engine error. `kind` names the matching Python exception class, `code` is its stable code, and \
     `details` is the whole error as a dict."
);

fn engine_error(py: Python<'_>, error: impl Into<BindingError>) -> PyErr {
    let error = error.into();
    let raised = EngineError::new_err(error.message().to_owned());
    match describe(py, &raised, &error) {
        Ok(()) => raised,
        Err(failure) => failure,
    }
}

/// Set the error's `kind`, `code` and `details`.
fn describe(py: Python<'_>, raised: &PyErr, error: &BindingError) -> PyResult<()> {
    let value = raised.value(py);
    value.setattr("kind", error.kind())?;
    value.setattr("code", error.code())?;
    value.setattr("details", to_python(py, &error.details())?)
}

// --- Arguments -----------------------------------------------

/// The deepest nesting the engine reads: the depth the JSON
/// parser allows.
const MAX_DEPTH: usize = 127;

/// An argument: JSON text from UTF-8 `bytes`, or a Python
/// value.
fn input<'a>(object: &'a Bound<'_, PyAny>) -> PyResult<Input<'a>> {
    if let Ok(bytes) = object.cast::<PyBytes>() {
        return std::str::from_utf8(bytes.as_bytes())
            .map(Input::Text)
            .map_err(|error| PyValueError::new_err(error.to_string()));
    }
    Ok(Input::Value(read(object, 0, &mut StringPool::default())?))
}

fn optional_input<'a>(object: Option<&'a Bound<'_, PyAny>>) -> PyResult<Option<Input<'a>>> {
    object
        .filter(|object| !object.is_none())
        .map(input)
        .transpose()
}

/// A value the JSON parser would refuse: the same engine error
/// as text that does not parse.
fn not_json(object: &Bound<'_, PyAny>, why: &str) -> PyErr {
    let error = Error::graph_message(format!("flow data is not valid JSON: {why}"));
    engine_error(object.py(), error)
}

/// Read a Python value as JSON, with the limits of the JSON
/// parser. A key that is not a `str`, or a value of another
/// type, is a `TypeError`.
fn read(object: &Bound<'_, PyAny>, depth: usize, strings: &mut StringPool) -> PyResult<FlowValue> {
    if let Ok(string) = object.cast::<PyString>() {
        return Ok(FlowValue::String(strings.intern(text_of(string)?)));
    }
    if let Ok(dict) = object.cast::<PyDict>() {
        nested(object, depth)?;
        let mut rows = Vec::with_capacity(dict.len());
        for (key, item) in dict.iter() {
            let key = key
                .cast::<PyString>()
                .map_err(|_| PyTypeError::new_err("a JSON object's keys must be str"))?;
            let key = strings.intern(text_of(key)?);
            rows.push((key, read(&item, depth + 1, strings)?));
        }
        return Ok(FlowValue::Object(FlowObj::from_entries(rows)));
    }
    if let Ok(list) = object.cast::<PyList>() {
        nested(object, depth)?;
        return list
            .iter()
            .map(|item| read(&item, depth + 1, strings))
            .collect::<PyResult<_>>()
            .map(FlowValue::Array);
    }
    if object.is_none() {
        return Ok(FlowValue::Null);
    }
    // `bool` is a subclass of `int`, so it is read first.
    if let Ok(flag) = object.cast::<PyBool>() {
        return Ok(FlowValue::Bool(flag.is_true()));
    }
    if object.cast::<PyInt>().is_ok() {
        if let Ok(int) = object.extract::<i64>() {
            return Ok(FlowValue::Number(int.into()));
        }
        // An int too large for 64 bits keeps its digits, as
        // JSON text does.
        let digits = object.str()?;
        return digits
            .to_str()?
            .parse::<Number>()
            .map(FlowValue::Number)
            .map_err(|error| PyValueError::new_err(error.to_string()));
    }
    if let Ok(float) = object.cast::<PyFloat>() {
        return Number::from_f64(float.value())
            .map(FlowValue::Number)
            .ok_or_else(|| not_json(object, "NaN and Infinity are not JSON numbers"));
    }
    if let Ok(tuple) = object.cast::<PyTuple>() {
        nested(object, depth)?;
        return tuple
            .iter()
            .map(|item| read(&item, depth + 1, strings))
            .collect::<PyResult<_>>()
            .map(FlowValue::Array);
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

/// A string's text, refusing a lone surrogate as the JSON
/// parser does.
fn text_of<'a>(string: &'a Bound<'_, PyString>) -> PyResult<&'a str> {
    string
        .to_str()
        .map_err(|_| not_json(string.as_any(), "a string holds a lone surrogate"))
}

// --- Results -------------------------------------------------

/// A JSON value as Python objects, as `json.loads` builds them.
fn to_python<'py>(py: Python<'py>, value: &FlowValue) -> PyResult<Bound<'py, PyAny>> {
    Builder::new(py).value(value)
}

/// Builds Python objects from JSON values, for one result.
///
/// All dicts with the same key share one Python `str`, as
/// `json.loads` does. A flow repeats a few keys thousands of
/// times, so this saves allocations, hashing and memory.
struct Builder<'py, 'v> {
    py: Python<'py>,
    keys: HashMap<&'v str, Bound<'py, PyString>>,
    /// Values visited while building the result, capped at the
    /// GIL threshold.
    work: Work,
}

impl<'py, 'v> Builder<'py, 'v> {
    fn new(py: Python<'py>) -> Self {
        Self {
            py,
            keys: HashMap::new(),
            work: Work::default(),
        }
    }

    fn value(&mut self, value: &'v FlowValue) -> PyResult<Bound<'py, PyAny>> {
        self.work.0 = (self.work.0 + 1).min(HELD_VALUES);
        let py = self.py;
        Ok(match value {
            FlowValue::Null => py.None().into_bound(py),
            FlowValue::Bool(flag) => PyBool::new(py, *flag).to_owned().into_any(),
            FlowValue::Number(number) => number_to_python(py, number)?,
            FlowValue::String(text) => PyString::new(py, text).into_any(),
            FlowValue::Array(items) => self.list(items.iter())?.into_any(),
            FlowValue::Object(map) => self.dict(map)?.into_any(),
        })
    }

    fn list(&mut self, items: impl Iterator<Item = &'v FlowValue>) -> PyResult<Bound<'py, PyList>> {
        let list = PyList::empty(self.py);
        for item in items {
            list.append(self.value(item)?)?;
        }
        Ok(list)
    }

    fn dict(&mut self, map: &'v FlowObj) -> PyResult<Bound<'py, PyDict>> {
        let dict = PyDict::new(self.py);
        for (key, item) in map {
            let key = self.key(key);
            dict.set_item(key, self.value(item)?)?;
        }
        Ok(dict)
    }

    /// Count one value, as [`Self::value`] does.
    fn count_value(&mut self) {
        self.work.0 = (self.work.0 + 1).min(HELD_VALUES);
    }

    fn string(&mut self, text: &str) -> Bound<'py, PyString> {
        self.count_value();
        PyString::new(self.py, text)
    }

    fn applied(
        &mut self,
        applied: &'v Applied,
        options: ApplyOptions,
    ) -> PyResult<Bound<'py, PyAny>> {
        self.count_value();
        let dict = PyDict::new(self.py);
        if options.forward {
            dict.set_item(
                self.key("forward_operations"),
                self.operations(&applied.forward)?,
            )?;
        }
        if options.backward {
            self.count_value();
            let batches = PyList::empty(self.py);
            for batch in &applied.backward {
                batches.append(self.operations(batch)?)?;
            }
            dict.set_item(self.key("backward_operations"), batches)?;
        }
        Ok(dict.into_any())
    }

    fn operations(&mut self, operations: &'v [Operation]) -> PyResult<Bound<'py, PyList>> {
        self.count_value();
        let list = PyList::empty(self.py);
        for operation in operations {
            list.append(self.operation(operation)?)?;
        }
        Ok(list)
    }

    fn operation(&mut self, operation: &'v Operation) -> PyResult<Bound<'py, PyDict>> {
        self.count_value();
        let dict = PyDict::new(self.py);
        dict.set_item(self.key("type"), self.string(operation.kind().as_str()))?;
        self.count_value();
        let list = PyList::empty(self.py);
        let key = match operation {
            Operation::AddNodes(nodes) => {
                for node in nodes {
                    self.count_value();
                    list.append(self.dict(node.as_map())?)?;
                }
                "nodes"
            }
            Operation::UpdateNodes(updates) => {
                for update in updates {
                    list.append(self.update(update)?)?;
                }
                "updates"
            }
            Operation::DeleteNodes(ids) | Operation::DeleteEdges(ids) => {
                for id in ids {
                    list.append(self.string(id))?;
                }
                "ids"
            }
            Operation::AddEdges(edges) => {
                for edge in edges {
                    self.count_value();
                    list.append(self.dict(edge.as_map())?)?;
                }
                "edges"
            }
        };
        dict.set_item(self.key(key), list)?;
        Ok(dict)
    }

    fn update(&mut self, update: &'v FieldUpdate) -> PyResult<Bound<'py, PyDict>> {
        self.count_value();
        let dict = PyDict::new(self.py);
        dict.set_item(self.key("id"), self.string(&update.id))?;
        self.count_value();
        let path = PyList::empty(self.py);
        for segment in update.path.iter() {
            match segment {
                Segment::Key(key) => path.append(self.string(key))?,
                Segment::Item(key) => {
                    self.count_value();
                    let item = PyDict::new(self.py);
                    item.set_item(self.key("key"), self.string(key))?;
                    path.append(item)?;
                }
            }
        }
        dict.set_item(self.key("path"), path)?;
        match &update.change {
            Change::Set(value) => {
                dict.set_item(self.key("op"), self.string("set_field"))?;
                dict.set_item(self.key("value"), self.value(value)?)?;
            }
            Change::Delete => {
                dict.set_item(self.key("op"), self.string("delete_field"))?;
            }
        }
        Ok(dict)
    }

    /// The Python `str` for a key: made the first time, shared
    /// after.
    fn key(&mut self, key: &'v str) -> Bound<'py, PyString> {
        let py = self.py;
        self.keys
            .entry(key)
            .or_insert_with(|| PyString::new(py, key))
            .clone()
    }
}

fn number_to_python<'py>(py: Python<'py>, number: &Number) -> PyResult<Bound<'py, PyAny>> {
    if let Some(int) = number.as_i64() {
        return Ok(int.into_pyobject(py)?.into_any());
    }
    if let Some(int) = number.as_u64() {
        return Ok(int.into_pyobject(py)?.into_any());
    }
    if number.is_integer() {
        // An integer too large for 64 bits keeps its digits.
        return py.get_type::<PyInt>().call1((number.to_string(),));
    }
    let float = number
        .as_f64()
        .filter(|float| float.is_finite())
        .ok_or_else(|| PyValueError::new_err("a number is not finite"))?;
    Ok(PyFloat::new(py, float).into_any())
}

// --- Work and the GIL ----------------------------------------

/// How much engine work a call holds the GIL for, in JSON
/// values.
///
/// A call that releases the GIL waits one switch interval (5 ms
/// by default) to take it back while another thread runs Python
/// code. Work below this limit is short next to that interval,
/// so it keeps the GIL.
const HELD_VALUES: usize = 8192;

/// JSON text counts one value per this many bytes. Real text
/// takes more bytes per value, so the count is never too small.
/// Text of 128 KB or more releases the GIL.
const TEXT_BYTES_PER_VALUE: usize = 16;

/// A node or an edge of a loaded graph counts as this many
/// values, about what a typical node holds. Counting values
/// would walk the graph.
const VALUES_PER_GRAPH_ITEM: usize = 200;

/// How large a piece of engine work is, in JSON values, up to
/// [`HELD_VALUES`].
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
struct Work(usize);

impl Work {
    /// The work on a value: its number of values, counted up to
    /// the limit.
    fn of_value(value: &FlowValue) -> Self {
        let mut count = 0;
        let mut stack = vec![value];
        while let Some(value) = stack.pop() {
            count += 1;
            if count >= HELD_VALUES {
                break;
            }
            match value {
                FlowValue::Array(items) => stack.extend(items),
                FlowValue::Object(map) => stack.extend(map.values()),
                _ => {}
            }
        }
        Self(count)
    }

    /// The work on an argument: text by its length, a value by
    /// its values.
    fn of_input(input: &Input<'_>) -> Self {
        match input {
            Input::Text(text) => Self(text.len() / TEXT_BYTES_PER_VALUE),
            Input::Value(value) => Self::of_value(value),
        }
    }

    /// The work on every node and edge of a graph.
    fn of_items(items: usize) -> Self {
        Self(items.saturating_mul(VALUES_PER_GRAPH_ITEM))
    }

    /// Whether the work runs without the GIL.
    fn is_large(self) -> bool {
        self.0 >= HELD_VALUES
    }
}

impl std::ops::Add for Work {
    type Output = Self;
    fn add(self, other: Self) -> Self {
        Self(self.0.saturating_add(other.0))
    }
}

/// Run engine work: with the GIL when it is small, without it
/// when it is large.
fn run<T: Send, E: Into<BindingError> + Send>(
    py: Python<'_>,
    work: Work,
    job: impl FnOnce() -> Result<T, E> + Send,
) -> PyResult<T> {
    let result = if work.is_large() {
        py.detach(job)
    } else {
        job()
    };
    result.map_err(|error| engine_error(py, error))
}

/// Run engine work as [`run`] does, and return its result as
/// Python objects.
fn call(
    py: Python<'_>,
    work: Work,
    job: impl FnOnce() -> BindingResult + Send,
) -> PyResult<Bound<'_, PyAny>> {
    finish(py, run(py, work, job)?)
}

/// A result as Python objects. A large result is dropped
/// without the GIL.
fn finish(py: Python<'_>, value: FlowValue) -> PyResult<Bound<'_, PyAny>> {
    let mut builder = Builder::new(py);
    let result = builder.value(&value);
    // A failed build can stop early, so count the values again.
    let work = if result.is_ok() {
        builder.work
    } else {
        Work::of_value(&value)
    };
    drop(builder);
    if work.is_large() {
        py.detach(move || drop(value));
    }
    result
}

/// Build operation results after the state lock is released.
/// `options` picks the operations to build. With
/// `forward_json`, the result also holds
/// `forward_operations_json`: each forward operation as JSON
/// `bytes`.
fn finish_applied(
    py: Python<'_>,
    applied: Applied,
    options: ApplyOptions,
    forward_json: bool,
) -> PyResult<Bound<'_, PyAny>> {
    let mut builder = Builder::new(py);
    let mut result = builder.applied(&applied, options);
    #[cfg(debug_assertions)]
    if let Ok(actual) = &result {
        // Compare with the generic builder on these operations,
        // not a new engine call.
        let generic = FlowValue::Object(bindings::applied_json(applied.clone(), options));
        let mut reference = Builder::new(py);
        let expected = reference.value(&generic)?;
        debug_assert_eq!(actual.repr()?.to_str()?, expected.repr()?.to_str()?);
        debug_assert_eq!(builder.work.0, reference.work.0);
    }
    if forward_json && let Ok(dict) = &result {
        let mut text = Vec::new();
        let added = PyList::new(
            py,
            applied.forward.iter().map(|operation| {
                bindings::write_operation_json(&mut text, operation);
                PyBytes::new(py, &text)
            }),
        )
        .and_then(|list| {
            dict.cast::<PyDict>()?
                .set_item("forward_operations_json", list)
        });
        if let Err(error) = added {
            result = Err(error);
        }
    }
    let work = builder.work;
    drop(builder);
    // A failed build may stop before it counts every value.
    if result.is_err() || work.is_large() {
        py.detach(move || drop(applied));
    }
    result
}

/// How many large graphs can wait for the drop thread. A graph
/// dropped while that many wait is dropped where it is.
const DROPS_WAITING: usize = 4;

/// Something that the drop thread frees.
type Dropped = Box<dyn Send>;

/// Whether the process may run on more than one CPU, its CPU
/// quota included.
static SPARE_CPU: LazyLock<bool> =
    LazyLock::new(|| std::thread::available_parallelism().is_ok_and(|cpus| cpus.get() > 1));

/// Drop a large graph on the drop thread, so the caller, often
/// a server's event loop, does not wait while it is freed.
/// Without that thread, or with [`DROPS_WAITING`] graphs
/// waiting, it is dropped here without the GIL.
fn drop_elsewhere(py: Python<'_>, value: Dropped) {
    static DROPS: LazyLock<Option<SyncSender<Dropped>>> = LazyLock::new(|| {
        let (sender, receiver) = sync_channel::<Dropped>(DROPS_WAITING);
        std::thread::Builder::new()
            .name("lfx-native-drop".into())
            .spawn(move || receiver.into_iter().for_each(drop))
            .ok()
            .map(|_| sender)
    });
    let value = match DROPS.as_ref() {
        Some(drops) => match drops.try_send(value) {
            Ok(()) => return,
            Err(TrySendError::Full(value) | TrySendError::Disconnected(value)) => value,
        },
        None => value,
    };
    py.detach(move || drop(value));
}

// --- The engine ----------------------------------------------

/// A flow graph that the engine keeps loaded, to apply or
/// replay many batches on it. A refused batch changes nothing.
///
/// `stage` applies a batch as `apply` does, but reads still see
/// the graph before it. `keep` commits the staged batch and
/// `drop` drops it, as after a database commit. While a batch
/// is staged, `apply`, `replay` and `stage` raise
/// `RuntimeError`.
///
/// Threads can share one state. A call releases the GIL to wait
/// for a held lock, and never waits for the GIL while it holds
/// the lock. So two threads cannot deadlock. Large work, such
/// as a long replay, runs without the GIL.
#[pyclass(module = "lfx_native", frozen)]
#[derive(Debug)]
struct GraphState {
    state: RwLock<lfx_ops::GraphState>,
}

/// A graph with no node and no edge: what a dropped graph
/// leaves in its place.
fn empty_graph() -> FlowValue {
    let mut root = FlowObj::new();
    root.insert("nodes".into(), FlowValue::Array(Vec::new()));
    root.insert("edges".into(), FlowValue::Array(Vec::new()));
    FlowValue::Object(root)
}

/// A large graph is dropped on the drop thread
/// ([`drop_elsewhere`]).
impl Drop for GraphState {
    fn drop(&mut self) {
        let state = self.state.get_mut().unwrap_or_else(PoisonError::into_inner);
        if !Work::of_items(state.item_count()).is_large() {
            return;
        }
        let empty = lfx_ops::GraphState::new(empty_graph()).expect("an empty graph loads");
        let state = std::mem::replace(state, empty);
        Python::attach(|py| drop_elsewhere(py, Box::new(state)));
    }
}

/// Why a call on the state could not run.
#[derive(Debug, Clone, Copy)]
enum Refused {
    /// A call panicked while it held the lock, so the graph may
    /// be half changed.
    Poisoned,
    /// A batch is staged, so no other batch can start.
    Staged,
    /// No batch is staged, so there is nothing to keep.
    NotStaged,
}

fn refused(refused: Refused) -> PyErr {
    match refused {
        Refused::Poisoned => {
            PyRuntimeError::new_err("this GraphState cannot be used: a call on it panicked")
        }
        Refused::Staged => {
            PyRuntimeError::new_err("a batch is staged: keep or drop it before the next batch")
        }
        Refused::NotStaged => PyRuntimeError::new_err("no batch is staged"),
    }
}

/// The state, locked for a batch, unless a batch is staged.
fn unstaged(
    state: RwLockWriteGuard<'_, lfx_ops::GraphState>,
) -> Result<RwLockWriteGuard<'_, lfx_ops::GraphState>, Refused> {
    if state.is_staged() {
        return Err(Refused::Staged);
    }
    Ok(state)
}

impl GraphState {
    /// Run `job` on the state locked for writing: with the GIL
    /// when the lock is free and `work` on the locked state is
    /// small, else without the GIL.
    fn write<T: Send>(
        &self,
        py: Python<'_>,
        work: impl FnOnce(&lfx_ops::GraphState) -> Work,
        job: impl FnOnce(RwLockWriteGuard<'_, lfx_ops::GraphState>) -> Result<T, Refused> + Send,
    ) -> Result<T, Refused> {
        match self.state.try_write() {
            Ok(state) if !work(&state).is_large() => return job(state),
            // The lock is released before the GIL.
            Ok(_) | Err(TryLockError::WouldBlock) => {}
            Err(TryLockError::Poisoned(_)) => return Err(Refused::Poisoned),
        }
        py.detach(|| job(self.state.write().map_err(|_| Refused::Poisoned)?))
    }

    /// Run `job` on the state locked for reading, as
    /// [`Self::write`] does.
    fn read<T: Send>(
        &self,
        py: Python<'_>,
        work: impl FnOnce(&lfx_ops::GraphState) -> Work,
        job: impl FnOnce(&lfx_ops::GraphState) -> T + Send,
    ) -> PyResult<T> {
        match self.state.try_read() {
            Ok(state) if !work(&state).is_large() => return Ok(job(&state)),
            Ok(_) | Err(TryLockError::WouldBlock) => {}
            Err(TryLockError::Poisoned(_)) => return Err(refused(Refused::Poisoned)),
        }
        py.detach(|| Ok(job(&*self.state.read().map_err(|_| Refused::Poisoned)?)))
            .map_err(refused)
    }

    /// Apply or stage a batch, with every rule, under the write
    /// lock.
    fn batch(
        &self,
        py: Python<'_>,
        operations: &Bound<'_, PyAny>,
        options: ApplyOptions,
        stage: bool,
    ) -> PyResult<(Applied, Work)> {
        let operations = input(operations)?;
        let work = Work::of_input(&operations);
        let applied = self
            .write(
                py,
                |_| work,
                |state| {
                    let mut graph = unstaged(state)?;
                    Ok(bindings::operations(operations).and_then(|operations| {
                        let applied = if stage {
                            graph.stage(operations, options)
                        } else {
                            graph.apply(operations, options)
                        };
                        Ok(applied?)
                    }))
                },
            )
            .map_err(refused)?;
        Ok((applied.map_err(|error| engine_error(py, error))?, work))
    }
}

#[pymethods]
impl GraphState {
    #[new]
    fn new(py: Python<'_>, flow: &Bound<'_, PyAny>) -> PyResult<Self> {
        let flow = input(flow)?;
        let work = Work::of_input(&flow);
        Ok(Self {
            state: RwLock::new(run(py, work, || bindings::graph_state(flow))?),
        })
    }

    /// Apply a batch, with every rule. Returns what it did.
    #[pyo3(signature = (operations, *, forward = false, backward = false, forward_json = false))]
    fn apply<'py>(
        &self,
        py: Python<'py>,
        operations: &Bound<'_, PyAny>,
        forward: bool,
        backward: bool,
        forward_json: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let options = ApplyOptions {
            forward: forward || forward_json,
            backward,
        };
        let (applied, _) = self.batch(py, operations, options, false)?;
        finish_applied(
            py,
            applied,
            ApplyOptions { forward, backward },
            forward_json,
        )
    }

    /// Apply a batch as `apply` does, and keep it staged until
    /// `keep` or `drop`. Returns what `apply` returns. A
    /// refused batch is not staged.
    #[pyo3(signature = (operations, *, forward = false, backward = false, forward_json = false))]
    fn stage<'py>(
        &self,
        py: Python<'py>,
        operations: &Bound<'_, PyAny>,
        forward: bool,
        backward: bool,
        forward_json: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let options = ApplyOptions {
            forward: forward || forward_json,
            backward,
        };
        let (staged, _) = self.batch(py, operations, options, true)?;
        finish_applied(py, staged, ApplyOptions { forward, backward }, forward_json)
    }

    /// Stage a batch and return only its forward operations.
    /// Each operation is a `bytes` object containing JSON text.
    fn stage_json<'py>(
        &self,
        py: Python<'py>,
        operations: &Bound<'_, PyAny>,
    ) -> PyResult<Bound<'py, PyList>> {
        let options = ApplyOptions {
            forward: true,
            backward: false,
        };
        let (staged, work) = self.batch(py, operations, options, true)?;
        let mut text = Vec::new();
        let list = PyList::new(
            py,
            staged.forward.iter().map(|operation| {
                bindings::write_operation_json(&mut text, operation);
                PyBytes::new(py, &text)
            }),
        );
        if work.is_large() {
            py.detach(move || drop(staged));
        }
        list
    }

    /// Commit the staged batch. Raises `RuntimeError` when no
    /// batch is staged.
    fn keep(&self, py: Python<'_>) -> PyResult<()> {
        let released = self
            .write(
                py,
                |_| Work::default(),
                |mut state| {
                    if state.keep() {
                        Ok(state.take_released())
                    } else {
                        Err(Refused::NotStaged)
                    }
                },
            )
            .map_err(refused)?;
        // The drop thread frees the removed nodes and edges
        // only with a spare CPU. With one CPU, it only adds a
        // thread switch.
        if let Some(released) = released {
            if *SPARE_CPU {
                drop_elsewhere(py, Box::new(released));
            } else {
                drop(released);
            }
        }
        Ok(())
    }

    /// Drop the staged batch, so the graph stays as it was
    /// before it. Returns whether a batch was staged.
    fn drop(&self, py: Python<'_>) -> PyResult<bool> {
        self.write(py, |_| Work::default(), |mut state| Ok(state.drop_staged()))
            .map_err(refused)
    }

    /// Whether a batch is staged.
    #[getter]
    fn staged(&self, py: Python<'_>) -> PyResult<bool> {
        self.read(py, |_| Work::default(), lfx_ops::GraphState::is_staged)
    }

    /// Replay stored operations, with no rule. Returns what it
    /// did.
    #[pyo3(signature = (operations, *, backward = false))]
    fn replay<'py>(
        &self,
        py: Python<'py>,
        operations: &Bound<'_, PyAny>,
        backward: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let operations = input(operations)?;
        let work = Work::of_input(&operations);
        let options = ReplayOptions { backward };
        let replayed = self
            .write(
                py,
                |_| work,
                |state| {
                    Ok(bindings::replay_to(
                        &mut *unstaged(state)?,
                        operations,
                        options,
                    ))
                },
            )
            .map_err(refused)?;
        finish(py, replayed.map_err(|error| engine_error(py, error))?)
    }

    /// The graph as JSON text: the committed graph, without a
    /// staged batch. With `staged`, the graph as `keep` will
    /// make it. Raises `RuntimeError` when `staged` is true and
    /// no batch is staged.
    #[pyo3(signature = (*, staged = false))]
    fn to_json(&self, py: Python<'_>, staged: bool) -> PyResult<String> {
        let work = |state: &lfx_ops::GraphState| Work::of_items(state.item_count());
        self.read(py, work, |state| {
            if staged {
                state.staged_to_json()
            } else {
                Some(state.to_json())
            }
        })?
        .ok_or_else(|| refused(Refused::NotStaged))
    }

    /// The SHA-256 hex digest of the graph's canonical form,
    /// without writing its text. `staged` works as in
    /// `to_json`.
    #[pyo3(signature = (*, staged = false))]
    fn graph_hash(&self, py: Python<'_>, staged: bool) -> PyResult<String> {
        let work = |state: &lfx_ops::GraphState| Work::of_items(state.item_count());
        self.read(py, work, |state| {
            if staged {
                state.staged_graph_hash()
            } else {
                Some(state.graph_hash())
            }
        })?
        .ok_or_else(|| refused(Refused::NotStaged))?
        .map_err(|error| engine_error(py, error))
    }

    /// The committed graph, without a staged batch, as a
    /// read-only `GraphSnapshot`. A new snapshot copies the
    /// node and edge lists and shares their JSON objects.
    /// Taking a large snapshot releases the GIL.
    fn snapshot(&self, py: Python<'_>) -> PyResult<GraphSnapshot> {
        let work = |state: &lfx_ops::GraphState| Work::of_items(state.item_count());
        let result = self.read(py, work, lfx_ops::GraphState::try_snapshot)?;
        let snapshot = if let Some(snapshot) = result {
            snapshot
        } else {
            // Release the GIL before waiting for another thread
            // to take a snapshot.
            py.detach(|| {
                let state = self.state.read().map_err(|_| Refused::Poisoned)?;
                Ok(state.snapshot())
            })
            .map_err(refused)?
        };
        Ok(GraphSnapshot::wrap(snapshot))
    }

    /// The committed graph as a dict, built without a copy.
    fn to_dict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        // `read_py_attached` waits for the lock without the
        // GIL, then holds both.
        let state = self
            .state
            .read_py_attached(py)
            .map_err(|_| refused(Refused::Poisoned))?;
        let mut builder = Builder::new(py);
        let graph = PyDict::new(py);
        for (key, entry) in state.entries() {
            let value = match entry {
                Entry::Value(value) => builder.value(value)?,
                Entry::Nodes(nodes) => builder.list(nodes.iter())?.into_any(),
                Entry::Edges(edges) => {
                    let list = PyList::empty(py);
                    for edge in edges.iter() {
                        list.append(builder.dict(edge)?)?;
                    }
                    list.into_any()
                }
            };
            graph.set_item(builder.key(key), value)?;
        }
        Ok(graph)
    }
}

/// A read-only graph from `GraphState.snapshot()`. Later
/// batches on the state do not change it. Threads can share it,
/// and large calls release the GIL.
#[pyclass(module = "lfx_native", frozen)]
#[derive(Debug)]
struct GraphSnapshot {
    snapshot: Option<lfx_ops::GraphSnapshot>,
    /// The work on the whole graph.
    work: Work,
}

impl GraphSnapshot {
    fn wrap(snapshot: lfx_ops::GraphSnapshot) -> Self {
        let work = Work::of_items(snapshot.item_count());
        Self {
            snapshot: Some(snapshot),
            work,
        }
    }
}

/// A large snapshot is dropped on the drop thread
/// ([`drop_elsewhere`]): it may hold the only copy of nodes
/// that the state has changed since.
impl Drop for GraphSnapshot {
    fn drop(&mut self) {
        if !self.work.is_large() {
            return;
        }
        let Some(snapshot) = self.snapshot.take() else {
            return;
        };
        let Some(data) = snapshot.into_unshared_data() else {
            return;
        };
        Python::attach(|py| drop_elsewhere(py, Box::new(data)));
    }
}

#[pymethods]
impl GraphSnapshot {
    /// The graph as JSON text: what the state's `to_json()`
    /// gave when the snapshot was taken.
    fn to_json(&self, py: Python<'_>) -> String {
        let snapshot = self
            .snapshot
            .as_ref()
            .expect("a live snapshot holds its graph");
        let write = || snapshot.to_json();
        if self.work.is_large() {
            py.detach(write)
        } else {
            write()
        }
    }

    /// The SHA-256 hex digest of the graph's canonical form:
    /// what the state's `graph_hash()` gave when the snapshot
    /// was taken.
    fn graph_hash(&self, py: Python<'_>) -> PyResult<String> {
        let snapshot = self
            .snapshot
            .as_ref()
            .expect("a live snapshot holds its graph");
        run(py, self.work, || snapshot.graph_hash())
    }
}

/// A flow graph read once, to validate, repair, hash, compare
/// and diff it.
///
/// Making it checks nothing. A check that passes does not run
/// again. The graph cannot change, so threads can share it.
#[pyclass(module = "lfx_native", frozen)]
#[derive(Debug)]
struct GraphPlain {
    plain: Option<lfx_ops::GraphPlain>,
    /// The work on the whole graph, counted once.
    work: Work,
}

impl GraphPlain {
    fn wrap(plain: lfx_ops::GraphPlain) -> Self {
        let work = Work::of_value(plain.as_value());
        Self {
            plain: Some(plain),
            work,
        }
    }

    fn core(&self) -> &lfx_ops::GraphPlain {
        self.plain
            .as_ref()
            .expect("a live plain graph holds its value")
    }
}

/// A large graph is dropped on the drop thread
/// ([`drop_elsewhere`]).
impl Drop for GraphPlain {
    fn drop(&mut self) {
        if !self.work.is_large() {
            return;
        }
        let Some(plain) = self.plain.take() else {
            return;
        };
        let value = plain.into_value();
        let deferred: Dropped = match value {
            FlowValue::Object(map) => {
                let Some(entries) = map.into_unshared_entries() else {
                    return;
                };
                Box::new(entries)
            }
            value => Box::new(value),
        };
        Python::attach(|py| drop_elsewhere(py, deferred));
    }
}

fn plain<'a>(object: Option<&'a Bound<'_, GraphPlain>>) -> (Option<&'a lfx_ops::GraphPlain>, Work) {
    object.map_or((None, Work::default()), |object| {
        let object = object.get();
        (Some(object.core()), object.work)
    })
}

#[pymethods]
impl GraphPlain {
    #[new]
    fn new(py: Python<'_>, flow: &Bound<'_, PyAny>) -> PyResult<Self> {
        let flow = input(flow)?;
        let work = Work::of_input(&flow);
        Ok(Self::wrap(run(py, work, || bindings::graph_plain(flow))?))
    }

    /// Every rule the graph breaks, as a list of violations.
    #[pyo3(signature = (base = None, *, check_values = true))]
    fn validate<'py>(
        &self,
        py: Python<'py>,
        base: Option<&Bound<'_, GraphPlain>>,
        check_values: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let (base, base_work) = plain(base);
        call(py, self.work + base_work, || {
            bindings::plain_validate(self.core(), base, check_values)
        })
    }

    /// Repair what has one fix. Returns the repaired graph and
    /// the fixes.
    #[pyo3(signature = (base = None))]
    fn repair<'py>(
        &self,
        py: Python<'py>,
        base: Option<&Bound<'_, GraphPlain>>,
    ) -> PyResult<(Bound<'py, GraphPlain>, Bound<'py, PyAny>)> {
        let (base, base_work) = plain(base);
        let (repaired, fixes) = run(py, self.work + base_work, || {
            bindings::plain_repair(self.core(), base)
        })?;
        // With no fixes, the repaired graph is this graph, so
        // its work is known.
        let work = if fixes.as_array().is_some_and(<[_]>::is_empty) {
            self.work
        } else {
            Work::of_value(repaired.as_value())
        };
        Ok((
            Bound::new(
                py,
                Self {
                    plain: Some(repaired),
                    work,
                },
            )?,
            to_python(py, &fixes)?,
        ))
    }

    /// The SHA-256 hex digest of the graph's canonical form.
    fn graph_hash(&self, py: Python<'_>) -> PyResult<String> {
        run(py, self.work, || self.core().graph_hash())
    }

    /// Whether the two graphs are the same graph.
    fn equals(&self, py: Python<'_>, other: &Bound<'_, GraphPlain>) -> PyResult<bool> {
        let other = other.get();
        run(py, self.work + other.work, || {
            self.core().equals(other.core())
        })
    }

    /// The operations that turn this graph into `target`,
    /// checked by replay.
    fn ops_diff<'py>(
        &self,
        py: Python<'py>,
        target: &Bound<'_, GraphPlain>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let target = target.get();
        call(py, self.work + target.work, || {
            bindings::plain_ops_diff(self.core(), target.core())
        })
    }

    /// The graph as JSON text.
    fn to_json(&self, py: Python<'_>) -> String {
        let write = || bindings::json_text(self.core().as_value());
        if self.work.is_large() {
            py.detach(write)
        } else {
            write()
        }
    }

    /// The graph as a dict.
    fn to_dict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        to_python(py, self.core().as_value())
    }
}

/// Module functions that run one engine call on JSON arguments.
/// In `fn name(a, b [c]; flag: bool)`, `a` and `b` are JSON
/// arguments, `c` is optional, and `flag` passes as it is. With
/// `-> T`, a function returns the `T`. Without it, it returns
/// its JSON result as Python objects ([`call`]).
macro_rules! engine_functions {
    (@run $py:ident, $work:ident, $job:expr) => { call($py, $work, $job) };
    (@run $py:ident, $work:ident, $job:expr, $ret:ty) => {
        run::<$ret, BindingError>($py, $work, $job)?.into_bound_py_any($py)
    };
    ($(
        $(#[$attr:meta])*
        fn $name:ident($($arg:ident),+ $([$($opt:ident),+])? $(; $($flag:ident: $flag_ty:ty),+)?)
            $(-> $ret:ty)? => $body:expr;
    )*) => {$(
        #[pyfunction]
        $(#[$attr])*
        fn $name<'py>(
            py: Python<'py>,
            $($arg: &Bound<'_, PyAny>,)+
            $($($opt: Option<&Bound<'_, PyAny>>,)+)?
            $($($flag: $flag_ty,)+)?
        ) -> PyResult<Bound<'py, PyAny>> {
            $(let $arg = input($arg)?;)+
            $($(let $opt = optional_input($opt)?;)+)?
            let work = Work::default()
                $(+ Work::of_input(&$arg))+
                $($(+ $opt.as_ref().map_or(Work::default(), Work::of_input))+)?;
            engine_functions!(@run py, work, || $body $(, $ret)?)
        }
    )*};
}

engine_functions! {
    /// Apply operations to a graph, with every rule. Returns
    /// `{"flow_data", ...}`.
    #[pyo3(signature = (flow, operations, *, forward = true, backward = false))]
    fn apply(flow, operations; forward: bool, backward: bool) =>
        bindings::apply(flow, operations, ApplyOptions { forward, backward });

    /// Replay stored operations on a graph, with no rule.
    /// Returns `{"flow_data", ...}`.
    #[pyo3(signature = (flow, operations, *, backward = false))]
    fn replay(flow, operations; backward: bool) =>
        bindings::replay(flow, operations, ReplayOptions { backward });

    /// The operations that turn `base` into `target`, checked
    /// by replay.
    fn ops_diff(base, target) => bindings::ops_diff(base, target);

    /// Every rule a graph breaks, as a list of violations.
    #[pyo3(signature = (flow, base = None, *, check_values = true))]
    fn validate(flow [base]; check_values: bool) => bindings::validate(flow, base, check_values);

    /// Repair what has one fix. Returns
    /// `{"flow_data", "fixes"}`.
    #[pyo3(signature = (flow, base = None))]
    fn repair(flow [base]) => bindings::repair(flow, base);

    /// The SHA-256 hex digest of a graph's canonical form.
    fn graph_hash(flow) -> String => bindings::graph_hash(flow);

    /// Whether two graphs are the same graph.
    fn graphs_equal(left, right) -> bool => bindings::graphs_equal(left, right);

    /// Whether two JSON values are the same value.
    fn values_equal(left, right) -> bool => bindings::values_equal(left, right);

    /// A JSON value in RFC 8785 canonical form, as text.
    fn canonical_json(value) -> String => bindings::canonical_json(value);

    /// A revision with a restore's fixes applied, after
    /// checking each one.
    fn apply_restore_fixes(revision, stored, fixes) =>
        bindings::apply_restore_fixes(revision, stored, fixes);

    /// The fixes that turn a revision's edges as read into the
    /// edges its preview shows.
    fn edge_fixes(read, shown) => bindings::edge_fixes(read, shown);

    /// The part of the fixes that touches the given edges.
    fn fixes_for_edges(fixes, edge_ids) => bindings::fixes_for_edges(fixes, edge_ids);

    /// Rows in order and without `__id__` and `__pos__`.
    fn strip_row_keys(rows) => bindings::strip_row_keys(rows);

    /// Rows in order, by `(__pos__, __id__)`, or as stored for
    /// a legacy table.
    fn ordered_rows(rows) => bindings::ordered_rows(rows);

    /// A flow whose top-level tables have their rows in order
    /// and without `__id__` and `__pos__`.
    fn strip_flow_table_row_keys(flow) => bindings::strip_flow_table_row_keys(flow);

    /// Rows with the ids and positions a write needs.
    #[pyo3(signature = (rows, previous = None, *, editor = false))]
    fn assign_row_ids(rows [previous]; editor: bool) =>
        bindings::assign_row_ids(rows, previous, editor);

    /// A node being added, with ids on every table.
    #[pyo3(signature = (node, *, editor = false))]
    fn assign_table_row_ids(node; editor: bool) => bindings::assign_table_row_ids(node, editor);

    /// `target` with ids on the tables it adds or changes
    /// relative to `base`.
    #[pyo3(signature = (base, target, *, editor = false))]
    fn assign_changed_table_row_ids(base, target; editor: bool) =>
        bindings::assign_changed_table_row_ids(base, target, editor);

    /// A node with ids on the tables it adds or changes
    /// relative to `previous`.
    #[pyo3(signature = (node, previous = None, *, editor = false))]
    fn assign_changed_node_table_row_ids(node [previous]; editor: bool) =>
        bindings::assign_changed_node_table_row_ids(node, previous, editor);

    /// Rows with `new_rows` appended, each with a new id one
    /// position past the last.
    fn append_table_rows(rows, new_rows) => bindings::append_table_rows(rows, new_rows);

    /// The names of a node's template fields whose value is a
    /// table.
    fn table_fields(node) => bindings::table_fields(node);
}

/// The SHA-256 hex digest of `text`, a `str` (as UTF-8) or
/// `bytes`. It equals
/// `hashlib.sha256(text.encode()).hexdigest()`, without the
/// copy that `encode` makes. Large text is hashed without the
/// GIL.
#[pyfunction]
fn text_sha256(py: Python<'_>, text: &Bound<'_, PyAny>) -> PyResult<String> {
    let bytes = if let Ok(string) = text.cast::<PyString>() {
        text_of(string)?.as_bytes()
    } else if let Ok(bytes) = text.cast::<PyBytes>() {
        bytes.as_bytes()
    } else {
        return Err(PyTypeError::new_err("text must be str or bytes"));
    };
    let hash = || bindings::text_sha256(bytes);
    Ok(if Work(bytes.len() / TEXT_BYTES_PER_VALUE).is_large() {
        py.detach(hash)
    } else {
        hash()
    })
}

/// A new random edge id in the editor's format.
#[pyfunction]
fn new_edge_id() -> String {
    lfx_ops::flow::id::new_edge_id()
}

/// A new random table row id in the editor's format.
#[pyfunction]
fn new_table_row_id() -> String {
    lfx_ops::flow::id::new_table_row_id()
}

/// The node schema the engine reads, as JSON text.
#[pyfunction]
fn node_schema() -> &'static str {
    lfx_ops::flow::model::FLOW_MODEL_JSON
}

/// The native part of `lfx_native`.
#[pymodule]
mod _native {
    #[pymodule_export]
    use super::{
        EngineError, GraphPlain, GraphSnapshot, GraphState, append_table_rows, apply,
        apply_restore_fixes, assign_changed_node_table_row_ids, assign_changed_table_row_ids,
        assign_row_ids, assign_table_row_ids, canonical_json, edge_fixes, fixes_for_edges,
        graph_hash, graphs_equal, new_edge_id, new_table_row_id, node_schema, ops_diff,
        ordered_rows, repair, replay, strip_flow_table_row_keys, strip_row_keys, table_fields,
        text_sha256, validate, values_equal,
    };
}
