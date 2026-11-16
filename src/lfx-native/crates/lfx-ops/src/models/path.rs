//! Paths into a graph by object key and array index, as violations and fixes name a place.
//!
//! An operation's path is different: a [`Segment`](crate::Segment) names a list item by its key.

use std::fmt;

use crate::data::value::AnyValue;

/// One step of a path into a graph: an object key or an array index.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum PathPart {
    /// An object key.
    Key(String),
    /// An array index.
    Index(usize),
}

impl From<&str> for PathPart {
    fn from(key: &str) -> Self {
        Self::Key(key.to_owned())
    }
}

impl From<usize> for PathPart {
    fn from(index: usize) -> Self {
        Self::Index(index)
    }
}

impl PathPart {
    /// The part as JSON: a string key or an integer index.
    pub(crate) fn to_value(&self) -> AnyValue {
        match self {
            Self::Key(key) => AnyValue::from(key.as_str()),
            Self::Index(index) => AnyValue::from(*index),
        }
    }
}

impl fmt::Display for PathPart {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Key(key) => f.write_str(key),
            Self::Index(index) => write!(f, "{index}"),
        }
    }
}

/// A path into a graph.
pub type GraphPath = Vec<PathPart>;

/// A step of a path that a walk holds while it reads, borrowed from the graph.
#[derive(Debug, Clone, Copy)]
pub(crate) enum Step<'a> {
    Key(&'a str),
    Index(usize),
}

/// A walk's path as an owned graph path.
pub(crate) fn owned_path(steps: &[Step<'_>]) -> GraphPath {
    steps
        .iter()
        .map(|step| match *step {
            Step::Key(key) => PathPart::Key(key.to_owned()),
            Step::Index(index) => PathPart::Index(index),
        })
        .collect()
}

/// The value at a path of object keys and array indexes.
pub(crate) fn resolve<'v>(root: &'v AnyValue, steps: &[PathPart]) -> Option<&'v AnyValue> {
    steps.iter().try_fold(root, |value, step| match step {
        PathPart::Key(key) => value.as_object()?.get(key),
        PathPart::Index(index) => value.as_array()?.get(*index),
    })
}

/// The value at a path of object keys and array indexes, to change it.
pub(crate) fn resolve_mut<'v>(
    root: &'v mut AnyValue,
    steps: &[PathPart],
) -> Option<&'v mut AnyValue> {
    steps.iter().try_fold(root, |value, step| match step {
        PathPart::Key(key) => value.as_object_mut()?.get_mut(key),
        PathPart::Index(index) => value.as_array_mut()?.get_mut(*index),
    })
}
