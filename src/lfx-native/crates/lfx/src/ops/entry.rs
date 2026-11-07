//! Reading nodes, edges and table rows, which stay untyped JSON.
//!
//! The engine keeps every key of a node or an edge, so it never turns them
//! into typed structs. These methods name the few things it reads from them.

use serde_json::{Map, Value};

/// What the engine reads from a node, an edge or a table row.
pub(crate) trait EntryExt {
    /// The string at `key`, when it is a string that is not empty.
    fn non_empty_str(&self, key: &str) -> Option<&str>;

    /// The id of an entry that passed structural validation. It is empty
    /// for an entry without a string id.
    fn id(&self) -> &str;

    /// A node's template: `data.node.template`.
    fn template(&self) -> Option<&Map<String, Value>>;

    /// The value of a node's template field: `data.node.template.<field>.value`.
    fn field_value(&self, field: &str) -> Option<&Value> {
        self.template()?.get(field)?.get("value")
    }
}

impl EntryExt for Map<String, Value> {
    fn non_empty_str(&self, key: &str) -> Option<&str> {
        self.get(key)?.as_str().filter(|text| !text.is_empty())
    }

    fn id(&self) -> &str {
        self.get("id").and_then(Value::as_str).unwrap_or_default()
    }

    fn template(&self) -> Option<&Map<String, Value>> {
        self.get("data")?.get("node")?.get("template")?.as_object()
    }
}

impl EntryExt for Value {
    fn non_empty_str(&self, key: &str) -> Option<&str> {
        self.as_object()?.non_empty_str(key)
    }

    fn id(&self) -> &str {
        self.as_object().map_or("", EntryExt::id)
    }

    fn template(&self) -> Option<&Map<String, Value>> {
        self.as_object()?.template()
    }
}
