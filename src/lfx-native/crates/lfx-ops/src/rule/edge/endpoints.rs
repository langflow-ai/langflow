//! The endpoints that a field write removes from a node: template fields
//! and outputs. The edges there go with them.

use std::borrow::Cow;

use crate::flow::model::{OUTPUTS_PATH, TEMPLATE_PATH};
use crate::flow::path::{PathExt, Segment};
use crate::json::FlowValue;
use crate::violation::error::Result;

use super::index::Endpoint;
use super::outputs::index_outputs;

/// Where a node keeps one kind of endpoint.
#[derive(Debug)]
struct Holder {
    /// The path of the holder in a node.
    path: &'static [&'static str],
    /// Whether the holder is a keyed list rather than an object.
    keyed: bool,
    /// The endpoint an entry of the holder is.
    endpoint: fn(String) -> Endpoint,
}

/// The template holds a node's fields, and the outputs list its outputs.
const HOLDERS: [Holder; 2] = [
    Holder {
        path: &TEMPLATE_PATH,
        keyed: false,
        endpoint: Endpoint::Field,
    },
    Holder {
        path: &OUTPUTS_PATH,
        keyed: true,
        endpoint: Endpoint::Output,
    },
];

/// Whether [`removed_endpoints`] needs the old value at `path`: a write there
/// can remove a field or an output that an edge ends at.
pub(crate) fn reads_before(path: &[Segment]) -> bool {
    HOLDERS
        .iter()
        .any(|holder| path.len() <= holder.path.len() && path.shares_start(holder.path))
}

/// The endpoints that a write at `path` of node `node_id` removed.
///
/// `before` is the old value at `path`, needed only when [`reads_before`] is true.
/// `after(keys)` reads the node after the write.
///
/// # Errors
///
/// An outputs list, before or after the write, breaks the keyed-list rules.
pub(crate) fn removed_endpoints<'a>(
    path: &[Segment],
    is_delete: bool,
    before: Option<&FlowValue>,
    after: impl Fn(&[&str]) -> Option<Cow<'a, FlowValue>>,
    node_id: &str,
) -> Result<Vec<Endpoint>> {
    let mut removed = Vec::new();
    for holder in &HOLDERS {
        if path.len() == holder.path.len() + 1 && path.has_start(holder.path) {
            if !is_delete {
                continue;
            }
            let name = match &path[holder.path.len()] {
                Segment::Item(key) if holder.keyed => key,
                Segment::Key(key) if !holder.keyed => key,
                _ => continue,
            };
            removed.push((holder.endpoint)(name.clone()));
        } else if path.len() <= holder.path.len() && path.shares_start(holder.path) {
            let before = before.expect("a write that reads before passes what it replaced");
            let held = holder.names(at_keys(before, &holder.path[path.len()..]), node_id)?;
            let kept = holder.names(after(holder.path).as_deref(), node_id)?;
            removed.extend(
                held.into_iter()
                    .filter(|name| !kept.contains(name))
                    .map(holder.endpoint),
            );
        }
    }
    Ok(removed)
}

impl Holder {
    /// The endpoint names in `held`: the output names, or the template keys.
    fn names(&self, held: Option<&FlowValue>, node_id: &str) -> Result<Vec<String>> {
        let Some(held) = held else {
            return Ok(Vec::new());
        };
        if self.keyed {
            return Ok(index_outputs(Cow::Borrowed(held), node_id)?
                .names()
                .map(str::to_owned)
                .collect());
        }
        Ok(held
            .as_object()
            .map(|object| object.keys().map(ToString::to_string).collect())
            .unwrap_or_default())
    }
}

/// The value at the object keys `keys` under `value`.
fn at_keys<'v>(value: &'v FlowValue, keys: &[&str]) -> Option<&'v FlowValue> {
    keys.iter().try_fold(value, |value, key| value.get(key))
}
