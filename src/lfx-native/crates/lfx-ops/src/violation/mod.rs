//! What a broken rule looks like, and the engine's error.

pub(crate) mod error;

use crate::json::{FlowObj, FlowValue};

/// The stable code of a graph rule.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[expect(missing_docs, reason = "each variant's name says the rule it codes")]
pub enum ViolationCode {
    FlowDataNotObject,
    CollectionNotList,
    NodeNotObject,
    EdgeNotObject,
    NodeIdMissing,
    NodeIdDuplicate,
    EdgeIdMissing,
    EdgeIdDuplicate,
    EdgeEndpointInvalid,
    NodeDataNotObject,
    NonFiniteNumber,
    TableRowNotObject,
    TableRowIdMissing,
    TableRowIdDuplicate,
    TableRowPosInvalid,
    /// An output or tool action has no finite `__pos__`.
    ListItemMissingPos,
    /// A table column is named `__id__` or `__pos__`.
    TableColumnReserved,
    /// A handle has only one of its two forms.
    EdgeHandleFormMissing,
    /// A handle is missing, is not an object, does not parse, or its forms disagree.
    EdgeHandleInvalid,
    /// A handle names an output or field its node does not have.
    EdgeHandleNotFound,
    /// Several edges go into an input that accepts only one edge.
    EdgeTargetOccupied,
    /// An edge has a note at one end.
    EdgeTouchesNote,
}

impl ViolationCode {
    /// The code as the API reports it.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Self::FlowDataNotObject => "FLOW_DATA_NOT_OBJECT",
            Self::CollectionNotList => "COLLECTION_NOT_LIST",
            Self::NodeNotObject => "NODE_NOT_OBJECT",
            Self::EdgeNotObject => "EDGE_NOT_OBJECT",
            Self::NodeIdMissing => "NODE_ID_MISSING",
            Self::NodeIdDuplicate => "NODE_ID_DUPLICATE",
            Self::EdgeIdMissing => "EDGE_ID_MISSING",
            Self::EdgeIdDuplicate => "EDGE_ID_DUPLICATE",
            Self::EdgeEndpointInvalid => "EDGE_ENDPOINT_INVALID",
            Self::NodeDataNotObject => "NODE_DATA_NOT_OBJECT",
            Self::NonFiniteNumber => "NON_FINITE_NUMBER",
            Self::TableRowNotObject => "TABLE_ROW_NOT_OBJECT",
            Self::TableRowIdMissing => "TABLE_ROW_ID_MISSING",
            Self::TableRowIdDuplicate => "TABLE_ROW_ID_DUPLICATE",
            Self::TableRowPosInvalid => "TABLE_ROW_POS_INVALID",
            Self::ListItemMissingPos => "LIST_ITEM_MISSING_POS",
            Self::TableColumnReserved => "TABLE_COLUMN_RESERVED",
            Self::EdgeHandleFormMissing => "EDGE_HANDLE_FORM_MISSING",
            Self::EdgeHandleInvalid => "EDGE_HANDLE_INVALID",
            Self::EdgeHandleNotFound => "EDGE_HANDLE_NOT_FOUND",
            Self::EdgeTargetOccupied => "EDGE_TARGET_OCCUPIED",
            Self::EdgeTouchesNote => "EDGE_TOUCHES_NOTE",
        }
    }

    /// What repair does for this rule, or `None` when the client fixes it.
    #[must_use]
    pub fn repair_action(self) -> Option<&'static str> {
        use ViolationCode as Code;
        Some(match self {
            Code::FlowDataNotObject => "replaced with an empty flow",
            Code::CollectionNotList => "replaced with an empty list",
            Code::NodeNotObject | Code::EdgeNotObject => "dropped the entry",
            Code::NodeIdMissing | Code::EdgeIdMissing | Code::EdgeIdDuplicate => {
                "assigned a generated id"
            }
            Code::NodeIdDuplicate => {
                "assigned a generated id; the first node keeps the id and its edges"
            }
            Code::EdgeEndpointInvalid | Code::EdgeTouchesNote => "dropped the edge",
            Code::NodeDataNotObject => "replaced with an empty object",
            Code::NonFiniteNumber => "replaced with null",
            Code::TableRowNotObject => "dropped the row",
            Code::TableRowIdMissing => "assigned a generated row id",
            Code::TableRowIdDuplicate => "assigned a generated row id; the first row keeps the id",
            Code::TableRowPosInvalid => "assigned a position that keeps the row where it is stored",
            Code::ListItemMissingPos => "assigned the midpoint of its array neighbours' positions",
            Code::EdgeHandleFormMissing => {
                "derived the missing form of the handle from the one present"
            }
            Code::EdgeHandleInvalid
            | Code::EdgeHandleNotFound
            | Code::EdgeTargetOccupied
            | Code::TableColumnReserved => {
                return None;
            }
        })
    }

    /// Who fixes a violation of this rule.
    #[must_use]
    pub fn resolution(self) -> Resolution {
        if self.repair_action().is_some() {
            Resolution::Auto
        } else {
            Resolution::Manual
        }
    }
}

/// How a violation is fixed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Resolution {
    /// The violation has exactly one fix, which `repair` applies.
    Auto,
    /// Fixing it means choosing what the person meant, so the client does.
    Manual,
}

impl Resolution {
    /// The resolution as the API reports it.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Auto => "auto",
            Self::Manual => "manual",
        }
    }
}

pub use crate::json::pointer::{GraphPath, PathPart};

pub(crate) fn path_of(base: &[PathPart], more: &[&str]) -> GraphPath {
    base.iter()
        .cloned()
        .chain(more.iter().map(|key| PathPart::from(*key)))
        .collect()
}

/// One broken rule, where it was found, and a message without graph values.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Violation {
    /// The rule.
    pub code: ViolationCode,
    /// Where it is broken.
    pub path: GraphPath,
    /// What is wrong.
    pub message: String,
    /// The edge an edge rule violation is about.
    pub edge_id: Option<String>,
}

impl Violation {
    pub(crate) fn new(code: ViolationCode, path: GraphPath, message: impl Into<String>) -> Self {
        Self {
            code,
            path,
            message: message.into(),
            edge_id: None,
        }
    }

    /// The violation as the API reports it.
    #[must_use]
    pub fn to_value(&self) -> FlowValue {
        let mut object = FlowObj::new();
        object.insert("code".into(), FlowValue::from(self.code.as_str()));
        object.insert(
            "path".into(),
            FlowValue::Array(self.path.iter().map(PathPart::to_value).collect()),
        );
        object.insert("message".into(), FlowValue::from(self.message.as_str()));
        object.insert(
            "resolution".into(),
            FlowValue::from(self.code.resolution().as_str()),
        );
        if let Some(edge_id) = &self.edge_id {
            object.insert("edge_id".into(), FlowValue::from(edge_id.as_str()));
        }
        FlowValue::Object(object)
    }
}
