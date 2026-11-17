//! JSON → operations: the strict parser, and a reader for operation text.

use std::str::FromStr;

use crate::collection::hash_map::HashSet;
use crate::json::pointer::{PathPart, resolve};
use crate::json::{FlowObj, FlowValue};

use crate::flow::deserialize::{DeserializeError, FromFlowValue, missing, read, unexpected};
use crate::flow::edge::Edge;
use crate::flow::model::{FLOW_MODEL, KeyedList};
use crate::flow::node::Node;
use crate::flow::path::{Segment, path_label};
use crate::json::serialize::quoted;
use crate::op::operation::{Change, FieldUpdate, NodePath, Operation, OperationKind};
use crate::violation::error::{Error, Result};
impl FromStr for OperationKind {
    type Err = DeserializeError;

    /// The kind that a `type` names.
    fn from_str(name: &str) -> Result<Self, DeserializeError> {
        match name {
            "add_nodes" => Ok(Self::AddNodes),
            "update_nodes" => Ok(Self::UpdateNodes),
            "delete_nodes" => Ok(Self::DeleteNodes),
            "add_edges" => Ok(Self::AddEdges),
            "delete_edges" => Ok(Self::DeleteEdges),
            _ => {
                let message = format!("unsupported operation type {}", quoted(name));
                Err(DeserializeError::new(message).at_key("type"))
            }
        }
    }
}

impl Operation {
    /// Parse a list of operations.
    ///
    /// # Errors
    ///
    /// Fails when `operations` is not a JSON list, or when one of its
    /// operations is not a valid operation.
    pub fn list_from_value(operations: FlowValue) -> Result<Vec<Self>> {
        Vec::from_value(operations).map_err(|error| error.into_error("operations"))
    }
}

impl TryFrom<FlowValue> for Operation {
    type Error = Error;

    /// Parse one operation. It fails unless the operation has exactly one of
    /// the protocol's shapes.
    fn try_from(operation: FlowValue) -> Result<Self> {
        Self::from_value(operation).map_err(|error| error.into_error("operation"))
    }
}

impl FromFlowValue for Operation {
    fn from_value(value: FlowValue) -> Result<Self, DeserializeError> {
        let object = FlowObj::from_value(value)?;
        Ok(match OperationKind::from_map(&object)? {
            OperationKind::AddNodes => {
                let nodes: Vec<Node> = payload(object, "nodes")?;
                no_repeated_ids(nodes.iter().map(Node::id))
                    .map_err(|error| error.at_key("nodes"))?;
                Self::AddNodes(nodes)
            }
            OperationKind::UpdateNodes => {
                let updates: Vec<FieldUpdate> = payload(object, "updates")?;
                no_repeated_paths(&updates).map_err(|error| error.at_key("updates"))?;
                Self::UpdateNodes(updates)
            }
            OperationKind::DeleteNodes => Self::DeleteNodes(payload(object, "ids")?),
            OperationKind::AddEdges => {
                let edges: Vec<Edge> = payload(object, "edges")?;
                no_repeated_ids(edges.iter().map(Edge::id))
                    .map_err(|error| error.at_key("edges"))?;
                Self::AddEdges(edges)
            }
            OperationKind::DeleteEdges => Self::DeleteEdges(payload(object, "ids")?),
        })
    }
}

/// Fail when an id repeats in one operation. For example, the second of two
/// nodes `a` fails with `[1].id: repeats the id 'a'`.
fn no_repeated_ids<'a>(ids: impl Iterator<Item = &'a str>) -> Result<(), DeserializeError> {
    let mut seen = HashSet::default();
    for (index, id) in ids.enumerate() {
        if !seen.insert(id) {
            let error = DeserializeError::new(format!("repeats the id {}", quoted(id)));
            return Err(error.at_key("id").at_index(index));
        }
    }
    Ok(())
}

/// Fail when one `update_nodes` writes one path of one node twice, which is a
/// client bug.
fn no_repeated_paths(updates: &[FieldUpdate]) -> Result<(), DeserializeError> {
    let mut seen = HashSet::default();
    for (index, update) in updates.iter().enumerate() {
        if !seen.insert((update.id.as_str(), &*update.path)) {
            let message = format!(
                "repeats the path {} of node {}",
                path_label(&update.path),
                quoted(&update.id)
            );
            return Err(DeserializeError::new(message).at_index(index));
        }
    }
    Ok(())
}

/// The value of an operation's one payload key, read as `T`. The operation
/// may hold only `type` and `key`.
fn payload<T: FromFlowValue>(object: FlowObj, key: &'static str) -> Result<T, DeserializeError> {
    let mut payload = None;
    for (name, value) in object {
        match name.as_str() {
            "type" => {}
            _ if name == key => payload = Some(read(value, key)?),
            _ => return Err(unexpected(&name)),
        }
    }
    payload.ok_or_else(|| missing(key))
}

impl FromFlowValue for FieldUpdate {
    fn from_value(value: FlowValue) -> Result<Self, DeserializeError> {
        let object = FlowObj::from_value(value)?;
        let set = match object.get("op") {
            None => return Err(DeserializeError::new("op is missing")),
            Some(FlowValue::String(op)) if op == "set_field" => true,
            Some(FlowValue::String(op)) if op == "delete_field" => false,
            Some(_) => {
                return Err(DeserializeError::new("must be set_field or delete_field").at_key("op"));
            }
        };
        let mut id: Option<String> = None;
        let mut path: Option<NodePath> = None;
        let mut written = None;
        for (name, value) in object {
            match name.as_str() {
                "op" => {}
                "id" => id = Some(read(value, "id")?),
                "path" => path = Some(read(value, "path")?),
                "value" if set => written = Some(value),
                _ => return Err(unexpected(&name)),
            }
        }
        let id = id.ok_or_else(|| missing("id"))?;
        if id.is_empty() {
            return Err(DeserializeError::new("must not be empty").at_key("id"));
        }
        let path = path.ok_or_else(|| missing("path"))?;
        let change = if set {
            Change::Set(written.ok_or_else(|| missing("value"))?)
        } else {
            Change::Delete
        };
        let update = Self { id, path, change };
        update.check_keys_kept()?;
        Ok(update)
    }
}

impl FieldUpdate {
    /// Check that the update keeps the key of every list item on its path. An
    /// item's key is its id, so no write may change it, as no write may change
    /// a node's `id`. To give an item another key, delete it and add it again.
    fn check_keys_kept(&self) -> Result<(), DeserializeError> {
        for (index, segment) in self.path.iter().enumerate() {
            let Segment::Item(key) = segment else {
                continue;
            };
            let inner = &self.path[index + 1..];
            let keyed = FLOW_MODEL.listed_at(&self.path[..index]);
            match keyed.key_after_write(inner, &self.change) {
                KeyWrite::Untouched => {}
                KeyWrite::Key(after) if after == key => {}
                _ if inner.is_empty() => {
                    let message = format!(
                        "a list item written at its key must carry the same key: {}",
                        quoted(key)
                    );
                    return Err(DeserializeError::new(message).at_key("value"));
                }
                _ => {
                    return Err(
                        DeserializeError::new("cannot change a list item's key").at_key("path")
                    );
                }
            }
        }
        Ok(())
    }
}

/// Read operations from JSON text straight into their types, without a JSON
/// value for the whole batch. It reads only text in the common shape: an
/// operation with its `type` first, and no repeated key. For any other text,
/// or text that breaks a rule, it returns `None`, and the caller reads the
/// text the general way, which gives the same operations or the exact error.
#[cfg(feature = "api")]
pub(crate) fn operations_from_text(text: &str) -> Option<Vec<Operation>> {
    let mut builder = crate::json::Builder::<true>::default();
    let mut deserializer = serde_json::Deserializer::from_str(text);
    let operations =
        serde::de::DeserializeSeed::deserialize(text::Operations(&mut builder), &mut deserializer)
            .ok()?;
    deserializer.end().ok()?;
    Some(operations)
}

#[cfg(feature = "api")]
mod text {
    use std::fmt;

    use serde::de::{
        self, DeserializeSeed, Deserializer, IgnoredAny, MapAccess, SeqAccess, Visitor,
    };

    use super::{
        Change, Edge, FieldUpdate, Node, NodePath, Operation, OperationKind, Segment,
        no_repeated_ids, no_repeated_paths,
    };
    use crate::flow::deserialize::FromFlowValue;
    use crate::json::{Builder, FiniteSeed, FlowValue};

    /// Any failure: the caller reads the text the general way.
    fn bail<E: de::Error>() -> E {
        E::custom("not in the common shape")
    }

    /// A key of an operation or a field update, read without allocating.
    #[derive(PartialEq, Eq)]
    enum Key {
        Type,
        Nodes,
        Updates,
        Ids,
        Edges,
        Op,
        Id,
        Path,
        Value,
        Other,
    }

    struct KeySeed;
    impl<'de> DeserializeSeed<'de> for KeySeed {
        type Value = Key;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Key, D::Error> {
            d.deserialize_str(self)
        }
    }
    impl Visitor<'_> for KeySeed {
        type Value = Key;
        fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("a key")
        }
        fn visit_str<E: de::Error>(self, key: &str) -> Result<Key, E> {
            Ok(match key {
                "type" => Key::Type,
                "nodes" => Key::Nodes,
                "updates" => Key::Updates,
                "ids" => Key::Ids,
                "edges" => Key::Edges,
                "op" => Key::Op,
                "id" => Key::Id,
                "path" => Key::Path,
                "value" => Key::Value,
                _ => Key::Other,
            })
        }
    }

    /// A string, as an owned `String`.
    struct Text;
    impl<'de> DeserializeSeed<'de> for Text {
        type Value = String;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<String, D::Error> {
            d.deserialize_str(self)
        }
    }
    impl Visitor<'_> for Text {
        type Value = String;
        fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("a string")
        }
        fn visit_str<E: de::Error>(self, text: &str) -> Result<String, E> {
            Ok(text.to_owned())
        }
    }

    /// A list, each item read by `item`.
    struct List<F>(F);
    impl<'de, T, F: FnMut(&mut dyn ItemReader<'de>) -> Option<T>> Visitor<'de> for List<F> {
        type Value = Vec<T>;
        fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("a list")
        }
        fn visit_seq<A: SeqAccess<'de>>(mut self, mut seq: A) -> Result<Vec<T>, A::Error> {
            let mut items = Vec::with_capacity(seq.size_hint().unwrap_or(0));
            loop {
                let mut reader = Reader::<A> {
                    seq: &mut seq,
                    done: false,
                    failed: false,
                };
                let item = (self.0)(&mut reader);
                if reader.failed {
                    return Err(bail());
                }
                if reader.done {
                    return Ok(items);
                }
                items.push(item.ok_or_else(bail)?);
            }
        }
    }

    /// Reads the next item of a list with a seed, without naming the access type.
    trait ItemReader<'de> {
        fn ops(&mut self, builder: &mut Builder<true>) -> Option<Operation>;
        fn value(&mut self, builder: &mut Builder<true>) -> Option<FlowValue>;
        fn text(&mut self) -> Option<String>;
        fn segment(&mut self) -> Option<Segment>;
        fn update(&mut self, builder: &mut Builder<true>) -> Option<FieldUpdate>;
    }

    struct Reader<'s, A> {
        seq: &'s mut A,
        done: bool,
        failed: bool,
    }

    impl<'de, A: SeqAccess<'de>> Reader<'_, A> {
        fn next<S: DeserializeSeed<'de>>(&mut self, seed: S) -> Option<S::Value> {
            match self.seq.next_element_seed(seed) {
                Ok(Some(item)) => Some(item),
                Ok(None) => {
                    self.done = true;
                    None
                }
                Err(_) => {
                    self.failed = true;
                    None
                }
            }
        }
    }

    impl<'de, A: SeqAccess<'de>> ItemReader<'de> for Reader<'_, A> {
        fn ops(&mut self, builder: &mut Builder<true>) -> Option<Operation> {
            self.next(OperationSeed(builder))
        }
        fn value(&mut self, builder: &mut Builder<true>) -> Option<FlowValue> {
            self.next(FiniteSeed(builder))
        }
        fn text(&mut self) -> Option<String> {
            self.next(Text)
        }
        fn segment(&mut self) -> Option<Segment> {
            self.next(SegmentSeed)
        }
        fn update(&mut self, builder: &mut Builder<true>) -> Option<FieldUpdate> {
            self.next(UpdateSeed(builder))
        }
    }

    /// The batch: a list of operations.
    pub(super) struct Operations<'b>(pub(super) &'b mut Builder<true>);
    impl<'de> DeserializeSeed<'de> for Operations<'_> {
        type Value = Vec<Operation>;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Vec<Operation>, D::Error> {
            let builder = self.0;
            d.deserialize_seq(List(|reader: &mut dyn ItemReader<'de>| reader.ops(builder)))
        }
    }

    struct OperationSeed<'b>(&'b mut Builder<true>);
    impl<'de> DeserializeSeed<'de> for OperationSeed<'_> {
        type Value = Operation;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Operation, D::Error> {
            d.deserialize_map(self)
        }
    }
    impl<'de> Visitor<'de> for OperationSeed<'_> {
        type Value = Operation;
        fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("an operation")
        }
        fn visit_map<M: MapAccess<'de>>(self, mut map: M) -> Result<Operation, M::Error> {
            let builder = self.0;
            if map.next_key_seed(KeySeed)? != Some(Key::Type) {
                return Err(bail());
            }
            let kind: OperationKind = map.next_value_seed(Text)?.parse().map_err(|_| bail())?;
            let expected = match kind {
                OperationKind::AddNodes => Key::Nodes,
                OperationKind::UpdateNodes => Key::Updates,
                OperationKind::DeleteNodes | OperationKind::DeleteEdges => Key::Ids,
                OperationKind::AddEdges => Key::Edges,
            };
            if map.next_key_seed(KeySeed)? != Some(expected) {
                return Err(bail());
            }
            let operation = match kind {
                OperationKind::AddNodes => {
                    let values = map.next_value_seed(Values(builder))?;
                    let nodes = values
                        .into_iter()
                        .map(Node::from_value)
                        .collect::<Result<Vec<_>, _>>()
                        .map_err(|_| bail())?;
                    no_repeated_ids(nodes.iter().map(Node::id)).map_err(|_| bail())?;
                    Operation::AddNodes(nodes)
                }
                OperationKind::AddEdges => {
                    let values = map.next_value_seed(Values(builder))?;
                    let edges = values
                        .into_iter()
                        .map(Edge::from_value)
                        .collect::<Result<Vec<_>, _>>()
                        .map_err(|_| bail())?;
                    no_repeated_ids(edges.iter().map(Edge::id)).map_err(|_| bail())?;
                    Operation::AddEdges(edges)
                }
                OperationKind::UpdateNodes => {
                    let updates = map.next_value_seed(Updates(builder))?;
                    no_repeated_paths(&updates).map_err(|_| bail())?;
                    Operation::UpdateNodes(updates)
                }
                OperationKind::DeleteNodes => Operation::DeleteNodes(map.next_value_seed(Ids)?),
                OperationKind::DeleteEdges => Operation::DeleteEdges(map.next_value_seed(Ids)?),
            };
            if map.next_key_seed(KeySeed)?.is_some() {
                return Err(bail());
            }
            Ok(operation)
        }
    }

    struct Values<'b>(&'b mut Builder<true>);
    impl<'de> DeserializeSeed<'de> for Values<'_> {
        type Value = Vec<FlowValue>;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Vec<FlowValue>, D::Error> {
            let builder = self.0;
            d.deserialize_seq(List(|reader: &mut dyn ItemReader<'de>| {
                reader.value(builder)
            }))
        }
    }

    struct Ids;
    impl<'de> DeserializeSeed<'de> for Ids {
        type Value = Vec<String>;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Vec<String>, D::Error> {
            d.deserialize_seq(List(|reader: &mut dyn ItemReader<'de>| reader.text()))
        }
    }

    struct Updates<'b>(&'b mut Builder<true>);
    impl<'de> DeserializeSeed<'de> for Updates<'_> {
        type Value = Vec<FieldUpdate>;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Vec<FieldUpdate>, D::Error> {
            let builder = self.0;
            d.deserialize_seq(List(|reader: &mut dyn ItemReader<'de>| {
                reader.update(builder)
            }))
        }
    }

    struct Path;
    impl<'de> DeserializeSeed<'de> for Path {
        type Value = Vec<Segment>;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Vec<Segment>, D::Error> {
            d.deserialize_seq(List(|reader: &mut dyn ItemReader<'de>| reader.segment()))
        }
    }

    /// A path segment: a string, or `{"key": ...}` with a non-empty key.
    struct SegmentSeed;
    impl<'de> DeserializeSeed<'de> for SegmentSeed {
        type Value = Segment;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<Segment, D::Error> {
            d.deserialize_any(self)
        }
    }
    impl<'de> Visitor<'de> for SegmentSeed {
        type Value = Segment;
        fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("a path segment")
        }
        fn visit_str<E: de::Error>(self, key: &str) -> Result<Segment, E> {
            Ok(Segment::Key(key.to_owned()))
        }
        fn visit_map<M: MapAccess<'de>>(self, mut map: M) -> Result<Segment, M::Error> {
            let Some(name) = map.next_key_seed(Text)? else {
                return Err(bail());
            };
            if name != "key" {
                return Err(bail());
            }
            let key = map.next_value_seed(Text)?;
            if key.is_empty() || map.next_key::<IgnoredAny>()?.is_some() {
                return Err(bail());
            }
            Ok(Segment::Item(key))
        }
    }

    struct UpdateSeed<'b>(&'b mut Builder<true>);
    impl<'de> DeserializeSeed<'de> for UpdateSeed<'_> {
        type Value = FieldUpdate;
        fn deserialize<D: Deserializer<'de>>(self, d: D) -> Result<FieldUpdate, D::Error> {
            d.deserialize_map(self)
        }
    }
    impl<'de> Visitor<'de> for UpdateSeed<'_> {
        type Value = FieldUpdate;
        fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
            f.write_str("a field update")
        }
        fn visit_map<M: MapAccess<'de>>(self, mut map: M) -> Result<FieldUpdate, M::Error> {
            let mut op = None;
            let mut id = None;
            let mut path = None;
            let mut value = None;
            while let Some(key) = map.next_key_seed(KeySeed)? {
                match key {
                    Key::Op if op.is_none() => op = Some(map.next_value_seed(Text)?),
                    Key::Id if id.is_none() => id = Some(map.next_value_seed(Text)?),
                    Key::Path if path.is_none() => path = Some(map.next_value_seed(Path)?),
                    Key::Value if value.is_none() => {
                        value = Some(map.next_value_seed(FiniteSeed(&mut *self.0))?);
                    }
                    _ => return Err(bail()),
                }
            }
            let id = id.filter(|id: &String| !id.is_empty()).ok_or_else(bail)?;
            let path = NodePath::try_from(path.ok_or_else(bail)?).map_err(|_| bail())?;
            let change = match (op.as_deref(), value) {
                (Some("set_field"), Some(value)) => Change::Set(value),
                (Some("delete_field"), None) => Change::Delete,
                _ => return Err(bail()),
            };
            let update = FieldUpdate { id, path, change };
            update.check_keys_kept().map_err(|_| bail())?;
            Ok(update)
        }
    }
}

// --- What a write does to a keyed list item's key ---------------------------------------------

impl KeyedList {
    /// What `change` at `inner`, a path inside an item, does to the item's key.
    /// Example: in a list keyed by `name`, a set of `"b"` at `["name"]` gives
    /// the item the key `b`.
    pub(crate) fn key_after_write<'c>(
        &self,
        inner: &[Segment],
        change: &'c Change,
    ) -> KeyWrite<'c> {
        if inner.len() > self.key.len() {
            return KeyWrite::Untouched;
        }
        let reaches = inner.iter().zip(&self.key).all(|pair| match pair {
            (Segment::Key(segment), PathPart::Key(part)) => segment == part,
            _ => false,
        });
        match change {
            _ if !reaches => KeyWrite::Untouched,
            Change::Set(value) => {
                match resolve(value, &self.key[inner.len()..]).and_then(FlowValue::as_str) {
                    Some(key) => KeyWrite::Key(key),
                    None => KeyWrite::Keyless,
                }
            }
            // A delete of the whole item leaves no item to key.
            Change::Delete if inner.is_empty() => KeyWrite::Untouched,
            Change::Delete => KeyWrite::Keyless,
        }
    }
}

/// What a write does to the key of the list item it writes in.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum KeyWrite<'c> {
    /// The write does not reach the key, or deletes the whole item.
    Untouched,
    /// After the write, the item has this key. It can be the key it had.
    Key(&'c str),
    /// After the write, the item has no key.
    Keyless,
}

#[cfg(test)]
mod tests {
    use crate::flow_value;

    use super::*;

    #[test]
    fn text_reads_and_writes_as_the_general_way_does() {
        let general = |text: &str| {
            let value: crate::json::FiniteFlowValue = serde_json::from_str(text).unwrap();
            Operation::list_from_value(value.0)
        };
        for text in [
            r#"[{"type":"add_nodes","nodes":[{"id":"a","data":{"node":{"template":{"t":{"value":"é 😀","n":1.5}}}}}]}]"#,
            r#"[{"type":"update_nodes","updates":[{"op":"set_field","id":"a","path":["data","node","outputs",{"key":"out"}],"value":{"name":"out","size":1}},{"id":"a","path":["data","node","template","rows","value",{"key":"r"}],"op":"delete_field"}]}]"#,
            r#"[{"type":"delete_nodes","ids":["a","b"]},{"type":"delete_edges","ids":["e"]}]"#,
            r#"[{"type":"add_edges","edges":[{"id":"e","source":"a","target":"b","data":{"x":[1,2]}}]}]"#,
            "[]",
        ] {
            assert_eq!(
                operations_from_text(text),
                Some(general(text).unwrap()),
                "{text}"
            );
            for operation in general(text).unwrap() {
                let mut written = Vec::new();
                operation.write_json(&mut written, crate::json::serialize::Ascii::Escape);
                let expected = crate::api::json_text(&operation.to_value());
                assert_eq!(String::from_utf8(written).unwrap(), expected);
            }
        }
        // Other shapes, and text that breaks a rule, are left to the general reader.
        for text in [
            r#"[{"ids":["a"],"type":"delete_nodes"}]"#,
            r#"[{"type":"delete_nodes","ids":["a"],"ids":["b"]}]"#,
            r#"[{"type":"delete_nodes","ids":[1]}]"#,
            r#"[{"type":"update_nodes","updates":[{"op":"set_field","id":"a","path":["id"],"value":"b"}]}]"#,
            r#"[{"type":"update_nodes","updates":[{"op":"delete_field","id":"a","path":["x"],"value":1}]}]"#,
            r#"[{"type":"add_nodes","nodes":[{"id":"a"},{"id":"a"}]}]"#,
            r#"{"type":"delete_nodes","ids":["a"]}"#,
            r#"[{"type":"delete_nodes","ids":["a"]}] x"#,
        ] {
            assert_eq!(operations_from_text(text), None, "{text}");
        }
    }

    #[test]
    fn operations_round_trip() {
        for operation in [
            flow_value!({"type": "add_nodes", "nodes": [{"id": "a", "data": {"node": {"template": {}}}}]}),
            flow_value!({"type": "update_nodes", "updates": [
                {"id": "a", "path": ["data", "node", "outputs", {"key": "out"}], "op": "set_field", "value": {"name": "out", "size": 1.0}},
                {"id": "a", "path": ["data", "node", "template", "rows", "value", {"key": "r"}], "op": "delete_field"},
            ]}),
            flow_value!({"type": "delete_nodes", "ids": ["a"]}),
            flow_value!({"type": "add_edges", "edges": [{"id": "e", "source": "a", "target": "b"}]}),
            flow_value!({"type": "delete_edges", "ids": ["e"]}),
        ] {
            let parsed = Operation::try_from(operation.clone()).unwrap();
            assert_eq!(parsed.kind().as_str(), operation["type"]);
            assert_eq!(parsed.to_value(), operation);
            assert_eq!(parsed.into_value(), operation);
        }
    }

    #[test]
    fn malformed_operations_are_refused() {
        for operation in [
            flow_value!([]),
            flow_value!({"type": "rename_nodes"}),
            flow_value!({"type": "update_edges", "updates": []}),
            flow_value!({"type": "add_nodes"}),
            flow_value!({"type": "add_nodes", "nodes": [1]}),
            flow_value!({"type": "add_nodes", "nodes": [], "extra": 1}),
            flow_value!({"type": "delete_nodes", "ids": [1]}),
            flow_value!({"type": "update_metadata", "fields": {"name": "x"}}),
            flow_value!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"]}]}),
            flow_value!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x"], "value": 1}]}),
            flow_value!({"type": "update_nodes", "updates": [{"id": "", "op": "delete_field", "path": ["x"]}]}),
            flow_value!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": []}]}),
            flow_value!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x", 0]}]}),
            flow_value!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": [{"key": ""}]}]}),
            flow_value!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": [{"id": "r"}]}]}),
            flow_value!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": [{"id": "r", "key": "k"}]}]}),
            flow_value!({"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x"], "expect": {"absent": true}}]}),
            flow_value!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"], "value": 1, "from_type": "number"}]}),
            flow_value!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"], "value": 1, "template_field": {}}]}),
            flow_value!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"], "value": 1, "secret": "literal"}]}), // pragma: allowlist secret
            flow_value!({"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["x"], "value": 1, "secrets": [{"path": [], "kind": "literal"}]}]}),
            flow_value!({"type": "update_nodes", "updates": [{"id": "a", "op": "move_field", "path": ["x"]}]}),
        ] {
            let error = Operation::try_from(operation.clone()).unwrap_err();
            assert_eq!(error.code.as_str(), "FLOW_OPERATION_INVALID", "{operation}");
        }
        assert!(Operation::list_from_value(flow_value!({})).is_err());
    }

    #[test]
    fn errors_say_where_the_operation_is_malformed() {
        for (operations, message) in [
            (flow_value!({}), "operations: must be a list"),
            (
                flow_value!([{"ids": ["a"]}]),
                "operations[0]: type is missing",
            ),
            (
                flow_value!([{"type": 5}]),
                "operations[0].type: must be a string",
            ),
            (
                flow_value!([{"type": "update_edges"}]),
                "operations[0].type: unsupported operation type 'update_edges'",
            ),
            (
                flow_value!([{"type": "delete_nodes", "ids": ["a"], "extra": 1}]),
                "operations[0]: unexpected key 'extra'",
            ),
            (
                flow_value!([{"type": "delete_nodes", "ids": ["a"]}, {"type": "delete_nodes", "ids": ["b", 5]}]),
                "operations[1].ids[1]: must be a string",
            ),
            (
                flow_value!([{"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["x", 0]}]}]),
                "operations[0].updates[0].path[1]: integer list indexes are not allowed; name a list item with {\"key\": ...}",
            ),
            (
                flow_value!([{"type": "add_nodes", "nodes": [{"data": {}}]}]),
                "operations[0].nodes[0].id: must be a non-empty string",
            ),
            (
                flow_value!([{"type": "add_nodes", "nodes": [{"id": "a", "data": {}}]}]),
                "operations[0].nodes[0].data.node: must be an object (node 'a')",
            ),
            (
                flow_value!([{"type": "add_nodes", "nodes": [
                    {"id": "a", "data": {"node": {"template": {}}}},
                    {"id": "a", "data": {"node": {"template": {}}}},
                ]}]),
                "operations[0].nodes[1].id: repeats the id 'a'",
            ),
            (
                flow_value!([{"type": "add_edges", "edges": [{"id": "e", "source": "a"}]}]),
                "operations[0].edges[0].target: must be a non-empty string",
            ),
            (
                flow_value!([{"type": "add_edges", "edges": [
                    {"id": "e", "source": "a", "target": "b"},
                    {"id": "e", "source": "b", "target": "a"},
                ]}]),
                "operations[0].edges[1].id: repeats the id 'e'",
            ),
            (
                flow_value!([{"type": "update_nodes", "updates": [{"id": "a", "op": "set_field", "path": ["id"], "value": "b"}]}]),
                "operations[0].updates[0].path: cannot change the node's id",
            ),
            (
                flow_value!([{"type": "update_nodes", "updates": [{"id": "a", "op": "delete_field", "path": ["data", "node"]}]}]),
                "operations[0].updates[0].path: cannot write the whole of data.node; write inside it",
            ),
            (
                flow_value!([{"type": "update_nodes", "updates": [
                    {"id": "a", "op": "delete_field", "path": ["position"]},
                    {"id": "a", "op": "set_field", "path": ["position"], "value": {}},
                ]}]),
                "operations[0].updates[1]: repeats the path [\"position\"] of node 'a'",
            ),
        ] {
            let error = Operation::list_from_value(operations).unwrap_err();
            assert_eq!(error.message, message);
        }
    }
}
