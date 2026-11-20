//! [`Edge`]: an edge object that passed its checks.

use crate::json::{FlowObj, FlowValue};

use crate::flow::deserialize::{DeserializeError, FromFlowValue};
use crate::flow::model::EntryExt;

/// An edge of a flow: one that `add_edges` adds, or one the flow holds.
///
/// Its `id`, `source` and `target` are non-empty strings. An `Edge` cannot be
/// made without these checks, and an edge is never written in place, so no
/// reader checks them again. Whether the nodes and handles it names exist
/// depends on the flow, so apply checks that. Like a [`Node`](crate::Node), an edge is
/// shared, not copied.
#[derive(Debug, Clone, PartialEq)]
pub struct Edge(FlowObj);

impl Edge {
    /// The edge's id.
    #[must_use]
    pub fn id(&self) -> &str {
        self.0.id()
    }

    /// The id of the node the edge leaves from.
    #[must_use]
    pub fn source(&self) -> &str {
        self.0.non_empty_str("source").unwrap_or_default()
    }

    /// The id of the node the edge goes into.
    #[must_use]
    pub fn target(&self) -> &str {
        self.0.non_empty_str("target").unwrap_or_default()
    }

    /// The edge as a JSON object.
    #[must_use]
    pub fn as_map(&self) -> &FlowObj {
        &self.0
    }

    /// The edge as a JSON object, moved out.
    #[must_use]
    pub fn into_map(self) -> FlowObj {
        self.0
    }

    /// Check that `edge` has the shape of an edge.
    fn check(edge: &FlowObj) -> Result<(), DeserializeError> {
        for key in ["id", "source", "target"] {
            if edge.non_empty_str(key).is_none() {
                return Err(DeserializeError::new("must be a non-empty string").at_key(key));
            }
        }
        Ok(())
    }
}

impl TryFrom<FlowObj> for Edge {
    type Error = DeserializeError;

    /// Check `edge`, and keep it as an edge.
    fn try_from(edge: FlowObj) -> Result<Self, DeserializeError> {
        Self::check(&edge)?;
        Ok(Self(edge))
    }
}

impl FromFlowValue for Edge {
    fn from_value(value: FlowValue) -> Result<Self, DeserializeError> {
        let edge = FlowObj::from_value(value)?;
        Self::check(&edge)?;
        Ok(Self(edge))
    }
}
