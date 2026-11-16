//! Reading typed values out of a parsed JSON value.
//!
//! Each type moves the parts it keeps out of an owned [`FlowValue`], so
//! parsing copies nothing. Example: `Vec<String>` refuses `["a", 5]`.

use crate::flow::path::Segment;
use crate::json::{FlowObj, FlowValue};

use crate::json::serialize::quoted;

/// A type that reads itself from a JSON value.
pub(crate) trait FromFlowValue: Sized {
    /// Read `value` as this type, or say why its shape is wrong.
    fn from_value(value: FlowValue) -> Result<Self, DeserializeError>;
}

/// One step into a JSON value.
#[derive(Debug, Clone, Copy)]
pub(crate) enum Place {
    /// An object key.
    Key(&'static str),
    /// A list index.
    Index(usize),
}

/// Why a JSON value does not have the expected shape, and where.
///
/// It is `pub` because `OperationKind::from_str` returns it.
#[derive(Debug)]
pub struct DeserializeError {
    /// The steps to the value that failed, innermost first.
    pub(crate) places: Vec<Place>,
    pub(crate) message: String,
}

impl DeserializeError {
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
}

impl FromFlowValue for FlowValue {
    fn from_value(value: FlowValue) -> Result<Self, DeserializeError> {
        Ok(value)
    }
}

impl FromFlowValue for String {
    fn from_value(value: FlowValue) -> Result<Self, DeserializeError> {
        match value {
            FlowValue::String(string) => Ok(string.to_string()),
            _ => Err(DeserializeError::new("must be a string")),
        }
    }
}

impl FromFlowValue for FlowObj {
    fn from_value(value: FlowValue) -> Result<Self, DeserializeError> {
        match value {
            FlowValue::Object(object) => Ok(object),
            _ => Err(DeserializeError::new("must be an object")),
        }
    }
}

impl<T: FromFlowValue> FromFlowValue for Vec<T> {
    fn from_value(value: FlowValue) -> Result<Self, DeserializeError> {
        let FlowValue::Array(items) = value else {
            return Err(DeserializeError::new("must be a list"));
        };
        items
            .into_iter()
            .enumerate()
            .map(|(index, item)| T::from_value(item).map_err(|error| error.at_index(index)))
            .collect()
    }
}

/// Read the value of the object key `key` as `T`, naming the key in any error.
pub(crate) fn read<T: FromFlowValue>(
    value: FlowValue,
    key: &'static str,
) -> Result<T, DeserializeError> {
    T::from_value(value).map_err(|error| error.at_key(key))
}

/// The error for a key that an object must have.
pub(crate) fn missing(key: &'static str) -> DeserializeError {
    DeserializeError::new(format!("{key} is missing"))
}

/// The error for a key that an object may not have.
pub(crate) fn unexpected(key: &str) -> DeserializeError {
    DeserializeError::new(format!("unexpected key {}", quoted(key)))
}

// --- Paths ---------------------------------------------------------------------------------

impl FromFlowValue for Segment {
    fn from_value(value: FlowValue) -> Result<Self, DeserializeError> {
        let invalid = || {
            DeserializeError::new(r#"must be an object key or {"key": ...} with a non-empty key"#)
        };
        match value {
            FlowValue::String(key) => Ok(Self::Key(key.to_string())),
            FlowValue::Number(_) => Err(DeserializeError::new(
                r#"integer list indexes are not allowed; name a list item with {"key": ...}"#,
            )),
            FlowValue::Object(item) if item.len() == 1 => match item.into_iter().next() {
                Some((name, FlowValue::String(key))) if name == "key" && !key.is_empty() => {
                    Ok(Self::Item(key.to_string()))
                }
                _ => Err(invalid()),
            },
            _ => Err(invalid()),
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::flow_value;

    use super::*;

    fn message<T: FromFlowValue + std::fmt::Debug>(value: FlowValue) -> String {
        T::from_value(value).unwrap_err().into_error("root").message
    }

    #[test]
    fn errors_name_the_place_that_failed() {
        assert_eq!(
            message::<Vec<String>>(flow_value!(["a", 5])),
            "root[1]: must be a string"
        );
        assert_eq!(
            message::<Vec<String>>(flow_value!({})),
            "root: must be a list"
        );
    }

    #[test]
    fn keys_name_themselves_in_errors() {
        let error = read::<Vec<String>>(flow_value!(["a", null]), "ids").unwrap_err();
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
