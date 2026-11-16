//! Numbers as JavaScript reads and prints them, and JavaScript's string order.

use std::cmp::Ordering;
use std::io::Write as _;

use crate::data::value::{AnyValue, Number};

use crate::models::error::{Error, Result};

/// Largest integer a JavaScript number holds exactly.
pub(super) const MAX_SAFE_INTEGER: i128 = 1 << 53;
/// ECMAScript prints numbers below 1e21 in plain notation.
const MAX_PLAIN_EXPONENT: i32 = 21;
const MIN_PLAIN_EXPONENT: i32 = -6;

/// A number as the double JavaScript reads it. Too large a number is infinite.
#[must_use]
pub fn as_double(number: &Number) -> f64 {
    number.as_f64().unwrap_or(f64::NAN)
}

/// Whether a number is finite as the double JavaScript reads it.
#[must_use]
pub fn is_finite_number(number: &Number) -> bool {
    as_double(number).is_finite()
}

/// Whether a value is a valid table row position: a finite number.
#[must_use]
pub fn is_row_position(value: &AnyValue) -> bool {
    matches!(value, AnyValue::Number(number) if is_finite_number(number))
}

pub(super) fn finite_double(number: &Number) -> Result<f64> {
    let double = as_double(number);
    if double.is_finite() {
        Ok(double)
    } else {
        Err(Error::non_finite())
    }
}

pub(super) fn format_double(value: f64, out: &mut Vec<u8>) {
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

/// Order strings by UTF-16 code units, the order JavaScript's default sort uses.
///
/// UTF-8 bytes give the same order when the first bytes that differ are below
/// 0xEE. Above that, a surrogate pair can sort before U+E000 to U+FFFF.
#[must_use]
pub fn utf16_cmp(left: &str, right: &str) -> Ordering {
    let (left_bytes, right_bytes) = (left.as_bytes(), right.as_bytes());
    match left_bytes.iter().zip(right_bytes).find(|(a, b)| a != b) {
        None => left_bytes.len().cmp(&right_bytes.len()),
        Some((a, b)) if *a < 0xEE && *b < 0xEE => a.cmp(b),
        Some(_) => left.encode_utf16().cmp(right.encode_utf16()),
    }
}
