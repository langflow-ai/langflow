//! Reading and writing an [`AnyValue`] through `serde_json`.

use std::fmt;
use std::str::FromStr;

use serde::de::{self, Deserialize, DeserializeSeed, Deserializer, MapAccess, SeqAccess, Visitor};

use crate::data::value::map::{Entries, entries_of, small_and_unique};
use crate::data::value::number::N;
use crate::data::value::string::StringSeed;
use crate::data::value::{AnyMap, AnyString, AnyValue, Number, StringPool};

// --- json! ------------------------------------------------------------------------------------

// These let `json!` take a value that is already an `AnyValue`.

impl serde::Serialize for AnyValue {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        match self {
            AnyValue::Null => serializer.serialize_unit(),
            AnyValue::Bool(flag) => serializer.serialize_bool(*flag),
            AnyValue::Number(number) => number.serialize(serializer),
            AnyValue::String(text) => serializer.serialize_str(text),
            AnyValue::Array(items) => serializer.collect_seq(items),
            AnyValue::Object(map) => map.serialize(serializer),
        }
    }
}

impl serde::Serialize for AnyMap {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.collect_map(self.iter().map(|(key, value)| (key.as_str(), value)))
    }
}

impl serde::Serialize for Number {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        match &self.0 {
            N::PosInt(int) => serializer.serialize_u64(*int),
            N::NegInt(int) => serializer.serialize_i64(*int),
            N::Float(float) => serializer.serialize_f64(*float),
            // A number kept as text stays text: `json!` keeps it with arbitrary_precision.
            N::Text(text) => serde_json::Number::from_str(text)
                .map_err(serde::ser::Error::custom)?
                .serialize(serializer),
        }
    }
}

// --- Parsing ----------------------------------------------------------------------------------

/// The key of the one-key map that holds a number's text (`arbitrary_precision`).
const NUMBER_TOKEN: &str = "$serde_json::private::Number";

impl<'de> Deserialize<'de> for AnyValue {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<AnyValue, D::Error> {
        Builder::<false>::default().value(deserializer)
    }
}

/// Why [`FiniteAnyValue`] refuses a number.
pub const NOT_FINITE: &str = "NaN and Infinity are not JSON numbers";

/// A value whose every number is finite as a double. Example: `1e400` fails
/// ([`NOT_FINITE`]). A large integer keeps its digits, as a Python `int` does.
#[derive(Debug, Clone, PartialEq)]
pub struct FiniteAnyValue(pub AnyValue);

impl<'de> Deserialize<'de> for FiniteAnyValue {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<FiniteAnyValue, D::Error> {
        Builder::<true>::default()
            .value(deserializer)
            .map(FiniteAnyValue)
    }
}

/// The stacks of members and items that a parse holds for open objects and
/// arrays. A closed one moves its members into a collection of exact size.
#[derive(Debug, Default)]
pub(crate) struct Builder<const FINITE: bool> {
    strings: StringPool,
    entries: Vec<(AnyString, AnyValue)>,
    items: Vec<AnyValue>,
}

impl<const FINITE: bool> Builder<FINITE> {
    fn value<'de, D: Deserializer<'de>>(mut self, deserializer: D) -> Result<AnyValue, D::Error> {
        deserializer.deserialize_any(AnyValueVisitor::<FINITE>(&mut self))
    }
}

/// Builds an [`AnyValue`] with a [`Builder`]. With `FINITE`, it refuses Infinity.
struct AnyValueVisitor<'b, const FINITE: bool>(&'b mut Builder<FINITE>);

/// Reads one JSON value as [`FiniteAnyValue`] does, with a builder shared
/// across the values of one input, so they share its string pool.
pub(crate) struct FiniteSeed<'b>(pub(crate) &'b mut Builder<true>);

impl<'de> DeserializeSeed<'de> for FiniteSeed<'_> {
    type Value = AnyValue;
    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<AnyValue, D::Error> {
        deserializer.deserialize_any(AnyValueVisitor::<true>(self.0))
    }
}

impl<'de, const FINITE: bool> DeserializeSeed<'de> for AnyValueVisitor<'_, FINITE> {
    type Value = AnyValue;

    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<AnyValue, D::Error> {
        deserializer.deserialize_any(self)
    }
}

impl<'de, const FINITE: bool> Visitor<'de> for AnyValueVisitor<'_, FINITE> {
    type Value = AnyValue;

    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("a JSON value")
    }

    fn visit_bool<E>(self, flag: bool) -> Result<AnyValue, E> {
        Ok(AnyValue::Bool(flag))
    }

    fn visit_i64<E>(self, int: i64) -> Result<AnyValue, E> {
        Ok(AnyValue::Number(int.into()))
    }

    fn visit_u64<E>(self, int: u64) -> Result<AnyValue, E> {
        Ok(AnyValue::Number(int.into()))
    }

    fn visit_f64<E>(self, float: f64) -> Result<AnyValue, E> {
        Ok(AnyValue::from(float))
    }

    fn visit_str<E>(self, text: &str) -> Result<AnyValue, E> {
        Ok(AnyValue::String(self.0.strings.intern(text)))
    }

    fn visit_string<E>(self, text: String) -> Result<AnyValue, E> {
        Ok(AnyValue::String(self.0.strings.intern(&text)))
    }

    fn visit_unit<E>(self) -> Result<AnyValue, E> {
        Ok(AnyValue::Null)
    }

    fn visit_none<E>(self) -> Result<AnyValue, E> {
        Ok(AnyValue::Null)
    }

    fn visit_some<D: Deserializer<'de>>(self, deserializer: D) -> Result<AnyValue, D::Error> {
        deserializer.deserialize_any(self)
    }

    fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<AnyValue, A::Error> {
        let builder = self.0;
        let start = builder.items.len();
        while let Some(item) = seq.next_element_seed(AnyValueVisitor(&mut *builder))? {
            builder.items.push(item);
        }
        Ok(AnyValue::Array(builder.items.drain(start..).collect()))
    }

    fn visit_map<A: MapAccess<'de>>(self, mut access: A) -> Result<AnyValue, A::Error> {
        let builder = self.0;
        let start = builder.entries.len();
        while let Some(key) = access.next_key_seed(StringSeed(&mut builder.strings))? {
            if builder.entries.len() == start && key == NUMBER_TOKEN {
                let text: String = access.next_value()?;
                let number: Number = text
                    .parse()
                    .map_err(|_| de::Error::custom("not a JSON number"))?;
                if FINITE && !number.is_integer() && number.as_f64().is_none_or(f64::is_infinite) {
                    return Err(de::Error::custom(NOT_FINITE));
                }
                return Ok(AnyValue::Number(number));
            }
            let value = access.next_value_seed(AnyValueVisitor(&mut *builder))?;
            builder.entries.push((key, value));
        }
        // A repeated key keeps its first position and its last value. The rows
        // are not shared yet, so no insert checks the reference count.
        let entries = if small_and_unique(&builder.entries[start..]) {
            // One allocation of exactly these rows.
            Entries::Small(builder.entries.drain(start..).collect())
        } else {
            entries_of(builder.entries.drain(start..).collect())
        };
        Ok(AnyValue::Object(AnyMap { entries }))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(text: &str) -> AnyValue {
        serde_json::from_str(text).unwrap()
    }

    #[test]
    fn a_finite_value_refuses_a_number_too_large_for_a_double() {
        for text in ["1e400", "[1, -1e400]", r#"{"a": {"b": [1E999]}}"#] {
            let error = serde_json::from_str::<FiniteAnyValue>(text).unwrap_err();
            assert!(error.to_string().starts_with(NOT_FINITE), "{text}: {error}");
            // AnyValue keeps the number's text.
            serde_json::from_str::<AnyValue>(text).unwrap();
        }
        let digits = format!("1{}", "0".repeat(309));
        let text = format!(r#"[{digits}, 1.5e308, 1e-400, {{"a": 1}}]"#);
        let FiniteAnyValue(value) = serde_json::from_str(&text).unwrap();
        assert_eq!(value, parse(&text));
    }

    #[test]
    fn json_text_reads_back_as_written() {
        let text = r#"{"x":[null,true,"é",{"k":-3}],"y":2.5}"#;
        assert_eq!(parse(text).to_string(), text);
    }
}
