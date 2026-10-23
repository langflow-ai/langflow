//! Random ids for things code adds to a flow, in the editor's formats.
//!
//! An id names an entry and nothing else: it is never derived from what the
//! entry connects or contains, so changing an edge's handles or a row's cells
//! never changes its id, and no code may parse one. Existing ids are kept as
//! they are.

use std::collections::HashSet;

/// The editor's id characters: short-unique-id's default alphanumeric dictionary.
const ALPHANUMERIC: &[u8; 62] = b"0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
const EDGE_ID_PREFIX: &str = "e-";
const EDGE_ID_LENGTH: usize = 21;
const TABLE_ROW_ID_LENGTH: usize = 10;
/// The largest multiple of 62 a byte holds: bytes at or above it are drawn
/// again, so every character is equally likely.
const UNBIASED_LIMIT: u8 = 248;

/// `length` random alphanumeric characters.
///
/// # Panics
///
/// The operating system has no random source, which no supported platform lacks.
#[must_use]
pub fn random_alphanumeric(length: usize) -> String {
    let mut out = String::with_capacity(length);
    let mut bytes = [0u8; 32];
    while out.len() < length {
        getrandom::fill(&mut bytes).expect("the operating system provides random bytes");
        for byte in bytes {
            if out.len() == length {
                break;
            }
            if byte < UNBIASED_LIMIT {
                out.push(char::from(ALPHANUMERIC[usize::from(byte % 62)]));
            }
        }
    }
    out
}

/// A new edge id, `e-` and 21 random alphanumerics, like the editor's `newEdgeId()`.
#[must_use]
pub fn new_edge_id() -> String {
    format!("{EDGE_ID_PREFIX}{}", random_alphanumeric(EDGE_ID_LENGTH))
}

/// A new table row `__id__`, 10 random alphanumerics, like the editor's `newTableRowId()`.
#[must_use]
pub fn new_table_row_id() -> String {
    random_alphanumeric(TABLE_ROW_ID_LENGTH)
}

/// A new id from `new_id` that `used` does not hold yet.
pub(crate) fn unused_id(used: &HashSet<String>, new_id: fn() -> String) -> String {
    loop {
        let id = new_id();
        if !used.contains(&id) {
            return id;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ids_have_the_editor_shapes() {
        let edge = new_edge_id();
        assert!(edge.starts_with("e-") && edge.len() == 23, "{edge}");
        let row = new_table_row_id();
        assert_eq!(row.len(), 10);
        assert!(row.bytes().all(|byte| ALPHANUMERIC.contains(&byte)));
        assert_ne!(new_table_row_id(), new_table_row_id());
    }
}
