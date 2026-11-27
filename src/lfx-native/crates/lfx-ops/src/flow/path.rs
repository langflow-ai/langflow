//! A path into a node: object keys and keyed list items, by
//! key.

use crate::flow_value;
use crate::types::{FlowStr, FlowValue};

/// One step of a field path.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum Segment {
    /// An object key.
    Key(FlowStr),
    /// An item of a list, named by its key: `{"key": ...}`.
    /// `model.json` names each list's key field.
    Item(FlowStr),
}

impl From<FlowStr> for Segment {
    /// Build an object-key segment from its key.
    fn from(key: FlowStr) -> Self {
        Self::Key(key)
    }
}

impl Segment {
    /// The string this segment holds. An object key and a list
    /// item both name that string. For example, `Key("a")` and
    /// `Item("b")` both give their text.
    #[must_use]
    fn as_str(&self) -> &str {
        match self {
            Self::Key(key) | Self::Item(key) => key,
        }
    }

    /// The segment as a path writes it in JSON. Example:
    /// `Key("a")` gives `"a"`, and `Item("b")` gives
    /// `{"key": "b"}`.
    pub(crate) fn to_value(&self) -> FlowValue {
        self.clone().into_value()
    }

    /// The same JSON as [`Self::to_value`], but it moves the
    /// key into the value instead of copying it.
    pub(crate) fn into_value(self) -> FlowValue {
        match self {
            Self::Key(key) => FlowValue::String(key),
            Self::Item(key) => flow_value!({"key": FlowValue::String(key)}),
        }
    }
}

/// A field path.
pub type Path = Vec<Segment>;

/// A part of a path that may be an object key, as `PathExt`
/// compares it.
pub trait AsKey {
    /// The object key, or `None` when this part is not one,
    /// such as a segment that names a list item.
    fn as_key(&self) -> Option<&str>;
}

impl AsKey for Segment {
    fn as_key(&self) -> Option<&str> {
        match self {
            Self::Key(key) => Some(key),
            Self::Item(_) => None,
        }
    }
}

/// Any string-like part, such as a `String`, a `&str` or an
/// `FlowStr`, is an object key.
impl<S: AsRef<str>> AsKey for S {
    fn as_key(&self) -> Option<&str> {
        Some(self.as_ref())
    }
}

/// A path part as it arrives in JSON: a string is an object
/// key, and anything else, such as `{"key": ...}`, is not.
impl AsKey for FlowValue {
    fn as_key(&self) -> Option<&str> {
        self.as_str()
    }
}

/// Compare a path with a list of object keys, such as
/// `["data", "node", "template"]`.
///
/// A path is a list of parts. A part of a field path is a
/// [`Segment`]: an object key or a list item. A part of a
/// `model.json` path is always an object key. Both kinds of
/// path work here, because each part gives its object key
/// through [`AsKey`].
pub(crate) trait PathExt {
    /// Whether `self` is exactly the object keys `path`.
    fn equals<S: AsRef<str>>(&self, path: &[S]) -> bool;

    /// Whether `self` starts with the object keys `path`. It
    /// may be exactly `path`.
    fn has_start<S: AsRef<str>>(&self, path: &[S]) -> bool;

    /// Whether `self` and `path` have the same object keys up
    /// to the length of the shorter one. An empty `self`
    /// matches any `path`. A caller that needs one to be a
    /// prefix of the other also compares their lengths.
    fn shares_start<S: AsRef<str>>(&self, path: &[S]) -> bool;

    /// Whether every part is an object key, so `self` names no
    /// list item.
    fn all_keys(&self) -> bool;
}

impl<T: AsKey> PathExt for [T] {
    fn equals<S: AsRef<str>>(&self, path: &[S]) -> bool {
        self.len() == path.len() && self.shares_start(path)
    }

    fn has_start<S: AsRef<str>>(&self, path: &[S]) -> bool {
        self.len() >= path.len() && self.shares_start(path)
    }

    fn shares_start<S: AsRef<str>>(&self, path: &[S]) -> bool {
        self.iter()
            .zip(path)
            .all(|(seg, key)| seg.as_key() == Some(key.as_ref()))
    }

    fn all_keys(&self) -> bool {
        self.iter().all(|part| part.as_key().is_some())
    }
}

/// The path as text for an error message. Each segment
/// contributes the string it holds, so
/// `[Key("outputs"), Item("text"), Key("name")]` prints as
/// `["outputs","text","name"]`.
#[must_use]
pub fn path_label(path: &[Segment]) -> String {
    if path.is_empty() {
        return String::from("[]");
    }
    format!(
        "[\"{}\"]",
        path.iter()
            .map(Segment::as_str)
            .collect::<Vec<&str>>()
            .join("\",\"")
    )
}

#[cfg(test)]
mod tests {

    use super::*;

    #[test]
    fn path_labels_print_the_segment_strings() {
        let path = [
            Segment::Key("out\"puts".into()),
            Segment::Item("text".into()),
            Segment::Key("name".into()),
        ];
        assert_eq!(path_label(&path), r#"["out"puts","text","name"]"#);
    }
}
