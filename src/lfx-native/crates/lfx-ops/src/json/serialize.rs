//! Write JSON text fast into a byte buffer.
//!
//! A flow is mostly long strings, such as code, so a string is
//! scanned eight bytes at a time. [`Ascii::Escape`] writes as Python's
//! `json.dumps` does by default. Example: `é` gives `\u00e9`.

use crate::json::{FlowObj, FlowValue};

/// Whether a written string escapes its characters above U+007F.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Ascii {
    /// Write them as they are, as RFC 8785 does.
    Keep,
    /// Write each as `\uXXXX`, a surrogate pair above U+FFFF.
    Escape,
}

/// Whether a byte starts an escape: `"`, `\`, a control character, or with
/// `ESCAPE`, a byte of a character above U+007F.
#[inline]
fn special<const ESCAPE: bool>(byte: u8) -> bool {
    byte < 0x20 || byte == b'"' || byte == b'\\' || (ESCAPE && byte >= 0x80)
}

const ONES: u64 = 0x0101_0101_0101_0101;
const HIGHS: u64 = 0x8080_8080_8080_8080;

/// The high bit of each zero byte of `word` (little-endian). A borrow can
/// also mark later bytes, but the lowest mark is always a zero byte.
#[inline]
fn zero_bytes(word: u64) -> u64 {
    word.wrapping_sub(ONES) & !word & HIGHS
}

/// Marks for the bytes of `word` that start an escape, as [`zero_bytes`]
/// marks: the lowest mark is always such a byte, and none means none is.
#[inline]
fn special_bytes<const ESCAPE: bool>(word: u64) -> u64 {
    let control = word.wrapping_sub(ONES * 0x20) & !word & HIGHS;
    let quote = zero_bytes(word ^ (ONES * u64::from(b'"')));
    let backslash = zero_bytes(word ^ (ONES * u64::from(b'\\')));
    let marks = control | quote | backslash;
    if ESCAPE {
        marks | (word & HIGHS)
    } else {
        marks
    }
}

/// `\uXXXX` for a UTF-16 unit, in lower-case hex.
fn unit_escape(unit: u16) -> [u8; 6] {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let digit = |shift: u16| HEX[usize::from((unit >> shift) & 0xf)];
    [b'\\', b'u', digit(12), digit(8), digit(4), digit(0)]
}

/// Write the escape of the character at `at`. Return its length in `text`.
fn write_escape(out: &mut Vec<u8>, text: &str, at: usize) -> usize {
    let byte = text.as_bytes()[at];
    let short: &[u8] = match byte {
        b'"' => b"\\\"",
        b'\\' => b"\\\\",
        0x08 => b"\\b",
        0x0c => b"\\f",
        b'\n' => b"\\n",
        b'\r' => b"\\r",
        b'\t' => b"\\t",
        0x00..=0x1f => {
            out.extend_from_slice(&unit_escape(u16::from(byte)));
            return 1;
        }
        _ => {
            let character = text[at..].chars().next().expect("a character starts here");
            for unit in character.encode_utf16(&mut [0; 2]) {
                out.extend_from_slice(&unit_escape(*unit));
            }
            return character.len_utf8();
        }
    };
    out.extend_from_slice(short);
    1
}

/// Write a string as a JSON string, quotes included.
pub(crate) fn write_str(out: &mut Vec<u8>, text: &str, ascii: Ascii) {
    match ascii {
        Ascii::Keep => write_str_with::<false>(out, text),
        Ascii::Escape => write_str_with::<true>(out, text),
    }
}

fn write_str_with<const ESCAPE: bool>(out: &mut Vec<u8>, text: &str) {
    let bytes = text.as_bytes();
    out.reserve(bytes.len() + 2);
    out.push(b'"');
    // `start` is the first byte not yet written; `at` is where the scan is.
    let (mut start, mut at) = (0, 0);
    while at < bytes.len() {
        // Skip eight bytes at a time while none starts an escape.
        while let Some(word) = bytes.get(at..at + 8) {
            let word = u64::from_le_bytes(word.try_into().expect("eight bytes"));
            let marks = special_bytes::<ESCAPE>(word);
            if marks == 0 {
                at += 8;
            } else {
                at += (marks.trailing_zeros() / 8) as usize;
                break;
            }
        }
        match bytes.get(at) {
            Some(&byte) if special::<ESCAPE>(byte) => {
                out.extend_from_slice(&bytes[start..at]);
                at += write_escape(out, text, at);
                start = at;
            }
            Some(_) => at += 1,
            None => break,
        }
    }
    out.extend_from_slice(&bytes[start..]);
    out.push(b'"');
}

/// Write a value as compact JSON text, object keys in their order.
pub(crate) fn write_value(out: &mut Vec<u8>, value: &FlowValue, ascii: Ascii) {
    match value {
        FlowValue::Null => out.extend_from_slice(b"null"),
        FlowValue::Bool(true) => out.extend_from_slice(b"true"),
        FlowValue::Bool(false) => out.extend_from_slice(b"false"),
        FlowValue::Number(number) => {
            use std::io::Write as _;
            write!(out, "{number}").expect("a number is written to memory");
        }
        FlowValue::String(text) => {
            if ascii == Ascii::Escape
                && let Some(encoded) = text.shared_ascii_json()
            {
                out.extend_from_slice(encoded);
            } else {
                write_str(out, text, ascii);
            }
        }
        FlowValue::Array(items) => write_seq(out, items, |out, item| write_value(out, item, ascii)),
        FlowValue::Object(map) => write_map(out, map, ascii),
    }
}

/// Write an object as compact JSON text, its keys in their order.
pub(crate) fn write_map(out: &mut Vec<u8>, map: &FlowObj, ascii: Ascii) {
    write_entries(
        out,
        map.iter(),
        |out, value| write_value(out, value, ascii),
        ascii,
    );
}

/// Write `items` as a JSON array, each with `write_item`.
pub(crate) fn write_seq<T>(
    out: &mut Vec<u8>,
    items: impl IntoIterator<Item = T>,
    mut write_item: impl FnMut(&mut Vec<u8>, T),
) {
    out.push(b'[');
    for (index, item) in items.into_iter().enumerate() {
        if index > 0 {
            out.push(b',');
        }
        write_item(out, item);
    }
    out.push(b']');
}

/// Write keys and values as a JSON object, each value with `write_value`.
pub(crate) fn write_entries<K: AsRef<str>, V>(
    out: &mut Vec<u8>,
    entries: impl IntoIterator<Item = (K, V)>,
    mut write_value: impl FnMut(&mut Vec<u8>, V),
    ascii: Ascii,
) {
    out.push(b'{');
    for (index, (key, value)) in entries.into_iter().enumerate() {
        if index > 0 {
            out.push(b',');
        }
        write_str(out, key.as_ref(), ascii);
        out.push(b':');
        write_value(out, value);
    }
    out.push(b'}');
}

/// Bytes the buffer holds as text. Everything written here is UTF-8.
pub(crate) fn into_string(out: Vec<u8>) -> String {
    String::from_utf8(out).expect("JSON text is written as UTF-8")
}

// --- Strings as Python's `repr` prints them -------------------------------------------------

/// A string as error messages quote it: as Python's `repr` prints it, so
/// messages read the same in every runtime.
pub(crate) fn quoted(value: &str) -> String {
    let quote = if value.contains('\'') && !value.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::with_capacity(value.len() + 2);
    out.push(quote);
    for c in value.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if is_printable(c) => out.push(c),
            c => {
                let code = u32::from(c);
                let escaped = if code < 0x100 {
                    format!("\\x{code:02x}")
                } else if code < 0x1_0000 {
                    format!("\\u{code:04x}")
                } else {
                    format!("\\U{code:08x}")
                };
                out.push_str(&escaped);
            }
        }
    }
    out.push(quote);
    out
}

/// Whether Python's `str.isprintable` holds for a character: not a control,
/// format, separator (other than a space), surrogate or private-use character.
fn is_printable(c: char) -> bool {
    !(c.is_control()
        || matches!(
            c,
            '\u{a0}' | '\u{ad}' | '\u{600}'..='\u{605}' | '\u{61c}' | '\u{6dd}' | '\u{70f}' | '\u{1680}'
                | '\u{180e}' | '\u{2000}'..='\u{200f}' | '\u{2028}'..='\u{202f}' | '\u{205f}'..='\u{2064}'
                | '\u{2066}'..='\u{206f}' | '\u{3000}' | '\u{e000}'..='\u{f8ff}' | '\u{feff}'
                | '\u{fff9}'..='\u{fffb}' | '\u{f0000}'..='\u{10ffff}'
        ))
}

#[cfg(test)]
mod tests {
    #[test]
    fn strings_are_quoted_as_python_prints_them() {
        assert_eq!(quoted("e1"), "'e1'");
        assert_eq!(quoted("it's"), "\"it's\"");
        assert_eq!(quoted("a'b\"c"), "'a\\'b\"c'");
        assert_eq!(quoted("tab\there\\"), "'tab\\there\\\\'");
        assert_eq!(quoted("\u{1}\u{a0}é"), "'\\x01\\xa0é'");
    }

    use std::fmt::Write as _;

    use super::*;

    /// A string written one character at a time, as the reference.
    fn reference(text: &str, ascii: Ascii) -> String {
        let mut out = String::from('"');
        for character in text.chars() {
            match character {
                '"' => out.push_str("\\\""),
                '\\' => out.push_str("\\\\"),
                '\n' => out.push_str("\\n"),
                '\r' => out.push_str("\\r"),
                '\t' => out.push_str("\\t"),
                '\u{8}' => out.push_str("\\b"),
                '\u{c}' => out.push_str("\\f"),
                '\0'..='\u{1f}' => write!(out, "\\u{:04x}", u32::from(character)).unwrap(),
                _ if ascii == Ascii::Escape && !character.is_ascii() => {
                    for unit in character.encode_utf16(&mut [0; 2]) {
                        write!(out, "\\u{unit:04x}").unwrap();
                    }
                }
                _ => out.push(character),
            }
        }
        out.push('"');
        out
    }

    #[test]
    fn strings_are_written_by_the_escape_rules() {
        let pieces = [
            "a", "\"", "\\", "\n", "\r", "\t", "\u{8}", "\u{c}", "\u{0}", "\u{1f}", "\u{7f}", "é",
            "œ", "😀", "\u{2028}", "\u{fffd}", "/",
        ];
        for ascii in [Ascii::Keep, Ascii::Escape] {
            for piece in pieces {
                for before in 0..96 {
                    for after in [0, 1, 7, 8, 15, 16, 17, 31, 32, 33, 63, 64] {
                        let text =
                            format!("{}{piece}{}{piece}", "x".repeat(before), "y".repeat(after));
                        let mut out = Vec::new();
                        write_str(&mut out, &text, ascii);
                        assert_eq!(into_string(out), reference(&text, ascii), "{text:?}");
                    }
                }
            }
            let dense: String = pieces.concat().repeat(9);
            let mut out = Vec::new();
            write_str(&mut out, &dense, ascii);
            assert_eq!(into_string(out), reference(&dense, ascii));
        }
    }

    #[test]
    fn values_are_written_compact_in_their_order() {
        let text =
            r#"{"b":[1,-2,1.0,1e300,12345678901234567890123,null,true,false,{}],"a":"é\n","":[]}"#;
        let value: FlowValue = serde_json::from_str(text).unwrap();
        let mut out = Vec::new();
        write_value(&mut out, &value, Ascii::Keep);
        assert_eq!(into_string(out), text.replace("1e300", "1e+300"));
    }
}
