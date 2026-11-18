//! Operations → JSON: as a value, and as text without building the value.

use crate::flow_value;
use crate::json::{FlowObj, FlowValue};

use crate::flow::edge::Edge;
use crate::flow::node::Node;
use crate::flow::path::Segment;
use crate::op::operation::{Change, FieldUpdate, Operation};
impl Operation {
    /// The operation as JSON. It copies every payload; a caller that owns
    /// the operation and drops it after printing uses [`Self::into_value`].
    #[must_use]
    pub fn to_value(&self) -> FlowValue {
        match self {
            Self::AddNodes(nodes) => flow_value!({
                "type": "add_nodes",
                "nodes": nodes.iter().map(|node| node.as_map().clone()).collect::<FlowValue>(),
            }),
            Self::UpdateNodes(updates) => flow_value!({
                "type": "update_nodes",
                "updates": updates.iter().map(FieldUpdate::to_value).collect::<FlowValue>(),
            }),
            Self::DeleteNodes(ids) => flow_value!({
                "type": "delete_nodes",
                "ids": ids.iter().map(String::as_str).collect::<FlowValue>(),
            }),
            Self::AddEdges(edges) => flow_value!({
                "type": "add_edges",
                "edges": edges.iter().map(|edge| edge.as_map().clone()).collect::<FlowValue>(),
            }),
            Self::DeleteEdges(ids) => flow_value!({
                "type": "delete_edges",
                "ids": ids.iter().map(String::as_str).collect::<FlowValue>(),
            }),
        }
    }

    /// The operation as JSON, with its payload moved into the result instead of copied.
    #[must_use]
    pub fn into_value(self) -> FlowValue {
        let (kind, key, payload) = match self {
            Self::AddNodes(nodes) => ("add_nodes", "nodes", objects(nodes, Node::into_map)),
            Self::UpdateNodes(updates) => (
                "update_nodes",
                "updates",
                FlowValue::Array(updates.into_iter().map(FieldUpdate::into_value).collect()),
            ),
            Self::DeleteNodes(ids) => ("delete_nodes", "ids", strings(ids)),
            Self::AddEdges(edges) => ("add_edges", "edges", objects(edges, Edge::into_map)),
            Self::DeleteEdges(ids) => ("delete_edges", "ids", strings(ids)),
        };
        let mut operation = FlowObj::new();
        operation.insert("type".into(), FlowValue::from(kind));
        operation.insert(key.into(), payload);
        FlowValue::Object(operation)
    }
}

fn objects<T>(objects: Vec<T>, into_map: fn(T) -> FlowObj) -> FlowValue {
    FlowValue::Array(
        objects
            .into_iter()
            .map(|object| FlowValue::Object(into_map(object)))
            .collect(),
    )
}

fn strings(strings: Vec<String>) -> FlowValue {
    FlowValue::Array(strings.into_iter().map(FlowValue::from).collect())
}

impl FieldUpdate {
    /// The update as JSON. It copies the value; see [`Self::into_value`].
    #[must_use]
    pub fn to_value(&self) -> FlowValue {
        let path = FlowValue::Array(self.path.iter().map(Segment::to_value).collect());
        match &self.change {
            Change::Set(value) => {
                let value = value.clone();
                flow_value!({"id": self.id.as_str(), "path": path, "op": "set_field", "value": value})
            }
            Change::Delete => {
                flow_value!({"id": self.id.as_str(), "path": path, "op": "delete_field"})
            }
        }
    }

    /// The update as JSON, with its path and value moved into the result instead of copied.
    #[must_use]
    pub fn into_value(self) -> FlowValue {
        let mut update = FlowObj::new();
        update.insert("id".into(), FlowValue::from(self.id));
        update.insert(
            "path".into(),
            FlowValue::Array(
                self.path
                    .into_segments()
                    .into_iter()
                    .map(Segment::into_value)
                    .collect(),
            ),
        );
        match self.change {
            Change::Set(value) => {
                update.insert("op".into(), FlowValue::from("set_field"));
                update.insert("value".into(), value);
            }
            Change::Delete => {
                update.insert("op".into(), FlowValue::from("delete_field"));
            }
        }
        FlowValue::Object(update)
    }
}

#[cfg(feature = "bindings")]
impl Operation {
    /// Write the operation as JSON text, as [`crate::json::serialize::write_value`]
    /// writes [`Self::to_value`], without building that value.
    pub(crate) fn write_json(&self, out: &mut Vec<u8>, ascii: crate::json::serialize::Ascii) {
        use crate::json::serialize::{write_map, write_seq, write_str};
        out.extend_from_slice(b"{\"type\":");
        write_str(out, self.kind().as_str(), ascii);
        match self {
            Self::AddNodes(nodes) => {
                out.extend_from_slice(b",\"nodes\":");
                write_seq(out, nodes, |out, node| write_map(out, node.as_map(), ascii));
            }
            Self::UpdateNodes(updates) => {
                out.extend_from_slice(b",\"updates\":");
                write_seq(out, updates, |out, update| update.write_json(out, ascii));
            }
            Self::DeleteNodes(ids) | Self::DeleteEdges(ids) => {
                out.extend_from_slice(b",\"ids\":");
                write_seq(out, ids, |out, id| write_str(out, id, ascii));
            }
            Self::AddEdges(edges) => {
                out.extend_from_slice(b",\"edges\":");
                write_seq(out, edges, |out, edge| write_map(out, edge.as_map(), ascii));
            }
        }
        out.push(b'}');
    }
}

#[cfg(feature = "bindings")]
impl FieldUpdate {
    fn write_json(&self, out: &mut Vec<u8>, ascii: crate::json::serialize::Ascii) {
        use crate::json::serialize::{write_seq, write_str, write_value};
        out.extend_from_slice(b"{\"id\":");
        write_str(out, &self.id, ascii);
        out.extend_from_slice(b",\"path\":");
        write_seq(out, self.path.iter(), |out, segment| match segment {
            Segment::Key(key) => write_str(out, key, ascii),
            Segment::Item(key) => {
                out.extend_from_slice(b"{\"key\":");
                write_str(out, key, ascii);
                out.push(b'}');
            }
        });
        match &self.change {
            Change::Set(value) => {
                out.extend_from_slice(b",\"op\":\"set_field\",\"value\":");
                write_value(out, value, ascii);
            }
            Change::Delete => out.extend_from_slice(b",\"op\":\"delete_field\""),
        }
        out.push(b'}');
    }
}
