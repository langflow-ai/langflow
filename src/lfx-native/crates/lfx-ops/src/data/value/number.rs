//! [`Number`]: a JSON number that keeps `1` and `1.0` apart.

use std::fmt;
use std::str::FromStr;

/// A JSON number: an integer or a double, or the text of one that neither holds exactly.
#[derive(Debug, Clone, PartialEq)]
pub struct Number(pub(super) N);

#[derive(Debug, Clone, PartialEq)]
pub(super) enum N {
    /// An integer from 0 to `u64::MAX`.
    PosInt(u64),
    /// A negative integer from `i64::MIN`.
    NegInt(i64),
    /// A finite double, from text with a fraction or an exponent.
    Float(f64),
    /// The text of an integer too large for 64 bits, or of a number that is
    /// infinite as a double.
    Text(Box<str>),
}

impl Number {
    /// A finite double as a number, or `None`.
    #[must_use]
    pub fn from_f64(value: f64) -> Option<Number> {
        value.is_finite().then_some(Number(N::Float(value)))
    }

    /// The number as an `i64`, when it is an integer that one holds.
    #[must_use]
    pub fn as_i64(&self) -> Option<i64> {
        match self.0 {
            N::PosInt(int) => i64::try_from(int).ok(),
            N::NegInt(int) => Some(int),
            N::Float(_) | N::Text(_) => None,
        }
    }

    /// The number as a `u64`, when it is an integer that one holds.
    #[must_use]
    pub fn as_u64(&self) -> Option<u64> {
        match self.0 {
            N::PosInt(int) => Some(int),
            N::NegInt(_) | N::Float(_) | N::Text(_) => None,
        }
    }

    /// The number as a double, `None` only for text that is not a number.
    #[must_use]
    #[expect(clippy::cast_precision_loss, reason = "a double is what is asked for")]
    pub fn as_f64(&self) -> Option<f64> {
        match &self.0 {
            N::PosInt(int) => Some(*int as f64),
            N::NegInt(int) => Some(*int as f64),
            N::Float(float) => Some(*float),
            N::Text(text) => text.parse().ok(),
        }
    }

    /// Whether the text had no fraction and no exponent, as a Python `int`.
    #[must_use]
    pub fn is_integer(&self) -> bool {
        match &self.0 {
            N::PosInt(_) | N::NegInt(_) => true,
            N::Float(_) => false,
            N::Text(text) => !text.contains(['.', 'e', 'E']),
        }
    }

    /// The number as an integer, when it is one that 128 bits hold.
    #[must_use]
    pub fn as_i128(&self) -> Option<i128> {
        match &self.0 {
            N::PosInt(int) => Some(i128::from(*int)),
            N::NegInt(int) => Some(i128::from(*int)),
            N::Text(text) if self.is_integer() => text.parse().ok(),
            N::Float(_) | N::Text(_) => None,
        }
    }
}

impl From<i64> for Number {
    fn from(int: i64) -> Self {
        match u64::try_from(int) {
            Ok(positive) => Number(N::PosInt(positive)),
            Err(_) => Number(N::NegInt(int)),
        }
    }
}

impl From<u64> for Number {
    fn from(int: u64) -> Self {
        Number(N::PosInt(int))
    }
}

/// `From` each narrower integer type for [`Number`], through the 64-bit type that holds it.
macro_rules! number_from {
    ($($int:ty => $wide:ty),*) => {$(
        impl From<$int> for Number {
            #[allow(clippy::cast_lossless, reason = "`From<usize>` for `u64` does not exist")]
            fn from(int: $int) -> Self {
                Number::from(int as $wide)
            }
        }
    )*};
}
number_from!(i32 => i64, u32 => u64, usize => u64);

/// The text of a JSON number is not a number.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NotANumber;

impl fmt::Display for NotANumber {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("not a JSON number")
    }
}

impl std::error::Error for NotANumber {}

/// A number from its JSON text: an integer that 64 bits hold, a finite double
/// from text with a fraction or an exponent, or else the text.
impl FromStr for Number {
    type Err = NotANumber;
    fn from_str(text: &str) -> Result<Self, NotANumber> {
        if !is_json_number(text) {
            return Err(NotANumber);
        }
        if !text.contains(['.', 'e', 'E']) {
            if let Ok(int) = text.parse::<u64>() {
                return Ok(Number(N::PosInt(int)));
            }
            if let Ok(int) = text.parse::<i64>() {
                return Ok(Number(N::NegInt(int)));
            }
            return Ok(Number(N::Text(text.into())));
        }
        match text.parse::<f64>() {
            Ok(float) if float.is_finite() => Ok(Number(N::Float(float))),
            _ => Ok(Number(N::Text(text.into()))),
        }
    }
}

/// Whether text has the grammar of a JSON number (RFC 8259).
fn is_json_number(text: &str) -> bool {
    let bytes = text.as_bytes();
    let mut at = usize::from(bytes.first() == Some(&b'-'));
    let digits = |at: &mut usize| {
        let start = *at;
        while bytes.get(*at).is_some_and(u8::is_ascii_digit) {
            *at += 1;
        }
        *at - start
    };
    match bytes.get(at) {
        Some(b'0') => at += 1,
        Some(b'1'..=b'9') => {
            digits(&mut at);
        }
        _ => return false,
    }
    if bytes.get(at) == Some(&b'.') {
        at += 1;
        if digits(&mut at) == 0 {
            return false;
        }
    }
    if matches!(bytes.get(at), Some(b'e' | b'E')) {
        at += 1;
        if matches!(bytes.get(at), Some(b'+' | b'-')) {
            at += 1;
        }
        if digits(&mut at) == 0 {
            return false;
        }
    }
    at == bytes.len()
}

/// The number's JSON text: integers in full, doubles in the shortest form that
/// reads back as the same double (`1.0`, `1e+300`), and text as it is.
impl fmt::Display for Number {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match &self.0 {
            N::PosInt(int) => write!(f, "{int}"),
            N::NegInt(int) => write!(f, "{int}"),
            N::Float(float) => f.write_str(&serde_json::to_string(float).map_err(|_| fmt::Error)?),
            N::Text(text) => f.write_str(text),
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::data::value::AnyValue;

    fn parse(text: &str) -> AnyValue {
        serde_json::from_str(text).unwrap()
    }

    #[test]
    fn numbers_keep_int_and_float_apart() {
        let value =
            parse("[1, 1.0, -0.0, 1e2, 12345678901234567890123, 1e400, -5, 18446744073709551615]");
        assert_eq!(
            value.to_string(),
            "[1,1.0,-0.0,100.0,12345678901234567890123,1e+400,-5,18446744073709551615]"
        );
        let items = value.as_array().unwrap();
        assert_ne!(items[0], items[1]);
        assert!(items[0].as_number().unwrap().is_integer());
        assert!(!items[1].as_number().unwrap().is_integer());
        assert!(items[5].as_f64().unwrap().is_infinite());
        assert_eq!(
            items[4].as_number().unwrap().as_i128(),
            Some(12_345_678_901_234_567_890_123)
        );
    }
}
