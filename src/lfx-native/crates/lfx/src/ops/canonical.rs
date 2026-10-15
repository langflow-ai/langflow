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
//! - `nodes`, `edges` and table rows are collections keyed by id. Their array
//!   order is not state; a table's order is its rows' `(_pos, _id)`.
//! - View state is everything `node_schema.json` declares display only. It is
//!   stored but never recorded and never compared.
//! - An edge's `sourceHandle` and `targetHandle` strings are JSON with `œ`
//!   standing for `"`. They compare by the object they encode.
//!
//! Equality compares the form structurally and stops at the first
//! difference; only [`graph_hash`] serializes it, with collections ordered, as
//! RFC 8785 text. The form is defined for any JSON graph, valid or not:
//! enforcing the rules is validation's job.
//!
//! Numbers compare as the doubles JavaScript holds. So an integer above 2^53
//! compares, prints and hashes as the double it rounds to, on purpose: the
//! editor cannot hold it either. Stored values keep their original text.

use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};
use std::fmt::Write as _;

use serde_json::{Map, Number, Value};
use sha2::{Digest, Sha256};

use crate::ops::error::{Error, Result};
use crate::ops::schema::NODE_SCHEMA;

/// The quote character of an edge handle's string form.
pub const HANDLE_QUOTE: char = 'œ';
/// The keys of an edge's two handles.
pub const HANDLE_KEYS: [&str; 2] = ["sourceHandle", "targetHandle"];

/// Largest integer a JavaScript number holds exactly.
const MAX_SAFE_INTEGER: i128 = 1 << 53;
/// ECMAScript prints numbers below 1e21 in plain notation.
const MAX_PLAIN_EXPONENT: i32 = 21;
const MIN_PLAIN_EXPONENT: i32 = -6;

/// The six JSON types. Integer versus float is not a type.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum JsonType {
    /// An object.
    Object,
    /// An array.
    Array,
    /// A string.
    String,
    /// A number.
    Number,
    /// `true` or `false`.
    Boolean,
    /// `null`.
    Null,
}

impl JsonType {
    /// The type's name, as `from_type` spells it.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Object => "object",
            Self::Array => "array",
            Self::String => "string",
            Self::Number => "number",
            Self::Boolean => "boolean",
            Self::Null => "null",
        }
    }

    /// The type a name names, if it names one.
    #[must_use]
    pub fn from_name(name: &str) -> Option<Self> {
        Some(match name {
            "object" => Self::Object,
            "array" => Self::Array,
            "string" => Self::String,
            "number" => Self::Number,
            "boolean" => Self::Boolean,
            "null" => Self::Null,
            _ => return None,
        })
    }
}

/// The JSON type of a value.
#[must_use]
pub fn json_type(value: &Value) -> JsonType {
    match value {
        Value::Null => JsonType::Null,
        Value::Bool(_) => JsonType::Boolean,
        Value::Number(_) => JsonType::Number,
        Value::String(_) => JsonType::String,
        Value::Array(_) => JsonType::Array,
        Value::Object(_) => JsonType::Object,
    }
}

// --- Numbers ---------------------------------------------------------------------------

/// A number as the double JavaScript reads it: correctly rounded, and
/// infinite when it is too large for a double.
#[must_use]
pub fn as_double(number: &Number) -> f64 {
    // The text is a valid JSON number, which always parses.
    number.as_str().parse().unwrap_or(f64::NAN)
}

/// Whether a number is finite as the double JavaScript reads it. An integer
/// too large for a double reads as Infinity, so it is not finite.
#[must_use]
pub fn is_finite_number(number: &Number) -> bool {
    as_double(number).is_finite()
}

/// Whether a value is a valid table row position: a finite number.
#[must_use]
pub fn is_row_position(value: &Value) -> bool {
    matches!(value, Value::Number(number) if is_finite_number(number))
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
fn format_number(number: &Number, out: &mut String) -> Result<()> {
    let double = finite_double(number)?;
    let text = number.as_str();
    if !text.contains(['.', 'e', 'E']) {
        // An integer prints exactly while JavaScript holds it exactly.
        if let Ok(integer) = text.parse::<i128>()
            && integer.abs() <= MAX_SAFE_INTEGER
        {
            write!(out, "{integer}").ok();
            return Ok(());
        }
    }
    format_double(double, out);
    Ok(())
}

fn format_double(value: f64, out: &mut String) {
    if value == 0.0 {
        out.push('0');
        return;
    }
    if value < 0.0 {
        out.push('-');
    }
    // `{:e}` prints the shortest digits that round-trip, which is also what
    // ECMAScript's Number::toString chooses; only the layout differs.
    let shortest = format!("{:e}", value.abs());
    let (mantissa, exponent) = shortest.split_once('e').unwrap_or((&shortest, "0"));
    let digits: String = mantissa.chars().filter(char::is_ascii_digit).collect();
    let k = i32::try_from(digits.len()).unwrap_or(i32::MAX);
    // value == 0.<digits> * 10^n
    let n = exponent.parse::<i32>().unwrap_or(0) + 1;
    if k <= n && n <= MAX_PLAIN_EXPONENT {
        out.push_str(&digits);
        out.extend(std::iter::repeat_n(
            '0',
            usize::try_from(n - k).unwrap_or(0),
        ));
    } else if 0 < n && n <= MAX_PLAIN_EXPONENT {
        let (whole, fraction) = digits.split_at(usize::try_from(n).unwrap_or(0));
        write!(out, "{whole}.{fraction}").ok();
    } else if MIN_PLAIN_EXPONENT < n && n <= 0 {
        out.push_str("0.");
        out.extend(std::iter::repeat_n('0', usize::try_from(-n).unwrap_or(0)));
        out.push_str(&digits);
    } else {
        let e = n - 1;
        let (first, rest) = digits.split_at(1);
        out.push_str(first);
        if !rest.is_empty() {
            write!(out, ".{rest}").ok();
        }
        write!(out, "e{}{}", if e >= 0 { '+' } else { '-' }, e.abs()).ok();
    }
}

// --- Serialization ----------------------------------------------------------------------

/// Order strings by UTF-16 code units, the order JavaScript's default sort uses.
#[must_use]
pub fn utf16_cmp(left: &str, right: &str) -> Ordering {
    left.encode_utf16().cmp(right.encode_utf16())
}

fn write_string(value: &str, out: &mut String) {
    // serde_json escapes exactly what RFC 8785 requires: `"`, `\` and the
    // control characters, with the short forms where JSON has them.
    out.push_str(&Value::from(value).to_string());
}

fn write_canonical(value: &Value, out: &mut String) -> Result<()> {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(number) => format_number(number, out)?,
        Value::String(string) => write_string(string, out),
        Value::Array(items) => {
            out.push('[');
            for (index, item) in items.iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                write_canonical(item, out)?;
            }
            out.push(']');
        }
        Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort_by(|a, b| utf16_cmp(a, b));
            out.push('{');
            for (index, key) in keys.into_iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                write_string(key, out);
                out.push(':');
                write_canonical(&map[key], out)?;
            }
            out.push('}');
        }
    }
    Ok(())
}

/// Serialize a JSON value in RFC 8785 canonical form.
///
/// # Errors
///
/// A number that is not finite as JavaScript reads it.
pub fn canonical_json(value: &Value) -> Result<String> {
    let mut out = String::new();
    write_canonical(value, &mut out)?;
    Ok(out)
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
pub fn values_equal(left: &Value, right: &Value) -> Result<bool> {
    Ok(match (left, right) {
        (Value::Number(a), Value::Number(b)) => finite_double(a)? == finite_double(b)?,
        (Value::Array(a), Value::Array(b)) => {
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
        (Value::Object(a), Value::Object(b)) => {
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
pub fn parse_handle(handle: &Value) -> Option<Map<String, Value>> {
    let text = handle.as_str()?.replace(HANDLE_QUOTE, "\"");
    match serde_json::from_str(&text) {
        Ok(Value::Object(object)) => Some(object),
        _ => None,
    }
}

// --- Table rows ---------------------------------------------------------------------------

/// A table's rows in order: by `(_pos, _id)`, or as stored for a legacy table without them.
///
/// Positions compare as the doubles JavaScript holds, and ids by UTF-16 code
/// units, as the editor sorts them.
#[must_use]
pub fn ordered_rows(rows: &[Value]) -> Vec<&Value> {
    let table = &NODE_SCHEMA.table;
    let (Some(id_key), Some(position_key)) = (table.id_key(), table.position.as_deref()) else {
        return rows.iter().collect();
    };
    let keys: Option<Vec<(f64, &str)>> = rows
        .iter()
        .map(|row| {
            let row = row.as_object()?;
            let position = match row.get(position_key)? {
                Value::Number(number) if is_finite_number(number) => as_double(number),
                _ => return None,
            };
            Some((position, row.get(id_key)?.as_str()?))
        })
        .collect();
    let Some(keys) = keys else {
        return rows.iter().collect();
    };
    let mut order: Vec<usize> = (0..rows.len()).collect();
    order.sort_by(|&a, &b| {
        keys[a]
            .0
            .total_cmp(&keys[b].0)
            .then_with(|| utf16_cmp(keys[a].1, keys[b].1))
    });
    order.into_iter().map(|index| &rows[index]).collect()
}

// --- The canonical form of a graph --------------------------------------------------------

/// A graph's canonical form, sharing every value it does not change.
enum Canon<'a> {
    /// A value taken as it is.
    Raw(&'a Value),
    /// The object a handle string encodes.
    Handle(Value),
    /// An object with some members changed, or a collection keyed by id.
    Object(HashMap<&'a str, Canon<'a>>),
    /// A collection ordered for serialization.
    Array(Vec<Canon<'a>>),
}

/// Whether the canonical form keys collections by id, for comparison, or
/// keeps them as lists ordered by id, for serialization.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Mode {
    Keyed,
    Ordered,
}

fn without(map: &Map<String, Value>, hidden: impl Fn(&str) -> bool) -> HashMap<&str, Canon<'_>> {
    map.iter()
        .filter(|(key, _)| !hidden(key))
        .map(|(key, value)| (key.as_str(), Canon::Raw(value)))
        .collect()
}

fn canonical_graph(flow: &Value, mode: Mode) -> Canon<'_> {
    let Value::Object(flow) = flow else {
        return Canon::Raw(flow);
    };
    let mut graph = without(flow, |key| NODE_SCHEMA.flow_view_state.contains(key));
    for key in ["nodes", "edges"] {
        let Some(Canon::Raw(Value::Array(entries))) = graph.get(key) else {
            continue;
        };
        let entries: Vec<Canon<'_>> = entries
            .iter()
            .map(|entry| {
                if key == "nodes" {
                    canonical_node(entry, mode)
                } else {
                    canonical_edge(entry)
                }
            })
            .collect();
        let collection = match mode {
            Mode::Keyed => by_id(entries, "id"),
            Mode::Ordered => {
                let mut entries = entries;
                entries.sort_by(|a, b| match (entry_id(a, "id"), entry_id(b, "id")) {
                    (Some(a), Some(b)) => utf16_cmp(a, b),
                    (None, Some(_)) => Ordering::Less,
                    (Some(_), None) => Ordering::Greater,
                    (None, None) => Ordering::Equal,
                });
                Canon::Array(entries)
            }
        };
        graph.insert(key, collection);
    }
    Canon::Object(graph)
}

/// The string member `key` of a canonical entry, borrowed from the graph.
fn entry_id<'a>(entry: &Canon<'a>, key: &str) -> Option<&'a str> {
    match entry {
        Canon::Raw(value) => value.as_object()?.get(key)?.as_str(),
        Canon::Object(map) => match map.get(key)? {
            Canon::Raw(value) => value.as_str(),
            _ => None,
        },
        _ => None,
    }
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

fn canonical_node(node: &Value, mode: Mode) -> Canon<'_> {
    let Value::Object(node_map) = node else {
        return Canon::Raw(node);
    };
    let mut canon = without(node_map, |key| NODE_SCHEMA.node_view_state.contains(key));
    let Some(Value::Object(data)) = node_map.get("data") else {
        return Canon::Object(canon);
    };
    let Some(Value::Object(body)) = data.get("node") else {
        return Canon::Object(canon);
    };
    let mut canon_body = without(body, |key| NODE_SCHEMA.node_data_view_state.contains(key));
    if let Some(Value::Object(template)) = body.get("template") {
        let fields = template
            .iter()
            .filter(|(key, _)| !NODE_SCHEMA.template_view_state.contains(key.as_str()))
            .map(|(key, field)| (key.as_str(), canonical_field(node, key, field, mode)))
            .collect();
        canon_body.insert("template", Canon::Object(fields));
    }
    let mut canon_data = without(data, |_| false);
    canon_data.insert("node", Canon::Object(canon_body));
    canon.insert("data", Canon::Object(canon_data));
    Canon::Object(canon)
}

/// A template field without its display-only keys, its table rows as a collection.
fn canonical_field<'a>(node: &'a Value, key: &str, field: &'a Value, mode: Mode) -> Canon<'a> {
    let Value::Object(field_map) = field else {
        return Canon::Raw(field);
    };
    let mut canon = without(field_map, |key| NODE_SCHEMA.field_view_state.contains(key));
    if let Some(Value::Array(rows)) = field_map.get("value")
        && NODE_SCHEMA.is_table_at(node, &["data", "node", "template", key, "value"])
    {
        match mode {
            Mode::Keyed => {
                let id_key = NODE_SCHEMA.table.id_key().unwrap_or("_id");
                // A legacy table without unique row ids keeps its array, which is its order.
                if let keyed @ Canon::Object(_) =
                    by_id(rows.iter().map(Canon::Raw).collect(), id_key)
                {
                    canon.insert("value", keyed);
                }
            }
            Mode::Ordered => {
                let rows = ordered_rows(rows).into_iter().map(Canon::Raw).collect();
                canon.insert("value", Canon::Array(rows));
            }
        }
    }
    Canon::Object(canon)
}

fn canonical_edge(edge: &Value) -> Canon<'_> {
    let Value::Object(edge_map) = edge else {
        return Canon::Raw(edge);
    };
    let mut canon = without(edge_map, |key| NODE_SCHEMA.edge_view_state.contains(key));
    for key in HANDLE_KEYS {
        if let Some(parsed) = edge_map.get(key).and_then(parse_handle) {
            canon.insert(key, Canon::Handle(Value::Object(parsed)));
        }
    }
    Canon::Object(canon)
}

/// One position in a canonical form: a canonical node, or a plain value.
#[derive(Clone, Copy)]
enum Node<'c, 'a> {
    Canon(&'c Canon<'a>),
    Value(&'c Value),
}

impl<'c, 'a> Node<'c, 'a> {
    fn of(canon: &'c Canon<'a>) -> Self {
        match canon {
            Canon::Raw(value) => Self::Value(value),
            Canon::Handle(value) => Self::Value(value),
            other => Self::Canon(other),
        }
    }

    fn json_type(self) -> JsonType {
        match self {
            Self::Canon(Canon::Object(_)) => JsonType::Object,
            Self::Canon(_) => JsonType::Array,
            Self::Value(value) => json_type(value),
        }
    }

    fn len(self) -> usize {
        match self {
            Self::Canon(Canon::Object(map)) => map.len(),
            Self::Canon(Canon::Array(items)) => items.len(),
            Self::Value(Value::Object(map)) => map.len(),
            Self::Value(Value::Array(items)) => items.len(),
            _ => 0,
        }
    }

    fn member(self, key: &str) -> Option<Self> {
        match self {
            Self::Canon(Canon::Object(map)) => map.get(key).map(Self::of),
            Self::Value(Value::Object(map)) => map.get(key).map(Self::Value),
            _ => None,
        }
    }

    fn members(self) -> Vec<(&'c str, Self)> {
        match self {
            Self::Canon(Canon::Object(map)) => map
                .iter()
                .map(|(key, value)| (*key, Self::of(value)))
                .collect(),
            Self::Value(Value::Object(map)) => map
                .iter()
                .map(|(key, value)| (key.as_str(), Self::Value(value)))
                .collect(),
            _ => Vec::new(),
        }
    }

    fn items(self) -> Vec<Self> {
        match self {
            Self::Canon(Canon::Array(items)) => items.iter().map(Self::of).collect(),
            Self::Value(Value::Array(items)) => items.iter().map(Self::Value).collect(),
            _ => Vec::new(),
        }
    }
}

fn canon_equal(left: Node<'_, '_>, right: Node<'_, '_>) -> Result<bool> {
    if let (Node::Value(left), Node::Value(right)) = (left, right) {
        return values_equal(left, right);
    }
    let kind = left.json_type();
    if kind != right.json_type() || left.len() != right.len() {
        return Ok(false);
    }
    if kind == JsonType::Object {
        for (key, value) in left.members() {
            match right.member(key) {
                Some(other) if canon_equal(value, other)? => {}
                _ => return Ok(false),
            }
        }
    } else {
        for (a, b) in left.items().into_iter().zip(right.items()) {
            if !canon_equal(a, b)? {
                return Ok(false);
            }
        }
    }
    Ok(true)
}

fn write_canon(node: Node<'_, '_>, out: &mut String) -> Result<()> {
    match node {
        Node::Value(value) => write_canonical(value, out),
        Node::Canon(Canon::Object(map)) => {
            let mut keys: Vec<&&str> = map.keys().collect();
            keys.sort_by(|a, b| utf16_cmp(a, b));
            out.push('{');
            for (index, key) in keys.into_iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                write_string(key, out);
                out.push(':');
                write_canon(Node::of(&map[key]), out)?;
            }
            out.push('}');
            Ok(())
        }
        Node::Canon(_) => {
            out.push('[');
            for (index, item) in node.items().into_iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                write_canon(item, out)?;
            }
            out.push(']');
            Ok(())
        }
    }
}

/// Serialize flow data in canonical graph form, as RFC 8785 text.
///
/// # Errors
///
/// A number that is not finite as JavaScript reads it.
pub fn canonical_graph_json(flow: &Value) -> Result<String> {
    let canon = canonical_graph(flow, Mode::Ordered);
    let mut out = String::new();
    write_canon(Node::of(&canon), &mut out)?;
    Ok(out)
}

/// The SHA-256 hex digest of flow data's canonical graph form.
///
/// # Errors
///
/// A number that is not finite as JavaScript reads it.
pub fn graph_hash(flow: &Value) -> Result<String> {
    let digest = Sha256::digest(canonical_graph_json(flow)?.as_bytes());
    let mut hex = String::with_capacity(64);
    for byte in digest {
        write!(hex, "{byte:02x}").ok();
    }
    Ok(hex)
}

/// Whether two flows are the same graph, stopping at the first difference.
///
/// # Errors
///
/// A compared number that is not finite as JavaScript reads it.
pub fn graphs_equal(left: &Value, right: &Value) -> Result<bool> {
    let left = canonical_graph(left, Mode::Keyed);
    let right = canonical_graph(right, Mode::Keyed);
    canon_equal(Node::of(&left), Node::of(&right))
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    fn canonical(text: &str) -> String {
        canonical_json(&serde_json::from_str(text).unwrap()).unwrap()
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
            let value: Value = serde_json::from_str(text).unwrap();
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
                let a: Value = serde_json::from_str(left).unwrap();
                let b: Value = serde_json::from_str(right).unwrap();
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
            "nodes": [
                {"id": "b", "selected": true, "data": {"node": {"template": {}}}},
                {"id": "a", "data": {"node": {"last_updated": "x", "template": {
                    "rows": {"type": "table", "value": [{"_id": "r2", "_pos": 2}, {"_id": "r1", "_pos": 1.0}]}
                }}}},
            ],
            "edges": [{"id": "e", "sourceHandle": "{œnameœ: œoutœ}", "animated": true}],
        });
        let right = json!({
            "nodes": [
                {"id": "a", "data": {"node": {"template": {
                    "rows": {"type": "table", "value": [{"_id": "r1", "_pos": 1}, {"_id": "r2", "_pos": 2}]}
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
}
