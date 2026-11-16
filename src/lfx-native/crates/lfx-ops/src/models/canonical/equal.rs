//! The canonical form of a graph, and [`graphs_equal`], which compares two forms.

use crate::data::maps::{HashMap, HashSet, State};
use crate::data::value::{AnyMap, AnyValue};

use crate::models::canonical::number::finite_double;
use crate::models::canonical::text::canonical_json;
use crate::models::canonical::{JsonType, TYPE_LIST_KEYS, values_equal};
use crate::models::error::Result;
use crate::models::handle::{HANDLE_KEYS, handle_spells, parse_handle};
use crate::models::schema::{KeyedList, NODE_SCHEMA, OUTPUTS_PATH, field_value_path};

// --- The canonical form of a graph --------------------------------------------------------

/// A graph's canonical form, sharing every value it does not change.
#[derive(Debug)]
pub(super) enum Canon<'a> {
    /// A value taken as it is.
    Raw(&'a AnyValue),
    /// A built value: a handle's object, or an edge's `data` with type sets.
    Owned(AnyValue),
    /// An object with some members changed, or a collection keyed by id.
    Object(HashMap<&'a str, Canon<'a>>),
    /// A collection ordered for serialization.
    Array(Vec<Canon<'a>>),
    /// A node taken as it is, made canonical only when it differs.
    Node(&'a AnyValue),
    /// An edge taken as it is, made canonical only when it differs.
    Edge(&'a AnyValue),
}

fn without(map: &AnyMap, hidden: impl Fn(&str) -> bool) -> HashMap<&str, Canon<'_>> {
    map.iter()
        .filter(|(key, _)| !hidden(key))
        .map(|(key, value)| (key.as_str(), Canon::Raw(value)))
        .collect()
}

/// A graph's canonical form for comparison, with its collections keyed by id.
pub(super) fn canonical_graph(flow: &AnyValue) -> Canon<'_> {
    let AnyValue::Object(flow) = flow else {
        return Canon::Raw(flow);
    };
    let mut graph = without(flow, |key| NODE_SCHEMA.is_flow_view_state(key));
    for (key, wrap) in [("nodes", Canon::Node as fn(_) -> _), ("edges", Canon::Edge)] {
        if let Some(Canon::Raw(AnyValue::Array(entries))) = graph.get(key) {
            graph.insert(key, by_id(entries, wrap));
        }
    }
    Canon::Object(graph)
}

/// A keyed list's items, keyed by item key for comparison. A list with a
/// missing or repeated key keeps its array.
fn keyed_items<'a>(keyed: &KeyedList, list: &'a AnyValue) -> Canon<'a> {
    let AnyValue::Array(items) = list else {
        return Canon::Raw(list);
    };
    let mut by_key = HashMap::with_capacity_and_hasher(items.len(), State::default());
    for item in items {
        match keyed.key_of(item) {
            Some(key) if !by_key.contains_key(key) => {
                by_key.insert(key, Canon::Raw(item));
            }
            _ => return Canon::Raw(list),
        }
    }
    Canon::Object(by_key)
}

/// Map each entry's id to it, or keep the list when an entry has no string id or two share one.
fn by_id<'a>(entries: &'a [AnyValue], wrap: fn(&'a AnyValue) -> Canon<'a>) -> Canon<'a> {
    let ids: Option<Vec<&'a str>> = entries
        .iter()
        .map(|entry| entry.as_object()?.get("id")?.as_str())
        .collect();
    let entries = entries.iter().map(wrap);
    let Some(ids) = ids else {
        return Canon::Array(entries.collect());
    };
    let mut seen = HashSet::with_capacity_and_hasher(ids.len(), State::default());
    if !ids.iter().all(|id| seen.insert(*id)) {
        return Canon::Array(entries.collect());
    }
    Canon::Object(ids.into_iter().zip(entries).collect())
}

pub(super) fn canonical_node(node: &AnyValue) -> Canon<'_> {
    let AnyValue::Object(node_map) = node else {
        return Canon::Raw(node);
    };
    let mut canon = without(node_map, |key| NODE_SCHEMA.node_view_state.contains(key));
    let Some(AnyValue::Object(data)) = node_map.get("data") else {
        return Canon::Object(canon);
    };
    let Some(AnyValue::Object(body)) = data.get("node") else {
        return Canon::Object(canon);
    };
    let mut canon_body = without(body, |key| NODE_SCHEMA.node_data_view_state.contains(key));
    if let (Some(outputs), Some(keyed)) = (
        body.get("outputs"),
        NODE_SCHEMA.natural_list_at(&OUTPUTS_PATH),
    ) {
        canon_body.insert("outputs", keyed_items(keyed, outputs));
    }
    if let Some(AnyValue::Object(template)) = body.get("template") {
        let fields = template
            .iter()
            .filter(|(key, _)| !NODE_SCHEMA.template_view_state.contains(key.as_str()))
            .map(|(key, field)| (key.as_str(), canonical_field(node, key, field)))
            .collect();
        canon_body.insert("template", Canon::Object(fields));
    }
    let mut canon_data = without(data, |_| false);
    canon_data.insert("node", Canon::Object(canon_body));
    canon.insert("data", Canon::Object(canon_data));
    Canon::Object(canon)
}

/// A template field without its display-only keys, its keyed list keyed.
fn canonical_field<'a>(node: &'a AnyValue, key: &str, field: &'a AnyValue) -> Canon<'a> {
    let AnyValue::Object(field_map) = field else {
        return Canon::Raw(field);
    };
    let mut canon = without(field_map, |key| NODE_SCHEMA.field_view_state.contains(key));
    if let Some(value) = field_map.get("value")
        && let Some(keyed) = NODE_SCHEMA.keyed_list_at(node, &field_value_path(key))
    {
        canon.insert("value", keyed_items(keyed, value));
    }
    Canon::Object(canon)
}

/// An edge without its view state, its handles as objects with type sets.
pub(super) fn canonical_edge(edge: &AnyValue) -> Result<Canon<'_>> {
    let AnyValue::Object(edge_map) = edge else {
        return Ok(Canon::Raw(edge));
    };
    let mut canon = without(edge_map, |key| NODE_SCHEMA.edge_view_state.contains(key));
    for key in HANDLE_KEYS {
        if let Some(parsed) = edge_map.get(key).and_then(parse_handle) {
            let handle = handle_with_type_sets(AnyValue::Object(parsed))?;
            canon.insert(key, Canon::Owned(handle));
        }
    }
    if let Some(data) = edge_map.get("data") {
        canon.insert("data", Canon::Owned(edge_data_with_type_sets(data)?));
    }
    Ok(Canon::Object(canon))
}

/// A handle object with each type list sorted and without repeats. Any other
/// value is returned as it is.
///
/// # Errors
///
/// A type holds a number that is not finite.
pub(crate) fn handle_with_type_sets(mut handle: AnyValue) -> Result<AnyValue> {
    if let AnyValue::Object(map) = &mut handle {
        for key in TYPE_LIST_KEYS {
            if let Some(AnyValue::Array(types)) = map.get_mut(key) {
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
pub(crate) fn edge_data_with_type_sets(data: &AnyValue) -> Result<AnyValue> {
    let mut data = data.clone();
    if let AnyValue::Object(map) = &mut data {
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
pub(super) enum View<'c, 'a> {
    /// An object the canonical form rebuilt, or a collection keyed by id.
    Object(&'c HashMap<&'a str, Canon<'a>>),
    /// A collection the canonical form ordered for serialization.
    Array(&'c [Canon<'a>]),
    /// A value the canonical form shares with the graph, or a handle's object.
    Value(&'c AnyValue),
    /// A node taken as it is ([`Canon::Node`]). Only [`canon_equal`] reads it.
    Node(&'a AnyValue),
    Edge(&'a AnyValue),
}

impl<'c, 'a> View<'c, 'a> {
    pub(super) fn of(canon: &'c Canon<'a>) -> Self {
        match canon {
            Canon::Raw(value) => Self::Value(value),
            Canon::Owned(value) => Self::Value(value),
            Canon::Object(map) => Self::Object(map),
            Canon::Array(items) => Self::Array(items),
            Canon::Node(node) => Self::Node(node),
            Canon::Edge(edge) => Self::Edge(edge),
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
            Self::Value(AnyValue::Object(map)) => map.len(),
            Self::Value(AnyValue::Array(items)) => items.len(),
            Self::Value(_) => 0,
            Self::Node(_) | Self::Edge(_) => unreachable!("{NODE_READ}"),
        }
    }

    fn member(self, key: &str) -> Option<Self> {
        match self {
            Self::Object(map) => map.get(key).map(Self::of),
            Self::Value(AnyValue::Object(map)) => map.get(key).map(Self::Value),
            Self::Array(_) | Self::Value(_) => None,
            Self::Node(_) | Self::Edge(_) => unreachable!("{NODE_READ}"),
        }
    }

    fn item(self, index: usize) -> Option<Self> {
        match self {
            Self::Array(items) => items.get(index).map(Self::of),
            Self::Value(AnyValue::Array(items)) => items.get(index).map(Self::Value),
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
            Self::Value(AnyValue::Object(map)) => {
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

const NODE_READ: &str = "canon_equal makes a node canonical before it reads it";

/// Nodes proven equal: the left node's entries address maps to a copy of the
/// left node and the right node's entries address. The copy makes a write to
/// the left node copy it first, so a changed node gets a new address.
pub(crate) type Proven = HashMap<usize, (AnyMap, usize)>;

pub(super) fn canon_equal(
    left: View<'_, '_>,
    right: View<'_, '_>,
    proven: Option<&Proven>,
) -> Result<bool> {
    match (left, right) {
        (View::Value(left), View::Value(right)) => return values_equal(left, right),
        (View::Node(left), View::Node(right)) => return nodes_equal(left, right, proven),
        (View::Edge(left), View::Edge(right)) => {
            // Equal edges whose handles spell their `data` handles have one
            // canonical form, and `values_equal` checked all its numbers.
            if matches!(values_equal(left, right), Ok(true)) && handles_spell_data(left) {
                return Ok(true);
            }
            let (left, right) = (canonical_edge(left)?, canonical_edge(right)?);
            return canon_equal(View::of(&left), View::of(&right), proven);
        }
        (View::Edge(edge), other) | (other, View::Edge(edge)) => {
            let edge = canonical_edge(edge)?;
            return canon_equal(View::of(&edge), other, proven);
        }
        (View::Node(node), other) | (other, View::Node(node)) => {
            let node = canonical_node(node);
            return canon_equal(View::of(&node), other, proven);
        }
        _ => {}
    }
    let kind = left.json_type();
    if kind != right.json_type() || left.len() != right.len() {
        return Ok(false);
    }
    if kind == JsonType::Object {
        return left.all_members(|key, value| match right.member(key) {
            Some(other) => canon_equal(value, other, proven),
            None => Ok(false),
        });
    }
    for index in 0..left.len() {
        match (left.item(index), right.item(index)) {
            (Some(a), Some(b)) if canon_equal(a, b, proven)? => {}
            _ => return Ok(false),
        }
    }
    Ok(true)
}

/// Whether each handle string of `edge` spells the same handle in its `data`.
fn handles_spell_data(edge: &AnyValue) -> bool {
    let Some(edge) = edge.as_object() else {
        return false;
    };
    let data = edge.get("data").and_then(AnyValue::as_object);
    HANDLE_KEYS.iter().all(|key| match edge.get(key) {
        None => true,
        Some(AnyValue::String(text)) => data
            .and_then(|data| data.get(key))
            .and_then(AnyValue::as_object)
            .is_some_and(|object| handle_spells(text, object)),
        Some(_) => false,
    })
}

/// Whether two nodes have the same canonical form.
///
/// Nodes equal as they are skip the canonical form. The form parses nothing,
/// so it cannot make them differ or fail.
fn nodes_equal(left: &AnyValue, right: &AnyValue, proven: Option<&Proven>) -> Result<bool> {
    if let (Some(l), Some(r)) = (left.as_object(), right.as_object())
        && proven.is_some_and(|proven| {
            proven
                .get(&l.entries_ptr())
                .is_some_and(|(_, right)| *right == r.entries_ptr())
        })
    {
        return Ok(true);
    }
    if matches!(values_equal(left, right), Ok(true)) {
        return Ok(true);
    }
    let (left, right) = (canonical_node(left), canonical_node(right));
    canon_equal(View::of(&left), View::of(&right), proven)
}

/// Whether two flows are the same graph, stopping at the first difference.
///
/// # Errors
///
/// Either graph has a number that [`graph_hash`](super::graph_hash) refuses.
pub fn graphs_equal(left: &AnyValue, right: &AnyValue) -> Result<bool> {
    graphs_equal_given(left, right, None)
}

/// [`graphs_equal`], with the nodes in `proven` taken as equal.
pub(crate) fn graphs_equal_given(
    left: &AnyValue,
    right: &AnyValue,
    proven: Option<&Proven>,
) -> Result<bool> {
    let left = canonical_graph(left);
    let right = canonical_graph(right);
    let equal = canon_equal(View::of(&left), View::of(&right), proven)?;
    // Check unequal graphs to the end, so an infinite number always fails,
    // wherever the first difference is.
    if !equal {
        check_finite(View::of(&left))?;
        check_finite(View::of(&right))?;
    }
    Ok(equal)
}

/// Refuse a number in a canonical form that is not finite.
fn check_finite(view: View<'_, '_>) -> Result<()> {
    match view {
        View::Value(value) => check_finite_value(value),
        View::Object(map) => map
            .values()
            .try_for_each(|value| check_finite(View::of(value))),
        View::Array(items) => items
            .iter()
            .try_for_each(|item| check_finite(View::of(item))),
        // A node that is finite as it is has a finite canonical form.
        View::Node(node) => {
            check_finite_value(node).or_else(|_| check_finite(View::of(&canonical_node(node))))
        }
        View::Edge(edge) => check_finite(View::of(&canonical_edge(edge)?)),
    }
}

fn check_finite_value(value: &AnyValue) -> Result<()> {
    match value {
        AnyValue::Number(number) => finite_double(number).map(drop),
        AnyValue::Array(items) => items.iter().try_for_each(check_finite_value),
        AnyValue::Object(map) => map.values().try_for_each(check_finite_value),
        AnyValue::Null | AnyValue::Bool(_) | AnyValue::String(_) => Ok(()),
    }
}
