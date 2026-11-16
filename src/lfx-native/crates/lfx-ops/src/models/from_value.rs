//! Reading typed values out of a parsed JSON value.
//!
//! Each type moves the parts it keeps out of an owned [`AnyValue`], so
//! parsing copies nothing. Example: `Vec<String>` refuses `["a", 5]`.

use std::fmt::Write as _;

use crate::data::value::{AnyMap, AnyValue, FiniteAnyValue};

use crate::models::error::{Error, quoted};

/// A type that reads itself from a JSON value.
pub(crate) trait FromAnyValue: Sized {
    /// Read `value` as this type, or say why its shape is wrong.
    fn from_value(value: AnyValue) -> Result<Self, FromAnyValueError>;
}

/// One step into a JSON value.
#[derive(Debug, Clone, Copy)]
enum Place {
    /// An object key.
    Key(&'static str),
    /// A list index.
    Index(usize),
}

/// Why a JSON value does not have the expected shape, and where.
///
/// It is `pub` because `OperationKind::from_str` returns it.
#[derive(Debug)]
pub struct FromAnyValueError {
    /// The steps to the value that failed, innermost first.
    places: Vec<Place>,
    message: String,
}

impl FromAnyValueError {
    /// An error at the value being read.
    pub(crate) fn new(message: impl Into<String>) -> Self {
        Self {
            places: Vec::new(),
            message: message.into(),
        }
    }

    /// The same error, one object key further in.
    #[must_use]
    pub(crate) fn at_key(mut self, key: &'static str) -> Self {
        self.places.push(Place::Key(key));
        self
    }

    /// The same error, one list index further in.
    #[must_use]
    pub(crate) fn at_index(mut self, index: usize) -> Self {
        self.places.push(Place::Index(index));
        self
    }

    /// Turn this error into an engine [`Error`]. `root` names the value read.
    /// Example: `operations[0].ids[1]: must be a string`, from `places`
    /// `[1]`, `ids`, `[0]`.
    pub(crate) fn into_error(self, root: &str) -> Error {
        let mut location = root.to_owned();
        for place in self.places.iter().rev() {
            match place {
                Place::Key(key) => {
                    location.push('.');
                    location.push_str(key);
                }
                Place::Index(index) => {
                    let _ = write!(location, "[{index}]");
                }
            }
        }
        Error::invalid(format!("{location}: {}", self.message))
    }
}

impl FromAnyValue for AnyValue {
    fn from_value(value: AnyValue) -> Result<Self, FromAnyValueError> {
        Ok(value)
    }
}

impl FromAnyValue for String {
    fn from_value(value: AnyValue) -> Result<Self, FromAnyValueError> {
        match value {
            AnyValue::String(string) => Ok(string.to_string()),
            _ => Err(FromAnyValueError::new("must be a string")),
        }
    }
}

impl FromAnyValue for AnyMap {
    fn from_value(value: AnyValue) -> Result<Self, FromAnyValueError> {
        match value {
            AnyValue::Object(object) => Ok(object),
            _ => Err(FromAnyValueError::new("must be an object")),
        }
    }
}

impl<T: FromAnyValue> FromAnyValue for Vec<T> {
    fn from_value(value: AnyValue) -> Result<Self, FromAnyValueError> {
        let AnyValue::Array(items) = value else {
            return Err(FromAnyValueError::new("must be a list"));
        };
        items
            .into_iter()
            .enumerate()
            .map(|(index, item)| T::from_value(item).map_err(|error| error.at_index(index)))
            .collect()
    }
}

/// Read the value of the object key `key` as `T`, naming the key in any error.
pub(crate) fn read<T: FromAnyValue>(
    value: AnyValue,
    key: &'static str,
) -> Result<T, FromAnyValueError> {
    T::from_value(value).map_err(|error| error.at_key(key))
}

/// The error for a key that an object must have.
pub(crate) fn missing(key: &'static str) -> FromAnyValueError {
    FromAnyValueError::new(format!("{key} is missing"))
}

/// The error for a key that an object may not have.
pub(crate) fn unexpected(key: &str) -> FromAnyValueError {
    FromAnyValueError::new(format!("unexpected key {}", quoted(key)))
}

/// Parse JSON text, reporting a parse failure as an invalid graph.
pub(crate) fn parse_json(text: &str) -> Result<AnyValue, Error> {
    serde_json::from_str(text).map_err(|error| graph_not_json(&error))
}

/// [`parse_json`], but it refuses a number that is not finite as a double
/// ([`FiniteAnyValue`]).
pub(crate) fn parse_finite_json(text: &str) -> Result<AnyValue, Error> {
    serde_json::from_str(text)
        .map(|FiniteAnyValue(value)| value)
        .map_err(|error| graph_not_json(&error))
}

fn graph_not_json(error: &serde_json::Error) -> Error {
    Error::graph_message(format!(
        "flow data is not valid JSON: {}",
        parse_problem(error)
    ))
}

/// Why JSON text does not parse. A refused value, such as `1e400`, is named
/// without its place in the text, as Python names it.
pub(crate) fn parse_problem(error: &serde_json::Error) -> String {
    let text = error.to_string();
    if error.is_data()
        && let Some((problem, _)) = text.rsplit_once(" at line ")
    {
        return problem.to_owned();
    }
    text
}

#[cfg(test)]
mod tests {
    use crate::json;

    use super::*;

    fn message<T: FromAnyValue + std::fmt::Debug>(value: AnyValue) -> String {
        T::from_value(value).unwrap_err().into_error("root").message
    }

    #[test]
    fn errors_name_the_place_that_failed() {
        assert_eq!(
            message::<Vec<String>>(json!(["a", 5])),
            "root[1]: must be a string"
        );
        assert_eq!(message::<Vec<String>>(json!({})), "root: must be a list");
    }

    #[test]
    fn keys_name_themselves_in_errors() {
        let error = read::<Vec<String>>(json!(["a", null]), "ids").unwrap_err();
        assert_eq!(
            error.into_error("root").message,
            "root.ids[1]: must be a string"
        );
        assert_eq!(
            missing("id").into_error("root").message,
            "root: id is missing"
        );
        assert_eq!(
            unexpected("extra").into_error("root").message,
            "root: unexpected key 'extra'"
        );
    }
}
