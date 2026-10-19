//! The rules every stored flow graph follows.
//!
//! A write must keep these rules. The engine checks them on the
//! graph it starts from, and the diff checks them on the graph a save asks
//! for. Each rule has a stable code, so a refused write can name what is
//! wrong and where, and each violation says who fixes it: `repair`, or the
//! client.
//!
//! Two groups of rules are checked only against the stored graph a write
//! replaces (`base`), so what is stored stays acceptable until someone
//! touches it:
//!
//! - table rows: every table value the write adds or changes must have rows
//!   with a unique `__id__` and a numeric `__pos__`. Their order in the array
//!   is not state, so it is never checked, and legacy tables without row ids
//!   stay valid until someone edits them. The engine owns these two keys, so
//!   the column definition (`table_schema`) of such a table must not name a
//!   column `__id__` or `__pos__`;
//! - edge rules: every edge the write adds must carry valid handles that
//!   name an output and an input that exist, must not take an input that is
//!   already taken, and must not touch a note. An edge that changed counts as
//!   added, since a write deletes it and adds it again. They are the same
//!   checks the engine makes when it applies `add_edges`, so validation and
//!   apply never disagree.

use std::collections::{HashMap, HashSet};
use std::fmt;

use indexmap::IndexMap;
use serde_json::{Map, Value};

use crate::ops::canonical::{is_finite_number, is_row_position, values_equal};
use crate::ops::edges::{
    EdgeIndex, GraphRead, InputKind, check_edge, edge_changed, endpoint, index_outputs, node_body,
    read_handles,
};
use crate::ops::entry::EntryExt;
use crate::ops::error::{Error, ErrorCode, ErrorKind, Result};
use crate::ops::schema::{NODE_OBJECT_PATHS, NODE_SCHEMA, field_value_path};

/// The stable code of a graph rule.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[expect(missing_docs, reason = "each variant's name says the rule it codes")]
pub enum ViolationCode {
    FlowDataNotObject,
    CollectionNotList,
    NodeNotObject,
    EdgeNotObject,
    NodeIdMissing,
    NodeIdDuplicate,
    EdgeIdMissing,
    EdgeIdDuplicate,
    EdgeEndpointInvalid,
    NodeDataNotObject,
    NonFiniteNumber,
    TableRowNotObject,
    TableRowIdMissing,
    TableRowIdDuplicate,
    TableRowPosInvalid,
    /// A table's column definition names a column after a row key the engine owns.
    TableColumnReserved,
    /// A handle has one of its two forms, and the other is valid.
    EdgeHandleFormMissing,
    /// A handle is missing, is not an object, does not parse, or its forms disagree.
    EdgeHandleInvalid,
    /// A handle names an output or field its node does not have.
    EdgeHandleNotFound,
    /// A field that takes one connection, or a loop output, already has one.
    EdgeTargetOccupied,
    /// An edge has a note at one end.
    EdgeTouchesNote,
}

impl ViolationCode {
    /// The code as the API reports it.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Self::FlowDataNotObject => "FLOW_DATA_NOT_OBJECT",
            Self::CollectionNotList => "COLLECTION_NOT_LIST",
            Self::NodeNotObject => "NODE_NOT_OBJECT",
            Self::EdgeNotObject => "EDGE_NOT_OBJECT",
            Self::NodeIdMissing => "NODE_ID_MISSING",
            Self::NodeIdDuplicate => "NODE_ID_DUPLICATE",
            Self::EdgeIdMissing => "EDGE_ID_MISSING",
            Self::EdgeIdDuplicate => "EDGE_ID_DUPLICATE",
            Self::EdgeEndpointInvalid => "EDGE_ENDPOINT_INVALID",
            Self::NodeDataNotObject => "NODE_DATA_NOT_OBJECT",
            Self::NonFiniteNumber => "NON_FINITE_NUMBER",
            Self::TableRowNotObject => "TABLE_ROW_NOT_OBJECT",
            Self::TableRowIdMissing => "TABLE_ROW_ID_MISSING",
            Self::TableRowIdDuplicate => "TABLE_ROW_ID_DUPLICATE",
            Self::TableRowPosInvalid => "TABLE_ROW_POS_INVALID",
            Self::TableColumnReserved => "TABLE_COLUMN_RESERVED",
            Self::EdgeHandleFormMissing => "EDGE_HANDLE_FORM_MISSING",
            Self::EdgeHandleInvalid => "EDGE_HANDLE_INVALID",
            Self::EdgeHandleNotFound => "EDGE_HANDLE_NOT_FOUND",
            Self::EdgeTargetOccupied => "EDGE_TARGET_OCCUPIED",
            Self::EdgeTouchesNote => "EDGE_TOUCHES_NOTE",
        }
    }

    /// The fix for a violation that has one fix, or `None` for one the client fixes.
    ///
    /// A rule that has one fix but no code for it here would leave a flow that
    /// can neither be saved nor repaired, so every code is either fixed here or
    /// left to the client.
    #[must_use]
    pub fn repair_action(self) -> Option<&'static str> {
        use ViolationCode as Code;
        Some(match self {
            Code::FlowDataNotObject => "replaced with an empty flow",
            Code::CollectionNotList => "replaced with an empty list",
            Code::NodeNotObject | Code::EdgeNotObject => "dropped the entry",
            Code::NodeIdMissing | Code::EdgeIdMissing | Code::EdgeIdDuplicate => {
                "assigned a generated id"
            }
            Code::NodeIdDuplicate => {
                "assigned a generated id; the first node keeps the id and its edges"
            }
            Code::EdgeEndpointInvalid | Code::EdgeTouchesNote => "dropped the edge",
            Code::NodeDataNotObject => "replaced with an empty object",
            Code::NonFiniteNumber => "replaced with null",
            Code::TableRowNotObject => "dropped the row",
            Code::TableRowIdMissing => "assigned a generated row id",
            Code::TableRowIdDuplicate => "assigned a generated row id; the first row keeps the id",
            Code::TableRowPosInvalid => "assigned a position that keeps the row where it is stored",
            Code::EdgeHandleFormMissing => {
                "derived the missing form of the handle from the one present"
            }
            Code::EdgeHandleInvalid
            | Code::EdgeHandleNotFound
            | Code::EdgeTargetOccupied
            | Code::TableColumnReserved => {
                return None;
            }
        })
    }

    /// Who fixes a violation of this rule: repair when the rule has a fix,
    /// the client otherwise.
    #[must_use]
    pub fn resolution(self) -> Resolution {
        if self.repair_action().is_some() {
            Resolution::Auto
        } else {
            Resolution::Manual
        }
    }
}

impl fmt::Display for ViolationCode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Whether validation walks every value for numbers that are not finite.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Numbers {
    /// Walk every value. A graph from outside is checked this way.
    Check,
    /// Skip the walk. Stored values were checked when they were written, so
    /// indexing and replay stay proportional to the number of nodes and edges.
    Skip,
}

/// How a violation is fixed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Resolution {
    /// The violation has exactly one fix, which `repair` applies.
    Auto,
    /// Fixing it means choosing what the person meant, so the client does.
    Manual,
}

impl Resolution {
    /// The resolution as the API reports it.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Auto => "auto",
            Self::Manual => "manual",
        }
    }
}

/// One step of a path into a graph: an object key or an array index.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum PathPart {
    /// An object key.
    Key(String),
    /// An array index.
    Index(usize),
}

impl From<&str> for PathPart {
    fn from(key: &str) -> Self {
        Self::Key(key.to_owned())
    }
}

impl From<usize> for PathPart {
    fn from(index: usize) -> Self {
        Self::Index(index)
    }
}

impl PathPart {
    /// The part as JSON: a string key or an integer index.
    pub(crate) fn to_value(&self) -> Value {
        match self {
            Self::Key(key) => Value::from(key.as_str()),
            Self::Index(index) => Value::from(*index),
        }
    }
}

impl fmt::Display for PathPart {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Key(key) => f.write_str(key),
            Self::Index(index) => write!(f, "{index}"),
        }
    }
}

/// A path into a graph.
pub type GraphPath = Vec<PathPart>;

fn path_of(base: &[PathPart], more: &[&str]) -> GraphPath {
    base.iter()
        .cloned()
        .chain(more.iter().map(|key| PathPart::from(*key)))
        .collect()
}

/// One broken rule, where it was found, and a message without graph values.
///
/// An edge rule violation also names its edge, so a client can fix that edge
/// without counting its way through the edge list.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Violation {
    /// The rule.
    pub code: ViolationCode,
    /// Where it is broken.
    pub path: GraphPath,
    /// What is wrong.
    pub message: String,
    /// The edge an edge rule violation is about.
    pub edge_id: Option<String>,
}

impl Violation {
    fn new(code: ViolationCode, path: GraphPath, message: impl Into<String>) -> Self {
        Self {
            code,
            path,
            message: message.into(),
            edge_id: None,
        }
    }

    /// The violation as the API reports it.
    #[must_use]
    pub fn to_value(&self) -> Value {
        let mut object = Map::new();
        object.insert("code".into(), Value::from(self.code.as_str()));
        object.insert(
            "path".into(),
            Value::Array(self.path.iter().map(PathPart::to_value).collect()),
        );
        object.insert("message".into(), Value::from(self.message.as_str()));
        object.insert(
            "resolution".into(),
            Value::from(self.code.resolution().as_str()),
        );
        if let Some(edge_id) = &self.edge_id {
            object.insert("edge_id".into(), Value::from(edge_id.as_str()));
        }
        Value::Object(object)
    }
}

/// Every rule `flow` breaks, in the order the graph lists them.
///
/// With [`Numbers::Check`], it also walks every value for numbers that are
/// not finite as JavaScript reads them.
///
/// `base` is the stored graph a write replaces. When it is given, every table
/// value `flow` adds or changes relative to it is checked too, and so is every
/// edge it adds, once the graph's structure is sound. Pass an empty
/// graph for a flow that has no stored graph yet.
///
/// # Errors
///
/// Reading an edge's handles or a node's outputs failed in a way that is not
/// a violation of the edge being checked.
pub fn find_graph_violations(
    flow: &Value,
    numbers: Numbers,
    base: Option<&Value>,
) -> Result<Vec<Violation>> {
    let Value::Object(graph) = flow else {
        return Ok(vec![Violation::new(
            ViolationCode::FlowDataNotObject,
            Vec::new(),
            "flow data must be an object",
        )]);
    };
    let mut violations = Vec::new();
    let nodes = graph.get("nodes").and_then(Value::as_array);
    let edges = graph.get("edges").and_then(Value::as_array);
    for (key, collection) in [("nodes", nodes), ("edges", edges)] {
        if collection.is_none() {
            violations.push(Violation::new(
                ViolationCode::CollectionNotList,
                vec![key.into()],
                format!("flow data {key} must be a list"),
            ));
        }
    }

    let mut node_ids = HashSet::new();
    if let Some(nodes) = nodes {
        for (index, node) in nodes.iter().enumerate() {
            node_violations(
                node,
                &["nodes".into(), index.into()],
                &mut node_ids,
                &mut violations,
            );
        }
    }
    if let Some(edges) = edges {
        let mut edge_ids = HashSet::new();
        for (index, edge) in edges.iter().enumerate() {
            edge_violations(
                edge,
                &["edges".into(), index.into()],
                &mut edge_ids,
                &node_ids,
                &mut violations,
            );
        }
    }

    if let Some(base) = base
        && nodes.is_some()
    {
        let structural = violations.is_empty();
        violations.extend(find_table_violations(base, flow)?);
        if structural {
            violations.extend(find_edge_violations(base, flow)?);
        }
    }
    if numbers == Numbers::Check {
        non_finite_violations(flow, &mut Vec::new(), &mut violations);
    }
    Ok(violations)
}

/// Fail with every violation `flow` has, if it has any.
///
/// # Errors
///
/// An invalid graph error listing the violations, or what
/// [`find_graph_violations`] fails with.
pub fn validate_flow_data(
    flow: &Value,
    numbers: Numbers,
    context: &str,
    base: Option<&Value>,
) -> Result<()> {
    let violations = find_graph_violations(flow, numbers, base)?;
    let Some(first) = violations.first() else {
        return Ok(());
    };
    let location = if first.path.is_empty() {
        "<root>".to_owned()
    } else {
        first
            .path
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join(".")
    };
    let more = if violations.len() > 1 {
        format!(" (and {} more)", violations.len() - 1)
    } else {
        String::new()
    };
    Err(Error::graph(
        format!("{context}: {} at {location}{more}", first.message),
        violations,
    ))
}

fn node_violations<'a>(
    node: &'a Value,
    path: &[PathPart],
    node_ids: &mut HashSet<&'a str>,
    violations: &mut Vec<Violation>,
) {
    let Value::Object(node) = node else {
        violations.push(Violation::new(
            ViolationCode::NodeNotObject,
            path.to_vec(),
            "node must be an object",
        ));
        return;
    };
    match node.non_empty_str("id") {
        None => violations.push(Violation::new(
            ViolationCode::NodeIdMissing,
            path_of(path, &["id"]),
            "node must have a non-empty string id",
        )),
        Some(id) if !node_ids.insert(id) => violations.push(Violation::new(
            ViolationCode::NodeIdDuplicate,
            path_of(path, &["id"]),
            "duplicate node id",
        )),
        Some(_) => {}
    }
    if let Some(object_path) = missing_node_object(node) {
        violations.push(Violation::new(
            ViolationCode::NodeDataNotObject,
            path_of(path, object_path),
            format!("{} must be an object", object_path.join(".")),
        ));
    }
}

/// The first of `data`, `data.node` and `data.node.template` that is not an object.
pub(crate) fn missing_node_object(node: &Map<String, Value>) -> Option<&'static [&'static str]> {
    let mut value = node;
    for object_path in NODE_OBJECT_PATHS {
        let key = object_path[object_path.len() - 1];
        match value.get(key) {
            Some(Value::Object(object)) => value = object,
            _ => return Some(object_path),
        }
    }
    None
}

fn edge_violations<'a>(
    edge: &'a Value,
    path: &[PathPart],
    edge_ids: &mut HashSet<&'a str>,
    node_ids: &HashSet<&str>,
    violations: &mut Vec<Violation>,
) {
    let Value::Object(edge) = edge else {
        violations.push(Violation::new(
            ViolationCode::EdgeNotObject,
            path.to_vec(),
            "edge must be an object",
        ));
        return;
    };
    match edge.non_empty_str("id") {
        None => violations.push(Violation::new(
            ViolationCode::EdgeIdMissing,
            path_of(path, &["id"]),
            "edge must have a non-empty string id",
        )),
        Some(id) if !edge_ids.insert(id) => violations.push(Violation::new(
            ViolationCode::EdgeIdDuplicate,
            path_of(path, &["id"]),
            "duplicate edge id",
        )),
        Some(_) => {}
    }
    for end in ["source", "target"] {
        let message = match edge.non_empty_str(end) {
            None => format!("edge must have a non-empty string {end}"),
            Some(node_id) if !node_ids.contains(node_id) => {
                format!("edge {end} node does not exist")
            }
            Some(_) => continue,
        };
        violations.push(Violation::new(
            ViolationCode::EdgeEndpointInvalid,
            path_of(path, &[end]),
            message,
        ));
    }
}

fn non_finite_violations(value: &Value, path: &mut GraphPath, violations: &mut Vec<Violation>) {
    match value {
        Value::Number(number) if !is_finite_number(number) => violations.push(Violation::new(
            ViolationCode::NonFiniteNumber,
            path.clone(),
            "NaN, Infinity and integers too large for a double are not valid JSON",
        )),
        Value::Object(map) => {
            for (key, item) in map {
                path.push(PathPart::Key(key.clone()));
                non_finite_violations(item, path, violations);
                path.pop();
            }
        }
        Value::Array(items) => {
            for (index, item) in items.iter().enumerate() {
                path.push(PathPart::Index(index));
                non_finite_violations(item, path, violations);
                path.pop();
            }
        }
        _ => {}
    }
}

// --- Edges a write adds ------------------------------------------------------------------

/// A structurally valid graph, indexed for the edge rules without copying it.
#[derive(Debug)]
pub(crate) struct GraphView<'a> {
    nodes: HashMap<&'a str, &'a Map<String, Value>>,
    edges: HashMap<&'a str, &'a Map<String, Value>>,
    edges_at: HashMap<&'a str, Vec<&'a str>>,
}

impl<'a> GraphView<'a> {
    /// Build the indexes of a graph that passed structural validation.
    pub fn new(graph: &'a Value) -> Self {
        let mut view = Self {
            nodes: HashMap::new(),
            edges: HashMap::new(),
            edges_at: HashMap::new(),
        };
        for node in list(graph, "nodes").iter().filter_map(Value::as_object) {
            view.nodes.insert(node.id(), node);
        }
        for edge in list(graph, "edges").iter().filter_map(Value::as_object) {
            let id = edge.id();
            view.edges.insert(id, edge);
            let (source, target) = (endpoint(edge, "source"), endpoint(edge, "target"));
            view.edges_at.entry(source).or_default().push(id);
            if target != source {
                view.edges_at.entry(target).or_default().push(id);
            }
        }
        view
    }
}

impl GraphRead for GraphView<'_> {
    fn node(&self, id: &str) -> Option<&Map<String, Value>> {
        self.nodes.get(id).copied()
    }

    fn edge(&self, id: &str) -> Option<&Map<String, Value>> {
        self.edges.get(id).copied()
    }

    fn edge_ids_at(&self, node_id: &str) -> impl Iterator<Item = &str> {
        self.edges_at.get(node_id).into_iter().flatten().copied()
    }
}

fn list<'a>(graph: &'a Value, key: &str) -> &'a [Value] {
    graph
        .get(key)
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .unwrap_or_default()
}

/// The indexes of the edges `target` adds relative to `base`, and of the edges it cuts.
///
/// Added edges are new edges, and edges that changed ([`edge_changed`]),
/// which a write deletes and adds again. A cut edge is one `target` keeps
/// unchanged while it removes the template field or output at one of its
/// ends. Applying that removal deletes the edge, so a target that keeps it
/// can never be replayed. Both graphs must be structurally sound.
///
/// # Errors
///
/// A compared value holds a number that is not finite, or an outputs list
/// that a write changes is not a valid keyed list.
pub fn changed_edges(base: &Value, target: &Value) -> Result<Vec<usize>> {
    let stored: HashMap<&str, &Map<String, Value>> = list(base, "edges")
        .iter()
        .filter_map(Value::as_object)
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
fn removed_ends(base: &Value, target: &Value) -> Result<HashMap<String, RemovedEnds>> {
    let stored: HashMap<&str, &Map<String, Value>> = list(base, "nodes")
        .iter()
        .filter_map(Value::as_object)
        .map(|node| (node.id(), node))
        .collect();
    let mut removed = HashMap::new();
    for node in list(target, "nodes").iter().filter_map(Value::as_object) {
        let Some(stored) = stored.get(node.id()) else {
            continue;
        };
        let fields = removed_fields(template(stored)?, template(node)?);
        let outputs = removed_outputs(node_body(stored)?, node_body(node)?, node.id())?;
        if !fields.is_empty() || !outputs.is_empty() {
            removed.insert(node.id().to_owned(), RemovedEnds { fields, outputs });
        }
    }
    Ok(removed)
}

/// A node's template. Structural validation keeps it an object.
fn template(node: &Map<String, Value>) -> Result<&Map<String, Value>> {
    node.template()
        .ok_or_else(|| Error::invalid("node data.node.template must be an object"))
}

/// The template keys `before` has and `after` does not.
fn removed_fields(before: &Map<String, Value>, after: &Map<String, Value>) -> HashSet<String> {
    before
        .keys()
        .filter(|key| !after.contains_key(*key))
        .cloned()
        .collect()
}

/// The output names `before` has and `after` does not. Outputs that compare
/// equal are not indexed, so a write that leaves them alone reads nothing.
fn removed_outputs(
    before: &Map<String, Value>,
    after: &Map<String, Value>,
    node_id: &str,
) -> Result<HashSet<String>> {
    let Some(outputs_before) = before.get("outputs") else {
        return Ok(HashSet::new());
    };
    let outputs_after = after.get("outputs");
    if let Some(outputs_after) = outputs_after
        && values_equal(outputs_before, outputs_after)?
    {
        return Ok(HashSet::new());
    }
    let kept: HashSet<String> = match outputs_after {
        Some(outputs_after) => index_outputs(outputs_after, node_id)?
            .names()
            .map(str::to_owned)
            .collect(),
        None => HashSet::new(),
    };
    Ok(index_outputs(outputs_before, node_id)?
        .names()
        .filter(|name| !kept.contains(*name))
        .map(str::to_owned)
        .collect())
}

/// Whether a kept edge leaves from or enters a field or output the write removes.
///
/// Applying the removal reads the handles of every edge at that node
/// strictly, so an edge there whose handles cannot be read counts too, and
/// the edge rules report it.
fn is_cut(edge: &Map<String, Value>, removed: &HashMap<String, RemovedEnds>) -> bool {
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

/// The edge rules broken by the edges `target` adds, rewires or cuts relative to `base`.
///
/// `target` must be structurally sound: unique ids, and edges whose endpoints
/// exist. Checking one edge reads the other edges into its input, so it can
/// fail on one of them: each violation is reported once, at the edge that
/// broke the rule.
///
/// # Errors
///
/// A check failed in a way that is not an edge rule.
pub fn find_edge_violations(base: &Value, target: &Value) -> Result<Vec<Violation>> {
    let indexes = changed_edges(base, target)?;
    if indexes.is_empty() {
        return Ok(Vec::new());
    }
    let view = GraphView::new(target);
    let mut edge_index = EdgeIndex::default();
    let edges = list(target, "edges");
    let index_of: HashMap<&str, usize> = edges
        .iter()
        .enumerate()
        .filter_map(|(index, edge)| Some((edge.as_object().map(EntryExt::id)?, index)))
        .collect();
    let mut violations: IndexMap<String, Violation> = IndexMap::new();
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

// --- Table rows ------------------------------------------------------------------------

/// A table value a write adds or changes, where it is, and its field's column definition.
#[derive(Debug)]
pub struct ChangedTable<'a> {
    /// Where the table value is: `nodes.<index>.data.node.template.<field>.value`.
    pub path: GraphPath,
    /// `None` when the node has no string id.
    pub node_id: Option<&'a str>,
    /// The name of the template field that holds the table.
    pub field: &'a str,
    #[expect(missing_docs, reason = "the name says what it is")]
    pub rows: &'a [Value],
    /// The field's `table_schema`, which declares its columns; `None` when it has none.
    pub table_schema: Option<&'a Value>,
}

/// The table values `target` adds or changes relative to `base`, in the order the graph lists them.
///
/// # Errors
///
/// A compared table holds a number that is not finite.
pub fn changed_tables<'a>(base: &Value, target: &'a Value) -> Result<Vec<ChangedTable<'a>>> {
    let mut stored: HashMap<&str, &Map<String, Value>> = HashMap::new();
    for node in list(base, "nodes") {
        if let (Some(template), Some(id)) =
            (node.template(), node.get("id").and_then(Value::as_str))
        {
            stored.entry(id).or_insert(template);
        }
    }
    let mut tables = Vec::new();
    for (index, node) in list(target, "nodes").iter().enumerate() {
        let Some(fields) = node.template() else {
            continue;
        };
        let node_id = node.get("id").and_then(Value::as_str);
        let stored_fields = node_id.and_then(|id| stored.get(id));
        for (name, field) in fields {
            let Some(Value::Array(rows)) = field.as_object().and_then(|field| field.get("value"))
            else {
                continue;
            };
            // Only tables: a natural-key list (tool actions) is not one, even under a table-typed field.
            if !NODE_SCHEMA.is_table_at(node, &field_value_path(name)) {
                continue;
            }
            let stored_value = stored_fields
                .and_then(|fields| fields.get(name))
                .and_then(Value::as_object)
                .and_then(|field| field.get("value"));
            if let Some(stored_value) = stored_value
                && values_equal(stored_value, &field["value"])?
            {
                continue;
            }
            tables.push(ChangedTable {
                path: vec![
                    "nodes".into(),
                    index.into(),
                    "data".into(),
                    "node".into(),
                    "template".into(),
                    name.as_str().into(),
                    "value".into(),
                ],
                node_id,
                field: name,
                rows,
                table_schema: field.get("table_schema"),
            });
        }
    }
    Ok(tables)
}

/// The column and row rules broken by table values `target` adds or changes relative to `base`.
///
/// # Errors
///
/// A compared table holds a number that is not finite.
pub fn find_table_violations(base: &Value, target: &Value) -> Result<Vec<Violation>> {
    let mut violations = Vec::new();
    for table in changed_tables(base, target)? {
        if let Some(table_schema) = table.table_schema {
            let field_path = &table.path[..table.path.len() - 1];
            let schema_path = path_of(field_path, &["table_schema"]);
            violations.extend(table_column_violations(table_schema, &schema_path));
        }
        violations.extend(table_row_violations(table.rows, &table.path));
    }
    Ok(violations)
}

/// A violation for every column `table_schema` names after a row key.
///
/// `table_schema` is a list of columns, or an object whose `columns` is that
/// list. `path` is where `table_schema` is. Anything else declares no columns.
#[must_use]
pub fn table_column_violations(table_schema: &Value, path: &[PathPart]) -> Vec<Violation> {
    let (columns, columns_path) = match table_schema {
        Value::Object(schema) => (schema.get("columns"), path_of(path, &["columns"])),
        list => (Some(list), path.to_vec()),
    };
    let Some(Value::Array(columns)) = columns else {
        return Vec::new();
    };
    let mut violations = Vec::new();
    for (index, column) in columns.iter().enumerate() {
        let Some(name) = column.get("name").and_then(Value::as_str) else {
            continue;
        };
        if is_row_key(name) {
            let mut name_path = columns_path.clone();
            name_path.extend([index.into(), "name".into()]);
            violations.push(Violation::new(
                ViolationCode::TableColumnReserved,
                name_path,
                format!("table column must not be named {name}"),
            ));
        }
    }
    violations
}

/// Whether `name` is one of the two keys the engine owns in every table row.
fn is_row_key(name: &str) -> bool {
    let keys = &NODE_SCHEMA.table_keys;
    name == keys.id || name == keys.position
}

/// The row rules one table value breaks.
#[must_use]
pub fn table_row_violations(rows: &[Value], path: &[PathPart]) -> Vec<Violation> {
    let (id_key, position_key) = (&NODE_SCHEMA.table_keys.id, &NODE_SCHEMA.table_keys.position);
    let mut violations = Vec::new();
    let mut seen = HashSet::new();
    for (index, row) in rows.iter().enumerate() {
        let row_path: GraphPath = path.iter().cloned().chain([index.into()]).collect();
        let Value::Object(row) = row else {
            violations.push(Violation::new(
                ViolationCode::TableRowNotObject,
                row_path,
                "table row must be an object",
            ));
            continue;
        };
        match row.non_empty_str(id_key) {
            None => violations.push(Violation::new(
                ViolationCode::TableRowIdMissing,
                path_of(&row_path, &[id_key]),
                format!("table row must have a non-empty string {id_key}"),
            )),
            Some(id) if !seen.insert(id) => violations.push(Violation::new(
                ViolationCode::TableRowIdDuplicate,
                path_of(&row_path, &[id_key]),
                "duplicate row id",
            )),
            Some(_) => {}
        }
        if !row.get(position_key).is_some_and(is_row_position) {
            violations.push(Violation::new(
                ViolationCode::TableRowPosInvalid,
                path_of(&row_path, &[position_key]),
                format!("table row must have a finite numeric {position_key}"),
            ));
        }
    }
    violations
}
