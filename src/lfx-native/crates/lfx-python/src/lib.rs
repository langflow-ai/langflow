//! The Python binding of lfx: the `lfx_native` package.
//!
//! Every function takes Python values and returns Python values. An argument
//! that is `bytes` is UTF-8 JSON text, which the engine parses; any other
//! argument is read as the JSON value it is: `dict`, `list`, `tuple`, `str`,
//! `int`, `float`, `bool` or `None`. A `str` is a JSON string, never text to
//! parse, so a string value cannot be mistaken for a graph.
//! Reading Python objects is about four times cheaper than `json.dumps` and a
//! parse, and building them about three times cheaper than writing JSON and
//! `json.loads`.
//!
//! An engine error is raised as [`EngineError`], which carries the error's
//! `kind` (the matching Python exception class of
//! `lfx.services.flow_operations` or `langflow.services.flow_history`), its
//! `code`, and `details`: the whole error as a dict. The binding holds no
//! rules: each function calls `lfx::ops::api`.
//!
//! Engine work runs without the GIL only when it is large ([`Work`]): a
//! thread that gives the GIL back must wait for it again, and while another
//! thread runs Python code, that wait is one switch interval (5 ms by
//! default). A field write is much shorter than that, so small calls keep
//! the GIL.

use std::collections::HashMap;
use std::sync::mpsc::{SyncSender, TrySendError, sync_channel};
use std::sync::{LazyLock, PoisonError, RwLock, RwLockWriteGuard, TryLockError};

use lfx::ops::api::{self, ApiError, ApiResult, Input};
use lfx::ops::{
    Applied, ApplyOptions, Change, Entry, Error, FieldUpdate, Operation, ReplayOptions, Segment,
};
use lfx::value::{AnyMap, AnyValue, Number, StringPool};
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
    Ok(Input::Value(read(object, 0, &mut StringPool::default())?))
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
fn read(object: &Bound<'_, PyAny>, depth: usize, strings: &mut StringPool) -> PyResult<AnyValue> {
    if let Ok(string) = object.cast::<PyString>() {
        return Ok(AnyValue::String(strings.intern(text_of(string)?)));
    }
    if let Ok(dict) = object.cast::<PyDict>() {
        nested(object, depth)?;
        let mut map = AnyMap::with_capacity(dict.len());
        for (key, item) in dict.iter() {
            let key = key
                .cast::<PyString>()
                .map_err(|_| PyTypeError::new_err("a JSON object's keys must be str"))?;
            let key = strings.intern(text_of(key)?);
            map.insert_shared(key, read(&item, depth + 1, strings)?);
        }
        return Ok(AnyValue::Object(map));
    }
    if let Ok(list) = object.cast::<PyList>() {
        nested(object, depth)?;
        return list
            .iter()
            .map(|item| read(&item, depth + 1, strings))
            .collect::<PyResult<_>>()
            .map(AnyValue::Array);
    }
    if object.is_none() {
        return Ok(AnyValue::Null);
    }
    // `bool` is a subclass of `int`, so it is read first.
    if let Ok(flag) = object.cast::<PyBool>() {
        return Ok(AnyValue::Bool(flag.is_true()));
    }
    if object.cast::<PyInt>().is_ok() {
        if let Ok(int) = object.extract::<i64>() {
            return Ok(AnyValue::Number(int.into()));
        }
        // An int too large for 64 bits keeps its digits, as JSON text does.
        let digits = object.str()?;
        return digits
            .to_str()?
            .parse::<Number>()
            .map(AnyValue::Number)
            .map_err(|error| PyValueError::new_err(error.to_string()));
    }
    if let Ok(float) = object.cast::<PyFloat>() {
        return Number::from_f64(float.value())
            .map(AnyValue::Number)
            .ok_or_else(|| not_json(object, "NaN and Infinity are not JSON numbers"));
    }
    if let Ok(tuple) = object.cast::<PyTuple>() {
        nested(object, depth)?;
        return tuple
            .iter()
            .map(|item| read(&item, depth + 1, strings))
            .collect::<PyResult<_>>()
            .map(AnyValue::Array);
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
fn to_python<'py>(py: Python<'py>, value: &AnyValue) -> PyResult<Bound<'py, PyAny>> {
    Builder::new(py).value(value)
}

/// Builds Python objects from JSON values, for one result.
///
/// Each distinct dict key becomes one Python `str`, which every dict with
/// that key shares, as `json.loads` does: a flow repeats the same few keys
/// thousands of times. A shared key is a new reference, not a new object, so
/// it is not allocated, copied or hashed again, and the result takes less
/// memory. A `str` cannot change, so sharing it is safe.
struct Builder<'py, 'v> {
    py: Python<'py>,
    keys: HashMap<&'v str, Bound<'py, PyString>>,
    /// Values visited while building the result, capped at the GIL threshold.
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

    fn value(&mut self, value: &'v AnyValue) -> PyResult<Bound<'py, PyAny>> {
        self.work.0 = (self.work.0 + 1).min(HELD_VALUES);
        let py = self.py;
        Ok(match value {
            AnyValue::Null => py.None().into_bound(py),
            AnyValue::Bool(flag) => PyBool::new(py, *flag).to_owned().into_any(),
            AnyValue::Number(number) => number_to_python(py, number)?,
            AnyValue::String(text) => PyString::new(py, text).into_any(),
            AnyValue::Array(items) => self.list(items.iter())?.into_any(),
            AnyValue::Object(map) => self.dict(map)?.into_any(),
        })
    }

    fn list(&mut self, items: impl Iterator<Item = &'v AnyValue>) -> PyResult<Bound<'py, PyList>> {
        let list = PyList::empty(self.py);
        for item in items {
            list.append(self.value(item)?)?;
        }
        Ok(list)
    }

    fn dict(&mut self, map: &'v AnyMap) -> PyResult<Bound<'py, PyDict>> {
        let dict = PyDict::new(self.py);
        for (key, item) in map {
            let key = self.key(key);
            dict.set_item(key, self.value(item)?)?;
        }
        Ok(dict)
    }

    /// Count the same JSON values that the generic value builder visits.
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

    /// The Python `str` for a key: made the first time, shared after.
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

// --- Work and the GIL -----------------------------------------------------------------------

/// How much engine work a call holds the GIL for, in JSON values.
///
/// A call gives the GIL back only for work larger than this: while it runs
/// without the GIL, other Python threads run, but it must then wait for the
/// GIL again, and while another thread runs Python code that wait is one
/// switch interval (5 ms by default). Work below this is short next to that
/// interval, so a call that keeps the GIL never stops other threads for
/// longer than a Python thread does.
const HELD_VALUES: usize = 8192;

/// JSON text counts as one value per this many bytes, fewer than stored
/// operations or flows take per value. So text counts as larger than its
/// values, never smaller: text of 128 KB or more is parsed without the GIL.
const TEXT_BYTES_PER_VALUE: usize = 16;

/// A node or an edge of a loaded graph counts as this many values, about
/// what a typical node holds. Counting nodes and edges costs nothing, where
/// counting values would walk the graph.
const VALUES_PER_GRAPH_ITEM: usize = 200;

/// How large a piece of engine work is, in JSON values, up to [`HELD_VALUES`].
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord)]
struct Work(usize);

impl Work {
    /// The work on a value: its number of values, counted up to the limit.
    fn of_value(value: &AnyValue) -> Self {
        let mut count = 0;
        let mut stack = vec![value];
        while let Some(value) = stack.pop() {
            count += 1;
            if count >= HELD_VALUES {
                break;
            }
            match value {
                AnyValue::Array(items) => stack.extend(items),
                AnyValue::Object(map) => stack.extend(map.values()),
                _ => {}
            }
        }
        Self(count)
    }

    /// The work on an argument: text by its length, a value by its values.
    fn of_input(input: &Input<'_>) -> Self {
        match input {
            Input::Text(text) => Self(text.len() / TEXT_BYTES_PER_VALUE),
            Input::Value(value) => Self::of_value(value),
        }
    }

    fn of_inputs<'a, 't: 'a>(inputs: impl IntoIterator<Item = &'a Input<'t>>) -> Self {
        inputs
            .into_iter()
            .fold(Self::default(), |work, input| work + Self::of_input(input))
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

/// Run engine work: with the GIL when it is small, without it when it is large.
fn run<T: Send>(
    py: Python<'_>,
    work: Work,
    job: impl FnOnce() -> ApiResult<T> + Send,
) -> PyResult<T> {
    let result = if work.is_large() {
        py.detach(job)
    } else {
        job()
    };
    result.map_err(|error| engine_error(py, &error))
}

/// Run engine work as [`run`] does, and return its result as Python objects.
fn call(
    py: Python<'_>,
    work: Work,
    job: impl FnOnce() -> ApiResult + Send,
) -> PyResult<Bound<'_, PyAny>> {
    finish(py, run(py, work, job)?)
}

/// A result as Python objects. A large result is dropped without the GIL:
/// freeing a large graph takes time.
fn finish(py: Python<'_>, value: AnyValue) -> PyResult<Bound<'_, PyAny>> {
    let mut builder = Builder::new(py);
    let result = builder.value(&value);
    // Successful conversion already visited every value. A conversion error
    // can stop early, so keep the original bounded scan on that path.
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

/// Build operation results after the state lock has been released.
///
/// `options` says which operations become Python objects. With
/// `forward_json`, the forward operations also come back as JSON text,
/// one `bytes` each, under `forward_operations_json`.
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
        // Check the same operation objects, so unordered cascades cannot
        // change the reference result between two independent engine calls.
        let generic = AnyValue::Object(api::applied_json(applied.clone(), options));
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
                api::write_operation_json(&mut text, operation);
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
    if result.is_err() {
        // Preserve the generic builder's bounded scan when conversion stops early.
        let value = AnyValue::Object(api::applied_json(applied, options));
        if Work::of_value(&value).is_large() {
            py.detach(move || drop(value));
        }
    } else if work.is_large() {
        py.detach(move || drop(applied));
    }
    result
}

/// How many large graphs can wait for the drop thread. A graph dropped
/// while that many wait is dropped where it is.
const DROPS_WAITING: usize = 4;

/// Something that the drop thread frees.
type Dropped = Box<dyn Send>;

/// Drop a large graph on a thread of its own, so that the thread that lets
/// go of it, often a server's event loop, does not wait while it is freed:
/// freeing a large graph frees many small allocations. Without that thread,
/// or with [`DROPS_WAITING`] graphs waiting already, it is dropped here,
/// without the GIL.
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

// --- The engine -----------------------------------------------------------------------------

/// A flow graph that the engine keeps loaded, to apply or replay many
/// batches on it.
///
/// Replay, history playback and rebase carry out many batches on one graph
/// and read it once. A refused batch changes nothing.
///
/// A batch can be staged instead of applied: `stage` applies it with every
/// rule and returns what `apply` returns, but the graph as read stays the
/// graph before the batch until `keep` commits the batch or `drop` drops it,
/// as after a database commit that succeeds or fails. While a batch is
/// staged, `apply`, `replay` and `stage` raise `RuntimeError`.
///
/// Threads can share one state. A batch waits for the calls that read the
/// graph, and they wait for it, as with any lock. A call never waits for the
/// lock while it holds the GIL: it takes a free lock at once, and releases
/// the GIL to wait for a lock that another thread holds. It never waits for
/// the GIL while it holds the lock either. So two threads cannot deadlock.
/// Small work runs with the GIL ([`Work`]); large work, such as a long
/// replay, runs without it.
#[pyclass(module = "lfx_native", frozen)]
#[derive(Debug)]
struct GraphState {
    state: RwLock<lfx::ops::GraphState>,
}

/// A graph with no node and no edge: what a dropped graph leaves in its place.
fn empty_graph() -> AnyValue {
    let mut root = AnyMap::new();
    root.insert("nodes".into(), AnyValue::Array(Vec::new()));
    root.insert("edges".into(), AnyValue::Array(Vec::new()));
    AnyValue::Object(root)
}

/// A large graph is dropped on the drop thread ([`drop_elsewhere`]).
impl Drop for GraphState {
    fn drop(&mut self) {
        let state = self.state.get_mut().unwrap_or_else(PoisonError::into_inner);
        if !Work::of_items(state.item_count()).is_large() {
            return;
        }
        let empty = lfx::ops::GraphState::new(empty_graph()).expect("an empty graph loads");
        let state = std::mem::replace(state, empty);
        Python::attach(|py| drop_elsewhere(py, Box::new(state)));
    }
}

/// A call on the state panicked while it held the lock, so the graph may be
/// half changed.
struct Poisoned;

fn poisoned(_: Poisoned) -> PyErr {
    PyRuntimeError::new_err("this GraphState cannot be used: a call on it panicked")
}

/// Why a call on the state could not run.
#[derive(Debug, Clone, Copy)]
enum Refused {
    Poisoned,
    /// A batch is staged, so no other batch can start.
    Staged,
    /// No batch is staged, so there is nothing to keep.
    NotStaged,
}

impl From<Poisoned> for Refused {
    fn from(_: Poisoned) -> Self {
        Self::Poisoned
    }
}

fn refused(refused: Refused) -> PyErr {
    match refused {
        Refused::Poisoned => poisoned(Poisoned),
        Refused::Staged => {
            PyRuntimeError::new_err("a batch is staged: keep or drop it before the next batch")
        }
        Refused::NotStaged => PyRuntimeError::new_err("no batch is staged"),
    }
}

/// The state, locked for a batch, unless a batch is staged.
fn unstaged(
    state: RwLockWriteGuard<'_, lfx::ops::GraphState>,
) -> Result<RwLockWriteGuard<'_, lfx::ops::GraphState>, Refused> {
    if state.is_staged() {
        return Err(Refused::Staged);
    }
    Ok(state)
}

impl GraphState {
    /// Run `job` on the state locked for writing: with the GIL when the lock
    /// is free and `work` on the locked state is small, else without the GIL.
    fn write<T: Send>(
        &self,
        py: Python<'_>,
        work: impl FnOnce(&lfx::ops::GraphState) -> Work,
        job: impl FnOnce(RwLockWriteGuard<'_, lfx::ops::GraphState>) -> Result<T, Refused> + Send,
    ) -> Result<T, Refused> {
        match self.state.try_write() {
            Ok(state) if !work(&state).is_large() => return job(state),
            // The lock is released before the GIL.
            Ok(_) | Err(TryLockError::WouldBlock) => {}
            Err(TryLockError::Poisoned(_)) => return Err(Refused::Poisoned),
        }
        py.detach(|| job(self.state.write().map_err(|_| Poisoned)?))
    }

    /// Run `job` on the state locked for reading, as [`Self::write`] does.
    fn read<T: Send>(
        &self,
        py: Python<'_>,
        work: impl FnOnce(&lfx::ops::GraphState) -> Work,
        job: impl FnOnce(&lfx::ops::GraphState) -> T + Send,
    ) -> Result<T, Poisoned> {
        match self.state.try_read() {
            Ok(state) if !work(&state).is_large() => return Ok(job(&state)),
            Ok(_) | Err(TryLockError::WouldBlock) => {}
            Err(TryLockError::Poisoned(_)) => return Err(Poisoned),
        }
        py.detach(|| Ok(job(&*self.state.read().map_err(|_| Poisoned)?)))
    }
}

#[pymethods]
impl GraphState {
    #[new]
    fn new(py: Python<'_>, flow: &Bound<'_, PyAny>) -> PyResult<Self> {
        let flow = input(flow)?;
        let work = Work::of_input(&flow);
        Ok(Self {
            state: RwLock::new(run(py, work, || api::graph_state(flow))?),
        })
    }

    /// Apply a batch, with every rule; returns what it did.
    #[pyo3(signature = (operations, *, forward = false, backward = false, forward_json = false))]
    fn apply<'py>(
        &self,
        py: Python<'py>,
        operations: &Bound<'_, PyAny>,
        forward: bool,
        backward: bool,
        forward_json: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let operations = input(operations)?;
        let work = Work::of_input(&operations);
        let options = ApplyOptions {
            forward: forward || forward_json,
            backward,
        };
        let applied = self
            .write(
                py,
                |_| work,
                |state| {
                    Ok(api::apply_to_typed(
                        &mut *unstaged(state)?,
                        operations,
                        options,
                    ))
                },
            )
            .map_err(refused)?;
        finish_applied(
            py,
            applied.map_err(|error| engine_error(py, &error))?,
            ApplyOptions { forward, backward },
            forward_json,
        )
    }

    /// Apply a batch with every rule, as `apply` does, and keep it staged
    /// until `keep` or `drop`; returns what `apply` returns. A refused batch
    /// is not staged.
    #[pyo3(signature = (operations, *, forward = false, backward = false, forward_json = false))]
    fn stage<'py>(
        &self,
        py: Python<'py>,
        operations: &Bound<'_, PyAny>,
        forward: bool,
        backward: bool,
        forward_json: bool,
    ) -> PyResult<Bound<'py, PyAny>> {
        let operations = input(operations)?;
        let work = Work::of_input(&operations);
        let options = ApplyOptions {
            forward: forward || forward_json,
            backward,
        };
        let staged = self
            .write(
                py,
                |_| work,
                |state| {
                    Ok(api::stage_to_typed(
                        &mut *unstaged(state)?,
                        operations,
                        options,
                    ))
                },
            )
            .map_err(refused)?;
        finish_applied(
            py,
            staged.map_err(|error| engine_error(py, &error))?,
            ApplyOptions { forward, backward },
            forward_json,
        )
    }

    /// Commit the staged batch. Raises `RuntimeError` when no batch is staged.
    fn keep(&self, py: Python<'_>) -> PyResult<()> {
        self.write(
            py,
            |_| Work::default(),
            |mut state| {
                if state.keep() {
                    Ok(())
                } else {
                    Err(Refused::NotStaged)
                }
            },
        )
        .map_err(refused)
    }

    /// Drop the staged batch, so the graph stays as it was before it.
    /// Returns whether a batch was staged.
    fn drop(&self, py: Python<'_>) -> PyResult<bool> {
        self.write(py, |_| Work::default(), |mut state| Ok(state.drop_staged()))
            .map_err(refused)
    }

    /// Whether a batch is staged.
    #[getter]
    fn staged(&self, py: Python<'_>) -> PyResult<bool> {
        self.read(py, |_| Work::default(), lfx::ops::GraphState::is_staged)
            .map_err(poisoned)
    }

    /// Replay stored operations, with no rule; returns what it did.
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
                |state| Ok(api::replay_to(&mut *unstaged(state)?, operations, options)),
            )
            .map_err(refused)?;
        finish(py, replayed.map_err(|error| engine_error(py, &error))?)
    }

    /// The graph as JSON text: the committed graph, without a staged batch.
    /// With `staged`, the graph with the staged batch, as `keep` will make
    /// it: a server writes it in the transaction that records the batch.
    /// Raises `RuntimeError` when `staged` is true and no batch is staged.
    #[pyo3(signature = (*, staged = false))]
    fn to_json(&self, py: Python<'_>, staged: bool) -> PyResult<String> {
        let work = |state: &lfx::ops::GraphState| Work::of_items(state.item_count());
        if !staged {
            return self.read(py, work, api::graph_json).map_err(poisoned);
        }
        self.read(py, work, api::staged_graph_json)
            .map_err(poisoned)?
            .ok_or_else(|| refused(Refused::NotStaged))
    }

    /// The SHA-256 hex digest of the graph's canonical form, as
    /// `GraphPlain.graph_hash` gives for the graph's JSON text, without
    /// writing or reading the text. With `staged`, the graph with the staged
    /// batch, as `keep` will make it; raises `RuntimeError` when no batch is
    /// staged.
    #[pyo3(signature = (*, staged = false))]
    fn graph_hash(&self, py: Python<'_>, staged: bool) -> PyResult<String> {
        let work = |state: &lfx::ops::GraphState| Work::of_items(state.item_count());
        let hashed = if staged {
            self.read(py, work, api::staged_state_graph_hash)
                .map_err(poisoned)?
                .map_err(|error| engine_error(py, &error))?
                .ok_or_else(|| refused(Refused::NotStaged))?
        } else {
            self.read(py, work, api::state_graph_hash)
                .map_err(poisoned)?
                .map_err(|error| engine_error(py, &error))?
        };
        Ok(hashed)
    }

    /// The committed graph as it is now, without a staged batch, as a
    /// read-only `GraphSnapshot`. It shares every node and edge with the
    /// state, so it costs a pointer for each; a later batch copies only the
    /// nodes it changes. Another thread can write and hash the snapshot while
    /// batches go on.
    fn snapshot(&self, py: Python<'_>) -> PyResult<GraphSnapshot> {
        let cached = self
            .read(py, |_| Work::default(), lfx::ops::GraphState::try_snapshot)
            .map_err(poisoned)?;
        let snapshot = if let Some(snapshot) = cached {
            snapshot
        } else {
            // Neither the state lock nor the capture mutex is held while the
            // GIL is released to wait for another native capture.
            py.detach(|| {
                let state = self.state.read().map_err(|_| Poisoned)?;
                Ok(state.snapshot())
            })
            .map_err(poisoned)?
        };
        Ok(GraphSnapshot::wrap(snapshot))
    }

    /// The graph as a dict, built from the loaded graph without a copy: the
    /// committed graph, without a staged batch.
    fn to_dict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        // Building Python objects needs the GIL and the lock together:
        // read_py_attached waits for the lock without the GIL.
        let state = self
            .state
            .read_py_attached(py)
            .map_err(|_| poisoned(Poisoned))?;
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

/// A graph as a `GraphState` held it when `GraphState.snapshot()` took it:
/// read only, and unchanged by the state's later batches. Threads can share
/// it; its large calls run without the GIL.
#[pyclass(module = "lfx_native", frozen)]
#[derive(Debug)]
struct GraphSnapshot {
    snapshot: Option<lfx::ops::GraphSnapshot>,
    /// The work on the whole graph.
    work: Work,
}

impl GraphSnapshot {
    fn wrap(snapshot: lfx::ops::GraphSnapshot) -> Self {
        let work = Work::of_items(snapshot.item_count());
        Self {
            snapshot: Some(snapshot),
            work,
        }
    }
}

/// A large snapshot is dropped on the drop thread ([`drop_elsewhere`]): it
/// may hold the only copy of nodes that the state has changed since.
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
    /// The graph as JSON text: what the state's `to_json()` gave when the snapshot was taken.
    fn to_json(&self, py: Python<'_>) -> String {
        let snapshot = self
            .snapshot
            .as_ref()
            .expect("a live snapshot holds its graph");
        let write = || api::snapshot_json(snapshot);
        if self.work.is_large() {
            py.detach(write)
        } else {
            write()
        }
    }

    /// The SHA-256 hex digest of the graph's canonical form: what the
    /// state's `graph_hash()` gave when the snapshot was taken.
    fn graph_hash(&self, py: Python<'_>) -> PyResult<String> {
        let snapshot = self
            .snapshot
            .as_ref()
            .expect("a live snapshot holds its graph");
        run(py, self.work, || api::snapshot_graph_hash(snapshot))
    }
}

/// A flow graph read once, to run many checks on it: validate, repair, hash,
/// compare and diff, without reading the graph again for each call.
///
/// Nothing is checked when it is made, and a check that passes is not run
/// again. The graph cannot change, so threads can share it.
#[pyclass(module = "lfx_native", frozen)]
#[derive(Debug)]
struct GraphPlain {
    plain: Option<lfx::ops::GraphPlain>,
    /// The work on the whole graph, counted once.
    work: Work,
}

impl GraphPlain {
    fn wrap(plain: lfx::ops::GraphPlain) -> Self {
        let work = Work::of_value(plain.as_value());
        Self {
            plain: Some(plain),
            work,
        }
    }

    fn core(&self) -> &lfx::ops::GraphPlain {
        self.plain
            .as_ref()
            .expect("a live plain graph holds its value")
    }
}

/// A large graph is dropped on the drop thread ([`drop_elsewhere`]).
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
            AnyValue::Object(map) => {
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

fn plain<'a>(
    object: Option<&'a Bound<'_, GraphPlain>>,
) -> (Option<&'a lfx::ops::GraphPlain>, Work) {
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
        Ok(Self::wrap(run(py, work, || api::graph_plain(flow))?))
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
            api::plain_validate(self.core(), base, check_values)
        })
    }

    /// Repair what has one fix; returns the repaired graph and the fixes.
    #[pyo3(signature = (base = None))]
    fn repair<'py>(
        &self,
        py: Python<'py>,
        base: Option<&Bound<'_, GraphPlain>>,
    ) -> PyResult<(Bound<'py, GraphPlain>, Bound<'py, PyAny>)> {
        let (base, base_work) = plain(base);
        let (repaired, fixes) = run(py, self.work + base_work, || {
            api::plain_repair(self.core(), base)
        })?;
        // No fixes means the repaired graph is the same graph, so its size
        // classification is already known. Do not walk it again on a cache hit.
        let work = if fixes.as_array().is_some_and(Vec::is_empty) {
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
        run(py, self.work, || api::plain_graph_hash(self.core()))
    }

    /// Whether the two graphs are the same graph.
    fn equals(&self, py: Python<'_>, other: &Bound<'_, GraphPlain>) -> PyResult<bool> {
        let other = other.get();
        run(py, self.work + other.work, || {
            api::plain_equals(self.core(), other.core())
        })
    }

    /// The operations that turn this graph into `target`, checked by replay.
    fn ops_diff<'py>(
        &self,
        py: Python<'py>,
        target: &Bound<'_, GraphPlain>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let target = target.get();
        call(py, self.work + target.work, || {
            api::plain_ops_diff(self.core(), target.core())
        })
    }

    /// The graph as JSON text.
    fn to_json(&self, py: Python<'_>) -> String {
        let write = || api::json_text(self.core().as_value());
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

/// Apply operations to a graph, with every rule; returns `{"flow_data", ...}`.
#[pyfunction]
#[pyo3(signature = (flow, operations, *, forward = true, backward = false))]
fn apply<'py>(
    py: Python<'py>,
    flow: &Bound<'_, PyAny>,
    operations: &Bound<'_, PyAny>,
    forward: bool,
    backward: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let (flow, operations) = (input(flow)?, input(operations)?);
    let options = ApplyOptions { forward, backward };
    let work = Work::of_inputs([&flow, &operations]);
    call(py, work, || api::apply(flow, operations, options))
}

/// Replay stored operations on a graph, with no rule; returns `{"flow_data", ...}`.
#[pyfunction]
#[pyo3(signature = (flow, operations, *, backward = false))]
fn replay<'py>(
    py: Python<'py>,
    flow: &Bound<'_, PyAny>,
    operations: &Bound<'_, PyAny>,
    backward: bool,
) -> PyResult<Bound<'py, PyAny>> {
    let (flow, operations) = (input(flow)?, input(operations)?);
    let options = ReplayOptions { backward };
    let work = Work::of_inputs([&flow, &operations]);
    call(py, work, || api::replay(flow, operations, options))
}

/// The operations that turn `base` into `target`, checked by replay.
#[pyfunction]
fn ops_diff<'py>(
    py: Python<'py>,
    base: &Bound<'_, PyAny>,
    target: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let (base, target) = (input(base)?, input(target)?);
    let work = Work::of_inputs([&base, &target]);
    call(py, work, || api::ops_diff(base, target))
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
    let work = Work::of_inputs([&flow].into_iter().chain(base.as_ref()));
    call(py, work, || api::validate(flow, base, check_values))
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
    let work = Work::of_inputs([&flow].into_iter().chain(base.as_ref()));
    call(py, work, || api::repair(flow, base))
}

/// The SHA-256 hex digest of a graph's canonical form.
/// The SHA-256 hex digest of `text`, a `str` (as UTF-8) or `bytes`: what
/// `hashlib.sha256(text.encode()).hexdigest()` gives, without the copy that
/// `encode` makes while it holds the GIL. The UTF-8 bytes of an ASCII `str`,
/// as JSON text is, are its own buffer. Large text is hashed without the GIL.
#[pyfunction]
fn text_sha256(py: Python<'_>, text: &Bound<'_, PyAny>) -> PyResult<String> {
    let bytes = if let Ok(string) = text.cast::<PyString>() {
        text_of(string)?.as_bytes()
    } else if let Ok(bytes) = text.cast::<PyBytes>() {
        bytes.as_bytes()
    } else {
        return Err(PyTypeError::new_err("text must be str or bytes"));
    };
    let hash = || api::text_sha256(bytes);
    Ok(if Work(bytes.len() / TEXT_BYTES_PER_VALUE).is_large() {
        py.detach(hash)
    } else {
        hash()
    })
}

#[pyfunction]
fn graph_hash(py: Python<'_>, flow: &Bound<'_, PyAny>) -> PyResult<String> {
    let flow = input(flow)?;
    let work = Work::of_inputs([&flow]);
    run(py, work, || api::graph_hash(flow))
}

/// Whether two graphs are the same graph.
#[pyfunction]
fn graphs_equal(
    py: Python<'_>,
    left: &Bound<'_, PyAny>,
    right: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let (left, right) = (input(left)?, input(right)?);
    let work = Work::of_inputs([&left, &right]);
    run(py, work, || api::graphs_equal(left, right))
}

/// Whether two JSON values are the same value.
#[pyfunction]
fn values_equal(
    py: Python<'_>,
    left: &Bound<'_, PyAny>,
    right: &Bound<'_, PyAny>,
) -> PyResult<bool> {
    let (left, right) = (input(left)?, input(right)?);
    let work = Work::of_inputs([&left, &right]);
    run(py, work, || api::values_equal(left, right))
}

/// A JSON value in RFC 8785 canonical form, as text.
#[pyfunction]
fn canonical_json(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<String> {
    let value = input(value)?;
    let work = Work::of_inputs([&value]);
    run(py, work, || api::canonical_json(value))
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
    let work = Work::of_inputs([&revision, &stored, &fixes]);
    call(py, work, || {
        api::apply_restore_fixes(revision, stored, fixes)
    })
}

/// The fixes that turn a revision's edges as read into the edges its preview shows.
#[pyfunction]
fn edge_fixes<'py>(
    py: Python<'py>,
    read: &Bound<'_, PyAny>,
    shown: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let (read, shown) = (input(read)?, input(shown)?);
    let work = Work::of_inputs([&read, &shown]);
    call(py, work, || api::edge_fixes(read, shown))
}

/// The part of the fixes that touches the given edges.
#[pyfunction]
fn fixes_for_edges<'py>(
    py: Python<'py>,
    fixes: &Bound<'_, PyAny>,
    edge_ids: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let (fixes, edge_ids) = (input(fixes)?, input(edge_ids)?);
    let work = Work::of_inputs([&fixes, &edge_ids]);
    call(py, work, || api::fixes_for_edges(fixes, edge_ids))
}

/// Rows in order and without `__id__` and `__pos__`.
#[pyfunction]
fn strip_row_keys<'py>(py: Python<'py>, rows: &Bound<'_, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let rows = input(rows)?;
    let work = Work::of_inputs([&rows]);
    call(py, work, || api::strip_row_keys(rows))
}

/// Rows in order, by `(__pos__, __id__)`, or as stored for a legacy table.
#[pyfunction]
fn ordered_rows<'py>(py: Python<'py>, rows: &Bound<'_, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let rows = input(rows)?;
    let work = Work::of_inputs([&rows]);
    call(py, work, || api::ordered_rows(rows))
}

/// A flow whose top-level tables have their rows in order and without `__id__` and `__pos__`.
#[pyfunction]
fn strip_flow_table_row_keys<'py>(
    py: Python<'py>,
    flow: &Bound<'_, PyAny>,
) -> PyResult<Bound<'py, PyAny>> {
    let flow = input(flow)?;
    let work = Work::of_inputs([&flow]);
    call(py, work, || api::strip_flow_table_row_keys(flow))
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
    let work = Work::of_inputs([&rows].into_iter().chain(previous.as_ref()));
    call(py, work, || api::assign_row_ids(rows, previous, editor))
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
    let work = Work::of_inputs([&node]);
    call(py, work, || api::assign_table_row_ids(node, editor))
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
    let work = Work::of_inputs([&base, &target]);
    call(py, work, || {
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
    let work = Work::of_inputs([&node].into_iter().chain(previous.as_ref()));
    call(py, work, || {
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
    let work = Work::of_inputs([&rows, &new_rows]);
    call(py, work, || api::append_table_rows(rows, new_rows))
}

/// The names of a node's template fields whose value is a table.
#[pyfunction]
fn table_fields<'py>(py: Python<'py>, node: &Bound<'_, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    let node = input(node)?;
    let work = Work::of_inputs([&node]);
    call(py, work, || api::table_fields(node))
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
        EngineError, GraphPlain, GraphSnapshot, GraphState, append_table_rows, apply,
        apply_restore_fixes, assign_changed_node_table_row_ids, assign_changed_table_row_ids,
        assign_row_ids, assign_table_row_ids, canonical_json, edge_fixes, fixes_for_edges,
        graph_hash, graphs_equal, new_edge_id, new_table_row_id, node_schema, ops_diff,
        ordered_rows, repair, replay, strip_flow_table_row_keys, strip_row_keys, table_fields,
        text_sha256, validate, values_equal,
    };
}
