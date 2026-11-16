//! The errors the engine raises, each with a kind and a stable code.

use std::fmt;
use std::fmt::Write as _;

use crate::flow::deserialize::{DeserializeError, Place};
use crate::flow::list::ListError;
use crate::json::NonFinite;

use crate::violation::{Violation, ViolationCode};

/// What went wrong, which decides who can fix it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorKind {
    /// An operation is malformed, or breaks a rule of the graph it is applied to.
    InvalidOperation,
    /// A graph breaks the rules every stored flow graph follows.
    InvalidGraph,
    /// Derived operations do not replay to the graph they were derived from.
    /// This is always a bug in the diff or the engine, never bad input.
    ReplayMismatch,
    /// A restore's fix does not address a violation the restore would hit.
    RestoreFixNotAllowed,
}

impl ErrorKind {
    /// The name of the matching Python exception class.
    #[must_use]
    pub fn class_name(self) -> &'static str {
        match self {
            Self::InvalidOperation => "FlowOperationValidationError",
            Self::InvalidGraph => "FlowDataValidationError",
            Self::ReplayMismatch => "FlowOperationReplayError",
            Self::RestoreFixNotAllowed => "RestoreFixNotAllowedError",
        }
    }
}

/// The stable code an error carries.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorCode {
    /// An operation is malformed or breaks a graph rule.
    OperationInvalid,
    /// A graph breaks the graph rules; the error lists the violations.
    GraphInvalid,
    /// Derived operations do not replay to their target.
    ReplayMismatch,
    /// A restore's fix addresses no violation.
    RestoreFixNotAllowed,
    /// An edge breaks an edge rule.
    Violation(ViolationCode),
}

impl ErrorCode {
    /// The code as the API reports it.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Self::OperationInvalid => "FLOW_OPERATION_INVALID",
            Self::GraphInvalid => "FLOW_GRAPH_INVALID",
            Self::ReplayMismatch => "FLOW_OPERATION_REPLAY_MISMATCH",
            Self::RestoreFixNotAllowed => "RESTORE_FIX_NOT_ALLOWED",
            Self::Violation(code) => code.as_str(),
        }
    }
}

impl fmt::Display for ErrorCode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// An engine error: its kind, its code, a message without graph values, and
/// for an edge rule the edge that broke it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Error {
    /// Who can fix it.
    pub kind: ErrorKind,
    /// The code clients match on; it does not change between releases.
    pub code: ErrorCode,
    /// What went wrong, for people. It holds no graph values.
    pub message: String,
    /// The edge that broke an edge rule. Checking one edge can find another
    /// one broken, so it is not always the edge being checked.
    pub edge_id: Option<String>,
    /// Every rule an invalid graph breaks.
    pub violations: Vec<Violation>,
}

/// The engine's result type.
pub type Result<T, E = Error> = std::result::Result<T, E>;

/// An invalid-operation [`Error`] with a `format!` message.
macro_rules! invalid {
    ($($message:tt)+) => {
        $crate::violation::error::Error::invalid(format!($($message)+))
    };
}

/// Return an invalid-operation [`Error`] with a `format!` message.
macro_rules! bail {
    ($($message:tt)+) => {
        return Err($crate::violation::error::invalid!($($message)+))
    };
}

pub(crate) use {bail, invalid};

impl Error {
    /// A malformed operation, or one that breaks a graph rule.
    pub fn invalid(message: impl Into<String>) -> Self {
        Self::invalid_with(ErrorCode::OperationInvalid, message)
    }

    /// An invalid operation with its own code.
    pub fn invalid_with(code: ErrorCode, message: impl Into<String>) -> Self {
        Self {
            kind: ErrorKind::InvalidOperation,
            code,
            message: message.into(),
            edge_id: None,
            violations: Vec::new(),
        }
    }

    /// A graph that breaks the graph rules.
    pub fn graph(message: impl Into<String>, violations: Vec<Violation>) -> Self {
        Self {
            kind: ErrorKind::InvalidGraph,
            violations,
            ..Self::invalid_with(ErrorCode::GraphInvalid, message)
        }
    }

    /// A graph that is not a graph at all, such as text that is not JSON.
    pub fn graph_message(message: impl Into<String>) -> Self {
        Self::graph(message, Vec::new())
    }

    /// A value that is not a valid JSON number as JavaScript reads it.
    pub(crate) fn non_finite() -> Self {
        Self::graph_message(
            "NaN, Infinity and integers too large for a double are not valid JSON numbers",
        )
    }
}

impl DeserializeError {
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

impl From<ListError> for Error {
    fn from(error: ListError) -> Self {
        Self::invalid(error.0)
    }
}

impl From<NonFinite> for Error {
    fn from(_: NonFinite) -> Self {
        Self::non_finite()
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for Error {}
