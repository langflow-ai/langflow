//! The versioned envelope stored in `flow_operation.ops`, and packing
//! operations into rows.
//!
//! ```text
//! {
//!   "version": 1,
//!   "batches": [
//!     {
//!       "request_id": "<uuid>",
//!       "actor_user_id": "<uuid>",
//!       "operations": [
//!         {"revision": 42, "cause": "upgrade_component", "operation": {...}},
//!         {"revision": 43, "operation": {...}}
//!       ]
//!     }
//!   ]
//! }
//! ```
//!
//! A row holds one batch per request, in revision order. Each batch names the
//! authenticated actor and the request that produced its operations, so a
//! row never implies a single author. A request that spans rows has one batch
//! in each.
//!
//! The operation order is canonical: operation `i` of a row starting at
//! revision `s` carries revision `s + i`, counted across the row's batches.
//! `cause` is optional: a display hint the history uses to group a write's
//! operations. Nothing checks it.
//!
//! Decoding validates all of it; a row that does not match is corruption.

use std::collections::{BTreeSet, HashSet};
use std::{fmt, io};

use serde_json::{Map, Value};

use crate::ops::canonical::{as_double, is_integer_text};
use crate::ops::error::{Result, bail};
use crate::ops::ops::{FieldUpdate, Operation};

/// The envelope version this engine reads and writes.
pub const ENVELOPE_VERSION: u64 = 1;

/// A kind of damage a stored history can show.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Damage {
    /// The envelope is not a version this engine reads.
    UnsupportedEnvelope,
    /// The row's operations do not fill its revision range.
    CountMismatch,
    /// An operation carries the wrong revision.
    RevisionOutOfOrder,
    /// An operation does not parse.
    MalformedOperation,
    /// A batch is not a request's batch.
    MalformedBatch,
    /// A request has more than one batch in a row.
    RequestRepeated,
    /// No checkpoint precedes the revision.
    NoCheckpoint,
    /// A checkpoint's graph does not hash to its stored hash.
    CheckpointMismatch,
    /// A revision is missing or repeated.
    MissingRevisions,
    /// A recorded operation does not apply to the graph before it.
    OperationDoesNotApply,
}

impl Damage {
    /// The kind of damage, as the history reports it.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Self::UnsupportedEnvelope => "unsupported operation envelope",
            Self::CountMismatch => "operation count does not match the row's revision range",
            Self::RevisionOutOfOrder => "operation revision out of order",
            Self::MalformedOperation => "malformed operation",
            Self::MalformedBatch => "malformed request batch",
            Self::RequestRepeated => "a request has more than one batch in the row",
            Self::NoCheckpoint => "no checkpoint to replay from",
            Self::CheckpointMismatch => "checkpoint does not match its hash",
            Self::MissingRevisions => "missing revisions",
            Self::OperationDoesNotApply => "operation does not apply",
        }
    }
}

impl fmt::Display for Damage {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Damage found in a stored history, and the revision it was found at.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Corruption {
    #[expect(missing_docs, reason = "the type says what it is")]
    pub damage: Damage,
    /// The revision replay found the damage at; `None` when the damage is
    /// not tied to one revision.
    pub revision: Option<u64>,
}

impl Corruption {
    pub(crate) fn at(damage: Damage, revision: u64) -> Self {
        Self {
            damage,
            revision: Some(revision),
        }
    }
}

impl fmt::Display for Corruption {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self.revision {
            Some(revision) => write!(
                f,
                "history is damaged at revision {revision}: {}",
                self.damage
            ),
            None => write!(f, "history is damaged: {}", self.damage),
        }
    }
}

impl std::error::Error for Corruption {}

/// One accepted operation and everything recorded about it.
#[derive(Debug, Clone, PartialEq)]
pub struct RecordedOperation {
    /// The revision the operation produced.
    pub revision: u64,
    /// The authenticated user who made it, as a lowercase hyphenated UUID.
    pub actor_user_id: String,
    /// The request that carried it, as a lowercase hyphenated UUID.
    pub request_id: String,
    /// The operation.
    pub operation: Operation,
    /// What made the write, a display hint.
    pub cause: Option<String>,
}

impl RecordedOperation {
    /// The operation's element inside its request's batch.
    #[must_use]
    pub fn to_value(&self) -> Value {
        let mut element = Map::new();
        element.insert("revision".into(), Value::from(self.revision));
        if let Some(cause) = &self.cause {
            element.insert("cause".into(), Value::from(cause.as_str()));
        }
        element.insert("operation".into(), self.operation.to_value());
        Value::Object(element)
    }
}

/// The request a batch comes from, and the authenticated user who sent it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Request<'a> {
    /// The request, as a UUID.
    pub request_id: &'a str,
    /// The authenticated user, as a UUID.
    pub actor_user_id: &'a str,
}

/// An empty batch for one request.
#[must_use]
pub fn batch_header(request: Request<'_>) -> Value {
    let mut batch = Map::new();
    batch.insert("request_id".into(), Value::from(request.request_id));
    batch.insert("actor_user_id".into(), Value::from(request.actor_user_id));
    batch.insert("operations".into(), Value::Array(Vec::new()));
    Value::Object(batch)
}

/// Group a row's operations into one batch per request, in revision order.
///
/// # Errors
///
/// A request's operations name two actors.
pub fn encode_envelope(operations: &[RecordedOperation]) -> Result<Value> {
    let mut batches = Vec::new();
    for request in by_request(operations) {
        let first = &request[0];
        if request
            .iter()
            .any(|operation| operation.actor_user_id != first.actor_user_id)
        {
            bail!(
                "request {} has operations from two actors",
                first.request_id
            );
        }
        let mut batch = batch_header(Request {
            request_id: &first.request_id,
            actor_user_id: &first.actor_user_id,
        });
        batch["operations"] = request.iter().map(RecordedOperation::to_value).collect();
        batches.push(batch);
    }
    let mut envelope = Map::new();
    envelope.insert("version".into(), Value::from(ENVELOPE_VERSION));
    envelope.insert("batches".into(), Value::Array(batches));
    Ok(Value::Object(envelope))
}

/// The runs of consecutive operations that one request carried.
fn by_request(operations: &[RecordedOperation]) -> impl Iterator<Item = &[RecordedOperation]> {
    operations.chunk_by(|a, b| a.request_id == b.request_id)
}

/// The row's distinct actors, sorted so the list is deterministic.
#[must_use]
pub fn distinct_actor_ids(operations: &[RecordedOperation]) -> Vec<String> {
    let actors: BTreeSet<&str> = operations
        .iter()
        .map(|operation| operation.actor_user_id.as_str())
        .collect();
    actors.into_iter().map(str::to_owned).collect()
}

/// One entry per request in the row, in revision order.
#[must_use]
pub fn request_ids_in_order(operations: &[RecordedOperation]) -> Vec<String> {
    by_request(operations)
        .map(|request| request[0].request_id.clone())
        .collect()
}

/// A stored `flow_operation` row: its revision range and its envelope.
#[derive(Debug, Clone, PartialEq)]
pub struct StoredRow {
    /// The revision of the row's first operation.
    pub start_revision: u64,
    /// The revision of the row's last operation.
    pub end_revision: u64,
    /// The envelope.
    pub ops: Value,
}

/// Read a UUID as Python's `UUID()` reads its string form, and print it in
/// the canonical lowercase hyphenated form.
///
/// Accepted: 32 hex digits, with any hyphens, optionally in braces, and
/// optionally behind `urn:` and `uuid:`.
#[must_use]
pub fn normalize_uuid(text: &str) -> Option<String> {
    let text = text.replace("urn:", "").replace("uuid:", "");
    let hex: String = text
        .trim_matches(['{', '}'])
        .chars()
        .filter(|c| *c != '-')
        .collect();
    if hex.len() != 32 || !hex.chars().all(|c| c.is_ascii_hexdigit()) {
        return None;
    }
    let hex = hex.to_ascii_lowercase();
    Some(format!(
        "{}-{}-{}-{}-{}",
        &hex[..8],
        &hex[8..12],
        &hex[12..16],
        &hex[16..20],
        &hex[20..]
    ))
}

/// Decode and validate a stored row's envelope against its revision range.
///
/// # Errors
///
/// The row is damaged.
pub fn decode_row(row: &StoredRow) -> Result<Vec<RecordedOperation>, Corruption> {
    let start = row.start_revision;
    let unsupported = || Corruption::at(Damage::UnsupportedEnvelope, start);
    let Value::Object(envelope) = &row.ops else {
        return Err(unsupported());
    };
    if !envelope
        .get("version")
        .is_some_and(|version| is_integer(version, ENVELOPE_VERSION))
    {
        return Err(unsupported());
    }
    let Some(Value::Array(batches)) = envelope.get("batches") else {
        return Err(unsupported());
    };

    let mut decoded: Vec<RecordedOperation> = Vec::new();
    let mut seen_requests = HashSet::new();
    for batch in batches {
        let first = start + count(&decoded);
        let malformed = || Corruption::at(Damage::MalformedBatch, first);
        let Some(elements) = batch
            .get("operations")
            .and_then(Value::as_array)
            .filter(|elements| !elements.is_empty())
        else {
            return Err(malformed());
        };
        let uuid = |key: &str| {
            batch
                .get(key)
                .and_then(Value::as_str)
                .and_then(normalize_uuid)
        };
        let (Some(request_id), Some(actor_user_id)) = (uuid("request_id"), uuid("actor_user_id"))
        else {
            return Err(malformed());
        };
        // A request's operations are contiguous, so a row holds one batch per request.
        if !seen_requests.insert(request_id.clone()) {
            return Err(Corruption::at(Damage::RequestRepeated, first));
        }
        for element in elements {
            let expected = start + count(&decoded);
            let revision_matches = element
                .get("revision")
                .is_some_and(|revision| is_integer(revision, expected));
            if !revision_matches {
                return Err(Corruption::at(Damage::RevisionOutOfOrder, expected));
            }
            let operation = element
                .get("operation")
                .and_then(|operation| Operation::try_from(operation.clone()).ok())
                .ok_or_else(|| Corruption::at(Damage::MalformedOperation, expected))?;
            let cause = match element.get("cause") {
                None | Some(Value::Null) => None,
                Some(Value::String(cause)) => Some(cause.clone()),
                Some(_) => return Err(Corruption::at(Damage::MalformedOperation, expected)),
            };
            decoded.push(RecordedOperation {
                revision: expected,
                actor_user_id: actor_user_id.clone(),
                request_id: request_id.clone(),
                operation,
                cause,
            });
        }
    }
    if i128::from(count(&decoded)) != i128::from(row.end_revision) - i128::from(start) + 1 {
        return Err(Corruption::at(Damage::CountMismatch, start));
    }
    Ok(decoded)
}

fn count(decoded: &[RecordedOperation]) -> u64 {
    u64::try_from(decoded.len()).unwrap_or(u64::MAX)
}

/// Whether a JSON value is a number equal to `expected`. A float equal to it
/// counts, as Python compares numbers; `true` does not.
fn is_integer(value: &Value, expected: u64) -> bool {
    let Value::Number(number) = value else {
        return false;
    };
    if number.as_u64() == Some(expected) {
        return true;
    }
    #[expect(
        clippy::cast_precision_loss,
        clippy::float_cmp,
        reason = "Python compares the float exactly"
    )]
    let float_equal = !is_integer_text(number) && as_double(number) == expected as f64;
    float_equal
}

// --- Packing operations into rows --------------------------------------------------------

/// The two bounds on a stored row.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RowLimits {
    /// The most operations a row holds.
    pub ops: usize,
    /// The most bytes a row's envelope takes, as compact JSON.
    pub bytes: usize,
}

/// A row ready to store.
#[derive(Debug, Clone, PartialEq)]
pub struct PackedRow {
    /// The revision of the row's first operation.
    pub start_revision: u64,
    /// The revision of the row's last operation.
    pub end_revision: u64,
    /// The envelope.
    pub ops: Value,
    /// The row's distinct actors, sorted.
    pub actor_user_ids: Vec<String>,
    /// The row's requests, in revision order.
    pub request_ids: Vec<String>,
}

/// Counts the bytes written to it, so a size is measured without building the text.
#[derive(Debug, Default)]
struct ByteCount(usize);

impl io::Write for ByteCount {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.0 += bytes.len();
        Ok(bytes.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

/// The size of what `write` writes, as compact JSON.
fn measured(write: impl FnOnce(&mut ByteCount) -> serde_json::Result<()>) -> usize {
    let mut count = ByteCount::default();
    write(&mut count).expect("JSON values and strings always serialize");
    count.0
}

fn json_size(value: &Value) -> usize {
    measured(|out| serde_json::to_writer(out, value))
}

const NIL_UUID: &str = "00000000-0000-0000-0000-000000000000";

fn envelope_overhead() -> usize {
    json_size(&serde_json::json!({"version": ENVELOPE_VERSION, "batches": []}))
}

/// Request and actor ids are UUIDs, so every batch header has the same size.
fn batch_overhead() -> usize {
    let request = Request {
        request_id: NIL_UUID,
        actor_user_id: NIL_UUID,
    };
    json_size(&batch_header(request)) + 1
}

/// Split operations to fit the row size limit, and number them from `latest_revision`.
#[must_use]
pub fn sequence(
    operations: Vec<Operation>,
    latest_revision: u64,
    request: Request<'_>,
    cause: Option<&str>,
    bytes_limit: usize,
) -> Vec<RecordedOperation> {
    let budget = bytes_limit.saturating_sub(envelope_overhead() + batch_overhead());
    let mut revision = latest_revision;
    let mut recorded = Vec::new();
    for operation in operations {
        for part in split_to_fit(operation, budget) {
            revision += 1;
            recorded.push(RecordedOperation {
                revision,
                actor_user_id: request.actor_user_id.to_owned(),
                request_id: request.request_id.to_owned(),
                operation: part,
                cause: cause.map(str::to_owned),
            });
        }
    }
    recorded
}

/// Group consecutive operations into rows within both limits.
///
/// A partly filled row is never reopened; each write starts new rows. An
/// operation that starts a request's batch in the row also pays for the
/// batch header.
///
/// # Errors
///
/// A request's operations name two actors.
pub fn pack_rows(operations: Vec<RecordedOperation>, limits: RowLimits) -> Result<Vec<PackedRow>> {
    let mut rows: Vec<Vec<RecordedOperation>> = Vec::new();
    let mut current: Vec<RecordedOperation> = Vec::new();
    let mut size = envelope_overhead();
    for operation in operations {
        let element_size = json_size(&operation.to_value()) + 1;
        let starts_batch = current
            .last()
            .is_none_or(|last| last.request_id != operation.request_id);
        let mut added = element_size + if starts_batch { batch_overhead() } else { 0 };
        if !current.is_empty() && (current.len() >= limits.ops || size + added > limits.bytes) {
            rows.push(std::mem::take(&mut current));
            size = envelope_overhead();
            added = element_size + batch_overhead();
        }
        current.push(operation);
        size += added;
    }
    if !current.is_empty() {
        rows.push(current);
    }
    rows.into_iter()
        .map(|row| {
            Ok(PackedRow {
                start_revision: row.first().map_or(0, |first| first.revision),
                end_revision: row.last().map_or(0, |last| last.revision),
                ops: encode_envelope(&row)?,
                actor_user_ids: distinct_actor_ids(&row),
                request_ids: request_ids_in_order(&row),
            })
        })
        .collect()
}

/// Split a list-valued operation into operations of the same type that each fit `budget`.
///
/// Items are never split, so an item larger than the budget becomes an
/// operation of its own that exceeds it.
#[must_use]
pub fn split_to_fit(operation: Operation, budget: usize) -> Vec<Operation> {
    if json_size(&operation.to_value()) <= budget {
        return vec![operation];
    }
    match operation {
        Operation::AddNodes(nodes) => chunks(nodes, budget, Operation::AddNodes, entry_len),
        Operation::AddEdges(edges) => chunks(edges, budget, Operation::AddEdges, entry_len),
        Operation::DeleteNodes(ids) => chunks(ids, budget, Operation::DeleteNodes, |id| id_len(id)),
        Operation::DeleteEdges(ids) => chunks(ids, budget, Operation::DeleteEdges, |id| id_len(id)),
        Operation::UpdateNodes(updates) => {
            chunks(updates, budget, Operation::UpdateNodes, update_len)
        }
        Operation::UpdateMetadata {
            fields,
            delete_keys,
        } => {
            let items = fields
                .into_iter()
                .map(|(key, value)| MetadataItem::Set(key, value))
                .chain(delete_keys.into_iter().map(MetadataItem::Delete))
                .collect();
            chunks(items, budget, MetadataItem::operation, MetadataItem::len)
        }
    }
}

/// Split `items` into runs, each built into one operation by `build`, that
/// fit `budget`. `item_len` is an item's size as compact JSON.
fn chunks<T>(
    items: Vec<T>,
    budget: usize,
    build: fn(Vec<T>) -> Operation,
    item_len: impl Fn(&T) -> usize,
) -> Vec<Operation> {
    if items.len() <= 1 {
        return vec![build(items)];
    }
    let empty_size = json_size(&build(Vec::new()).to_value());
    let mut parts = Vec::new();
    let mut chunk = Vec::new();
    let mut size = empty_size;
    for item in items {
        // One more byte for the comma.
        let item_size = item_len(&item) + 1;
        if !chunk.is_empty() && size + item_size > budget {
            parts.push(build(std::mem::take(&mut chunk)));
            size = empty_size;
        }
        chunk.push(item);
        size += item_size;
    }
    parts.push(build(chunk));
    parts
}

fn entry_len(entry: &Map<String, Value>) -> usize {
    measured(|out| serde_json::to_writer(out, entry))
}

fn id_len(id: &str) -> usize {
    measured(|out| serde_json::to_writer(out, id))
}

fn update_len(update: &FieldUpdate) -> usize {
    json_size(&update.to_value())
}

/// One key an `update_metadata` sets or deletes.
#[derive(Debug)]
enum MetadataItem {
    Set(String, Value),
    Delete(String),
}

impl MetadataItem {
    /// The `update_metadata` that sets and deletes `items`.
    fn operation(items: Vec<Self>) -> Operation {
        let mut fields = Map::new();
        let mut delete_keys = Vec::new();
        for item in items {
            match item {
                Self::Set(key, value) => {
                    fields.insert(key, value);
                }
                Self::Delete(key) => delete_keys.push(key),
            }
        }
        Operation::UpdateMetadata {
            fields,
            delete_keys,
        }
    }

    /// The item's size, counted as `["set", key, value]` or `["delete", key, null]`.
    fn len(&self) -> usize {
        let (action, key, value) = match self {
            Self::Set(key, value) => ("set", key, value),
            Self::Delete(key) => ("delete", key, &Value::Null),
        };
        measured(|out| serde_json::to_writer(out, &(action, key, value)))
    }
}
