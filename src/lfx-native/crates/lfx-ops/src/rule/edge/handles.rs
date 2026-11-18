//! An edge's handles: the output it leaves from and the input it enters.
//! An edge holds each handle twice, as an object in `data` and as a string
//! where `œ` stands for `"`. The two forms must agree.

use crate::map::hash::IndexSet;
use crate::compare::{edge_data_with_type_sets, handle_with_type_sets, values_equal};
use crate::flow::edge_handle::{HANDLE_KEYS, handle_spells, parse_handle};
use crate::flow::model::FLOW_MODEL;
use crate::json::{FlowObj, FlowValue};
use crate::violation::ViolationCode;
use crate::violation::error::Result;

use super::{error, invalid};

/// Whether an edge enters a template field or a loop output.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum InputKind {
    /// A template field, named by `targetHandle.fieldName`.
    Field,
    /// A loop output, named by `targetHandle.name`.
    LoopOutput,
}

/// The input an edge enters at its target.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Input {
    /// A field or a loop output.
    pub kind: InputKind,
    /// The field's or output's name.
    pub name: String,
}

impl Input {
    pub(super) fn field(name: &str) -> Self {
        Self {
            kind: InputKind::Field,
            name: name.to_owned(),
        }
    }

    pub(super) fn loop_output(name: &str) -> Self {
        Self {
            kind: InputKind::LoopOutput,
            name: name.to_owned(),
        }
    }
}

/// The output an edge leaves from and the input it enters.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Handles {
    /// The source output's name.
    pub output: String,
    /// The target input.
    pub input: Input,
}

/// Read an edge's handles. Both forms must be present and agree.
///
/// # Errors
///
/// An edge rule the handles break, naming this edge.
pub fn read_handles(edge: &FlowObj) -> Result<Handles> {
    let source = handle(edge, "sourceHandle")?;
    let target = handle(edge, "targetHandle")?;
    let output = match source.get("name") {
        Some(FlowValue::String(name)) if !name.is_empty() => name.to_string(),
        _ => {
            return Err(invalid(edge, "sourceHandle must name an output"));
        }
    };
    // A present key counts at any value. Example: `"name": null` with `fieldName` names both.
    let names_field = target.contains_key("fieldName");
    if names_field == target.contains_key("name") {
        return Err(invalid(
            edge,
            "targetHandle must name exactly one of a field or an output",
        ));
    }
    let (kind, key) = if names_field {
        (InputKind::Field, "fieldName")
    } else {
        (InputKind::LoopOutput, "name")
    };
    match target.get(key) {
        Some(FlowValue::String(name)) if !name.is_empty() => Ok(Handles {
            output,
            input: Input {
                kind,
                name: name.to_string(),
            },
        }),
        _ => Err(invalid(
            edge,
            "targetHandle must name its field or output as a string",
        )),
    }
}

fn handle<'e>(edge: &'e FlowObj, key: &str) -> Result<&'e FlowObj> {
    // A present key counts at any value. Example: `"data": null` is not an object.
    let data = match edge.get("data") {
        None => None,
        Some(FlowValue::Object(data)) => Some(data),
        Some(_) => {
            return Err(invalid(edge, "data must be an object"));
        }
    };
    let object = data.and_then(|data| data.get(key));
    if let Some(object) = object
        && !object.is_object()
    {
        return Err(invalid(edge, format!("data.{key} must be an object")));
    }
    // Fast path: text that spells the object as the editor writes it needs no parse.
    let spelled = match (
        edge.get(key).and_then(FlowValue::as_str),
        object.and_then(FlowValue::as_object),
    ) {
        (Some(text), Some(object)) => handle_spells(text, object),
        _ => false,
    };
    if let Some(string) = edge.get(key).filter(|_| !spelled) {
        let Some(parsed) = parse_handle(string) else {
            return Err(invalid(
                edge,
                format!("{key} must be an escaped JSON object"),
            ));
        };
        if let Some(object) = object
            && !values_equal(&FlowValue::Object(parsed), object)?
        {
            return Err(invalid(
                edge,
                format!("{key} and data.{key} name different handles"),
            ));
        }
    }
    match (
        object.and_then(FlowValue::as_object),
        edge.contains_key(key),
    ) {
        (Some(object), true) => Ok(object),
        (Some(_), false) => Err(error(
            edge,
            ViolationCode::EdgeHandleFormMissing,
            format!("{key} is missing"),
        )),
        (None, true) => Err(error(
            edge,
            ViolationCode::EdgeHandleFormMissing,
            format!("data.{key} is missing"),
        )),
        (None, false) => Err(invalid(edge, format!("edge has no {key}"))),
    }
}

/// Whether an edge changed between two graphs. View state, handle spelling and
/// the order of a handle's type list do not count.
///
/// # Errors
///
/// A compared value holds a number that is not finite.
pub fn edge_changed(before: &FlowObj, after: &FlowObj) -> Result<bool> {
    let keys: IndexSet<&str> = before
        .keys()
        .chain(after.keys())
        .map(crate::json::FlowStr::as_str)
        .filter(|key| !FLOW_MODEL.edge_view_state.contains(key))
        .collect();
    for key in keys {
        let same = match (before.get(key), after.get(key)) {
            // Fast path: the same text that spells the `data` handle needs no parse.
            (Some(old), Some(new))
                if HANDLE_KEYS.contains(&key)
                    && old == new
                    && spells_data_handle(before, key, old) =>
            {
                true
            }
            (Some(old), Some(new)) if HANDLE_KEYS.contains(&key) => {
                let old = handle_value(old);
                let new = handle_value(new);
                values_equal(&old, &new)?
                    || values_equal(&handle_with_type_sets(old)?, &handle_with_type_sets(new)?)?
            }
            (Some(old), Some(new)) if key == "data" => {
                values_equal(old, new)?
                    || values_equal(
                        &edge_data_with_type_sets(old)?,
                        &edge_data_with_type_sets(new)?,
                    )?
            }
            (Some(old), Some(new)) => values_equal(old, new)?,
            _ => false,
        };
        if !same {
            return Ok(true);
        }
    }
    Ok(false)
}

/// Whether the handle string `handle` spells the object at `data.<key>` ([`handle_spells`]).
fn spells_data_handle(edge: &FlowObj, key: &str, handle: &FlowValue) -> bool {
    let object = edge
        .get("data")
        .and_then(FlowValue::as_object)
        .and_then(|data| data.get(key))
        .and_then(FlowValue::as_object);
    match (handle.as_str(), object) {
        (Some(text), Some(object)) => handle_spells(text, object),
        _ => false,
    }
}

/// A handle string compares by the object it encodes.
fn handle_value(handle: &FlowValue) -> FlowValue {
    parse_handle(handle).map_or_else(|| handle.clone(), FlowValue::Object)
}
