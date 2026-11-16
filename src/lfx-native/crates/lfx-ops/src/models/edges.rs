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

use std::borrow::Cow;
use std::fmt;
use std::sync::LazyLock;

use crate::data::maps::{HashMap, IndexSet};
use crate::data::value::{AnyMap, AnyValue};

use crate::data::layered::Layered;
use crate::models::canonical::{edge_data_with_type_sets, handle_with_type_sets, values_equal};
use crate::models::entry::EntryExt;
use crate::models::error::{Error, Result, bail, invalid, quoted};
use crate::models::handle::{HANDLE_KEYS, handle_spells, parse_handle};
use crate::models::keyed::ListIndex;
use crate::models::operation::{PathExt, Segment};
use crate::models::schema::{KeyedList, NODE_SCHEMA, OUTPUTS_PATH, TEMPLATE_PATH};
use crate::models::validate::ViolationCode;

/// The type of a note node.
pub const NOTE_NODE_TYPE: &str = "noteNode";

static OUTPUTS_LIST: LazyLock<&'static KeyedList> = LazyLock::new(|| {
    NODE_SCHEMA
        .keyed_list_at(&AnyValue::Null, &OUTPUTS_PATH)
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

/// Whether [`removed_endpoints`] needs the old value at `path`.
/// Example: a write at `["data", "node"]` replaces the template and the outputs.
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
    before: Option<&AnyValue>,
    after: impl Fn(&[&str]) -> Option<Cow<'a, AnyValue>>,
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
    fn names(&self, held: Option<&AnyValue>, node_id: &str) -> Result<Vec<String>> {
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
fn at_keys<'v>(value: &'v AnyValue, keys: &[&str]) -> Option<&'v AnyValue> {
    keys.iter().try_fold(value, |value, key| value.get(key))
}

/// Read access to an indexed graph, enough to check edges.
pub(crate) trait GraphRead {
    /// Whether the graph has a node with `id`.
    fn has_node(&self, id: &str) -> bool;
    /// The value at the object keys `path` of the node `id`, with the batch's writes.
    fn node_value(&self, id: &str, path: &[&str]) -> Option<Cow<'_, AnyValue>>;
    /// The edge with `id`.
    fn edge(&self, id: &str) -> Option<&AnyMap>;
    /// The ids of the edges at a node.
    fn edge_ids_at(&self, node_id: &str) -> impl Iterator<Item = &str>;
}

/// The source or target of an edge that passed structural validation.
pub(crate) fn endpoint<'e>(edge: &'e AnyMap, end: &str) -> &'e str {
    edge.get(end).and_then(AnyValue::as_str).unwrap_or_default()
}

/// Each edge's handles and each node's connections, built on first use.
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
    pub fn handles(&mut self, edge: &AnyMap) -> Result<Handles> {
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
    pub fn insert(&mut self, edge: &AnyMap) {
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

    /// Drop the index entries of an edge, before it is removed.
    pub fn forget(&mut self, edge: &AnyMap) {
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

fn connect(connections: &mut Connections, node_id: &str, edge: &AnyMap, handles: &Handles) {
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

fn disconnect(connections: &mut Connections, node_id: &str, edge: &AnyMap, handles: &Handles) {
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

fn error(edge: &AnyMap, code: ViolationCode, reason: impl std::fmt::Display) -> Error {
    Error::edge(edge.id(), code, reason)
}

fn invalid(edge: &AnyMap, reason: impl std::fmt::Display) -> Error {
    error(edge, ViolationCode::EdgeHandleInvalid, reason)
}

fn not_found(edge: &AnyMap, reason: impl std::fmt::Display) -> Error {
    error(edge, ViolationCode::EdgeHandleNotFound, reason)
}

/// Read an edge's handles. Both forms must be present and agree.
///
/// # Errors
///
/// An edge rule the handles break, naming this edge.
pub fn read_handles(edge: &AnyMap) -> Result<Handles> {
    let source = handle(edge, "sourceHandle")?;
    let target = handle(edge, "targetHandle")?;
    let output = match source.get("name") {
        Some(AnyValue::String(name)) if !name.is_empty() => name.to_string(),
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
        Some(AnyValue::String(name)) if !name.is_empty() => Ok(Handles {
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

fn handle<'e>(edge: &'e AnyMap, key: &str) -> Result<&'e AnyMap> {
    // A present key counts at any value. Example: `"data": null` is not an object.
    let data = match edge.get("data") {
        None => None,
        Some(AnyValue::Object(data)) => Some(data),
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
        edge.get(key).and_then(AnyValue::as_str),
        object.and_then(AnyValue::as_object),
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
            && !values_equal(&AnyValue::Object(parsed), object)?
        {
            return Err(invalid(
                edge,
                format!("{key} and data.{key} name different handles"),
            ));
        }
    }
    match (object.and_then(AnyValue::as_object), edge.contains_key(key)) {
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
pub fn edge_changed(before: &AnyMap, after: &AnyMap) -> Result<bool> {
    let keys: IndexSet<&str> = before
        .keys()
        .chain(after.keys())
        .map(crate::data::value::AnyString::as_str)
        .filter(|key| !NODE_SCHEMA.edge_view_state.contains(key))
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
fn spells_data_handle(edge: &AnyMap, key: &str, handle: &AnyValue) -> bool {
    let object = edge
        .get("data")
        .and_then(AnyValue::as_object)
        .and_then(|data| data.get(key))
        .and_then(AnyValue::as_object);
    match (handle.as_str(), object) {
        (Some(text), Some(object)) => handle_spells(text, object),
        _ => false,
    }
}

/// A handle string compares by the object it encodes.
fn handle_value(handle: &AnyValue) -> AnyValue {
    parse_handle(handle).map_or_else(|| handle.clone(), AnyValue::Object)
}

/// A node's outputs, indexed by name.
#[derive(Debug)]
pub(crate) struct Outputs<'g> {
    /// The outputs list, which is an array.
    items: Cow<'g, AnyValue>,
    /// `None` for a short list whose names were checked: it is scanned.
    index: Option<ListIndex>,
}

/// Lists this short are scanned for a name instead of indexed.
const SCANNED_OUTPUTS: usize = 16;

impl Outputs<'_> {
    /// The output named `name`.
    pub fn get(&self, name: &str) -> Option<&AnyValue> {
        let items = self.items.as_array()?;
        match &self.index {
            Some(index) => index.slot(name).map(|slot| &items[slot]),
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
fn short_with_unique_keys(list: &[AnyValue]) -> bool {
    if list.len() > SCANNED_OUTPUTS {
        return false;
    }
    let mut keys: [&str; SCANNED_OUTPUTS] = [""; SCANNED_OUTPUTS];
    for (slot, item) in list.iter().enumerate() {
        match outputs_list().key_of(item).filter(|key| !key.is_empty()) {
            Some(key) if !keys[..slot].contains(&key) => keys[slot] = key,
            _ => return false,
        }
    }
    true
}

/// Index an outputs list. Each output must have a unique name.
pub(crate) fn index_outputs<'g>(items: Cow<'g, AnyValue>, node_id: &str) -> Result<Outputs<'g>> {
    let AnyValue::Array(list) = items.as_ref() else {
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
    edge: &AnyMap,
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
fn check_no_note(graph: &impl GraphRead, edge: &AnyMap) -> Result<()> {
    for end in ["source", "target"] {
        let node_id = endpoint(edge, end);
        if !graph.has_node(node_id) {
            bail!("edge {}: {end} node does not exist", quoted(edge.id()));
        }
        let node_type = graph.node_value(node_id, &["type"]);
        if node_type.as_deref().and_then(AnyValue::as_str) == Some(NOTE_NODE_TYPE) {
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
fn check_source_output(graph: &impl GraphRead, edge: &AnyMap, handles: &Handles) -> Result<()> {
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
fn check_target_input(graph: &impl GraphRead, edge: &AnyMap, handles: &Handles) -> Result<Takes> {
    let target = endpoint(edge, "target");
    let name = &handles.input.name;
    match handles.input.kind {
        InputKind::Field => {
            let [data, body, template] = TEMPLATE_PATH;
            let field = graph.node_value(target, &[data, body, template, name]);
            let Some(field) = field.as_deref().and_then(AnyValue::as_object) else {
                return Err(not_found(
                    edge,
                    format!(
                        "target node {} has no field {}",
                        quoted(target),
                        quoted(name)
                    ),
                ));
            };
            Ok(if field.get("list") == Some(&AnyValue::Bool(true)) {
                Takes::Many
            } else {
                Takes::One
            })
        }
        InputKind::LoopOutput => {
            let allows_loop = node_outputs(graph, target)?.and_then(|outputs| {
                outputs
                    .get(name)
                    .map(|output| output.get("allows_loop") == Some(&AnyValue::Bool(true)))
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
    edge: &AnyMap,
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
