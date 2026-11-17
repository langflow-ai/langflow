//! The canonical form of a graph, and [`graphs_equal`], which compares two forms.

use crate::collection::hash_map::{HashMap, HashSet, State};
use crate::json::{FlowObj, FlowValue};

use crate::compare::Result;
use crate::compare::graph_hash::canonical_json;
use crate::compare::{JsonType, TYPE_LIST_KEYS, values_equal};
use crate::flow::edge_handle::{HANDLE_KEYS, handle_spells, parse_handle};
use crate::flow::model::{FLOW_MODEL, KeyedList, OUTPUTS_PATH, field_value_path};
use crate::json::finite_double;

// --- The canonical form of a graph --------------------------------------------------------

/// A graph's canonical form, sharing every value it does not change.
#[derive(Debug)]
pub(super) enum CanonicalForm<'a> {
    /// A value taken as it is.
    Raw(&'a FlowValue),
    /// A built value: a handle's object, or an edge's `data` with type sets.
    Owned(FlowValue),
    /// An object with some members changed, or a collection keyed by id.
    Object(HashMap<&'a str, CanonicalForm<'a>>),
    /// A collection ordered for serialization.
    Array(Vec<CanonicalForm<'a>>),
    /// A node taken as it is, made canonical only when it differs.
    Node(&'a FlowValue),
    /// An edge taken as it is, made canonical only when it differs.
    Edge(&'a FlowValue),
}

fn without(map: &FlowObj, hidden: impl Fn(&str) -> bool) -> HashMap<&str, CanonicalForm<'_>> {
    map.iter()
        .filter(|(key, _)| !hidden(key))
        .map(|(key, value)| (key.as_str(), CanonicalForm::Raw(value)))
        .collect()
}

/// A graph's canonical form for comparison, with its collections keyed by id.
pub(super) fn canonical_graph(flow: &FlowValue) -> CanonicalForm<'_> {
    let FlowValue::Object(flow) = flow else {
        return CanonicalForm::Raw(flow);
    };
    let mut graph = without(flow, |key| FLOW_MODEL.is_flow_view_state(key));
    for (key, wrap) in [
        ("nodes", CanonicalForm::Node as fn(_) -> _),
        ("edges", CanonicalForm::Edge),
    ] {
        if let Some(CanonicalForm::Raw(FlowValue::Array(entries))) = graph.get(key) {
            graph.insert(key, by_id(entries, wrap));
        }
    }
    CanonicalForm::Object(graph)
}

/// A keyed list's items, keyed by item key for comparison. A list with a
/// missing or repeated key keeps its array.
fn keyed_items<'a>(keyed: &KeyedList, list: &'a FlowValue) -> CanonicalForm<'a> {
    let FlowValue::Array(items) = list else {
        return CanonicalForm::Raw(list);
    };
    let mut by_key = HashMap::with_capacity_and_hasher(items.len(), State::default());
    for item in items {
        match keyed.key_of(item) {
            Some(key) if !by_key.contains_key(key) => {
                by_key.insert(key, CanonicalForm::Raw(item));
            }
            _ => return CanonicalForm::Raw(list),
        }
    }
    CanonicalForm::Object(by_key)
}

/// Map each node's or edge's id to it, or keep the list when one has no string id or two share one.
fn by_id<'a>(
    entries: &'a [FlowValue],
    wrap: fn(&'a FlowValue) -> CanonicalForm<'a>,
) -> CanonicalForm<'a> {
    let ids: Option<Vec<&'a str>> = entries
        .iter()
        .map(|entry| entry.as_object()?.get("id")?.as_str())
        .collect();
    let entries = entries.iter().map(wrap);
    let Some(ids) = ids else {
        return CanonicalForm::Array(entries.collect());
    };
    let mut seen = HashSet::with_capacity_and_hasher(ids.len(), State::default());
    if !ids.iter().all(|id| seen.insert(*id)) {
        return CanonicalForm::Array(entries.collect());
    }
    CanonicalForm::Object(ids.into_iter().zip(entries).collect())
}

pub(super) fn canonical_node(node: &FlowValue) -> CanonicalForm<'_> {
    let FlowValue::Object(node_map) = node else {
        return CanonicalForm::Raw(node);
    };
    let mut canon = without(node_map, |key| FLOW_MODEL.node_view_state.contains(key));
    let Some(FlowValue::Object(data)) = node_map.get("data") else {
        return CanonicalForm::Object(canon);
    };
    let Some(FlowValue::Object(body)) = data.get("node") else {
        return CanonicalForm::Object(canon);
    };
    let mut canon_body = without(body, |key| FLOW_MODEL.node_data_view_state.contains(key));
    if let (Some(outputs), Some(keyed)) =
        (body.get("outputs"), FLOW_MODEL.named_list_at(&OUTPUTS_PATH))
    {
        canon_body.insert("outputs", keyed_items(keyed, outputs));
    }
    if let Some(FlowValue::Object(template)) = body.get("template") {
        let fields = template
            .iter()
            .filter(|(key, _)| !FLOW_MODEL.template_view_state.contains(key.as_str()))
            .map(|(key, field)| (key.as_str(), canonical_field(node, key, field)))
            .collect();
        canon_body.insert("template", CanonicalForm::Object(fields));
    }
    let mut canon_data = without(data, |_| false);
    canon_data.insert("node", CanonicalForm::Object(canon_body));
    canon.insert("data", CanonicalForm::Object(canon_data));
    CanonicalForm::Object(canon)
}

/// A template field without its display-only keys, its keyed list keyed.
fn canonical_field<'a>(node: &'a FlowValue, key: &str, field: &'a FlowValue) -> CanonicalForm<'a> {
    let FlowValue::Object(field_map) = field else {
        return CanonicalForm::Raw(field);
    };
    let mut canon = without(field_map, |key| FLOW_MODEL.field_view_state.contains(key));
    if let Some(value) = field_map.get("value")
        && let Some(keyed) = FLOW_MODEL.keyed_list_at(node, &field_value_path(key))
    {
        canon.insert("value", keyed_items(keyed, value));
    }
    CanonicalForm::Object(canon)
}

/// An edge without its view state, its handles as objects with type sets.
pub(super) fn canonical_edge(edge: &FlowValue) -> Result<CanonicalForm<'_>> {
    let FlowValue::Object(edge_map) = edge else {
        return Ok(CanonicalForm::Raw(edge));
    };
    let mut canon = without(edge_map, |key| FLOW_MODEL.edge_view_state.contains(key));
    for key in HANDLE_KEYS {
        if let Some(parsed) = edge_map.get(key).and_then(parse_handle) {
            let handle = handle_with_type_sets(FlowValue::Object(parsed))?;
            canon.insert(key, CanonicalForm::Owned(handle));
        }
    }
    if let Some(data) = edge_map.get("data") {
        canon.insert(
            "data",
            CanonicalForm::Owned(edge_data_with_type_sets(data)?),
        );
    }
    Ok(CanonicalForm::Object(canon))
}

/// A handle object with each type list sorted and without repeats. Any other
/// value is returned as it is.
///
/// # Errors
///
/// A type holds a number that is not finite.
pub(crate) fn handle_with_type_sets(mut handle: FlowValue) -> Result<FlowValue> {
    if let FlowValue::Object(map) = &mut handle {
        for key in TYPE_LIST_KEYS {
            if let Some(FlowValue::Array(types)) = map.get_mut(key) {
                let mut by_text = std::mem::take(types)
                    .into_iter()
                    .map(|item| Ok((canonical_json(&item)?, item)))
                    .collect::<Result<Vec<_>>>()?;
                by_text.sort_by(|a, b| a.0.cmp(&b.0));
                by_text.dedup_by(|a, b| a.0 == b.0);
                *types = by_text.into_iter().map(|(_, item)| item).collect();
            }
        }
    }
    Ok(handle)
}

/// An edge's `data`, with [`handle_with_type_sets`] on each handle object in it.
///
/// # Errors
///
/// A type holds a number that is not finite.
pub(crate) fn edge_data_with_type_sets(data: &FlowValue) -> Result<FlowValue> {
    let mut data = data.clone();
    if let FlowValue::Object(map) = &mut data {
        for key in HANDLE_KEYS {
            if let Some(handle) = map.get_mut(key) {
                *handle = handle_with_type_sets(std::mem::take(handle))?;
            }
        }
    }
    Ok(data)
}

/// A read-only view of one position in a canonical form.
///
/// `'c` is the lifetime of the canonical form, and `'a` that of the graph it borrows from.
#[derive(Debug, Clone, Copy)]
pub(super) enum CanonicalRef<'c, 'a> {
    /// An object the canonical form rebuilt, or a collection keyed by id.
    Object(&'c HashMap<&'a str, CanonicalForm<'a>>),
    /// A collection the canonical form ordered for serialization.
    Array(&'c [CanonicalForm<'a>]),
    /// A value the canonical form shares with the graph, or a handle's object.
    Value(&'c FlowValue),
    /// A node taken as it is ([`CanonicalForm::Node`]). Only [`canonical_equal`] reads it.
    Node(&'a FlowValue),
    Edge(&'a FlowValue),
}

impl<'c, 'a> CanonicalRef<'c, 'a> {
    pub(super) fn of(canon: &'c CanonicalForm<'a>) -> Self {
        match canon {
            CanonicalForm::Raw(value) => Self::Value(value),
            CanonicalForm::Owned(value) => Self::Value(value),
            CanonicalForm::Object(map) => Self::Object(map),
            CanonicalForm::Array(items) => Self::Array(items),
            CanonicalForm::Node(node) => Self::Node(node),
            CanonicalForm::Edge(edge) => Self::Edge(edge),
        }
    }

    fn json_type(self) -> JsonType {
        match self {
            Self::Object(_) => JsonType::Object,
            Self::Array(_) => JsonType::Array,
            Self::Value(value) => JsonType::from(value),
            Self::Node(_) | Self::Edge(_) => unreachable!("{NODE_READ}"),
        }
    }

    fn len(self) -> usize {
        match self {
            Self::Object(map) => map.len(),
            Self::Array(items) => items.len(),
            Self::Value(FlowValue::Object(map)) => map.len(),
            Self::Value(FlowValue::Array(items)) => items.len(),
            Self::Value(_) => 0,
            Self::Node(_) | Self::Edge(_) => unreachable!("{NODE_READ}"),
        }
    }

    fn member(self, key: &str) -> Option<Self> {
        match self {
            Self::Object(map) => map.get(key).map(Self::of),
            Self::Value(FlowValue::Object(map)) => map.get(key).map(Self::Value),
            Self::Array(_) | Self::Value(_) => None,
            Self::Node(_) | Self::Edge(_) => unreachable!("{NODE_READ}"),
        }
    }

    fn item(self, index: usize) -> Option<Self> {
        match self {
            Self::Array(items) => items.get(index).map(Self::of),
            Self::Value(FlowValue::Array(items)) => items.get(index).map(Self::Value),
            Self::Object(_) | Self::Value(_) => None,
            Self::Node(_) | Self::Edge(_) => unreachable!("{NODE_READ}"),
        }
    }

    /// Whether `check` holds for every member of an object, stopping at a failure.
    fn all_members(self, mut check: impl FnMut(&str, Self) -> Result<bool>) -> Result<bool> {
        match self {
            Self::Object(map) => {
                for (key, value) in map {
                    if !check(key, Self::of(value))? {
                        return Ok(false);
                    }
                }
            }
            Self::Value(FlowValue::Object(map)) => {
                for (key, value) in map {
                    if !check(key, Self::Value(value))? {
                        return Ok(false);
                    }
                }
            }
            Self::Array(_) | Self::Value(_) => {}
            Self::Node(_) | Self::Edge(_) => unreachable!("{NODE_READ}"),
        }
        Ok(true)
    }
}

const NODE_READ: &str = "canonical_equal makes a node canonical before it reads it";

/// Nodes known to be equal: the address of the left node's keys and values maps to a copy of the
/// left node and the address of the right node's keys and values. The copy makes a write to
/// the left node copy it first, so a changed node gets a new address.
pub(crate) type KnownEqual = HashMap<usize, (FlowObj, usize)>;

pub(super) fn canonical_equal(
    left: CanonicalRef<'_, '_>,
    right: CanonicalRef<'_, '_>,
    known_equal: Option<&KnownEqual>,
) -> Result<bool> {
    match (left, right) {
        (CanonicalRef::Value(left), CanonicalRef::Value(right)) => {
            return values_equal(left, right);
        }
        (CanonicalRef::Node(left), CanonicalRef::Node(right)) => {
            return nodes_equal(left, right, known_equal);
        }
        (CanonicalRef::Edge(left), CanonicalRef::Edge(right)) => {
            // Equal edges whose handles spell their `data` handles have one
            // canonical form, and `values_equal` checked all its numbers.
            if matches!(values_equal(left, right), Ok(true)) && handles_spell_data(left) {
                return Ok(true);
            }
            let left = canonical_edge(left)?;
            let right = canonical_edge(right)?;
            return canonical_equal(
                CanonicalRef::of(&left),
                CanonicalRef::of(&right),
                known_equal,
            );
        }
        (CanonicalRef::Edge(edge), other) | (other, CanonicalRef::Edge(edge)) => {
            let edge = canonical_edge(edge)?;
            return canonical_equal(CanonicalRef::of(&edge), other, known_equal);
        }
        (CanonicalRef::Node(node), other) | (other, CanonicalRef::Node(node)) => {
            let node = canonical_node(node);
            return canonical_equal(CanonicalRef::of(&node), other, known_equal);
        }
        _ => {}
    }
    let kind = left.json_type();
    if kind != right.json_type() || left.len() != right.len() {
        return Ok(false);
    }
    if kind == JsonType::Object {
        return left.all_members(|key, value| match right.member(key) {
            Some(other) => canonical_equal(value, other, known_equal),
            None => Ok(false),
        });
    }
    for index in 0..left.len() {
        match (left.item(index), right.item(index)) {
            (Some(a), Some(b)) if canonical_equal(a, b, known_equal)? => {}
            _ => return Ok(false),
        }
    }
    Ok(true)
}

/// Whether each handle string of `edge` spells the same handle in its `data`.
fn handles_spell_data(edge: &FlowValue) -> bool {
    let Some(edge) = edge.as_object() else {
        return false;
    };
    let data = edge.get("data").and_then(FlowValue::as_object);
    HANDLE_KEYS.iter().all(|key| match edge.get(key) {
        None => true,
        Some(FlowValue::String(text)) => data
            .and_then(|data| data.get(key))
            .and_then(FlowValue::as_object)
            .is_some_and(|object| handle_spells(text, object)),
        Some(_) => false,
    })
}

/// Whether two nodes have the same canonical form.
///
/// Nodes equal as they are skip the canonical form. The form parses nothing,
/// so it cannot make them differ or fail.
fn nodes_equal(
    left: &FlowValue,
    right: &FlowValue,
    known_equal: Option<&KnownEqual>,
) -> Result<bool> {
    if let (Some(l), Some(r)) = (left.as_object(), right.as_object())
        && known_equal.is_some_and(|known_equal| {
            known_equal
                .get(&l.entries_ptr())
                .is_some_and(|(_, right)| *right == r.entries_ptr())
        })
    {
        return Ok(true);
    }
    if matches!(values_equal(left, right), Ok(true)) {
        return Ok(true);
    }
    let left = canonical_node(left);
    let right = canonical_node(right);
    canonical_equal(
        CanonicalRef::of(&left),
        CanonicalRef::of(&right),
        known_equal,
    )
}

/// Whether two flows are the same graph, stopping at the first difference.
///
/// # Errors
///
/// Either graph has a number that [`graph_hash`](fn@super::graph_hash) refuses.
pub fn graphs_equal(left: &FlowValue, right: &FlowValue) -> Result<bool> {
    graphs_equal_given(left, right, None)
}

/// [`graphs_equal`], with the nodes in `known_equal` taken as equal.
pub(crate) fn graphs_equal_given(
    left: &FlowValue,
    right: &FlowValue,
    known_equal: Option<&KnownEqual>,
) -> Result<bool> {
    let left = canonical_graph(left);
    let right = canonical_graph(right);
    let equal = canonical_equal(
        CanonicalRef::of(&left),
        CanonicalRef::of(&right),
        known_equal,
    )?;
    // Check unequal graphs to the end, so an infinite number always fails,
    // wherever the first difference is.
    if !equal {
        check_finite(CanonicalRef::of(&left))?;
        check_finite(CanonicalRef::of(&right))?;
    }
    Ok(equal)
}

/// Refuse a number in a canonical form that is not finite.
fn check_finite(view: CanonicalRef<'_, '_>) -> Result<()> {
    match view {
        CanonicalRef::Value(value) => check_finite_value(value),
        CanonicalRef::Object(map) => map
            .values()
            .try_for_each(|value| check_finite(CanonicalRef::of(value))),
        CanonicalRef::Array(items) => items
            .iter()
            .try_for_each(|item| check_finite(CanonicalRef::of(item))),
        // A node that is finite as it is has a finite canonical form.
        CanonicalRef::Node(node) => check_finite_value(node)
            .or_else(|_| check_finite(CanonicalRef::of(&canonical_node(node)))),
        CanonicalRef::Edge(edge) => check_finite(CanonicalRef::of(&canonical_edge(edge)?)),
    }
}

fn check_finite_value(value: &FlowValue) -> Result<()> {
    match value {
        FlowValue::Number(number) => finite_double(number).map(drop),
        FlowValue::Array(items) => items.iter().try_for_each(check_finite_value),
        FlowValue::Object(map) => map.values().try_for_each(check_finite_value),
        FlowValue::Null | FlowValue::Bool(_) | FlowValue::String(_) => Ok(()),
    }
}
