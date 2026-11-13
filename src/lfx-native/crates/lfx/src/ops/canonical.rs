//! Canonical form of flow data, for equality and checkpoint hashes.
//!
//! Two graphs are equal when their canonical forms are the same JSON value.
//! The form is the graph with its view state removed, and with everything
//! whose order is not state keyed by id:
//!
//! - JSON values compare as RFC 8785 (JSON Canonicalization Scheme) prints
//!   them: `1` and `1.0` are the same value, `true` and `1` are not, and key
//!   order is never a change. JavaScript cannot tell integers from floats, so
//!   a `0.0` that comes back from the editor as `0` must not count as an edit.
//! - `nodes` and `edges` are collections keyed by id, and the items of every
//!   keyed list (outputs, tool actions, table rows) are collections keyed by
//!   item key. Their array order is not state; a keyed list's order is its
//!   items' `(__pos__, key)`.
//! - View state is everything `node_schema.json` declares display only. It is
//!   stored but never recorded and never compared.
//! - An edge's `sourceHandle` and `targetHandle` strings are JSON with `œ`
//!   standing for `"`. They compare by the object they encode.
//! - A handle's `inputTypes` and `output_types` compare as sets. The hash
//!   keeps their order, so that no stored hash changes.
//!
//! Equality compares the form structurally and stops at the first
//! difference; only [`graph_hash`] serializes it, with collections ordered, as
//! RFC 8785 text. The form is defined for any JSON graph, valid or not:
//! enforcing the rules is validation's job.
//!
//! Numbers compare as the doubles JavaScript holds. So an integer above 2^53
//! compares, prints and hashes as the double it rounds to, on purpose: the
//! editor cannot hold it either. Stored values keep what [`crate::value::Number`]
//! keeps: an integer or a double, and the text of a number neither holds.

use std::borrow::Cow;
use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};
use std::fmt::Write as _;
use std::io::Write as _;

use crate::json_out::{self, Ascii};
use crate::value::{AnyMap, AnyString, AnyValue, Number};
use sha2::{Digest, Sha256};

use crate::ops::error::{Error, Result};
use crate::ops::schema::{KeyedList, NODE_SCHEMA, OUTPUTS_PATH, field_value_path};

/// The quote character of an edge handle's string form.
pub const HANDLE_QUOTE: char = 'œ';
/// The keys of an edge's two handles.
pub const HANDLE_KEYS: [&str; 2] = ["sourceHandle", "targetHandle"];
/// The keys of a handle that hold a list of types. Their order is not state.
pub const TYPE_LIST_KEYS: [&str; 2] = ["inputTypes", "output_types"];

/// Largest integer a JavaScript number holds exactly.
const MAX_SAFE_INTEGER: i128 = 1 << 53;
/// ECMAScript prints numbers below 1e21 in plain notation.
const MAX_PLAIN_EXPONENT: i32 = 21;
const MIN_PLAIN_EXPONENT: i32 = -6;

/// The six JSON types. Integer versus float is not a type.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[expect(missing_docs, reason = "each variant is the JSON type it names")]
pub enum JsonType {
    Object,
    Array,
    String,
    Number,
    Boolean,
    Null,
}

/// The JSON type of a value.
impl From<&AnyValue> for JsonType {
    fn from(value: &AnyValue) -> Self {
        match value {
            AnyValue::Null => Self::Null,
            AnyValue::Bool(_) => Self::Boolean,
            AnyValue::Number(_) => Self::Number,
            AnyValue::String(_) => Self::String,
            AnyValue::Array(_) => Self::Array,
            AnyValue::Object(_) => Self::Object,
        }
    }
}

// --- Numbers ---------------------------------------------------------------------------

/// A number as the double JavaScript reads it: correctly rounded, and
/// infinite when it is too large for a double.
#[must_use]
pub fn as_double(number: &Number) -> f64 {
    number.as_f64().unwrap_or(f64::NAN)
}

/// Whether a number is finite as the double JavaScript reads it. An integer
/// too large for a double reads as Infinity, so it is not finite.
#[must_use]
pub fn is_finite_number(number: &Number) -> bool {
    as_double(number).is_finite()
}

/// Whether a number is written as an integer, with no fraction and no
/// exponent, which is how Python tells an `int` from a `float`.
#[must_use]
pub fn is_integer_text(number: &Number) -> bool {
    number.is_integer()
}

/// Whether a value is a valid table row position: a finite number.
#[must_use]
pub fn is_row_position(value: &AnyValue) -> bool {
    matches!(value, AnyValue::Number(number) if is_finite_number(number))
}

fn finite_double(number: &Number) -> Result<f64> {
    let double = as_double(number);
    if double.is_finite() {
        Ok(double)
    } else {
        Err(Error::non_finite())
    }
}

/// Print a number as RFC 8785 does, which is JavaScript's `Number::toString`.
fn format_number(number: &Number, out: &mut Sink) -> Result<()> {
    let double = finite_double(number)?;
    if is_integer_text(number) {
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

fn format_double(value: f64, out: &mut Vec<u8>) {
    if value == 0.0 {
        out.push(b'0');
        return;
    }
    if value < 0.0 {
        out.push(b'-');
    }
    // `{:e}` prints the shortest digits that round-trip, which is also what
    // ECMAScript's Number::toString chooses; only the layout differs.
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

// --- Serialization ----------------------------------------------------------------------

/// Order strings by UTF-16 code units, the order JavaScript's default sort uses.
///
/// UTF-8 bytes order as code points do, and code points order as UTF-16
/// units do, except a code point above U+FFFF, which UTF-16 writes as
/// surrogates from 0xD800, against one from U+E000 to U+FFFF. The first
/// byte of both in UTF-8 is 0xEE or more, so the bytes decide unless the
/// first bytes that differ are.
#[must_use]
pub fn utf16_cmp(left: &str, right: &str) -> Ordering {
    let (left_bytes, right_bytes) = (left.as_bytes(), right.as_bytes());
    match left_bytes.iter().zip(right_bytes).find(|(a, b)| a != b) {
        None => left_bytes.len().cmp(&right_bytes.len()),
        Some((a, b)) if *a < 0xEE && *b < 0xEE => a.cmp(b),
        Some(_) => left.encode_utf16().cmp(right.encode_utf16()),
    }
}

/// The canonical text that a [`Sink`] holds before it gives it to the hash.
const HASH_CHUNK: usize = 1 << 16;

/// Where canonical text goes: memory, or the hash, a chunk at a time.
struct Sink {
    buf: Vec<u8>,
    hash: Option<Sha256>,
}

impl Sink {
    fn text() -> Self {
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

    fn into_text(self) -> String {
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

/// Write a string as RFC 8785 does: `"` and `\` escaped, and the control
/// characters, with the short forms where JSON has them. That is exactly
/// what `serde_json` writes, and [`json_out`] writes the same text.
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

// --- Value equality ---------------------------------------------------------------------

/// Whether two JSON values have the same canonical form, stopping at the first difference.
///
/// Objects compare key by key in any order, arrays item by item, and numbers
/// as the doubles JavaScript would hold.
///
/// # Errors
///
/// A compared number that is not finite as JavaScript reads it.
#[expect(
    clippy::float_cmp,
    reason = "canonical equality compares the exact doubles"
)]
pub fn values_equal(left: &AnyValue, right: &AnyValue) -> Result<bool> {
    Ok(match (left, right) {
        (AnyValue::Number(a), AnyValue::Number(b)) => finite_double(a)? == finite_double(b)?,
        (AnyValue::Array(a), AnyValue::Array(b)) => {
            if a.len() != b.len() {
                return Ok(false);
            }
            for (a, b) in a.iter().zip(b) {
                if !values_equal(a, b)? {
                    return Ok(false);
                }
            }
            true
        }
        (AnyValue::Object(a), AnyValue::Object(b)) => {
            if a.len() != b.len() {
                return Ok(false);
            }
            for (key, a) in a {
                match b.get(key) {
                    Some(b) if values_equal(a, b)? => {}
                    _ => return Ok(false),
                }
            }
            true
        }
        _ => left == right,
    })
}

// --- Handles ----------------------------------------------------------------------------

/// The object a handle string encodes (JSON with `œ` for `"`), or `None` when
/// it encodes none.
///
/// The string is parsed as strict JSON, as JavaScript's `JSON.parse` reads
/// it: `NaN` and `Infinity` do not parse.
#[must_use]
pub fn parse_handle(handle: &AnyValue) -> Option<AnyMap> {
    let text = handle.as_str()?.replace(HANDLE_QUOTE, "\"");
    match serde_json::from_str(&text) {
        Ok(AnyValue::Object(object)) => Some(object),
        _ => None,
    }
}

/// Whether `handle` spells `object` as a handle is written: its JSON, keys in
/// their order, with `œ` for each `"`, and with or without one space after
/// each `:` and `,` outside strings (`json.dumps` writes one, `JSON.stringify`
/// none).
///
/// Such text encodes exactly `object`, so [`parse_handle`] would read it as a
/// value equal to `object`, and a caller can skip it. Other text can still
/// encode `object` (other key order, spacing or number spelling): parse it.
#[must_use]
pub fn handle_spells(handle: &str, object: &AnyMap) -> bool {
    // [`values_equal`] refuses a number that is not finite: leave those to it.
    fn finite(value: &AnyValue) -> bool {
        match value {
            AnyValue::Number(number) => number.as_f64().is_some_and(f64::is_finite),
            AnyValue::Array(items) => items.iter().all(finite),
            AnyValue::Object(map) => map.values().all(finite),
            _ => true,
        }
    }
    if !object.values().all(finite) {
        return false;
    }
    let mut text = Vec::with_capacity(handle.len());
    json_out::write_map(&mut text, object, Ascii::Keep);
    let mut quote = [0; 4];
    let quote = HANDLE_QUOTE.encode_utf8(&mut quote).as_bytes();
    let mut handle = handle.as_bytes();
    let (mut in_string, mut escaped) = (false, false);
    // The handle reads as `parse_handle` reads it: each `œ` as `"`. A `œ` in
    // the written text cannot match, as the handle's `œ` reads as `"`.
    for &byte in &text {
        if let Some(after) = handle.strip_prefix(quote) {
            if byte != b'"' {
                return false;
            }
            handle = after;
        } else if handle.first() == Some(&byte) {
            handle = &handle[1..];
        } else {
            return false;
        }
        if in_string {
            if escaped {
                escaped = false;
            } else if byte == b'\\' {
                escaped = true;
            } else if byte == b'"' {
                in_string = false;
            }
        } else if byte == b'"' {
            in_string = true;
        } else if byte == b':' || byte == b',' {
            // Space between tokens does not change what the text encodes.
            handle = handle.strip_prefix(b" ").unwrap_or(handle);
        }
    }
    handle.is_empty()
}

// --- Table rows ---------------------------------------------------------------------------

/// A table's rows in order: by `(__pos__, __id__)`, or as stored for a legacy table without them.
///
/// Positions compare as the doubles JavaScript holds, and ids by UTF-16 code
/// units, as the editor sorts them.
#[must_use]
pub fn ordered_rows(rows: &[AnyValue]) -> Vec<&AnyValue> {
    row_order(rows)
        .into_iter()
        .map(|slot| &rows[slot])
        .collect()
}

/// The array indexes of a table's rows, in the order [`ordered_rows`] gives.
pub(crate) fn row_order(rows: &[AnyValue]) -> Vec<usize> {
    item_order(&NODE_SCHEMA.table, rows)
}

/// The array indexes of a keyed list's items in its order: by
/// `(__pos__, key)`, or as stored when an item has no numeric position or no
/// string key. Positions compare as the doubles JavaScript holds, and keys by
/// UTF-16 code units.
pub(crate) fn item_order(keyed: &KeyedList, items: &[AnyValue]) -> Vec<usize> {
    let keys: Option<Vec<(f64, &str)>> = items
        .iter()
        .map(|item| {
            let position = match item.as_object()?.get(&keyed.position)? {
                AnyValue::Number(number) if is_finite_number(number) => as_double(number),
                _ => return None,
            };
            Some((position, keyed.key_of(item)?))
        })
        .collect();
    let mut order: Vec<usize> = (0..items.len()).collect();
    if let Some(keys) = keys {
        order.sort_by(|&a, &b| {
            keys[a]
                .0
                .total_cmp(&keys[b].0)
                .then_with(|| utf16_cmp(keys[a].1, keys[b].1))
        });
    }
    order
}

// --- The canonical form of a graph --------------------------------------------------------

/// A graph's canonical form, sharing every value it does not change.
#[derive(Debug)]
enum Canon<'a> {
    /// A value taken as it is.
    Raw(&'a AnyValue),
    /// A value the canonical form built: the object a handle string
    /// encodes, or an edge's `data` with its type lists as sets.
    Owned(AnyValue),
    /// An object with some members changed, or a collection keyed by id.
    Object(HashMap<&'a str, Canon<'a>>),
    /// A collection ordered for serialization.
    Array(Vec<Canon<'a>>),
    /// A node of a graph keyed for comparison, taken as it is. The comparison
    /// makes it canonical only when it differs from the other node as it is.
    Node(&'a AnyValue),
}

fn without(map: &AnyMap, hidden: impl Fn(&str) -> bool) -> HashMap<&str, Canon<'_>> {
    map.iter()
        .filter(|(key, _)| !hidden(key))
        .map(|(key, value)| (key.as_str(), Canon::Raw(value)))
        .collect()
}

/// A graph's canonical form for comparison, with its collections keyed by id.
fn canonical_graph(flow: &AnyValue) -> Result<Canon<'_>> {
    let AnyValue::Object(flow) = flow else {
        return Ok(Canon::Raw(flow));
    };
    let mut graph = without(flow, |key| NODE_SCHEMA.is_flow_view_state(key));
    for key in ["nodes", "edges"] {
        let Some(Canon::Raw(AnyValue::Array(entries))) = graph.get(key) else {
            continue;
        };
        let entries: Vec<Canon<'_>> = entries
            .iter()
            .map(|entry| match key {
                "nodes" => Ok(Canon::Node(entry)),
                _ => canonical_edge(entry),
            })
            .collect::<Result<_>>()?;
        graph.insert(key, by_id(entries, "id"));
    }
    Ok(Canon::Object(graph))
}

/// The string member `key` of a canonical entry, borrowed from the graph.
fn entry_id<'a>(entry: &Canon<'a>, key: &str) -> Option<&'a str> {
    match entry {
        Canon::Raw(value) | Canon::Node(value) => value.as_object()?.get(key)?.as_str(),
        Canon::Object(map) => match map.get(key)? {
            Canon::Raw(value) => value.as_str(),
            _ => None,
        },
        _ => None,
    }
}

/// A keyed list's items, whose array order is not state. For comparison they
/// are a collection keyed by item key; for the hash they are a list in the
/// list's order ([`item_order`]). A list with an item that has no string key,
/// or two items with one key, keeps its array, which is then its order.
fn keyed_items<'a>(keyed: &KeyedList, list: &'a AnyValue) -> Canon<'a> {
    let AnyValue::Array(items) = list else {
        return Canon::Raw(list);
    };
    let mut by_key = HashMap::with_capacity(items.len());
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
fn by_id<'a>(entries: Vec<Canon<'a>>, id_key: &str) -> Canon<'a> {
    let ids: Option<Vec<&'a str>> = entries
        .iter()
        .map(|entry| entry_id(entry, id_key))
        .collect();
    let Some(ids) = ids else {
        return Canon::Array(entries);
    };
    let mut seen = HashSet::with_capacity(ids.len());
    if !ids.iter().all(|id| seen.insert(*id)) {
        return Canon::Array(entries);
    }
    Canon::Object(ids.into_iter().zip(entries).collect())
}

fn canonical_node(node: &AnyValue) -> Canon<'_> {
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

/// A template field without its display-only keys. A keyed list as its
/// value (table rows, tool actions) is a collection keyed by item key.
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

/// An edge without its view state, its handle strings as the objects they
/// encode. For comparison, each handle's type lists are sets. The hash
/// keeps their order, so that no stored hash changes.
fn canonical_edge(edge: &AnyValue) -> Result<Canon<'_>> {
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

/// A handle object with each type list sorted and without repeats. Two
/// handles that differ only in the order of their types are then equal.
/// A value that is not an object is returned as it is.
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
enum View<'c, 'a> {
    /// An object the canonical form rebuilt, or a collection keyed by id.
    Object(&'c HashMap<&'a str, Canon<'a>>),
    /// A collection the canonical form ordered for serialization.
    Array(&'c [Canon<'a>]),
    /// A value the canonical form shares with the graph, or a handle's object.
    Value(&'c AnyValue),
    /// A node taken as it is ([`Canon::Node`]). Only [`canon_equal`] reads it,
    /// and it makes the node canonical first when it needs to.
    Node(&'a AnyValue),
}

impl<'c, 'a> View<'c, 'a> {
    fn of(canon: &'c Canon<'a>) -> Self {
        match canon {
            Canon::Raw(value) => Self::Value(value),
            Canon::Owned(value) => Self::Value(value),
            Canon::Object(map) => Self::Object(map),
            Canon::Array(items) => Self::Array(items),
            Canon::Node(node) => Self::Node(node),
        }
    }

    fn json_type(self) -> JsonType {
        match self {
            Self::Object(_) => JsonType::Object,
            Self::Array(_) => JsonType::Array,
            Self::Value(value) => JsonType::from(value),
            Self::Node(_) => unreachable!("{NODE_READ}"),
        }
    }

    fn len(self) -> usize {
        match self {
            Self::Object(map) => map.len(),
            Self::Array(items) => items.len(),
            Self::Value(AnyValue::Object(map)) => map.len(),
            Self::Value(AnyValue::Array(items)) => items.len(),
            Self::Value(_) => 0,
            Self::Node(_) => unreachable!("{NODE_READ}"),
        }
    }

    fn member(self, key: &str) -> Option<Self> {
        match self {
            Self::Object(map) => map.get(key).map(Self::of),
            Self::Value(AnyValue::Object(map)) => map.get(key).map(Self::Value),
            Self::Array(_) | Self::Value(_) => None,
            Self::Node(_) => unreachable!("{NODE_READ}"),
        }
    }

    fn item(self, index: usize) -> Option<Self> {
        match self {
            Self::Array(items) => items.get(index).map(Self::of),
            Self::Value(AnyValue::Array(items)) => items.get(index).map(Self::Value),
            Self::Object(_) | Self::Value(_) => None,
            Self::Node(_) => unreachable!("{NODE_READ}"),
        }
    }

    /// Whether `check` holds for every member of an object, stopping at the
    /// first member it fails for.
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
            Self::Node(_) => unreachable!("{NODE_READ}"),
        }
        Ok(true)
    }
}

const NODE_READ: &str = "canon_equal makes a node canonical before it reads it";

fn canon_equal(left: View<'_, '_>, right: View<'_, '_>) -> Result<bool> {
    match (left, right) {
        (View::Value(left), View::Value(right)) => return values_equal(left, right),
        (View::Node(left), View::Node(right)) => return nodes_equal(left, right),
        (View::Node(node), other) | (other, View::Node(node)) => {
            let node = canonical_node(node);
            return canon_equal(View::of(&node), other);
        }
        _ => {}
    }
    let kind = left.json_type();
    if kind != right.json_type() || left.len() != right.len() {
        return Ok(false);
    }
    if kind == JsonType::Object {
        return left.all_members(|key, value| match right.member(key) {
            Some(other) => canon_equal(value, other),
            None => Ok(false),
        });
    }
    for index in 0..left.len() {
        match (left.item(index), right.item(index)) {
            (Some(a), Some(b)) if canon_equal(a, b)? => {}
            _ => return Ok(false),
        }
    }
    Ok(true)
}

/// Whether two nodes have the same canonical form.
///
/// Two nodes that are equal as they are have the same canonical form, and
/// the comparison skips building it. The canonical form only leaves out
/// display-only keys and keys table rows by id: it parses nothing, and it
/// reads only numbers that [`values_equal`] has checked. Any other answer,
/// including an error, comes from the canonical forms.
fn nodes_equal(left: &AnyValue, right: &AnyValue) -> Result<bool> {
    if matches!(values_equal(left, right), Ok(true)) {
        return Ok(true);
    }
    let (left, right) = (canonical_node(left), canonical_node(right));
    canon_equal(View::of(&left), View::of(&right))
}

// --- The canonical text of a graph ----------------------------------------------------

/// A member of a graph's canonical form, for its text: shared with the graph
/// wherever the form does not change it. The form of a node is made only
/// when the node is written, and dropped after.
#[derive(Debug)]
enum Part<'a> {
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
enum EdgeIn<'a> {
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

/// A graph's top-level members in canonical form: every key but the view
/// state, with `nodes` and `edges` when they are lists.
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

/// A node's canonical form, as [`canonical_node`] makes it, with its keyed
/// lists in their order.
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

/// A template field's canonical form, as [`canonical_field`] makes it, with
/// a keyed list as its value in the list's order.
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

/// An edge's canonical form for the hash: without its view state, its
/// handle strings as the objects they encode, their type lists in order.
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

/// The id a node or an edge is ordered by: its `id` string, unless the
/// canonical form leaves `id` out.
fn entry_order_id(map: Option<&AnyMap>, hidden: bool) -> Option<&str> {
    if hidden {
        return None;
    }
    map?.get("id")?.as_str()
}

/// The indexes of `ids` in order: by id, an entry without one first, and
/// entries with one id in their order.
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

fn write_part(part: Part<'_>, out: &mut Sink) -> Result<()> {
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
fn flow_part(flow: &AnyValue) -> Part<'_> {
    match flow {
        AnyValue::Object(map) => Part::Object(graph_parts(map)),
        other => Part::Raw(other),
    }
}

/// Serialize flow data in canonical graph form, as RFC 8785 text.
///
/// # Errors
///
/// A number that is not finite as JavaScript reads it.
pub fn canonical_graph_json(flow: &AnyValue) -> Result<String> {
    let mut out = Sink::text();
    write_part(flow_part(flow), &mut out)?;
    Ok(out.into_text())
}

/// The SHA-256 hex digest of flow data's canonical graph form.
///
/// The text goes into the hash a chunk at a time, as it is written: the
/// whole text of a large graph is never held.
///
/// # Errors
///
/// A number that is not finite as JavaScript reads it.
pub fn graph_hash(flow: &AnyValue) -> Result<String> {
    let mut out = Sink::hash();
    write_part(flow_part(flow), &mut out)?;
    Ok(out.into_hex_digest())
}

/// [`graph_hash`] of a loaded graph, from its parts: the top-level keys, with
/// `nodes` and `edges` in their place, as the graph as a value has them.
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

/// Whether two flows are the same graph, stopping at the first difference.
///
/// # Errors
///
/// A number that is not finite as JavaScript reads it, in either graph's
/// canonical form: the graphs that [`graph_hash`] refuses.
pub fn graphs_equal(left: &AnyValue, right: &AnyValue) -> Result<bool> {
    let left = canonical_graph(left)?;
    let right = canonical_graph(right)?;
    let equal = canon_equal(View::of(&left), View::of(&right))?;
    // Equal graphs had every number read. Graphs that differ stopped at the
    // first difference, so they are checked to the end, or which answer a
    // number that is not finite gets would depend on where the difference is.
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
        // A node whose numbers are all finite as it is has a canonical form
        // with finite numbers. Only another node needs its canonical form,
        // which leaves out display-only keys and what they hold.
        View::Node(node) => {
            check_finite_value(node).or_else(|_| check_finite(View::of(&canonical_node(node))))
        }
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

#[cfg(test)]
mod tests {
    use crate::json;

    use super::*;

    fn canonical(text: &str) -> String {
        canonical_json(&serde_json::from_str(text).unwrap()).unwrap()
    }

    #[test]
    fn a_handle_spells_its_object_only_when_it_encodes_it() {
        let object = |text: &str| -> AnyMap {
            match serde_json::from_str(text).unwrap() {
                AnyValue::Object(map) => map,
                _ => unreachable!(),
            }
        };
        let handle = object(
            r#"{"dataType": "Prompt", "id": "P-1", "name": "prompt", "output_types": ["Message"]}"#,
        );
        // Both spellings a handle is written in, and a `"` that reads as itself.
        for text in [
            "{œdataTypeœ: œPromptœ, œidœ: œP-1œ, œnameœ: œpromptœ, œoutput_typesœ: [œMessageœ]}",
            "{œdataTypeœ:œPromptœ,œidœ:œP-1œ,œnameœ:œpromptœ,œoutput_typesœ:[œMessageœ]}",
            "{\"dataTypeœ:œPromptœ,œidœ:œP-1œ,œnameœ:œpromptœ,œoutput_typesœ:[œMessageœ]}",
        ] {
            assert!(handle_spells(text, &handle), "{text}");
            let parsed = parse_handle(&AnyValue::String(text.into())).unwrap();
            assert!(
                values_equal(&AnyValue::Object(parsed), &AnyValue::Object(handle.clone())).unwrap()
            );
        }
        // Other text is left to the parse, which decides.
        for text in [
            "{œidœ: œP-1œ, œdataTypeœ: œPromptœ, œnameœ: œpromptœ, œoutput_typesœ: [œMessageœ]}",
            "{ œdataTypeœ: œPromptœ, œidœ: œP-1œ, œnameœ: œpromptœ, œoutput_typesœ: [œMessageœ]}",
            "{œdataTypeœ:  œPromptœ, œidœ: œP-1œ, œnameœ: œpromptœ, œoutput_typesœ: [œMessageœ]}",
            "{œdataTypeœ: œPromptœ, œidœ: œP-2œ, œnameœ: œpromptœ, œoutput_typesœ: [œMessageœ]}",
            "{œdataTypeœ: œPromptœ, œidœ: œP-1œ, œnameœ: œpromptœ, œoutput_typesœ: [œMessageœ]} ",
        ] {
            assert!(!handle_spells(text, &handle), "{text}");
        }
        // A space inside a string is text, not spacing.
        let spaced = object(r#"{"name": "a b"}"#);
        assert!(handle_spells("{œnameœ: œa bœ}", &spaced));
        assert!(!handle_spells("{œnameœ: œa  bœ}", &spaced));
        // An `œ` in the object cannot be spelled: the handle's `œ` reads as `"`.
        assert!(!handle_spells(
            "{œnameœ: œaœbœ}",
            &object(r#"{"name": "aœb"}"#)
        ));
        // A number that is not finite is left to `values_equal`, which refuses it.
        assert!(!handle_spells("{œnœ: 1e400}", &object(r#"{"n": 1e400}"#)));
    }

    #[test]
    fn numbers_print_as_javascript_does() {
        for (text, expected) in [
            ("0", "0"),
            ("-0", "0"),
            ("-0.0", "0"),
            ("1.0", "1"),
            ("-1.5", "-1.5"),
            ("0.1", "0.1"),
            ("123.456", "123.456"),
            ("1e20", "100000000000000000000"),
            ("1e21", "1e+21"),
            ("1.5e21", "1.5e+21"),
            ("0.000001", "0.000001"),
            ("1e-7", "1e-7"),
            ("1.25e-7", "1.25e-7"),
            ("5e-324", "5e-324"),
            ("1.7976931348623157e308", "1.7976931348623157e+308"),
            ("333333333.3333333", "333333333.3333333"),
            ("9007199254740992", "9007199254740992"),
            ("9007199254740993", "9007199254740992"),
            ("-9007199254740993", "-9007199254740992"),
            ("12345678901234567890123", "1.2345678901234568e+22"),
        ] {
            assert_eq!(canonical(text), expected, "{text}");
        }
    }

    #[test]
    fn non_finite_numbers_are_rejected() {
        for text in ["1e400", "-1e400", &format!("1{}", "0".repeat(309))] {
            let value: AnyValue = serde_json::from_str(text).unwrap();
            assert!(canonical_json(&value).is_err(), "{text}");
        }
        // The largest integer below the double overflow rounds to the largest double.
        let below = "179769313486231580793728971405303415079934132710037826936173778980444968292764750946649017977587207096330286416692887910946555547851940402630657488671505820681908902000708383676273854845817711531764475730270069855571366959622842914819860834936475292719074168444365510704342711559699508093042880177904174497791";
        assert_eq!(canonical(below), "1.7976931348623157e+308");
    }

    #[test]
    fn object_keys_sort_by_utf16_code_units() {
        let value = json!({"\u{20ac}": 1, "\r": 2, "\u{fb33}": 3, "1": 4, "\u{1f600}": 5, "\u{80}": 6, "\u{f6}": 7});
        assert_eq!(
            canonical_json(&value).unwrap(),
            "{\"\\r\":2,\"1\":4,\"\u{80}\":6,\"\u{f6}\":7,\"\u{20ac}\":1,\"\u{1f600}\":5,\"\u{fb33}\":3}"
        );
    }

    #[test]
    fn strings_escape_only_what_json_requires() {
        assert_eq!(
            canonical_json(&json!("a\"b\\c\n\u{1}é/")).unwrap(),
            "\"a\\\"b\\\\c\\n\\u0001é/\""
        );
    }

    #[test]
    fn equality_matches_the_canonical_form() {
        let samples = [
            "null",
            "true",
            "false",
            "0",
            "0.0",
            "-0.0",
            "1",
            "1.0",
            "1.5",
            "9007199254740992",
            "9007199254740993",
            "9007199254740992.0",
            "1e21",
            "\"\"",
            "\"a\"",
            "\"1\"",
            "[]",
            "[1]",
            "[1.0]",
            "[1,2]",
            "[2,1]",
            "{}",
            "{\"a\":1}",
            "{\"a\":1.0}",
            "{\"b\":1}",
            "{\"a\":1,\"b\":[true,null]}",
            "{\"b\":[true,null],\"a\":1}",
            "{\"a\":{\"b\":{\"c\":0}}}",
            "{\"a\":{\"b\":{\"c\":-0.0}}}",
            "{\"a\":{\"b\":{\"c\":1}}}",
        ];
        for left in samples {
            for right in samples {
                let a: AnyValue = serde_json::from_str(left).unwrap();
                let b: AnyValue = serde_json::from_str(right).unwrap();
                assert_eq!(
                    values_equal(&a, &b).unwrap(),
                    canonical_json(&a).unwrap() == canonical_json(&b).unwrap(),
                    "{left} vs {right}"
                );
            }
        }
    }

    #[test]
    fn handles_parse_strictly() {
        assert_eq!(
            parse_handle(&json!("{œnameœ:œoutœ}")),
            Some(json!({"name": "out"}).as_object().unwrap().clone())
        );
        assert_eq!(parse_handle(&json!("{œaœ:NaN}")), None);
        assert_eq!(parse_handle(&json!("[1]")), None);
        assert_eq!(parse_handle(&json!(1)), None);
    }

    #[test]
    fn graphs_compare_their_canonical_forms() {
        let left = json!({
            "viewport": {"x": 1},
            "description": "every top-level key but nodes and edges is view state",
            "nodes": [
                {"id": "b", "selected": true, "data": {"node": {"template": {}}}},
                {"id": "a", "data": {"node": {"last_updated": "x", "template": {
                    "rows": {"type": "table", "value": [{"__id__": "r2", "__pos__": 2}, {"__id__": "r1", "__pos__": 1.0}]}
                }}}},
            ],
            "edges": [{"id": "e", "sourceHandle": "{œnameœ: œoutœ}", "animated": true}],
        });
        let right = json!({
            "nodes": [
                {"id": "a", "data": {"node": {"template": {
                    "rows": {"type": "table", "value": [{"__id__": "r1", "__pos__": 1}, {"__id__": "r2", "__pos__": 2}]}
                }}}},
                {"id": "b", "data": {"node": {"template": {}}}},
            ],
            "edges": [{"id": "e", "sourceHandle": "{œnameœ:œoutœ}"}],
        });
        assert!(graphs_equal(&left, &right).unwrap());
        assert_eq!(graph_hash(&left).unwrap(), graph_hash(&right).unwrap());

        let mut changed = right.clone();
        changed["nodes"][1]["data"]["node"]["template"]["x"] = json!(1);
        assert!(!graphs_equal(&left, &changed).unwrap());
        assert_ne!(graph_hash(&left).unwrap(), graph_hash(&changed).unwrap());
    }

    #[rustfmt::skip]
        const FIXTURES: [&str; 12] = [
            include_str!("../../../../fixtures/apply_cases.json"),
            include_str!("../../../../fixtures/backward_cases.json"),
            include_str!("../../../../fixtures/canonical_cases.json"),
            include_str!("../../../../fixtures/diff_cases.json"),
            include_str!("../../../../fixtures/editor_cases.json"),
            include_str!("../../../../fixtures/limit_cases.json"),
            include_str!("../../../../fixtures/merge_cases.json"),
            include_str!("../../../../fixtures/property_cases.json"),
            include_str!("../../../../fixtures/repair_cases.json"),
            include_str!("../../../../fixtures/restore_cases.json"),
            include_str!("../../../../fixtures/table_cases.json"),
            include_str!("../../../../fixtures/validation_cases.json"),
        ];

    /// Every graph in every fixture case.
    fn fixture_graphs() -> Vec<AnyValue> {
        let mut out = Vec::new();
        for text in FIXTURES {
            let file: AnyValue = serde_json::from_str(text).unwrap();
            let mut found = Vec::new();
            graphs(&file, &mut found);
            out.extend(found.into_iter().cloned());
        }
        out
    }

    #[test]
    fn graph_hash_streams_the_canonical_text() {
        let all = fixture_graphs();
        assert!(all.len() > 500, "only {} graphs", all.len());
        for graph in &all {
            let Ok(text) = canonical_graph_json(graph) else {
                assert!(graph_hash(graph).is_err());
                continue;
            };
            let digest = Sha256::digest(text.as_bytes());
            let hex = digest.iter().fold(String::new(), |mut hex, byte| {
                write!(hex, "{byte:02x}").ok();
                hex
            });
            assert_eq!(graph_hash(graph).unwrap(), hex, "{graph}");
        }
    }

    #[test]
    fn a_loaded_graph_hashes_as_its_value_does() {
        let mut loaded = 0;
        for graph in fixture_graphs() {
            let Ok(state) = crate::ops::GraphState::new(graph) else {
                continue;
            };
            assert_eq!(state.graph_hash(), graph_hash(&state.to_value()));
            loaded += 1;
        }
        assert!(loaded > 300, "only {loaded} graphs loaded");
    }

    /// The comparison that makes every node canonical before it compares
    /// anything: what `graphs_equal` did before it compared nodes as they are.
    fn graphs_equal_eager(left: &AnyValue, right: &AnyValue) -> Result<bool> {
        fn eager(canon: Canon<'_>) -> Canon<'_> {
            match canon {
                Canon::Node(node) => canonical_node(node),
                Canon::Object(map) => Canon::Object(
                    map.into_iter()
                        .map(|(key, value)| (key, eager(value)))
                        .collect(),
                ),
                Canon::Array(items) => Canon::Array(items.into_iter().map(eager).collect()),
                other => other,
            }
        }
        let left = eager(canonical_graph(left)?);
        let right = eager(canonical_graph(right)?);
        canon_equal(View::of(&left), View::of(&right))
    }

    /// Every graph in a fixture case, nested ones included.
    fn graphs<'v>(value: &'v AnyValue, out: &mut Vec<&'v AnyValue>) {
        match value {
            AnyValue::Object(map) => {
                if map.get("nodes").is_some_and(AnyValue::is_array) {
                    out.push(value);
                }
                map.values().for_each(|value| graphs(value, out));
            }
            AnyValue::Array(items) => items.iter().for_each(|value| graphs(value, out)),
            _ => {}
        }
    }

    /// The graph with its nodes in reverse order, and `number` under `key`
    /// on each node.
    fn reshuffled(graph: &AnyValue, key: &str, number: &str) -> AnyValue {
        let mut graph = graph.clone();
        if let Some(AnyValue::Array(nodes)) = graph.get_mut("nodes") {
            nodes.reverse();
            for node in nodes.iter_mut().filter_map(AnyValue::as_object_mut) {
                node.insert(key.to_owned(), serde_json::from_str(number).unwrap());
            }
        }
        graph
    }

    #[test]
    fn graphs_equal_answers_as_the_eager_comparison() {
        let hidden = NODE_SCHEMA
            .node_view_state
            .iter()
            .min()
            .expect("a node view-state key");
        assert!(!NODE_SCHEMA.node_view_state.contains("compared"));
        let mut pairs = 0;
        for text in FIXTURES {
            let file: AnyValue = serde_json::from_str(text).unwrap();
            let cases = file
                .as_object()
                .into_iter()
                .flat_map(crate::value::AnyMap::values)
                .filter_map(AnyValue::as_array)
                .flatten();
            for case in cases {
                let mut found = Vec::new();
                graphs(case, &mut found);
                // Equal in canonical form but not as they are: a display-only
                // key, with a finite number and with one that is not. And a
                // number that is not finite where the comparison reads it,
                // which it refuses.
                let shuffled: Vec<AnyValue> = found
                    .iter()
                    .flat_map(|graph| {
                        [
                            reshuffled(graph, hidden, "1"),
                            reshuffled(graph, hidden, "1e400"),
                            reshuffled(graph, "compared", "1e400"),
                        ]
                    })
                    .collect();
                let all: Vec<(&AnyValue, bool)> = found
                    .into_iter()
                    .chain(&shuffled)
                    .map(|graph| (graph, graph_hash(graph).is_err()))
                    .collect();
                for &(left, left_refused) in &all {
                    for &(right, right_refused) in &all {
                        // A graph whose hash is refused is refused, whatever
                        // the other graph is. The eager comparison stops at
                        // the first difference, so it may answer not equal.
                        let (new, old) =
                            (graphs_equal(left, right), graphs_equal_eager(left, right));
                        if left_refused || right_refused {
                            assert_eq!(new, Err(Error::non_finite()), "{left}\n{right}");
                            assert!(!matches!(old, Ok(true)), "{left}\n{right}");
                        } else {
                            assert_eq!(new, old, "{left}\n{right}");
                        }
                        pairs += 1;
                    }
                }
            }
        }
        assert!(pairs > 10_000, "only {pairs} pairs");
    }
}
