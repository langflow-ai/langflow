//! Canonical text: [`canonical_json`] of a value and [`graph_hash`] of a graph.

use std::borrow::Cow;
use std::cmp::Ordering;
use std::fmt::Write as _;
use std::io::Write as _;

use crate::data::json_out::{self, Ascii};
use crate::data::value::{AnyMap, AnyString, AnyValue, Number};
use sha2::{Digest, Sha256};

use crate::models::canonical::number::{MAX_SAFE_INTEGER, finite_double, format_double, utf16_cmp};
use crate::models::error::Result;
use crate::models::handle::{HANDLE_KEYS, parse_handle};
use crate::models::keyed::item_order;
use crate::models::schema::{KeyedList, NODE_SCHEMA, OUTPUTS_PATH, field_value_path};

/// Print a number as RFC 8785 does, which is JavaScript's `Number::toString`.
fn format_number(number: &Number, out: &mut Sink) -> Result<()> {
    let double = finite_double(number)?;
    if number.is_integer() {
        // An integer prints exactly while JavaScript holds it exactly.
        if let Some(integer) = number.as_i128()
            && integer.abs() <= MAX_SAFE_INTEGER
        {
            write!(out.buf, "{integer}").ok();
            return Ok(());
        }
    }
    format_double(double, &mut out.buf);
    Ok(())
}

/// The canonical text that a [`Sink`] holds before it gives it to the hash.
const HASH_CHUNK: usize = 1 << 16;

/// Where canonical text goes: memory, or the hash, a chunk at a time.
pub(super) struct Sink {
    buf: Vec<u8>,
    hash: Option<Sha256>,
}

impl Sink {
    pub(super) fn text() -> Self {
        Self {
            buf: Vec::new(),
            hash: None,
        }
    }

    fn hash() -> Self {
        Self {
            buf: Vec::with_capacity(HASH_CHUNK + HASH_CHUNK / 2),
            hash: Some(Sha256::new()),
        }
    }

    fn put(&mut self, text: &[u8]) {
        self.buf.extend_from_slice(text);
    }

    /// Give the text to the hash once a chunk of it is held.
    fn pass_on(&mut self) {
        if let Some(hash) = &mut self.hash
            && self.buf.len() >= HASH_CHUNK
        {
            hash.update(&self.buf);
            self.buf.clear();
        }
    }

    pub(super) fn into_text(self) -> String {
        json_out::into_string(self.buf)
    }

    fn into_hex_digest(mut self) -> String {
        let mut hash = self.hash.take().expect("a hash sink");
        hash.update(&self.buf);
        let mut hex = String::with_capacity(64);
        for byte in hash.finalize() {
            write!(hex, "{byte:02x}").ok();
        }
        hex
    }
}

/// Write a string as RFC 8785 does, which is how [`json_out`] writes it.
fn write_string(value: &str, out: &mut Sink) {
    json_out::write_str(&mut out.buf, value, Ascii::Keep);
}

fn write_canonical(value: &AnyValue, out: &mut Sink) -> Result<()> {
    match value {
        AnyValue::Null => out.put(b"null"),
        AnyValue::Bool(true) => out.put(b"true"),
        AnyValue::Bool(false) => out.put(b"false"),
        AnyValue::Number(number) => format_number(number, out)?,
        AnyValue::String(string) => write_string(string, out),
        AnyValue::Array(items) => write_list(out, (b'[', b']'), items, write_canonical)?,
        AnyValue::Object(map) => {
            let write_entry = |(key, value): (&AnyString, &AnyValue), out: &mut Sink| {
                write_string(key, out);
                out.put(b":");
                write_canonical(value, out)
            };
            // Most objects keep the order they were written in, often sorted.
            if map.keys().is_sorted_by(|a, b| utf16_cmp(a, b).is_lt()) {
                write_list(out, (b'{', b'}'), map.iter(), write_entry)?;
            } else {
                let mut entries: Vec<(&AnyString, &AnyValue)> = map.iter().collect();
                entries.sort_by(|a, b| utf16_cmp(a.0, b.0));
                write_list(out, (b'{', b'}'), entries, write_entry)?;
            }
        }
    }
    Ok(())
}

/// Serialize a JSON value in RFC 8785 canonical form.
///
/// # Errors
///
/// A number that is not finite as JavaScript reads it.
pub fn canonical_json(value: &AnyValue) -> Result<String> {
    let mut out = Sink::text();
    write_canonical(value, &mut out)?;
    Ok(out.into_text())
}

// --- The canonical text of a graph ----------------------------------------------------

/// A member of a graph's canonical form, for its text. A node's form exists
/// only while the node is written.
#[derive(Debug)]
pub(super) enum Part<'a> {
    /// A value taken as it is.
    Raw(&'a AnyValue),
    /// A value the form built: the object a handle string encodes.
    Owned(AnyValue),
    /// An object with some members changed.
    Object(Parts<'a>),
    /// A keyed list's items, in the list's order ([`item_order`]).
    Items(Vec<&'a AnyValue>),
    /// A graph's nodes, written in order of id.
    Nodes(Vec<Cow<'a, AnyValue>>),
    /// A graph's edges, written in order of id.
    Edges(Vec<EdgeIn<'a>>),
}

/// An object's members in canonical form, in no order.
type Parts<'a> = Vec<(&'a str, Part<'a>)>;

/// An edge as a graph holds it: an item of its list, or a loaded edge's object.
#[derive(Debug, Clone, Copy)]
pub(super) enum EdgeIn<'a> {
    Value(&'a AnyValue),
    Map(&'a AnyMap),
}

/// The members of an object without the ones `hidden` names.
fn visible(map: &AnyMap, hidden: impl Fn(&str) -> bool) -> Parts<'_> {
    map.iter()
        .filter(|(key, _)| !hidden(key))
        .map(|(key, value)| (key.as_str(), Part::Raw(value)))
        .collect()
}

/// Set a member: in its place when the object has it, last otherwise.
fn set<'a>(parts: &mut Parts<'a>, key: &'a str, part: Part<'a>) {
    match parts.iter_mut().find(|(at, _)| *at == key) {
        Some(slot) => slot.1 = part,
        None => parts.push((key, part)),
    }
}

/// A graph's top-level members in canonical form, without view state.
fn graph_parts(flow: &AnyMap) -> Parts<'_> {
    let mut parts = visible(flow, |key| NODE_SCHEMA.is_flow_view_state(key));
    for (key, part) in &mut parts {
        if let Part::Raw(AnyValue::Array(entries)) = part {
            match *key {
                "nodes" => *part = Part::Nodes(entries.iter().map(Cow::Borrowed).collect()),
                "edges" => *part = Part::Edges(entries.iter().map(EdgeIn::Value).collect()),
                _ => {}
            }
        }
    }
    parts
}

/// A keyed list's items in the list's order, or the value as it is when it is not a list.
fn ordered_items<'a>(keyed: &KeyedList, list: &'a AnyValue) -> Part<'a> {
    let AnyValue::Array(items) = list else {
        return Part::Raw(list);
    };
    Part::Items(
        item_order(keyed, items)
            .into_iter()
            .map(|slot| &items[slot])
            .collect(),
    )
}

/// [`canonical_node`](super::equal::canonical_node) for the hash, with keyed lists in their order.
fn node_part(node: &AnyValue) -> Part<'_> {
    let AnyValue::Object(node_map) = node else {
        return Part::Raw(node);
    };
    let mut parts = visible(node_map, |key| NODE_SCHEMA.node_view_state.contains(key));
    let Some(AnyValue::Object(data)) = node_map.get("data") else {
        return Part::Object(parts);
    };
    let Some(AnyValue::Object(body)) = data.get("node") else {
        return Part::Object(parts);
    };
    let mut body_parts = visible(body, |key| NODE_SCHEMA.node_data_view_state.contains(key));
    if let (Some(outputs), Some(keyed)) = (
        body.get("outputs"),
        NODE_SCHEMA.natural_list_at(&OUTPUTS_PATH),
    ) {
        set(&mut body_parts, "outputs", ordered_items(keyed, outputs));
    }
    if let Some(AnyValue::Object(template)) = body.get("template") {
        let fields = template
            .iter()
            .filter(|(key, _)| !NODE_SCHEMA.template_view_state.contains(key.as_str()))
            .map(|(key, field)| (key.as_str(), field_part(node, key, field)))
            .collect();
        set(&mut body_parts, "template", Part::Object(fields));
    }
    let mut data_parts = visible(data, |_| false);
    set(&mut data_parts, "node", Part::Object(body_parts));
    set(&mut parts, "data", Part::Object(data_parts));
    Part::Object(parts)
}

/// `canonical_field` for the hash, with a keyed list in its order.
fn field_part<'a>(node: &'a AnyValue, key: &str, field: &'a AnyValue) -> Part<'a> {
    let AnyValue::Object(field_map) = field else {
        return Part::Raw(field);
    };
    let mut parts = visible(field_map, |key| NODE_SCHEMA.field_view_state.contains(key));
    if let Some(value) = field_map.get("value")
        && let Some(keyed) = NODE_SCHEMA.keyed_list_at(node, &field_value_path(key))
    {
        set(&mut parts, "value", ordered_items(keyed, value));
    }
    Part::Object(parts)
}

/// [`canonical_edge`](super::equal::canonical_edge) for the hash, with type lists in their stored order.
fn edge_part(edge: EdgeIn<'_>) -> Part<'_> {
    let edge_map = match edge {
        EdgeIn::Map(map) | EdgeIn::Value(AnyValue::Object(map)) => map,
        EdgeIn::Value(other) => return Part::Raw(other),
    };
    let mut parts = visible(edge_map, |key| NODE_SCHEMA.edge_view_state.contains(key));
    for key in HANDLE_KEYS {
        if let Some(parsed) = edge_map.get(key).and_then(parse_handle) {
            set(&mut parts, key, Part::Owned(AnyValue::Object(parsed)));
        }
    }
    Part::Object(parts)
}

/// The `id` a node or an edge is ordered by, unless view state hides `id`.
fn entry_order_id(map: Option<&AnyMap>, hidden: bool) -> Option<&str> {
    if hidden {
        return None;
    }
    map?.get("id")?.as_str()
}

/// The indexes of `ids` sorted by id. Entries without an id come first.
fn id_order(ids: &[Option<&str>]) -> Vec<usize> {
    let mut order: Vec<usize> = (0..ids.len()).collect();
    order.sort_by(|&a, &b| match (ids[a], ids[b]) {
        (Some(a), Some(b)) => utf16_cmp(a, b),
        (None, Some(_)) => Ordering::Less,
        (Some(_), None) => Ordering::Greater,
        (None, None) => Ordering::Equal,
    });
    order
}

pub(super) fn write_part(part: Part<'_>, out: &mut Sink) -> Result<()> {
    match part {
        Part::Raw(value) => write_canonical(value, out),
        Part::Owned(value) => write_canonical(&value, out),
        Part::Object(mut parts) => {
            parts.sort_by(|a, b| utf16_cmp(a.0, b.0));
            write_list(out, (b'{', b'}'), parts, |(key, part), out| {
                write_string(key, out);
                out.put(b":");
                write_part(part, out)
            })
        }
        Part::Items(items) => write_list(out, (b'[', b']'), items, write_canonical),
        Part::Nodes(nodes) => {
            let hidden = NODE_SCHEMA.node_view_state.contains("id");
            let ids: Vec<Option<&str>> = nodes
                .iter()
                .map(|node| entry_order_id(node.as_object(), hidden))
                .collect();
            write_list(out, (b'[', b']'), id_order(&ids), |slot, out| {
                write_part(node_part(&nodes[slot]), out)
            })
        }
        Part::Edges(edges) => {
            let hidden = NODE_SCHEMA.edge_view_state.contains("id");
            let ids: Vec<Option<&str>> = edges
                .iter()
                .map(|edge| {
                    let map = match edge {
                        EdgeIn::Map(map) => Some(*map),
                        EdgeIn::Value(value) => value.as_object(),
                    };
                    entry_order_id(map, hidden)
                })
                .collect();
            write_list(out, (b'[', b']'), id_order(&ids), |slot, out| {
                write_part(edge_part(edges[slot]), out)
            })
        }
    }
}

/// Write `items` between `open` and `close`, separated by commas.
fn write_list<T>(
    out: &mut Sink,
    (open, close): (u8, u8),
    items: impl IntoIterator<Item = T>,
    mut write_item: impl FnMut(T, &mut Sink) -> Result<()>,
) -> Result<()> {
    out.buf.push(open);
    for (index, item) in items.into_iter().enumerate() {
        if index > 0 {
            out.buf.push(b',');
        }
        write_item(item, out)?;
        out.pass_on();
    }
    out.buf.push(close);
    Ok(())
}

/// The canonical form of flow data, to write.
pub(super) fn flow_part(flow: &AnyValue) -> Part<'_> {
    match flow {
        AnyValue::Object(map) => Part::Object(graph_parts(map)),
        other => Part::Raw(other),
    }
}

/// The SHA-256 hex digest of flow data's canonical graph form.
///
/// The text goes into the hash in chunks, so a large graph's text is never held.
///
/// # Errors
///
/// A number that is not finite as JavaScript reads it.
pub fn graph_hash(flow: &AnyValue) -> Result<String> {
    let mut out = Sink::hash();
    write_part(flow_part(flow), &mut out)?;
    Ok(out.into_hex_digest())
}

/// [`graph_hash`] of a loaded graph, from its top-level keys, nodes and edges.
pub(crate) fn loaded_graph_hash<'a>(
    root: &'a AnyMap,
    nodes: Vec<Cow<'a, AnyValue>>,
    edges: Vec<&'a AnyMap>,
) -> Result<String> {
    let mut parts = visible(root, |key| NODE_SCHEMA.is_flow_view_state(key));
    set(&mut parts, "nodes", Part::Nodes(nodes));
    set(
        &mut parts,
        "edges",
        Part::Edges(edges.into_iter().map(EdgeIn::Map).collect()),
    );
    let mut out = Sink::hash();
    write_part(Part::Object(parts), &mut out)?;
    Ok(out.into_hex_digest())
}
