//! Canonical text: [`canonical_json`] of a value and [`graph_hash`] of a graph.

use std::borrow::Cow;
use std::cmp::Ordering;
use std::fmt::Write as _;
use std::io::Write as _;

use crate::json::serialize::{self, Ascii};
use crate::json::{FlowObj, FlowStr, FlowValue, Number};
use sha2::{Digest, Sha256};

use crate::compare::Result;
use crate::flow::edge_handle::{HANDLE_KEYS, parse_handle};
use crate::flow::list::item_order;
use crate::flow::model::{FLOW_MODEL, KeyedList, OUTPUTS_PATH, field_value_path};
use crate::json::{finite_double, utf16_cmp};

/// Largest integer a JavaScript number holds exactly.
pub(crate) const MAX_SAFE_INTEGER: i128 = 1 << 53;
/// ECMAScript prints numbers below 1e21 in plain notation.
const MAX_PLAIN_EXPONENT: i32 = 21;
const MIN_PLAIN_EXPONENT: i32 = -6;

pub(crate) fn format_double(value: f64, out: &mut Vec<u8>) {
    if value == 0.0 {
        out.push(b'0');
        return;
    }
    if value < 0.0 {
        out.push(b'-');
    }
    // `{:e}` gives the same shortest digits as ECMAScript. Only the layout differs.
    let shortest = format!("{:e}", value.abs());
    let (mantissa, exponent) = shortest.split_once('e').unwrap_or((&shortest, "0"));
    let digits: String = mantissa.chars().filter(char::is_ascii_digit).collect();
    let k = i32::try_from(digits.len()).unwrap_or(i32::MAX);
    // value == 0.<digits> * 10^n
    let n = exponent.parse::<i32>().unwrap_or(0) + 1;
    let zeros = |out: &mut Vec<u8>, count: i32| {
        out.extend(std::iter::repeat_n(
            b'0',
            usize::try_from(count).unwrap_or(0),
        ));
    };
    if k <= n && n <= MAX_PLAIN_EXPONENT {
        out.extend_from_slice(digits.as_bytes());
        zeros(out, n - k);
    } else if 0 < n && n <= MAX_PLAIN_EXPONENT {
        let (whole, fraction) = digits.split_at(usize::try_from(n).unwrap_or(0));
        write!(out, "{whole}.{fraction}").ok();
    } else if MIN_PLAIN_EXPONENT < n && n <= 0 {
        out.extend_from_slice(b"0.");
        zeros(out, -n);
        out.extend_from_slice(digits.as_bytes());
    } else {
        let e = n - 1;
        let (first, rest) = digits.split_at(1);
        out.extend_from_slice(first.as_bytes());
        if !rest.is_empty() {
            write!(out, ".{rest}").ok();
        }
        write!(out, "e{}{}", if e >= 0 { '+' } else { '-' }, e.abs()).ok();
    }
}

/// Print a number as RFC 8785 does, which is JavaScript's `Number::toString`.
fn format_number(number: &Number, out: &mut HashWriter) -> Result<()> {
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

/// The canonical text that a [`HashWriter`] holds before it gives it to the hash.
const HASH_CHUNK: usize = 1 << 16;

/// Where canonical text goes: memory, or the hash, a chunk at a time.
pub(super) struct HashWriter {
    buf: Vec<u8>,
    hash: Option<Sha256>,
}

impl HashWriter {
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
        serialize::into_string(self.buf)
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

/// Write a string as RFC 8785 does, which is how [`serialize`] writes it.
fn write_string(value: &str, out: &mut HashWriter) {
    serialize::write_str(&mut out.buf, value, Ascii::Keep);
}

fn write_canonical(value: &FlowValue, out: &mut HashWriter) -> Result<()> {
    match value {
        FlowValue::Null => out.put(b"null"),
        FlowValue::Bool(true) => out.put(b"true"),
        FlowValue::Bool(false) => out.put(b"false"),
        FlowValue::Number(number) => format_number(number, out)?,
        FlowValue::String(string) => write_string(string, out),
        FlowValue::Array(items) => write_list(out, (b'[', b']'), items, write_canonical)?,
        FlowValue::Object(map) => {
            let write_entry = |(key, value): (&FlowStr, &FlowValue), out: &mut HashWriter| {
                write_string(key, out);
                out.put(b":");
                write_canonical(value, out)
            };
            // Most objects keep the order they were written in, often sorted.
            if map.keys().is_sorted_by(|a, b| utf16_cmp(a, b).is_lt()) {
                write_list(out, (b'{', b'}'), map.iter(), write_entry)?;
            } else {
                let mut entries: Vec<(&FlowStr, &FlowValue)> = map.iter().collect();
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
pub fn canonical_json(value: &FlowValue) -> Result<String> {
    let mut out = HashWriter::text();
    write_canonical(value, &mut out)?;
    Ok(out.into_text())
}

// --- The canonical text of a graph ----------------------------------------------------

/// A member of a graph's canonical form, for its text. A node's form exists
/// only while the node is written.
#[derive(Debug)]
pub(super) enum HashPart<'a> {
    /// A value taken as it is.
    Raw(&'a FlowValue),
    /// A value the form built: the object a handle string encodes.
    Owned(FlowValue),
    /// An object with some members changed.
    Object(HashParts<'a>),
    /// A keyed list's items, in the list's order ([`item_order`]).
    Items(Vec<&'a FlowValue>),
    /// A graph's nodes, written in order of id.
    Nodes(Vec<Cow<'a, FlowValue>>),
    /// A graph's edges, written in order of id.
    Edges(Vec<EdgeIn<'a>>),
}

/// An object's members in canonical form, in no order.
type HashParts<'a> = Vec<(&'a str, HashPart<'a>)>;

/// An edge as a graph holds it: an item of its list, or a loaded edge's object.
#[derive(Debug, Clone, Copy)]
pub(super) enum EdgeIn<'a> {
    Value(&'a FlowValue),
    Map(&'a FlowObj),
}

/// The members of an object without the ones `hidden` names.
fn visible(map: &FlowObj, hidden: impl Fn(&str) -> bool) -> HashParts<'_> {
    map.iter()
        .filter(|(key, _)| !hidden(key))
        .map(|(key, value)| (key.as_str(), HashPart::Raw(value)))
        .collect()
}

/// Set a member: in its place when the object has it, last otherwise.
fn set<'a>(parts: &mut HashParts<'a>, key: &'a str, part: HashPart<'a>) {
    match parts.iter_mut().find(|(at, _)| *at == key) {
        Some(existing) => existing.1 = part,
        None => parts.push((key, part)),
    }
}

/// A graph's top-level members in canonical form, without view state.
fn graph_parts(flow: &FlowObj) -> HashParts<'_> {
    let mut parts = visible(flow, |key| FLOW_MODEL.is_flow_view_state(key));
    for (key, part) in &mut parts {
        if let HashPart::Raw(FlowValue::Array(entries)) = part {
            match *key {
                "nodes" => *part = HashPart::Nodes(entries.iter().map(Cow::Borrowed).collect()),
                "edges" => *part = HashPart::Edges(entries.iter().map(EdgeIn::Value).collect()),
                _ => {}
            }
        }
    }
    parts
}

/// A keyed list's items in the list's order, or the value as it is when it is not a list.
fn ordered_items<'a>(keyed: &KeyedList, list: &'a FlowValue) -> HashPart<'a> {
    let FlowValue::Array(items) = list else {
        return HashPart::Raw(list);
    };
    HashPart::Items(
        item_order(keyed, items)
            .into_iter()
            .map(|index| &items[index])
            .collect(),
    )
}

/// [`canonical_node`](super::canonical_form::canonical_node) for the hash, with keyed lists in their order.
fn node_part(node: &FlowValue) -> HashPart<'_> {
    let FlowValue::Object(node_map) = node else {
        return HashPart::Raw(node);
    };
    let mut parts = visible(node_map, |key| FLOW_MODEL.node_view_state.contains(key));
    let Some(FlowValue::Object(data)) = node_map.get("data") else {
        return HashPart::Object(parts);
    };
    let Some(FlowValue::Object(body)) = data.get("node") else {
        return HashPart::Object(parts);
    };
    let mut body_parts = visible(body, |key| FLOW_MODEL.node_data_view_state.contains(key));
    if let (Some(outputs), Some(keyed)) =
        (body.get("outputs"), FLOW_MODEL.named_list_at(&OUTPUTS_PATH))
    {
        set(&mut body_parts, "outputs", ordered_items(keyed, outputs));
    }
    if let Some(FlowValue::Object(template)) = body.get("template") {
        let fields = template
            .iter()
            .filter(|(key, _)| !FLOW_MODEL.template_view_state.contains(key.as_str()))
            .map(|(key, field)| (key.as_str(), field_part(node, key, field)))
            .collect();
        set(&mut body_parts, "template", HashPart::Object(fields));
    }
    let mut data_parts = visible(data, |_| false);
    set(&mut data_parts, "node", HashPart::Object(body_parts));
    set(&mut parts, "data", HashPart::Object(data_parts));
    HashPart::Object(parts)
}

/// `canonical_field` for the hash, with a keyed list in its order.
fn field_part<'a>(node: &'a FlowValue, key: &str, field: &'a FlowValue) -> HashPart<'a> {
    let FlowValue::Object(field_map) = field else {
        return HashPart::Raw(field);
    };
    let mut parts = visible(field_map, |key| FLOW_MODEL.field_view_state.contains(key));
    if let Some(value) = field_map.get("value")
        && let Some(keyed) = FLOW_MODEL.keyed_list_at(node, &field_value_path(key))
    {
        set(&mut parts, "value", ordered_items(keyed, value));
    }
    HashPart::Object(parts)
}

/// [`canonical_edge`](super::canonical_form::canonical_edge) for the hash, with type lists in their stored order.
fn edge_part(edge: EdgeIn<'_>) -> HashPart<'_> {
    let edge_map = match edge {
        EdgeIn::Map(map) | EdgeIn::Value(FlowValue::Object(map)) => map,
        EdgeIn::Value(other) => return HashPart::Raw(other),
    };
    let mut parts = visible(edge_map, |key| FLOW_MODEL.edge_view_state.contains(key));
    for key in HANDLE_KEYS {
        if let Some(parsed) = edge_map.get(key).and_then(parse_handle) {
            set(&mut parts, key, HashPart::Owned(FlowValue::Object(parsed)));
        }
    }
    HashPart::Object(parts)
}

/// The `id` a node or an edge is ordered by, unless view state hides `id`.
fn entry_order_id(map: Option<&FlowObj>, hidden: bool) -> Option<&str> {
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

pub(super) fn write_part(part: HashPart<'_>, out: &mut HashWriter) -> Result<()> {
    match part {
        HashPart::Raw(value) => write_canonical(value, out),
        HashPart::Owned(value) => write_canonical(&value, out),
        HashPart::Object(mut parts) => {
            parts.sort_by(|a, b| utf16_cmp(a.0, b.0));
            write_list(out, (b'{', b'}'), parts, |(key, part), out| {
                write_string(key, out);
                out.put(b":");
                write_part(part, out)
            })
        }
        HashPart::Items(items) => write_list(out, (b'[', b']'), items, write_canonical),
        HashPart::Nodes(nodes) => {
            let hidden = FLOW_MODEL.node_view_state.contains("id");
            let ids: Vec<Option<&str>> = nodes
                .iter()
                .map(|node| entry_order_id(node.as_object(), hidden))
                .collect();
            write_list(out, (b'[', b']'), id_order(&ids), |index, out| {
                write_part(node_part(&nodes[index]), out)
            })
        }
        HashPart::Edges(edges) => {
            let hidden = FLOW_MODEL.edge_view_state.contains("id");
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
            write_list(out, (b'[', b']'), id_order(&ids), |index, out| {
                write_part(edge_part(edges[index]), out)
            })
        }
    }
}

/// Write `items` between `open` and `close`, separated by commas.
fn write_list<T>(
    out: &mut HashWriter,
    (open, close): (u8, u8),
    items: impl IntoIterator<Item = T>,
    mut write_item: impl FnMut(T, &mut HashWriter) -> Result<()>,
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
pub(super) fn flow_part(flow: &FlowValue) -> HashPart<'_> {
    match flow {
        FlowValue::Object(map) => HashPart::Object(graph_parts(map)),
        other => HashPart::Raw(other),
    }
}

/// The SHA-256 hex digest of flow data's canonical graph form.
///
/// The text goes into the hash in chunks, so a large graph's text is never held.
///
/// # Errors
///
/// A number that is not finite as JavaScript reads it.
pub fn graph_hash(flow: &FlowValue) -> Result<String> {
    let mut out = HashWriter::hash();
    write_part(flow_part(flow), &mut out)?;
    Ok(out.into_hex_digest())
}

/// [`graph_hash`] of a loaded graph, from its top-level keys, nodes and edges.
pub(crate) fn loaded_graph_hash<'a>(
    root: &'a FlowObj,
    nodes: Vec<Cow<'a, FlowValue>>,
    edges: Vec<&'a FlowObj>,
) -> Result<String> {
    let mut parts = visible(root, |key| FLOW_MODEL.is_flow_view_state(key));
    set(&mut parts, "nodes", HashPart::Nodes(nodes));
    set(
        &mut parts,
        "edges",
        HashPart::Edges(edges.into_iter().map(EdgeIn::Map).collect()),
    );
    let mut out = HashWriter::hash();
    write_part(HashPart::Object(parts), &mut out)?;
    Ok(out.into_hex_digest())
}
