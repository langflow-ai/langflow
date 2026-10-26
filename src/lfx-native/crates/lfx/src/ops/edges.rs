//! The rules an edge follows when a write adds it or changes its handles.
//!
//! An edge connects one output of its source node to one input of its target
//! node, and its handles name them: `sourceHandle.name` is an output of the
//! source, and `targetHandle.fieldName` is a template field of the target. A
//! loop feedback edge instead names an output of its target, with
//! `targetHandle.name`, and that output must declare `allows_loop`.
//!
//! Every edge carries each handle twice: as an object under `data`, and as an
//! escaped JSON string (`œ` stands for `"`). Both forms must be present and
//! agree. Nothing is exempt: group nodes are checked like any node, and an
//! edge may not touch a note, which has no handles.
//!
//! An edge never changes in place: a write deletes it and adds it again. The
//! rules apply only to the edges a write adds. A stored edge that breaks them
//! stays until something touches it; but an edge whose handles a rule must
//! read, to see whether a field is taken or which edges a removed output
//! carries, is read strictly too.
//!
//! An edge needs both of its ends. A node's endpoints are the keys of its
//! template, which edges enter, and the items of its outputs list, which
//! edges leave and loop feedback edges enter. When an endpoint goes, its
//! edges go with it (a cascade delete): a deleted node takes every edge at
//! it, and a write that removes an endpoint, directly or by replacing what
//! holds it, takes the endpoint's edges (`removed_endpoints`).

use std::borrow::Cow;
use std::collections::HashMap;
use std::fmt;
use std::sync::LazyLock;

use indexmap::IndexSet;
use serde_json::{Map, Value};

use crate::ops::canonical::{HANDLE_KEYS, HANDLE_QUOTE, parse_handle, values_equal};
use crate::ops::entry::EntryExt;
use crate::ops::error::{Error, Result, bail, invalid, quoted};
use crate::ops::keyed::ListIndex;
use crate::ops::ops::{PathExt, Segment};
use crate::ops::schema::{KeyedList, NODE_SCHEMA, OUTPUTS_PATH, TEMPLATE_PATH};
use crate::ops::state::Layered;
use crate::ops::validate::ViolationCode;

/// The type of a note node.
pub const NOTE_NODE_TYPE: &str = "noteNode";

static OUTPUTS_LIST: LazyLock<&'static KeyedList> = LazyLock::new(|| {
    NODE_SCHEMA
        .keyed_list_at(&Value::Null, &OUTPUTS_PATH)
        .expect("node_schema.json declares the outputs list")
});

/// The keyed list of a node's outputs.
pub(crate) fn outputs_list() -> &'static KeyedList {
    &OUTPUTS_LIST
}

/// Whether an edge enters a template field or a loop output.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum InputKind {
    /// A template field, named by `targetHandle.fieldName`.
    Field,
    /// A loop output, named by `targetHandle.name`.
    LoopOutput,
}

/// The input an edge enters at its target.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Input {
    /// A field or a loop output.
    pub kind: InputKind,
    /// The field's or output's name.
    pub name: String,
}

impl Input {
    fn field(name: &str) -> Self {
        Self {
            kind: InputKind::Field,
            name: name.to_owned(),
        }
    }

    fn loop_output(name: &str) -> Self {
        Self {
            kind: InputKind::LoopOutput,
            name: name.to_owned(),
        }
    }
}

/// The output an edge leaves from and the input it enters.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Handles {
    /// The source output's name.
    pub output: String,
    /// The target input.
    pub input: Input,
}

/// A node's edges, by the input they enter and the output they leave from.
#[derive(Debug, Clone, Default)]
pub struct Connections {
    /// Edges into each input of the node.
    pub inputs: HashMap<Input, IndexSet<String>>,
    /// Edges out of each output of the node.
    pub outputs: HashMap<String, IndexSet<String>>,
}

impl Connections {
    /// The ids of the edges at `endpoint`: into a field, or out of an output
    /// and, for a loop output, into it.
    pub(crate) fn at(&self, endpoint: &Endpoint) -> impl Iterator<Item = &String> {
        let (input, output) = match endpoint {
            Endpoint::Field(name) => (Input::field(name), None),
            Endpoint::Output(name) => (Input::loop_output(name), self.outputs.get(name)),
        };
        self.inputs.get(&input).into_iter().chain(output).flatten()
    }
}

/// A place on a node that edges attach to.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum Endpoint {
    /// A template field, which edges enter.
    Field(String),
    /// An output, which edges leave and loop feedback edges enter.
    Output(String),
}

/// Where a node keeps one kind of endpoint.
#[derive(Debug)]
struct Holder {
    /// The path of the holder in a node.
    path: &'static [&'static str],
    /// Whether the holder is a keyed list, whose items a path names with
    /// `{"key": ...}`, rather than an object, whose keys a path names.
    keyed: bool,
    /// The endpoint an entry of the holder is.
    endpoint: fn(String) -> Endpoint,
}

/// The template holds a node's fields, and the outputs list its outputs.
const HOLDERS: [Holder; 2] = [
    Holder {
        path: &TEMPLATE_PATH,
        keyed: false,
        endpoint: Endpoint::Field,
    },
    Holder {
        path: &OUTPUTS_PATH,
        keyed: true,
        endpoint: Endpoint::Output,
    },
];

/// Whether [`removed_endpoints`] reads what a write at `path` replaced: the
/// write is at a holder's path or at an ancestor (anc.) path of it.
pub(crate) fn reads_before(path: &[Segment]) -> bool {
    HOLDERS
        .iter()
        .any(|holder| path.len() <= holder.path.len() && path.shares_start(holder.path))
}

/// The endpoints that a write at `path` of node `node_id` removed.
///
/// `before` is what the path held before the write, which only a write that
/// [`reads_before`] needs, and `after(keys)` is the value at the object keys
/// `keys` of the node after it. A delete of one template key or one output removes that
/// endpoint. A write that replaces or deletes the outputs list, or anything
/// holding a template or an outputs list, removes the endpoints it held that
/// the node no longer has. Any other write removes none.
///
/// # Errors
///
/// An outputs list, before or after the write, breaks the keyed-list rules.
pub(crate) fn removed_endpoints<'a>(
    path: &[Segment],
    is_delete: bool,
    before: Option<&Value>,
    after: impl Fn(&[&str]) -> Option<Cow<'a, Value>>,
    node_id: &str,
) -> Result<Vec<Endpoint>> {
    let mut removed = Vec::new();
    for holder in &HOLDERS {
        if path.len() == holder.path.len() + 1 && path.has_start(holder.path) {
            if !is_delete {
                continue;
            }
            let name = match &path[holder.path.len()] {
                Segment::Item(key) if holder.keyed => key,
                Segment::Key(key) if !holder.keyed => key,
                _ => continue,
            };
            removed.push((holder.endpoint)(name.clone()));
        } else if path.len() <= holder.path.len() && path.shares_start(holder.path) {
            let before = before.expect("a write that reads before passes what it replaced");
            let held = holder.names(at_keys(before, &holder.path[path.len()..]), node_id)?;
            let kept = holder.names(after(holder.path).as_deref(), node_id)?;
            removed.extend(
                held.into_iter()
                    .filter(|name| !kept.contains(name))
                    .map(holder.endpoint),
            );
        }
    }
    Ok(removed)
}

impl Holder {
    /// The names of the endpoints in `held`, a value of this holder: the
    /// names of an outputs list, or the keys of a template.
    fn names(&self, held: Option<&Value>, node_id: &str) -> Result<Vec<String>> {
        let Some(held) = held else {
            return Ok(Vec::new());
        };
        if self.keyed {
            return Ok(index_outputs(Cow::Borrowed(held), node_id)?
                .names()
                .map(str::to_owned)
                .collect());
        }
        Ok(held
            .as_object()
            .map(|object| object.keys().cloned().collect())
            .unwrap_or_default())
    }
}

/// The value at the object keys `keys` under `value`.
fn at_keys<'v>(value: &'v Value, keys: &[&str]) -> Option<&'v Value> {
    keys.iter().try_fold(value, |value, key| value.get(key))
}

/// Read access to an indexed graph, enough to check edges.
pub(crate) trait GraphRead {
    /// Whether the graph has a node with `id`.
    fn has_node(&self, id: &str) -> bool;
    /// The value at the object keys `path` of the node `id`, as the reader
    /// sees it. The graph state reads through its batch's field writes, and
    /// copies a value only when the batch wrote inside it.
    fn node_value(&self, id: &str, path: &[&str]) -> Option<Cow<'_, Value>>;
    /// The edge with `id`.
    fn edge(&self, id: &str) -> Option<&Map<String, Value>>;
    /// The ids of the edges at a node.
    fn edge_ids_at(&self, node_id: &str) -> impl Iterator<Item = &str>;
}

/// The source or target of an edge that passed structural validation.
pub(crate) fn endpoint<'e>(edge: &'e Map<String, Value>, end: &str) -> &'e str {
    edge.get(end).and_then(Value::as_str).unwrap_or_default()
}

/// What is indexed so far about edges: each edge's handles, and each node's
/// connections. Both are built the first time something asks for them, and
/// a batch changes them through its layer, as it changes the graph.
#[derive(Debug)]
pub(crate) struct EdgeIndex {
    handles: Layered<Handles>,
    connections: Layered<Connections>,
}

impl Default for EdgeIndex {
    fn default() -> Self {
        Self {
            handles: Layered::new(),
            connections: Layered::new(),
        }
    }
}

impl EdgeIndex {
    /// An edge's handles, read strictly the first time.
    pub fn handles(&mut self, edge: &Map<String, Value>) -> Result<Handles> {
        let id = edge.id();
        if let Some(handles) = self.handles.get(id) {
            return Ok(handles.clone());
        }
        let handles = read_handles(edge)?;
        self.handles.insert(id.to_owned(), handles.clone());
        Ok(handles)
    }

    /// A node's connections, reading the handles of its edges the first time.
    pub fn connections(&mut self, graph: &impl GraphRead, node_id: &str) -> Result<&Connections> {
        if !self.connections.contains(node_id) {
            let mut connections = Connections::default();
            for id in graph.edge_ids_at(node_id) {
                let edge = graph
                    .edge(id)
                    .ok_or_else(|| invalid!("edge {} does not exist", quoted(id)))?;
                let handles = self.handles(edge)?;
                connect(&mut connections, node_id, edge, &handles);
            }
            self.connections.insert(node_id.to_owned(), connections);
        }
        Ok(self
            .connections
            .get(node_id)
            .expect("the connections were just built"))
    }

    /// Index a new edge at the nodes whose connections are built.
    ///
    /// An edge whose handles do not read (which only a backward operation puts back)
    /// leaves those nodes to be indexed again when something asks.
    pub fn insert(&mut self, edge: &Map<String, Value>) {
        let ends = [endpoint(edge, "source"), endpoint(edge, "target")];
        if !ends.iter().any(|end| self.connections.contains(end)) {
            return;
        }
        match self.handles(edge) {
            Ok(handles) => {
                for end in ends {
                    if let Some(connections) = self.connections.get_mut(end) {
                        connect(connections, end, edge, &handles);
                    }
                }
            }
            Err(_) => {
                for end in ends {
                    self.connections.remove(end);
                }
            }
        }
    }

    /// Drop what is indexed about an edge, before it is removed or its handles are rewritten.
    pub fn forget(&mut self, edge: &Map<String, Value>) {
        let id = edge.id();
        let Some(handles) = self.handles.get(id).cloned() else {
            return;
        };
        self.handles.remove(id);
        for end in [endpoint(edge, "source"), endpoint(edge, "target")] {
            if let Some(connections) = self.connections.get_mut(end) {
                disconnect(connections, end, edge, &handles);
            }
        }
    }

    /// Whether a node's connections are built.
    #[cfg(test)]
    pub fn has_connections(&self, node_id: &str) -> bool {
        self.connections.contains(node_id)
    }

    /// Drop a node's connections.
    pub fn forget_node(&mut self, node_id: &str) {
        self.connections.remove(node_id);
    }

    /// Make a batch's changes part of the index.
    pub fn fold(&mut self) {
        self.handles.fold();
        self.connections.fold();
    }

    /// Drop a batch's changes.
    pub fn discard(&mut self) {
        self.handles.discard();
        self.connections.discard();
    }
}

fn connect(
    connections: &mut Connections,
    node_id: &str,
    edge: &Map<String, Value>,
    handles: &Handles,
) {
    let id = edge.id().to_owned();
    if endpoint(edge, "target") == node_id {
        connections
            .inputs
            .entry(handles.input.clone())
            .or_default()
            .insert(id.clone());
    }
    if endpoint(edge, "source") == node_id {
        connections
            .outputs
            .entry(handles.output.clone())
            .or_default()
            .insert(id);
    }
}

fn disconnect(
    connections: &mut Connections,
    node_id: &str,
    edge: &Map<String, Value>,
    handles: &Handles,
) {
    let id = edge.id();
    if endpoint(edge, "target") == node_id
        && let Some(ids) = connections.inputs.get_mut(&handles.input)
    {
        ids.swap_remove(id);
    }
    if endpoint(edge, "source") == node_id
        && let Some(ids) = connections.outputs.get_mut(&handles.output)
    {
        ids.swap_remove(id);
    }
}

fn error(edge: &Map<String, Value>, code: ViolationCode, reason: impl std::fmt::Display) -> Error {
    Error::edge(edge.id(), code, reason)
}

/// Read an edge's handles strictly: both forms present, the string parsing to the object.
///
/// # Errors
///
/// An edge rule the handles break, naming this edge.
pub fn read_handles(edge: &Map<String, Value>) -> Result<Handles> {
    let source = handle(edge, "sourceHandle")?;
    let target = handle(edge, "targetHandle")?;
    let output = match source.get("name") {
        Some(Value::String(name)) if !name.is_empty() => name.clone(),
        _ => {
            return Err(error(
                edge,
                ViolationCode::EdgeHandleInvalid,
                "sourceHandle must name an output",
            ));
        }
    };
    // A key that is present counts, whatever its value: a field handle with "name": null names both.
    let names_field = target.contains_key("fieldName");
    if names_field == target.contains_key("name") {
        return Err(error(
            edge,
            ViolationCode::EdgeHandleInvalid,
            "targetHandle must name exactly one of a field or an output",
        ));
    }
    let (kind, key) = if names_field {
        (InputKind::Field, "fieldName")
    } else {
        (InputKind::LoopOutput, "name")
    };
    match target.get(key) {
        Some(Value::String(name)) if !name.is_empty() => Ok(Handles {
            output,
            input: Input {
                kind,
                name: name.clone(),
            },
        }),
        _ => Err(error(
            edge,
            ViolationCode::EdgeHandleInvalid,
            "targetHandle must name its field or output as a string",
        )),
    }
}

fn handle<'e>(edge: &'e Map<String, Value>, key: &str) -> Result<&'e Map<String, Value>> {
    // A key that is present counts, whatever its value: "data": null is not an object.
    let data = match edge.get("data") {
        None => None,
        Some(Value::Object(data)) => Some(data),
        Some(_) => {
            return Err(error(
                edge,
                ViolationCode::EdgeHandleInvalid,
                "data must be an object",
            ));
        }
    };
    let object = data.and_then(|data| data.get(key));
    if let Some(object) = object
        && !object.is_object()
    {
        return Err(error(
            edge,
            ViolationCode::EdgeHandleInvalid,
            format!("data.{key} must be an object"),
        ));
    }
    if let Some(string) = edge.get(key) {
        let Some(parsed) = parse_handle(string) else {
            return Err(error(
                edge,
                ViolationCode::EdgeHandleInvalid,
                format!("{key} must be an escaped JSON object"),
            ));
        };
        if let Some(object) = object
            && !values_equal(&Value::Object(parsed), object)?
        {
            return Err(error(
                edge,
                ViolationCode::EdgeHandleInvalid,
                format!("{key} and data.{key} name different handles"),
            ));
        }
    }
    match (object.and_then(Value::as_object), edge.contains_key(key)) {
        (Some(object), true) => Ok(object),
        (Some(_), false) => Err(error(
            edge,
            ViolationCode::EdgeHandleFormMissing,
            format!("{key} is missing"),
        )),
        (None, true) => Err(error(
            edge,
            ViolationCode::EdgeHandleFormMissing,
            format!("data.{key} is missing"),
        )),
        (None, false) => Err(error(
            edge,
            ViolationCode::EdgeHandleInvalid,
            format!("edge has no {key}"),
        )),
    }
}

/// Whether an edge changed between two graphs. View state is not a change,
/// and neither is another spelling of the same handle. A changed edge is
/// deleted and added again, so the edge rules check it like a new one.
///
/// # Errors
///
/// A compared value holds a number that is not finite.
pub fn edge_changed(before: &Map<String, Value>, after: &Map<String, Value>) -> Result<bool> {
    let keys: IndexSet<&String> = before
        .keys()
        .chain(after.keys())
        .filter(|key| !NODE_SCHEMA.edge_view_state.contains(key.as_str()))
        .collect();
    for key in keys {
        let same = match (before.get(key), after.get(key)) {
            (Some(old), Some(new)) if HANDLE_KEYS.contains(&key.as_str()) => {
                values_equal(&handle_value(old), &handle_value(new))?
            }
            (Some(old), Some(new)) => values_equal(old, new)?,
            _ => false,
        };
        if !same {
            return Ok(true);
        }
    }
    Ok(false)
}

/// A handle string compares by the object it encodes.
fn handle_value(handle: &Value) -> Value {
    parse_handle(handle).map_or_else(|| handle.clone(), Value::Object)
}

/// A handle's string form: compact JSON with `œ` standing for `"`.
#[must_use]
pub fn escape_handle(handle: &Value) -> String {
    handle.to_string().replace('"', &HANDLE_QUOTE.to_string())
}

/// Write each handle's missing form from the one present, in place, as the editor spells them.
pub fn derive_missing_handle_forms(edge: &mut Map<String, Value>) {
    if !edge.contains_key("data") {
        edge.insert("data".into(), Value::Object(Map::new()));
    }
    for key in HANDLE_KEYS {
        let object = edge["data"].get(key).cloned();
        match object {
            Some(object) if !edge.contains_key(key) => {
                edge.insert(key.into(), Value::String(escape_handle(&object)));
            }
            None => {
                if let Some(parsed) = edge.get(key).and_then(parse_handle)
                    && let Some(Value::Object(data)) = edge.get_mut("data")
                {
                    data.insert(key.into(), Value::Object(parsed));
                }
            }
            Some(_) => {}
        }
    }
}

/// A node's outputs, indexed by name.
#[derive(Debug)]
pub(crate) struct Outputs<'g> {
    /// The outputs list, which is an array.
    items: Cow<'g, Value>,
    index: ListIndex,
}

impl Outputs<'_> {
    /// The output named `name`.
    pub fn get(&self, name: &str) -> Option<&Value> {
        let slot = self.index.slot(name)?;
        self.items.as_array().map(|items| &items[slot])
    }

    /// The names of all outputs.
    pub fn names(&self) -> impl Iterator<Item = &str> {
        self.index.keys()
    }
}

/// Index an outputs list, which follows the keyed-list rules.
pub(crate) fn index_outputs<'g>(items: Cow<'g, Value>, node_id: &str) -> Result<Outputs<'g>> {
    let Value::Array(list) = items.as_ref() else {
        bail!("node {}: data.node.outputs must be a list", quoted(node_id));
    };
    let index = ListIndex::build(
        outputs_list(),
        list,
        &fmt::from_fn(|f| write!(f, "node {}: data.node.outputs", quoted(node_id))),
    )?;
    Ok(Outputs { items, index })
}

/// A node's outputs, or `None` for a node without an `outputs` key.
pub(crate) fn node_outputs<'g>(
    graph: &'g impl GraphRead,
    node_id: &str,
) -> Result<Option<Outputs<'g>>> {
    if !graph.has_node(node_id) {
        bail!("node {} does not exist", quoted(node_id));
    }
    let Some(outputs) = graph.node_value(node_id, &OUTPUTS_PATH) else {
        return Ok(None);
    };
    if !outputs.is_array() {
        return Err(Error::graph_message(format!(
            "node {}: data.node.outputs must be a list",
            quoted(node_id)
        )));
    }
    index_outputs(outputs, node_id).map(Some)
}

/// Check an edge a write adds, and return its handles.
///
/// The edge must not touch a note, its handles must be valid and name an
/// output of its source and an input of its target, and a single input must
/// not be taken by another edge.
///
/// # Errors
///
/// The edge rule this edge, or an edge it is checked against, breaks.
pub(crate) fn check_edge(
    graph: &impl GraphRead,
    index: &mut EdgeIndex,
    edge: &Map<String, Value>,
) -> Result<Handles> {
    check_no_note(graph, edge)?;
    let handles = index.handles(edge)?;
    check_source_output(graph, edge, &handles)?;
    if check_target_input(graph, edge, &handles)? == Takes::One {
        check_input_free(graph, index, edge, &handles)?;
    }
    Ok(handles)
}

/// How many edges an input takes.
#[derive(Debug, PartialEq, Eq)]
enum Takes {
    One,
    Many,
}

/// No edge has a note at either end: a note has no handles.
fn check_no_note(graph: &impl GraphRead, edge: &Map<String, Value>) -> Result<()> {
    for end in ["source", "target"] {
        let node_id = endpoint(edge, end);
        if !graph.has_node(node_id) {
            bail!("edge {}: {end} node does not exist", quoted(edge.id()));
        }
        let node_type = graph.node_value(node_id, &["type"]);
        if node_type.as_deref().and_then(Value::as_str) == Some(NOTE_NODE_TYPE) {
            return Err(error(
                edge,
                ViolationCode::EdgeTouchesNote,
                format!(
                    "its {end} {} is a note, which has no handles",
                    quoted(node_id)
                ),
            ));
        }
    }
    Ok(())
}

/// The source node has the output the edge leaves from.
fn check_source_output(
    graph: &impl GraphRead,
    edge: &Map<String, Value>,
    handles: &Handles,
) -> Result<()> {
    let source = endpoint(edge, "source");
    let found =
        node_outputs(graph, source)?.is_some_and(|outputs| outputs.get(&handles.output).is_some());
    if found {
        return Ok(());
    }
    Err(error(
        edge,
        ViolationCode::EdgeHandleNotFound,
        format!(
            "source node {} has no output {}",
            quoted(source),
            quoted(&handles.output)
        ),
    ))
}

/// The target node has the input the edge enters: a template field, or an
/// output that declares `allows_loop`. Returns how many edges it takes.
fn check_target_input(
    graph: &impl GraphRead,
    edge: &Map<String, Value>,
    handles: &Handles,
) -> Result<Takes> {
    let target = endpoint(edge, "target");
    let name = &handles.input.name;
    match handles.input.kind {
        InputKind::Field => {
            let [data, body, template] = TEMPLATE_PATH;
            let field = graph.node_value(target, &[data, body, template, name]);
            let Some(field) = field.as_deref().and_then(Value::as_object) else {
                return Err(error(
                    edge,
                    ViolationCode::EdgeHandleNotFound,
                    format!(
                        "target node {} has no field {}",
                        quoted(target),
                        quoted(name)
                    ),
                ));
            };
            Ok(if field.get("list") == Some(&Value::Bool(true)) {
                Takes::Many
            } else {
                Takes::One
            })
        }
        InputKind::LoopOutput => {
            let allows_loop = node_outputs(graph, target)?.and_then(|outputs| {
                outputs
                    .get(name)
                    .map(|output| output.get("allows_loop") == Some(&Value::Bool(true)))
            });
            if allows_loop == Some(true) {
                return Ok(Takes::One);
            }
            Err(error(
                edge,
                ViolationCode::EdgeHandleNotFound,
                format!(
                    "target node {} has no loop output {}",
                    quoted(target),
                    quoted(name)
                ),
            ))
        }
    }
}

/// An input that takes one edge has no other edge yet.
fn check_input_free(
    graph: &impl GraphRead,
    index: &mut EdgeIndex,
    edge: &Map<String, Value>,
    handles: &Handles,
) -> Result<()> {
    let id = edge.id();
    let target = endpoint(edge, "target");
    let taken = index
        .connections(graph, target)?
        .inputs
        .get(&handles.input)
        .and_then(|ids| ids.iter().filter(|other| *other != id).min());
    let Some(other) = taken else {
        return Ok(());
    };
    let kind = match handles.input.kind {
        InputKind::Field => "field",
        InputKind::LoopOutput => "output",
    };
    Err(error(
        edge,
        ViolationCode::EdgeTargetOccupied,
        format!(
            "{kind} {} of node {} takes one connection and already has {}",
            quoted(&handles.input.name),
            quoted(target),
            quoted(other)
        ),
    ))
}
