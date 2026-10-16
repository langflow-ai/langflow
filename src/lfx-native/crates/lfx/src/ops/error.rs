//! The errors the engine raises, each with a kind and a stable code.

use std::fmt;

use crate::ops::validate::{Violation, ViolationCode};

/// What went wrong, which decides who can fix it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorKind {
    /// An operation is malformed, or breaks a rule of the graph it is applied to.
    InvalidOperation,
    /// A write's `expect` does not hold: the graph changed since the writer read it.
    PreconditionFailed,
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
            Self::PreconditionFailed => "FlowOperationPreconditionError",
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
    /// A `set_field` changes a value's JSON type without declaring `from_type`.
    FieldTypeChangeUndeclared,
    /// A `set_field`'s `from_type` does not name the type it replaces.
    FieldTypePreconditionFailed,
    /// A write's `expect` does not hold.
    ExpectationFailed,
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
    /// The code as it crosses the API.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Self::OperationInvalid => "FLOW_OPERATION_INVALID",
            Self::FieldTypeChangeUndeclared => "FIELD_TYPE_CHANGE_UNDECLARED",
            Self::FieldTypePreconditionFailed => "FIELD_TYPE_PRECONDITION_FAILED",
            Self::ExpectationFailed => "EXPECTATION_FAILED",
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
#[derive(Debug, Clone, PartialEq)]
pub struct Error {
    /// What went wrong.
    pub kind: ErrorKind,
    /// The stable code.
    pub code: ErrorCode,
    /// What went wrong, for people.
    pub message: String,
    /// The edge that broke an edge rule. Checking one edge can find another
    /// one broken, so it is not always the edge being checked.
    pub edge_id: Option<String>,
    /// Every rule an invalid graph breaks.
    pub violations: Vec<Violation>,
}

/// The engine's result type.
pub type Result<T, E = Error> = std::result::Result<T, E>;

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

    /// An edge rule broken by the edge `edge_id`.
    pub fn edge(edge_id: &str, code: ViolationCode, reason: impl fmt::Display) -> Self {
        Self {
            edge_id: Some(edge_id.to_owned()),
            ..Self::invalid_with(
                ErrorCode::Violation(code),
                format!("edge {}: {reason}", quoted(edge_id)),
            )
        }
    }

    /// A write's expectation that does not hold.
    pub fn precondition(message: impl Into<String>) -> Self {
        Self {
            kind: ErrorKind::PreconditionFailed,
            ..Self::invalid_with(ErrorCode::ExpectationFailed, message)
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

    /// Derived operations that do not replay to their target.
    pub fn replay(message: impl Into<String>) -> Self {
        Self {
            kind: ErrorKind::ReplayMismatch,
            ..Self::invalid_with(ErrorCode::ReplayMismatch, message)
        }
    }

    /// A value that is not a valid JSON number as JavaScript reads it.
    pub(crate) fn non_finite() -> Self {
        Self::graph(
            "NaN, Infinity and integers too large for a double are not valid JSON numbers",
            Vec::new(),
        )
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {}", self.code, self.message)
    }
}

impl std::error::Error for Error {}

/// A string as error messages quote it: as Python's `repr` prints it, so
/// messages read the same in every runtime.
pub(crate) fn quoted(value: &str) -> String {
    let quote = if value.contains('\'') && !value.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::with_capacity(value.len() + 2);
    out.push(quote);
    for c in value.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if is_printable(c) => out.push(c),
            c => {
                let code = u32::from(c);
                let escaped = if code < 0x100 {
                    format!("\\x{code:02x}")
                } else if code < 0x1_0000 {
                    format!("\\u{code:04x}")
                } else {
                    format!("\\U{code:08x}")
                };
                out.push_str(&escaped);
            }
        }
    }
    out.push(quote);
    out
}

/// Whether Python's `str.isprintable` holds for a character: not a control,
/// format, separator (other than a space), surrogate or private-use character.
fn is_printable(c: char) -> bool {
    !(c.is_control()
        || matches!(
            c,
            '\u{a0}' | '\u{ad}' | '\u{600}'..='\u{605}' | '\u{61c}' | '\u{6dd}' | '\u{70f}' | '\u{1680}'
                | '\u{180e}' | '\u{2000}'..='\u{200f}' | '\u{2028}'..='\u{202f}' | '\u{205f}'..='\u{2064}'
                | '\u{2066}'..='\u{206f}' | '\u{3000}' | '\u{e000}'..='\u{f8ff}' | '\u{feff}'
                | '\u{fff9}'..='\u{fffb}' | '\u{f0000}'..='\u{10ffff}'
        ))
}

#[cfg(test)]
mod tests {
    use super::quoted;

    #[test]
    fn strings_are_quoted_as_python_prints_them() {
        assert_eq!(quoted("e1"), "'e1'");
        assert_eq!(quoted("it's"), "\"it's\"");
        assert_eq!(quoted("a'b\"c"), "'a\\'b\"c'");
        assert_eq!(quoted("tab\there\\"), "'tab\\there\\\\'");
        assert_eq!(quoted("\u{1}\u{a0}é"), "'\\x01\\xa0é'");
    }
}
