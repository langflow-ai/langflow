//! Operation types and their strict parser.
//!
//! The parser accepts exactly the shapes the operation protocol defines: no
//! unknown keys, no missing fields, no wrong types. A list item is addressed
//! by a selector, never by an index. Dumping leaves optional fields out when
//! they are unset, so a parsed and dumped operation reads as it was sent.

use serde_json::{Map, Value};

use crate::ops::canonical::JsonType;
use crate::ops::error::{Error, Result, quoted};

/// One step of a field path.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum Segment {
    /// An object key.
    Key(String),
    /// A table row, selected by its `_id`: `{"id": ...}`.
    ById(String),
    /// A natural-list item, selected by its key: `{"key": ...}`.
    ByKey(String),
}

impl Segment {
    /// The object key, if this segment is one.
    #[must_use]
    pub fn as_key(&self) -> Option<&str> {
        match self {
            Self::Key(key) => Some(key),
            _ => None,
        }
    }

    /// The key a selector names, or `None` for an object key.
    #[must_use]
    pub fn selector_key(&self) -> Option<&str> {
        match self {
            Self::Key(_) => None,
            Self::ById(key) | Self::ByKey(key) => Some(key),
        }
    }

    fn to_json(&self) -> Value {
        match self {
            Self::Key(key) => Value::from(key.as_str()),
            Self::ById(id) => single("id", Value::from(id.as_str())),
            Self::ByKey(key) => single("key", Value::from(key.as_str())),
        }
    }
}

/// A field path.
pub type Path = Vec<Segment>;

/// The JSON label of a path, for messages.
#[must_use]
pub fn path_label(path: &[Segment]) -> String {
    Value::Array(path.iter().map(Segment::to_json).collect()).to_string()
}

/// What a path must hold before a write.
#[derive(Debug, Clone, PartialEq)]
pub enum Expect {
    /// The path holds this value, compared canonically.
    Value(Value),
    /// The path does not exist.
    Absent,
}

/// What a field update does at its path.
#[derive(Debug, Clone, PartialEq)]
pub enum Change {
    /// Write a value.
    Set {
        /// The value written.
        value: Value,
        /// The JSON type the write replaces. Required when the type changes,
        /// so a number cannot silently become a string.
        from_type: Option<JsonType>,
        /// The metadata of the template field the path writes into, as of
        /// this operation. The engine ignores it; readers use it to strip
        /// secret values without replaying the flow.
        template_field: Option<Map<String, Value>>,
    },
    /// Remove the value.
    Delete,
}

/// One `set_field` or `delete_field` on a node or an edge.
#[derive(Debug, Clone, PartialEq)]
pub struct FieldUpdate {
    /// The node or edge written.
    pub id: String,
    /// Where it is written.
    pub path: Path,
    /// What the path must hold first. On a mismatch the whole batch fails.
    pub expect: Option<Expect>,
    /// The write.
    pub change: Change,
}

impl FieldUpdate {
    /// Whether this update is a `delete_field`.
    #[must_use]
    pub fn is_delete(&self) -> bool {
        matches!(self.change, Change::Delete)
    }

    /// A `set_field` of `value` at `path`.
    #[must_use]
    pub fn set(id: &str, path: Path, value: Value) -> Self {
        Self {
            id: id.to_owned(),
            path,
            expect: None,
            change: Change::Set {
                value,
                from_type: None,
                template_field: None,
            },
        }
    }

    /// A `delete_field` at `path`.
    #[must_use]
    pub fn delete(id: &str, path: Path) -> Self {
        Self {
            id: id.to_owned(),
            path,
            expect: None,
            change: Change::Delete,
        }
    }
}

/// A flow operation.
#[derive(Debug, Clone, PartialEq)]
pub enum Operation {
    /// Add nodes.
    AddNodes(Vec<Map<String, Value>>),
    /// Write fields of existing nodes.
    UpdateNodes(Vec<FieldUpdate>),
    /// Delete nodes, and the edges at them.
    DeleteNodes(Vec<String>),
    /// Add edges.
    AddEdges(Vec<Map<String, Value>>),
    /// Write fields of existing edges. A path may not start with `id`,
    /// `source` or `target`: connecting different nodes is a different edge.
    UpdateEdges(Vec<FieldUpdate>),
    /// Delete edges.
    DeleteEdges(Vec<String>),
    /// Set and delete top-level keys other than `nodes` and `edges`.
    UpdateMetadata {
        /// Keys to set.
        fields: Map<String, Value>,
        /// Keys to delete.
        delete_keys: Vec<String>,
    },
}

impl Operation {
    /// The operation's `type`.
    #[must_use]
    pub fn type_name(&self) -> &'static str {
        match self {
            Self::AddNodes(_) => "add_nodes",
            Self::UpdateNodes(_) => "update_nodes",
            Self::DeleteNodes(_) => "delete_nodes",
            Self::AddEdges(_) => "add_edges",
            Self::UpdateEdges(_) => "update_edges",
            Self::DeleteEdges(_) => "delete_edges",
            Self::UpdateMetadata { .. } => "update_metadata",
        }
    }

    /// Parse one operation.
    ///
    /// # Errors
    ///
    /// The operation does not have exactly one of the protocol's shapes.
    pub fn from_json(operation: Value) -> Result<Self> {
        let Value::Object(mut operation) = operation else {
            return Err(Error::invalid("operation must be a dict"));
        };
        let type_name = match operation.get("type") {
            Some(Value::String(name)) => name.clone(),
            other => {
                let shown = other.map_or_else(|| "None".to_owned(), Value::to_string);
                return Err(Error::invalid(format!(
                    "Unsupported operation type: {shown}"
                )));
            }
        };
        let allowed: &[&str] = match type_name.as_str() {
            "add_nodes" => &["type", "nodes"],
            "add_edges" => &["type", "edges"],
            "update_nodes" | "update_edges" => &["type", "updates"],
            "delete_nodes" | "delete_edges" => &["type", "ids"],
            "update_metadata" => &["type", "fields", "delete_keys"],
            _ => {
                return Err(Error::invalid(format!(
                    "Unsupported operation type: {}",
                    quoted(&type_name)
                )));
            }
        };
        only_keys(&operation, allowed, &type_name)?;
        let context = type_name.as_str();
        Ok(match context {
            "add_nodes" => Self::AddNodes(objects(
                required(&mut operation, "nodes", context)?,
                context,
            )?),
            "add_edges" => Self::AddEdges(objects(
                required(&mut operation, "edges", context)?,
                context,
            )?),
            "delete_nodes" => {
                Self::DeleteNodes(strings(required(&mut operation, "ids", context)?, context)?)
            }
            "delete_edges" => {
                Self::DeleteEdges(strings(required(&mut operation, "ids", context)?, context)?)
            }
            "update_nodes" | "update_edges" => {
                let Value::Array(items) = required(&mut operation, "updates", context)? else {
                    return Err(Error::invalid(format!("{context}.updates must be a list")));
                };
                let updates = items
                    .into_iter()
                    .enumerate()
                    .map(|(index, item)| parse_update(item, &format!("{context}.updates[{index}]")))
                    .collect::<Result<_>>()?;
                if context == "update_nodes" {
                    Self::UpdateNodes(updates)
                } else {
                    Self::UpdateEdges(updates)
                }
            }
            _ => {
                let fields = match operation.remove("fields") {
                    None => Map::new(),
                    Some(Value::Object(fields)) => fields,
                    Some(_) => {
                        return Err(Error::invalid("update_metadata.fields must be an object"));
                    }
                };
                let delete_keys = match operation.remove("delete_keys") {
                    None => Vec::new(),
                    Some(keys) => strings(keys, "update_metadata.delete_keys")?,
                };
                Self::UpdateMetadata {
                    fields,
                    delete_keys,
                }
            }
        })
    }

    /// Parse a list of operations.
    ///
    /// # Errors
    ///
    /// `operations` is not a list, or an operation does not parse.
    pub fn list_from_json(operations: Value) -> Result<Vec<Self>> {
        let Value::Array(operations) = operations else {
            return Err(Error::invalid("operations must be a list"));
        };
        operations.into_iter().map(Self::from_json).collect()
    }

    /// The operation as JSON, leaving out optional fields that are unset.
    #[must_use]
    pub fn to_json(&self) -> Value {
        let mut out = single("type", Value::from(self.type_name()));
        let Value::Object(object) = &mut out else {
            unreachable!("single() builds an object")
        };
        match self {
            Self::AddNodes(items) => {
                object.insert("nodes".into(), objects_json(items));
            }
            Self::AddEdges(items) => {
                object.insert("edges".into(), objects_json(items));
            }
            Self::DeleteNodes(ids) | Self::DeleteEdges(ids) => {
                object.insert("ids".into(), strings_json(ids));
            }
            Self::UpdateNodes(updates) | Self::UpdateEdges(updates) => {
                object.insert(
                    "updates".into(),
                    Value::Array(updates.iter().map(FieldUpdate::to_json).collect()),
                );
            }
            Self::UpdateMetadata {
                fields,
                delete_keys,
            } => {
                if !fields.is_empty() {
                    object.insert("fields".into(), Value::Object(fields.clone()));
                }
                if !delete_keys.is_empty() {
                    object.insert("delete_keys".into(), strings_json(delete_keys));
                }
            }
        }
        out
    }
}

impl FieldUpdate {
    /// The update as JSON, leaving out optional fields that are unset.
    #[must_use]
    pub fn to_json(&self) -> Value {
        let mut object = Map::new();
        object.insert("id".into(), Value::from(self.id.as_str()));
        object.insert(
            "path".into(),
            Value::Array(self.path.iter().map(Segment::to_json).collect()),
        );
        if let Some(expect) = &self.expect {
            object.insert(
                "expect".into(),
                match expect {
                    Expect::Value(value) => single("value", value.clone()),
                    Expect::Absent => single("absent", Value::Bool(true)),
                },
            );
        }
        match &self.change {
            Change::Set {
                value,
                from_type,
                template_field,
            } => {
                object.insert("op".into(), Value::from("set_field"));
                object.insert("value".into(), value.clone());
                if let Some(from_type) = from_type {
                    object.insert("from_type".into(), Value::from(from_type.as_str()));
                }
                if let Some(template_field) = template_field {
                    object.insert(
                        "template_field".into(),
                        Value::Object(template_field.clone()),
                    );
                }
            }
            Change::Delete => {
                object.insert("op".into(), Value::from("delete_field"));
            }
        }
        Value::Object(object)
    }
}

fn single(key: &str, value: Value) -> Value {
    let mut object = Map::new();
    object.insert(key.to_owned(), value);
    Value::Object(object)
}

fn objects_json(items: &[Map<String, Value>]) -> Value {
    Value::Array(items.iter().cloned().map(Value::Object).collect())
}

fn strings_json(items: &[String]) -> Value {
    Value::Array(
        items
            .iter()
            .map(|item| Value::from(item.as_str()))
            .collect(),
    )
}

fn only_keys(object: &Map<String, Value>, allowed: &[&str], context: &str) -> Result<()> {
    match object.keys().find(|key| !allowed.contains(&key.as_str())) {
        Some(key) => Err(Error::invalid(format!(
            "{context}: unexpected key {}",
            quoted(key)
        ))),
        None => Ok(()),
    }
}

fn required(object: &mut Map<String, Value>, key: &str, context: &str) -> Result<Value> {
    object
        .remove(key)
        .ok_or_else(|| Error::invalid(format!("{context}: {key} is required")))
}

fn objects(value: Value, context: &str) -> Result<Vec<Map<String, Value>>> {
    let Value::Array(items) = value else {
        return Err(Error::invalid(format!(
            "{context}: must be a list of objects"
        )));
    };
    items
        .into_iter()
        .map(|item| match item {
            Value::Object(object) => Ok(object),
            _ => Err(Error::invalid(format!(
                "{context}: must be a list of objects"
            ))),
        })
        .collect()
}

fn strings(value: Value, context: &str) -> Result<Vec<String>> {
    let Value::Array(items) = value else {
        return Err(Error::invalid(format!(
            "{context}: must be a list of strings"
        )));
    };
    items
        .into_iter()
        .map(|item| match item {
            Value::String(string) => Ok(string),
            _ => Err(Error::invalid(format!(
                "{context}: must be a list of strings"
            ))),
        })
        .collect()
}

fn parse_update(update: Value, context: &str) -> Result<FieldUpdate> {
    let Value::Object(mut update) = update else {
        return Err(Error::invalid(format!("{context} must be an object")));
    };
    let set = match update.get("op") {
        Some(Value::String(op)) if op == "set_field" => true,
        Some(Value::String(op)) if op == "delete_field" => false,
        _ => {
            return Err(Error::invalid(format!(
                "{context}: op must be set_field or delete_field"
            )));
        }
    };
    let allowed: &[&str] = if set {
        &[
            "id",
            "op",
            "path",
            "expect",
            "value",
            "from_type",
            "template_field",
        ]
    } else {
        &["id", "op", "path", "expect"]
    };
    only_keys(&update, allowed, context)?;
    let id = match update.remove("id") {
        Some(Value::String(id)) if !id.is_empty() => id,
        _ => {
            return Err(Error::invalid(format!(
                "{context}: id must be a non-empty string"
            )));
        }
    };
    let path = match update.remove("path") {
        Some(Value::Array(segments)) if !segments.is_empty() => segments
            .into_iter()
            .map(|segment| parse_segment(segment, context))
            .collect::<Result<Path>>()?,
        Some(Value::Array(_)) => {
            return Err(Error::invalid(format!("{context}: path must not be empty")));
        }
        _ => return Err(Error::invalid(format!("{context}: path must be a list"))),
    };
    let expect = match update.remove("expect") {
        None | Some(Value::Null) => None,
        Some(expect) => Some(parse_expect(expect, context)?),
    };
    let change = if set {
        let value = required(&mut update, "value", context)?;
        let from_type = match update.remove("from_type") {
            None | Some(Value::Null) => None,
            Some(Value::String(name)) => Some(JsonType::from_name(&name).ok_or_else(|| {
                Error::invalid(format!("{context}: from_type must name a JSON type"))
            })?),
            Some(_) => {
                return Err(Error::invalid(format!(
                    "{context}: from_type must name a JSON type"
                )));
            }
        };
        let template_field = match update.remove("template_field") {
            None | Some(Value::Null) => None,
            Some(Value::Object(field)) => Some(field),
            Some(_) => {
                return Err(Error::invalid(format!(
                    "{context}: template_field must be an object"
                )));
            }
        };
        Change::Set {
            value,
            from_type,
            template_field,
        }
    } else {
        Change::Delete
    };
    Ok(FieldUpdate {
        id,
        path,
        expect,
        change,
    })
}

fn parse_segment(segment: Value, context: &str) -> Result<Segment> {
    match segment {
        Value::String(key) => Ok(Segment::Key(key)),
        Value::Number(_) | Value::Bool(_) => Err(Error::invalid(format!(
            "{context}: path segments must be object keys or selectors; integer list indexes are not allowed"
        ))),
        Value::Object(selector) if selector.len() == 1 => match selector.into_iter().next() {
            Some((name, Value::String(key))) if !key.is_empty() && name == "id" => {
                Ok(Segment::ById(key))
            }
            Some((name, Value::String(key))) if !key.is_empty() && name == "key" => {
                Ok(Segment::ByKey(key))
            }
            _ => Err(Error::invalid(format!("{context}: invalid path segment"))),
        },
        _ => Err(Error::invalid(format!("{context}: invalid path segment"))),
    }
}

fn parse_expect(expect: Value, context: &str) -> Result<Expect> {
    if let Value::Object(expect) = expect
        && expect.len() == 1
    {
        match expect.into_iter().next() {
            Some((key, value)) if key == "value" => return Ok(Expect::Value(value)),
            Some((key, Value::Bool(true))) if key == "absent" => return Ok(Expect::Absent),
            _ => {}
        }
    }
    Err(Error::invalid(format!(
        "{context}.expect must be {{\"value\": ...}} or {{\"absent\": true}}"
    )))
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    #[test]
    fn operations_round_trip() {
        for operation in [
            json!({"type": "add_nodes", "nodes": [{"id": "a"}]}),
            json!({"type": "delete_edges", "ids": ["e"]}),
            json!({"type": "update_metadata", "fields": {"name": 1.0}}),
            json!({"type": "update_metadata", "delete_keys": ["x"]}),
            json!({"type": "update_nodes", "updates": [
                {"id": "a", "path": ["data", {"key": "out"}], "expect": {"absent": true}, "op": "set_field",
                 "value": null, "from_type": "string", "template_field": {"name": "x"}},
                {"id": "a", "path": ["x", {"id": "r"}], "expect": {"value": [1]}, "op": "delete_field"},
            ]}),
        ] {
            let parsed = Operation::from_json(operation.clone()).unwrap();
            assert_eq!(parsed.to_json(), operation);
        }
    }

    #[test]
    fn unset_optional_fields_are_left_out() {
        let parsed = Operation::from_json(json!({"type": "update_edges", "updates": [
            {"id": "e", "op": "set_field", "path": ["data"], "value": 1, "from_type": null, "expect": null}
        ]}))
        .unwrap();
        assert_eq!(
            parsed.to_json(),
            json!({"type": "update_edges", "updates": [{"id": "e", "path": ["data"], "op": "set_field", "value": 1}]})
        );
        let empty = Operation::from_json(json!({"type": "update_metadata"})).unwrap();
        assert_eq!(empty.to_json(), json!({"type": "update_metadata"}));
    }

    #[test]
    fn malformed_operations_are_refused() {
        for operation in [
            json!([]),
            json!({"type": "rename_nodes"}),
            json!({"type": "add_nodes"}),
            json!({"type": "add_nodes", "nodes": [1]}),
            json!({"type": "add_nodes", "nodes": [], "extra": 1}),
            json!({"type": "delete_nodes", "ids": [1]}),
            json!({"type": "update_metadata", "fields": null}),
            json!({"type": "update_metadata", "delete_keys": null}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x"], "value": 1}]}),
            json!({"type": "update_nodes", "updates": [{"id": "", "op": "delete_field", "path": ["x"]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": []}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x", 0]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": [{"id": ""}]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": [{"id": "r", "key": "k"}]}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x"], "expect": {}}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x"], "expect": {"absent": false}}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"], "value": 1, "from_type": "integer"}]}),
            json!({"type": "update_nodes", "updates": [{"id": "a", "op": "move_field", "path": ["x"]}]}),
        ] {
            let error = Operation::from_json(operation.clone()).unwrap_err();
            assert_eq!(error.code.as_str(), "FLOW_OPERATION_INVALID", "{operation}");
        }
        assert!(Operation::list_from_json(json!({})).is_err());
    }
}
