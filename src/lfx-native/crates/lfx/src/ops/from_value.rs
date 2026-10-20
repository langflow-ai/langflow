//! Reading typed values out of a parsed JSON value.
//!
//! A type that implements [`FromValue`] reads itself from an owned [`Value`]
//! and moves the parts it keeps out of it, so parsing copies nothing. Each
//! type checks its own JSON type: a `Vec<String>` refuses `["a", 5]`.
//! An object type loops over its keys once, moves each value it allows into
//! a named slot, and refuses any other key. An error records where it
//! happened, such as
//! `updates[0].path[1]`, only once it happens, so a value that parses
//! allocates nothing for it.

use std::fmt::Write as _;

use serde_json::{Map, Value};

use crate::ops::error::{Error, quoted};

/// A type that reads itself from a JSON value.
pub(crate) trait FromValue: Sized {
    /// Read `value` as this type. It takes `value` and moves the parts it
    /// keeps into the result, so nothing is copied; a part it does not keep
    /// is dropped. On failure, it says why `value` does not have this type's
    /// shape.
    fn from_value(value: Value) -> Result<Self, FromValueError>;
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
/// It is `pub` because the public `FromStr` for `OperationKind` returns it.
/// Its module is private, so code outside the crate cannot name it.
#[derive(Debug)]
pub struct FromValueError {
    /// The steps from the value that was read to the one that failed,
    /// innermost first. As in a stack trace, the error passes back up through
    /// the readers, and each one adds its own step on the way out, after the
    /// reader below it has failed.
    places: Vec<Place>,
    message: String,
}

impl FromValueError {
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
    fn at_index(mut self, index: usize) -> Self {
        self.places.push(Place::Index(index));
        self
    }

    /// Turn this error into an engine [`Error`] whose message starts with
    /// where the bad value is, for example
    /// `operations[0].ids[1]: must be a string`. `root` names the value that
    /// was read, here `operations`.
    ///
    /// Each reader adds its own step to `places` when the error passes back
    /// up through it, so the innermost step is first. The message names the
    /// outermost step first, so this reads `places` in reverse. In the
    /// example, `places` holds `[1]`, `ids`, `[0]`.
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

impl FromValue for Value {
    fn from_value(value: Value) -> Result<Self, FromValueError> {
        Ok(value)
    }
}

impl FromValue for String {
    fn from_value(value: Value) -> Result<Self, FromValueError> {
        match value {
            Value::String(string) => Ok(string),
            _ => Err(FromValueError::new("must be a string")),
        }
    }
}

impl FromValue for Map<String, Value> {
    fn from_value(value: Value) -> Result<Self, FromValueError> {
        match value {
            Value::Object(object) => Ok(object),
            _ => Err(FromValueError::new("must be an object")),
        }
    }
}

impl<T: FromValue> FromValue for Vec<T> {
    fn from_value(value: Value) -> Result<Self, FromValueError> {
        let Value::Array(items) = value else {
            return Err(FromValueError::new("must be a list"));
        };
        items
            .into_iter()
            .enumerate()
            .map(|(index, item)| T::from_value(item).map_err(|error| error.at_index(index)))
            .collect()
    }
}

/// Read the value of the object key `key` as `T`, naming the key in any error.
/// It takes `value` (see [`FromValue::from_value`]).
pub(crate) fn read<T: FromValue>(value: Value, key: &'static str) -> Result<T, FromValueError> {
    T::from_value(value).map_err(|error| error.at_key(key))
}

/// The error for a key that an object must have.
pub(crate) fn missing(key: &'static str) -> FromValueError {
    FromValueError::new(format!("{key} is missing"))
}

/// The error for a key that an object may not have.
pub(crate) fn unexpected(key: &str) -> FromValueError {
    FromValueError::new(format!("unexpected key {}", quoted(key)))
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    fn message<T: FromValue + std::fmt::Debug>(value: Value) -> String {
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
