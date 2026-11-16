//! The rules for an edge that a write adds.
//!
//! An edge goes from an output of its source (`sourceHandle.name`) to a
//! template field of its target (`targetHandle.fieldName`). A loop feedback
//! edge goes into an output with `allows_loop` (`targetHandle.name`).
//!
//! An edge holds each handle twice: as an object in `data`, and as a string
//! where `œ` stands for `"`. The two forms must agree.
//!
//! When a write removes a field or an output, it also removes the edges there.
//! The rules check only the edges a write adds or changes, and the edges it cuts.

use std::borrow::Cow;
use std::fmt;
use std::sync::LazyLock;

use crate::collection::hash_map::{HashMap, IndexSet};
use crate::json::{FlowObj, FlowValue};

use crate::collection::hash_map::{HashSet, IndexMap};
use crate::collection::pending_map::PendingMap;
use crate::compare::{edge_data_with_type_sets, handle_with_type_sets, values_equal};
use crate::flow::edge_handle::{HANDLE_KEYS, handle_spells, parse_handle};
use crate::flow::list::ListIndex;
use crate::flow::model::EntryExt;
use crate::flow::model::{FLOW_MODEL, KeyedList, OUTPUTS_PATH, TEMPLATE_PATH};
use crate::flow::node::NodeRef;
use crate::flow::path::{PathExt, Segment};
use crate::json::serialize::quoted;
use crate::violation::ViolationCode;
use crate::violation::error::{Error, Result, bail, invalid};
use crate::violation::error::{ErrorCode, ErrorKind};
use crate::violation::{PathPart, Violation};

/// The type of a note node.
pub const NOTE_NODE_TYPE: &str = "noteNode";

static OUTPUTS_LIST: LazyLock<&'static KeyedList> = LazyLock::new(|| {
    FLOW_MODEL
        .keyed_list_at(&FlowValue::Null, &OUTPUTS_PATH)
        .expect("model.json declares the outputs list")
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
    /// The ids of the edges at `endpoint`. For an output, this includes loop
    /// feedback edges into it.
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
    /// Whether the holder is a keyed list rather than an object.
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

/// Whether [`removed_endpoints`] needs the old value at `path`: a write there
/// can remove a field or an output that an edge ends at.
pub(crate) fn reads_before(path: &[Segment]) -> bool {
    HOLDERS
        .iter()
        .any(|holder| path.len() <= holder.path.len() && path.shares_start(holder.path))
}

/// The endpoints that a write at `path` of node `node_id` removed.
///
/// `before` is the old value at `path`, needed only when [`reads_before`] is true.
/// `after(keys)` reads the node after the write.
///
/// # Errors
///
/// An outputs list, before or after the write, breaks the keyed-list rules.
pub(crate) fn removed_endpoints<'a>(
    path: &[Segment],
    is_delete: bool,
    before: Option<&FlowValue>,
    after: impl Fn(&[&str]) -> Option<Cow<'a, FlowValue>>,
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
    /// The endpoint names in `held`: the output names, or the template keys.
    fn names(&self, held: Option<&FlowValue>, node_id: &str) -> Result<Vec<String>> {
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
            .map(|object| object.keys().map(ToString::to_string).collect())
            .unwrap_or_default())
    }
}

/// The value at the object keys `keys` under `value`.
fn at_keys<'v>(value: &'v FlowValue, keys: &[&str]) -> Option<&'v FlowValue> {
    keys.iter().try_fold(value, |value, key| value.get(key))
}

/// Read access to an indexed graph, enough to check edges.
pub(crate) trait GraphRead {
    /// Whether the graph has a node with `id`.
    fn has_node(&self, id: &str) -> bool;
    /// The value at the object keys `path` of the node `id`, with the batch's writes.
    fn node_value(&self, id: &str, path: &[&str]) -> Option<Cow<'_, FlowValue>>;
    /// The edge with `id`.
    fn edge(&self, id: &str) -> Option<&FlowObj>;
    /// The ids of the edges at a node.
    fn edge_ids_at(&self, node_id: &str) -> impl Iterator<Item = &str>;
}

/// The source or target of an edge that passed structural validation.
pub(crate) fn endpoint<'e>(edge: &'e FlowObj, end: &str) -> &'e str {
    edge.get(end)
        .and_then(FlowValue::as_str)
        .unwrap_or_default()
}

/// Each edge's handles and each node's connections, built on first use.
#[derive(Debug)]
pub(crate) struct EdgeIndex {
    handles: PendingMap<Handles>,
    connections: PendingMap<Connections>,
}

impl Default for EdgeIndex {
    fn default() -> Self {
        Self {
            handles: PendingMap::new(),
            connections: PendingMap::new(),
        }
    }
}

impl EdgeIndex {
    /// An edge's handles, read strictly the first time.
    pub fn handles(&mut self, edge: &FlowObj) -> Result<Handles> {
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
    /// If its handles do not read, those nodes are indexed again on next use.
    pub fn insert(&mut self, edge: &FlowObj) {
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

    /// Drop an edge from the index, before it is removed.
    pub fn forget(&mut self, edge: &FlowObj) {
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
    pub fn commit(&mut self) {
        self.handles.commit();
        self.connections.commit();
    }

    /// Drop a batch's changes.
    pub fn drop_pending(&mut self) {
        self.handles.drop_pending();
        self.connections.drop_pending();
    }
}

fn connect(connections: &mut Connections, node_id: &str, edge: &FlowObj, handles: &Handles) {
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

fn disconnect(connections: &mut Connections, node_id: &str, edge: &FlowObj, handles: &Handles) {
    let id = edge.id();
    if endpoint(edge, "target") == node_id
        && let Some(ids) = connections.inputs.get_mut(&handles.input)
    {
        ids.shift_remove(id);
    }
    if endpoint(edge, "source") == node_id
        && let Some(ids) = connections.outputs.get_mut(&handles.output)
    {
        ids.shift_remove(id);
    }
}

fn error(edge: &FlowObj, code: ViolationCode, reason: impl std::fmt::Display) -> Error {
    Error::edge(edge.id(), code, reason)
}

fn invalid(edge: &FlowObj, reason: impl std::fmt::Display) -> Error {
    error(edge, ViolationCode::EdgeHandleInvalid, reason)
}

fn not_found(edge: &FlowObj, reason: impl std::fmt::Display) -> Error {
    error(edge, ViolationCode::EdgeHandleNotFound, reason)
}

/// Read an edge's handles. Both forms must be present and agree.
///
/// # Errors
///
/// An edge rule the handles break, naming this edge.
pub fn read_handles(edge: &FlowObj) -> Result<Handles> {
    let source = handle(edge, "sourceHandle")?;
    let target = handle(edge, "targetHandle")?;
    let output = match source.get("name") {
        Some(FlowValue::String(name)) if !name.is_empty() => name.to_string(),
        _ => {
            return Err(invalid(edge, "sourceHandle must name an output"));
        }
    };
    // A present key counts at any value. Example: `"name": null` with `fieldName` names both.
    let names_field = target.contains_key("fieldName");
    if names_field == target.contains_key("name") {
        return Err(invalid(
            edge,
            "targetHandle must name exactly one of a field or an output",
        ));
    }
    let (kind, key) = if names_field {
        (InputKind::Field, "fieldName")
    } else {
        (InputKind::LoopOutput, "name")
    };
    match target.get(key) {
        Some(FlowValue::String(name)) if !name.is_empty() => Ok(Handles {
            output,
            input: Input {
                kind,
                name: name.to_string(),
            },
        }),
        _ => Err(invalid(
            edge,
            "targetHandle must name its field or output as a string",
        )),
    }
}

fn handle<'e>(edge: &'e FlowObj, key: &str) -> Result<&'e FlowObj> {
    // A present key counts at any value. Example: `"data": null` is not an object.
    let data = match edge.get("data") {
        None => None,
        Some(FlowValue::Object(data)) => Some(data),
        Some(_) => {
            return Err(invalid(edge, "data must be an object"));
        }
    };
    let object = data.and_then(|data| data.get(key));
    if let Some(object) = object
        && !object.is_object()
    {
        return Err(invalid(edge, format!("data.{key} must be an object")));
    }
    // Fast path: text that spells the object as the editor writes it needs no parse.
    let spelled = match (
        edge.get(key).and_then(FlowValue::as_str),
        object.and_then(FlowValue::as_object),
    ) {
        (Some(text), Some(object)) => handle_spells(text, object),
        _ => false,
    };
    if let Some(string) = edge.get(key).filter(|_| !spelled) {
        let Some(parsed) = parse_handle(string) else {
            return Err(invalid(
                edge,
                format!("{key} must be an escaped JSON object"),
            ));
        };
        if let Some(object) = object
            && !values_equal(&FlowValue::Object(parsed), object)?
        {
            return Err(invalid(
                edge,
                format!("{key} and data.{key} name different handles"),
            ));
        }
    }
    match (
        object.and_then(FlowValue::as_object),
        edge.contains_key(key),
    ) {
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
        (None, false) => Err(invalid(edge, format!("edge has no {key}"))),
    }
}

/// Whether an edge changed between two graphs. View state, handle spelling and
/// the order of a handle's type list do not count.
///
/// # Errors
///
/// A compared value holds a number that is not finite.
pub fn edge_changed(before: &FlowObj, after: &FlowObj) -> Result<bool> {
    let keys: IndexSet<&str> = before
        .keys()
        .chain(after.keys())
        .map(crate::json::FlowStr::as_str)
        .filter(|key| !FLOW_MODEL.edge_view_state.contains(key))
        .collect();
    for key in keys {
        let same = match (before.get(key), after.get(key)) {
            // Fast path: the same text that spells the `data` handle needs no parse.
            (Some(old), Some(new))
                if HANDLE_KEYS.contains(&key)
                    && old == new
                    && spells_data_handle(before, key, old) =>
            {
                true
            }
            (Some(old), Some(new)) if HANDLE_KEYS.contains(&key) => {
                let (old, new) = (handle_value(old), handle_value(new));
                values_equal(&old, &new)?
                    || values_equal(&handle_with_type_sets(old)?, &handle_with_type_sets(new)?)?
            }
            (Some(old), Some(new)) if key == "data" => {
                values_equal(old, new)?
                    || values_equal(
                        &edge_data_with_type_sets(old)?,
                        &edge_data_with_type_sets(new)?,
                    )?
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

/// Whether the handle string `handle` spells the object at `data.<key>` ([`handle_spells`]).
fn spells_data_handle(edge: &FlowObj, key: &str, handle: &FlowValue) -> bool {
    let object = edge
        .get("data")
        .and_then(FlowValue::as_object)
        .and_then(|data| data.get(key))
        .and_then(FlowValue::as_object);
    match (handle.as_str(), object) {
        (Some(text), Some(object)) => handle_spells(text, object),
        _ => false,
    }
}

/// A handle string compares by the object it encodes.
fn handle_value(handle: &FlowValue) -> FlowValue {
    parse_handle(handle).map_or_else(|| handle.clone(), FlowValue::Object)
}

/// A node's outputs, indexed by name.
#[derive(Debug)]
pub(crate) struct Outputs<'g> {
    /// The outputs list, which is an array.
    items: Cow<'g, FlowValue>,
    /// `None` for a short list whose names were checked: it is scanned.
    index: Option<ListIndex>,
}

/// Lists this short are scanned for a name instead of indexed.
const SCANNED_OUTPUTS: usize = 16;

impl Outputs<'_> {
    /// The output named `name`.
    pub fn get(&self, name: &str) -> Option<&FlowValue> {
        let items = self.items.as_array()?;
        match &self.index {
            Some(index) => index.item_index(name).map(|item_index| &items[item_index]),
            None => items
                .iter()
                .find(|item| outputs_list().key_of(item) == Some(name)),
        }
    }

    /// The names of all outputs.
    pub fn names(&self) -> Box<dyn Iterator<Item = &str> + '_> {
        match &self.index {
            Some(index) => Box::new(index.keys()),
            None => Box::new(
                self.items
                    .as_array()
                    .into_iter()
                    .flatten()
                    .filter_map(|item| outputs_list().key_of(item)),
            ),
        }
    }
}

/// Whether every item of a short list has a non-empty key that no other item has.
fn short_with_unique_keys(list: &[FlowValue]) -> bool {
    if list.len() > SCANNED_OUTPUTS {
        return false;
    }
    let mut keys: [&str; SCANNED_OUTPUTS] = [""; SCANNED_OUTPUTS];
    for (item_index, item) in list.iter().enumerate() {
        match outputs_list().key_of(item).filter(|key| !key.is_empty()) {
            Some(key) if !keys[..item_index].contains(&key) => keys[item_index] = key,
            _ => return false,
        }
    }
    true
}

/// Index an outputs list. Each output must have a unique name.
pub(crate) fn index_outputs<'g>(items: Cow<'g, FlowValue>, node_id: &str) -> Result<Outputs<'g>> {
    let FlowValue::Array(list) = items.as_ref() else {
        bail!("node {}: data.node.outputs must be a list", quoted(node_id));
    };
    if short_with_unique_keys(list) {
        return Ok(Outputs { items, index: None });
    }
    let index = ListIndex::build(outputs_list(), list);
    index.check_keys(&fmt::from_fn(|f| {
        write!(f, "node {}: data.node.outputs", quoted(node_id))
    }))?;
    Ok(Outputs {
        items,
        index: Some(index),
    })
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

/// Check an edge that a write adds, and return its handles.
///
/// # Errors
///
/// The edge rule this edge, or an edge it is checked against, breaks.
pub(crate) fn check_edge(
    graph: &impl GraphRead,
    index: &mut EdgeIndex,
    edge: &FlowObj,
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

/// The edge has no note at either end, because a note has no handles.
fn check_no_note(graph: &impl GraphRead, edge: &FlowObj) -> Result<()> {
    for end in ["source", "target"] {
        let node_id = endpoint(edge, end);
        if !graph.has_node(node_id) {
            bail!("edge {}: {end} node does not exist", quoted(edge.id()));
        }
        let node_type = graph.node_value(node_id, &["type"]);
        if node_type.as_deref().and_then(FlowValue::as_str) == Some(NOTE_NODE_TYPE) {
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
fn check_source_output(graph: &impl GraphRead, edge: &FlowObj, handles: &Handles) -> Result<()> {
    let source = endpoint(edge, "source");
    let found =
        node_outputs(graph, source)?.is_some_and(|outputs| outputs.get(&handles.output).is_some());
    if found {
        return Ok(());
    }
    Err(not_found(
        edge,
        format!(
            "source node {} has no output {}",
            quoted(source),
            quoted(&handles.output)
        ),
    ))
}

/// The target node has the input the edge enters. Returns how many edges it accepts.
fn check_target_input(graph: &impl GraphRead, edge: &FlowObj, handles: &Handles) -> Result<Takes> {
    let target = endpoint(edge, "target");
    let name = &handles.input.name;
    match handles.input.kind {
        InputKind::Field => {
            let [data, body, template] = TEMPLATE_PATH;
            let field = graph.node_value(target, &[data, body, template, name]);
            let Some(field) = field.as_deref().and_then(FlowValue::as_object) else {
                return Err(not_found(
                    edge,
                    format!(
                        "target node {} has no field {}",
                        quoted(target),
                        quoted(name)
                    ),
                ));
            };
            Ok(if field.get("list") == Some(&FlowValue::Bool(true)) {
                Takes::Many
            } else {
                Takes::One
            })
        }
        InputKind::LoopOutput => {
            let allows_loop = node_outputs(graph, target)?.and_then(|outputs| {
                outputs
                    .get(name)
                    .map(|output| output.get("allows_loop") == Some(&FlowValue::Bool(true)))
            });
            if allows_loop == Some(true) {
                return Ok(Takes::One);
            }
            Err(not_found(
                edge,
                format!(
                    "target node {} has no loop output {}",
                    quoted(target),
                    quoted(name)
                ),
            ))
        }
    }
}

/// An input that accepts only one edge has no other edge yet.
fn check_input_free(
    graph: &impl GraphRead,
    index: &mut EdgeIndex,
    edge: &FlowObj,
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

// --- Edges a write adds or cuts ----------------------------------------------------------------

/// A structurally valid graph, indexed for the edge rules.
#[derive(Debug)]
pub(crate) struct GraphView<'a> {
    nodes: HashMap<&'a str, &'a FlowValue>,
    edges: HashMap<&'a str, &'a FlowObj>,
    edges_at: HashMap<&'a str, Vec<&'a str>>,
}

impl<'a> GraphView<'a> {
    /// Build the indexes of a graph that passed structural validation.
    ///
    /// # Errors
    ///
    /// A node does not have the shape of a node.
    pub fn new(graph: &'a FlowValue) -> Result<Self> {
        let mut view = Self {
            nodes: HashMap::default(),
            edges: HashMap::default(),
            edges_at: HashMap::default(),
        };
        for node in list(graph, "nodes") {
            let Some(map) = node.as_object() else {
                continue;
            };
            view.nodes.insert(
                NodeRef::new(map)
                    .map_err(|error| error.into_error("node"))?
                    .id(),
                node,
            );
        }
        for edge in list(graph, "edges").iter().filter_map(FlowValue::as_object) {
            let id = edge.id();
            view.edges.insert(id, edge);
            let (source, target) = (endpoint(edge, "source"), endpoint(edge, "target"));
            view.edges_at.entry(source).or_default().push(id);
            if target != source {
                view.edges_at.entry(target).or_default().push(id);
            }
        }
        Ok(view)
    }
}

impl GraphRead for GraphView<'_> {
    fn has_node(&self, id: &str) -> bool {
        self.nodes.contains_key(id)
    }

    fn node_value(&self, id: &str, path: &[&str]) -> Option<Cow<'_, FlowValue>> {
        let node = self.nodes.get(id)?;
        path.iter()
            .try_fold(*node, |value, key| value.get(key))
            .map(Cow::Borrowed)
    }

    fn edge(&self, id: &str) -> Option<&FlowObj> {
        self.edges.get(id).copied()
    }

    fn edge_ids_at(&self, node_id: &str) -> impl Iterator<Item = &str> {
        self.edges_at.get(node_id).into_iter().flatten().copied()
    }
}

pub(crate) fn list<'a>(graph: &'a FlowValue, key: &str) -> &'a [FlowValue] {
    graph
        .get(key)
        .and_then(FlowValue::as_array)
        .unwrap_or_default()
}

/// The indexes of the edges that `target` adds, changes or cuts relative to `base`.
///
/// A cut edge goes from or into a field or output that `target` removes.
/// Replay deletes that edge, so `target` must not keep it.
pub(crate) fn changed_edges(base: &FlowValue, target: &FlowValue) -> Result<Vec<usize>> {
    let stored: HashMap<&str, &FlowObj> = list(base, "edges")
        .iter()
        .filter_map(FlowValue::as_object)
        .filter_map(|edge| Some((edge.get("id")?.as_str()?, edge)))
        .collect();
    let removed = removed_ends(base, target)?;
    let mut indexes = Vec::new();
    for (index, edge) in list(target, "edges").iter().enumerate() {
        let Some(edge) = edge.as_object() else {
            continue;
        };
        let changed = match stored.get(edge.id()) {
            None => true,
            Some(before) => edge_changed(before, edge)? || is_cut(edge, &removed),
        };
        if changed {
            indexes.push(index);
        }
    }
    Ok(indexes)
}

/// The template fields and outputs a write removes from one node.
#[derive(Debug)]
struct RemovedEnds {
    fields: HashSet<String>,
    outputs: HashSet<String>,
}

/// The template fields and outputs `target` removes from the nodes it keeps, by node id.
fn removed_ends(base: &FlowValue, target: &FlowValue) -> Result<HashMap<String, RemovedEnds>> {
    let stored: HashMap<&str, &FlowObj> = list(base, "nodes")
        .iter()
        .filter_map(FlowValue::as_object)
        .map(|node| (node.id(), node))
        .collect();
    let mut removed = HashMap::default();
    for node in list(target, "nodes")
        .iter()
        .filter_map(FlowValue::as_object)
    {
        let Some(stored) = stored.get(node.id()) else {
            continue;
        };
        let (stored, node) = (
            NodeRef::new(stored).map_err(|error| error.into_error("node"))?,
            NodeRef::new(node).map_err(|error| error.into_error("node"))?,
        );
        let fields = removed_fields(stored.template(), node.template());
        let outputs = removed_outputs(stored.body(), node.body(), node.id())?;
        if !fields.is_empty() || !outputs.is_empty() {
            removed.insert(node.id().to_owned(), RemovedEnds { fields, outputs });
        }
    }
    Ok(removed)
}

/// The template keys `before` has and `after` does not.
fn removed_fields(before: &FlowObj, after: &FlowObj) -> HashSet<String> {
    before
        .keys()
        .filter(|key| !after.contains_key(key))
        .map(ToString::to_string)
        .collect()
}

/// The output names `before` has and `after` does not.
fn removed_outputs(before: &FlowObj, after: &FlowObj, node_id: &str) -> Result<HashSet<String>> {
    let Some(outputs_before) = before.get("outputs") else {
        return Ok(HashSet::default());
    };
    let outputs_after = after.get("outputs");
    if let Some(outputs_after) = outputs_after
        && values_equal(outputs_before, outputs_after)?
    {
        return Ok(HashSet::default());
    }
    let kept: HashSet<String> = match outputs_after {
        Some(outputs_after) => index_outputs(Cow::Borrowed(outputs_after), node_id)?
            .names()
            .map(str::to_owned)
            .collect(),
        None => HashSet::default(),
    };
    Ok(index_outputs(Cow::Borrowed(outputs_before), node_id)?
        .names()
        .filter(|name| !kept.contains(*name))
        .map(str::to_owned)
        .collect())
}

/// Whether a kept edge goes from or into a field or output that the write removes.
/// An edge at such a node with handles that do not read also counts.
fn is_cut(edge: &FlowObj, removed: &HashMap<String, RemovedEnds>) -> bool {
    let source = removed.get(endpoint(edge, "source"));
    let target = removed.get(endpoint(edge, "target"));
    if source.is_none() && target.is_none() {
        return false;
    }
    let Ok(handles) = read_handles(edge) else {
        return true;
    };
    if source.is_some_and(|source| source.outputs.contains(&handles.output)) {
        return true;
    }
    target.is_some_and(|target| match handles.input.kind {
        InputKind::Field => target.fields.contains(&handles.input.name),
        InputKind::LoopOutput => target.outputs.contains(&handles.input.name),
    })
}

/// The edge rules broken by the edges `target` adds, changes or cuts relative to `base`.
/// Each violation is reported once, at the edge that breaks the rule.
pub(crate) fn find_edge_violations(base: &FlowValue, target: &FlowValue) -> Result<Vec<Violation>> {
    let indexes = changed_edges(base, target)?;
    if indexes.is_empty() {
        return Ok(Vec::new());
    }
    let view = GraphView::new(target)?;
    let mut edge_index = EdgeIndex::default();
    let edges = list(target, "edges");
    let index_of: HashMap<&str, usize> = edges
        .iter()
        .enumerate()
        .filter_map(|(index, edge)| Some((edge.as_object().map(EntryExt::id)?, index)))
        .collect();
    let mut violations: IndexMap<String, Violation> = IndexMap::default();
    for index in indexes {
        let Some(edge) = edges[index].as_object() else {
            continue;
        };
        let Err(error) = check_edge(&view, &mut edge_index, edge) else {
            continue;
        };
        let (ErrorKind::InvalidOperation, ErrorCode::Violation(code), Some(broken)) =
            (error.kind, error.code, error.edge_id.as_deref())
        else {
            return Err(error);
        };
        if !violations.contains_key(broken) {
            let path = vec![
                "edges".into(),
                index_of.get(broken).copied().unwrap_or(index).into(),
            ];
            violations.insert(
                broken.to_owned(),
                Violation {
                    edge_id: Some(broken.to_owned()),
                    ..Violation::new(code, path, error.message.clone())
                },
            );
        }
    }
    let mut violations: Vec<Violation> = violations.into_values().collect();
    violations.sort_by_key(|violation| match violation.path.get(1) {
        Some(PathPart::Index(index)) => *index,
        _ => 0,
    });
    Ok(violations)
}

impl Error {
    /// An edge rule broken by the edge `edge_id`.
    pub fn edge(edge_id: &str, code: ViolationCode, reason: impl fmt::Display) -> Self {
        Self {
            edge_id: Some(edge_id.to_owned()),
            ..Self::invalid_with(
                ErrorCode::Violation(code),
                format!("edge {}: {reason}", quoted(edge_id)),
            )
        }
    }
}
