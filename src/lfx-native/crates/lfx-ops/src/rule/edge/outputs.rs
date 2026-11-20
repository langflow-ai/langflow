//! A node's outputs list, indexed by output name.

use std::borrow::Cow;
use std::fmt;
use std::sync::LazyLock;

use crate::flow::list::ListIndex;
use crate::flow::model::{FLOW_MODEL, KeyedList, OUTPUTS_PATH};
use crate::json::FlowValue;
use crate::json::serialize::quoted;
use crate::violation::error::{Error, Result, bail};

use super::graph::GraphRead;

static OUTPUTS_LIST: LazyLock<&'static KeyedList> = LazyLock::new(|| {
    FLOW_MODEL
        .keyed_list_at(&FlowValue::Null, &OUTPUTS_PATH)
        .expect("model.json declares the outputs list")
});

/// The keyed list of a node's outputs.
pub(crate) fn outputs_list() -> &'static KeyedList {
    &OUTPUTS_LIST
}

/// A node's outputs, indexed by name.
#[derive(Debug)]
pub(crate) struct Outputs<'g> {
    /// The outputs list, which is an array.
    items: Cow<'g, FlowValue>,
    /// `None` for a short list whose names were checked: it is scanned.
    index: Option<ListIndex>,
}

/// Lists this short are scanned for a name instead of indexed.
const SCANNED_OUTPUTS: usize = 16;

impl Outputs<'_> {
    /// The output named `name`.
    pub fn get(&self, name: &str) -> Option<&FlowValue> {
        let items = self.items.as_array()?;
        match &self.index {
            Some(index) => index.item_index(name).map(|item_index| &items[item_index]),
            None => items
                .iter()
                .find(|item| outputs_list().key_of(item) == Some(name)),
        }
    }

    /// The names of all outputs.
    pub fn names(&self) -> Box<dyn Iterator<Item = &str> + '_> {
        match &self.index {
            Some(index) => Box::new(index.keys()),
            None => Box::new(
                self.items
                    .as_array()
                    .into_iter()
                    .flatten()
                    .filter_map(|item| outputs_list().key_of(item)),
            ),
        }
    }
}

/// Whether every item of a short list has a non-empty key that no other item has.
fn short_with_unique_keys(list: &[FlowValue]) -> bool {
    if list.len() > SCANNED_OUTPUTS {
        return false;
    }
    let mut keys: [&str; SCANNED_OUTPUTS] = [""; SCANNED_OUTPUTS];
    for (item_index, item) in list.iter().enumerate() {
        match outputs_list().key_of(item).filter(|key| !key.is_empty()) {
            Some(key) if !keys[..item_index].contains(&key) => keys[item_index] = key,
            _ => return false,
        }
    }
    true
}

/// Index an outputs list. Each output must have a unique name.
pub(crate) fn index_outputs<'g>(items: Cow<'g, FlowValue>, node_id: &str) -> Result<Outputs<'g>> {
    let FlowValue::Array(list) = items.as_ref() else {
        bail!("node {}: data.node.outputs must be a list", quoted(node_id));
    };
    if short_with_unique_keys(list) {
        return Ok(Outputs { items, index: None });
    }
    let index = ListIndex::build(outputs_list(), list);
    index.check_keys(&fmt::from_fn(|f| {
        write!(f, "node {}: data.node.outputs", quoted(node_id))
    }))?;
    Ok(Outputs {
        items,
        index: Some(index),
    })
}

/// A node's outputs, or `None` for a node without an `outputs` key.
pub(crate) fn node_outputs<'g>(
    graph: &'g impl GraphRead,
    node_id: &str,
) -> Result<Option<Outputs<'g>>> {
    if !graph.has_node(node_id) {
        bail!("node {} does not exist", quoted(node_id));
    }
    let Some(outputs) = graph.node_value(node_id, &OUTPUTS_PATH) else {
        return Ok(None);
    };
    if !outputs.is_array() {
        return Err(Error::graph_message(format!(
            "node {}: data.node.outputs must be a list",
            quoted(node_id)
        )));
    }
    index_outputs(outputs, node_id).map(Some)
}
