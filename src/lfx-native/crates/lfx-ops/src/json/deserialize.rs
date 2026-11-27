//! JSON text → [`FlowValue`], through `serde_json`.

use std::fmt;

use serde::de::{self, Deserialize, DeserializeSeed, Deserializer, MapAccess, SeqAccess, Visitor};

use crate::json::{FlowObj, FlowStr, FlowValue, Number, StringPool};
use crate::types::{Entries, StringSeed, entries_of, small_and_unique};

/// The key of the one-key map that holds a number's text
/// (`arbitrary_precision`).
const NUMBER_TOKEN: &str = "$serde_json::private::Number";

impl<'de> Deserialize<'de> for FlowValue {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<FlowValue, D::Error> {
        Builder::<false>::default().value(deserializer)
    }
}

/// Why [`FiniteFlowValue`] refuses a number.
pub const NOT_FINITE: &str = "NaN and Infinity are not JSON numbers";

/// A value whose every number is finite as a double. Example:
/// `1e400` fails ([`NOT_FINITE`]). A large integer keeps its
/// digits, as a Python `int` does.
#[derive(Debug, Clone, PartialEq)]
pub struct FiniteFlowValue(pub FlowValue);

impl<'de> Deserialize<'de> for FiniteFlowValue {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<FiniteFlowValue, D::Error> {
        Builder::<true>::default()
            .value(deserializer)
            .map(FiniteFlowValue)
    }
}

/// The stacks of members and items that a parse holds for open
/// objects and arrays. A closed one moves its members into a
/// collection of exact size.
#[derive(Debug, Default)]
pub(crate) struct Builder<const FINITE: bool> {
    pub(crate) strings: StringPool,
    entries: Vec<(FlowStr, FlowValue)>,
    items: Vec<FlowValue>,
}

impl<const FINITE: bool> Builder<FINITE> {
    fn value<'de, D: Deserializer<'de>>(mut self, deserializer: D) -> Result<FlowValue, D::Error> {
        deserializer.deserialize_any(FlowValueVisitor::<FINITE>(&mut self))
    }
}

/// Builds an [`FlowValue`] with a [`Builder`]. With `FINITE`,
/// it refuses Infinity.
struct FlowValueVisitor<'b, const FINITE: bool>(&'b mut Builder<FINITE>);

/// Reads one JSON value as [`FiniteFlowValue`] does, with a
/// builder shared across the values of one input, so they share
/// its string pool.
#[cfg(feature = "bindings")]
pub(crate) struct FiniteSeed<'b>(pub(crate) &'b mut Builder<true>);

#[cfg(feature = "bindings")]
impl<'de> DeserializeSeed<'de> for FiniteSeed<'_> {
    type Value = FlowValue;
    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<FlowValue, D::Error> {
        deserializer.deserialize_any(FlowValueVisitor::<true>(self.0))
    }
}

impl<'de, const FINITE: bool> DeserializeSeed<'de> for FlowValueVisitor<'_, FINITE> {
    type Value = FlowValue;

    fn deserialize<D: Deserializer<'de>>(self, deserializer: D) -> Result<FlowValue, D::Error> {
        deserializer.deserialize_any(self)
    }
}

impl<'de, const FINITE: bool> Visitor<'de> for FlowValueVisitor<'_, FINITE> {
    type Value = FlowValue;

    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("a JSON value")
    }

    fn visit_bool<E>(self, flag: bool) -> Result<FlowValue, E> {
        Ok(FlowValue::Bool(flag))
    }

    fn visit_i64<E>(self, int: i64) -> Result<FlowValue, E> {
        Ok(FlowValue::Number(int.into()))
    }

    fn visit_u64<E>(self, int: u64) -> Result<FlowValue, E> {
        Ok(FlowValue::Number(int.into()))
    }

    fn visit_f64<E>(self, float: f64) -> Result<FlowValue, E> {
        Ok(FlowValue::from(float))
    }

    fn visit_str<E>(self, text: &str) -> Result<FlowValue, E> {
        Ok(FlowValue::String(self.0.strings.intern(text)))
    }

    fn visit_string<E>(self, text: String) -> Result<FlowValue, E> {
        Ok(FlowValue::String(self.0.strings.intern(&text)))
    }

    fn visit_unit<E>(self) -> Result<FlowValue, E> {
        Ok(FlowValue::Null)
    }

    fn visit_none<E>(self) -> Result<FlowValue, E> {
        Ok(FlowValue::Null)
    }

    fn visit_some<D: Deserializer<'de>>(self, deserializer: D) -> Result<FlowValue, D::Error> {
        deserializer.deserialize_any(self)
    }

    fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<FlowValue, A::Error> {
        let builder = self.0;
        let start = builder.items.len();
        while let Some(item) = seq.next_element_seed(FlowValueVisitor(&mut *builder))? {
            builder.items.push(item);
        }
        Ok(FlowValue::Array(builder.items.drain(start..).collect()))
    }

    fn visit_map<A: MapAccess<'de>>(self, mut access: A) -> Result<FlowValue, A::Error> {
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
                return Ok(FlowValue::Number(number));
            }
            let value = access.next_value_seed(FlowValueVisitor(&mut *builder))?;
            builder.entries.push((key, value));
        }
        // A repeated key keeps its first position and its last
        // value. The rows are not shared yet, so no insert
        // checks the reference count.
        let entries = if small_and_unique(&builder.entries[start..]) {
            // One allocation of exactly these rows.
            Entries::Small(builder.entries.drain(start..).collect())
        } else {
            entries_of(builder.entries.drain(start..).collect())
        };
        Ok(FlowValue::Object(FlowObj { entries }))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(text: &str) -> FlowValue {
        serde_json::from_str(text).unwrap()
    }

    #[test]
    fn a_finite_value_refuses_a_number_too_large_for_a_double() {
        for text in ["1e400", "[1, -1e400]", r#"{"a": {"b": [1E999]}}"#] {
            let error = serde_json::from_str::<FiniteFlowValue>(text).unwrap_err();
            assert!(error.to_string().starts_with(NOT_FINITE), "{text}: {error}");
            // FlowValue keeps the number's text.
            serde_json::from_str::<FlowValue>(text).unwrap();
        }
        let digits = format!("1{}", "0".repeat(309));
        let text = format!(r#"[{digits}, 1.5e308, 1e-400, {{"a": 1}}]"#);
        let FiniteFlowValue(value) = serde_json::from_str(&text).unwrap();
        assert_eq!(value, parse(&text));
    }

    #[test]
    fn json_text_reads_back_as_written() {
        let text = r#"{"x":[null,true,"é",{"k":-3}],"y":2.5}"#;
        assert_eq!(parse(text).to_string(), text);
    }
}
