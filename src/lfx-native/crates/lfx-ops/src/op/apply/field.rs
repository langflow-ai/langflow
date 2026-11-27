//! Field writes: following an update's path through the batch's
//! writes, and writing its last segment. Replay uses the same
//! steps with no rule.

use std::borrow::Cow;

use crate::json::FlowValue;

use crate::flow::list::{ListIndex, ListProblem, check_position};
use crate::flow::model::{FLOW_MODEL, KeyedList};
use crate::flow::path::{AsKey, PathExt, Segment, path_label};
use crate::json::serialize::quoted;
use crate::op::ApplyOptions;
use crate::op::field_update::{
    FieldBackward, ListItemOnPath, ListProblemAt, NodeValue, PathEnd, SeqNum, SequencedUpdate,
    UpdateTarget, require_path, written_value,
};
use crate::op::operation::{Change, FieldUpdate};
use crate::rule::edge::{GraphRead, reads_before};
use crate::state::field_write::{FieldWrite, Holder};
use crate::state::{Graph, GraphState, Lists, field_value};
use crate::violation::error::{Result, bail, invalid};

impl GraphState {
    /// Apply one `set_field` or `delete_field` to a node, with
    /// the rules for list items. Returns what the path held
    /// before the write.
    pub(super) fn apply_field_update(
        &mut self,
        update: &mut FieldUpdate,
        context: SeqNum,
        options: ApplyOptions,
        backward: Option<&mut FieldBackward>,
    ) -> Result<Before> {
        let sequenced = SequencedUpdate { update, context };
        let update_target = self.find_update_target(&sequenced)?;
        check_lists_on_path(&sequenced, &update_target)?;
        require_path(&sequenced, &update_target)?;
        if let Some(backward) = backward {
            self.record_backward(&sequenced, backward)?;
        }
        let id = sequenced.update.id.as_str();
        let path = &sequenced.update.path;
        let exists = update_target.exists();
        let before = if exists && reads_before(path) {
            field_value(&self.graph, &mut self.lists, id, path, &context)?.map(Cow::into_owned)
        } else {
            None
        };
        check_written_item(&sequenced, &update_target)?;
        let value = written_value(update, options.forward);
        let sequenced = SequencedUpdate { update, context };
        self.write_update(&sequenced, &update_target, value)?;
        self.check_positions_kept(&sequenced, &update_target)?;
        Ok(if exists {
            Before::Value(before)
        } else {
            Before::Nothing
        })
    }

    /// Follow the write's path ([`Graph::read_field`]) and read
    /// what it holds. A segment that does not fit its value,
    /// such as a key of a list, is an error, not a missing
    /// value.
    ///
    /// # Errors
    ///
    /// A segment does not fit the value it reads, or a key
    /// names two items.
    pub(crate) fn find_update_target(
        &mut self,
        sequenced: &SequencedUpdate<'_>,
    ) -> Result<UpdateTarget> {
        let id = sequenced.update.id.as_str();
        let path = &sequenced.update.path;
        let last = path.len() - 1;
        let graph = &self.graph;
        let mut reader = PathReader::new(graph, &mut self.lists, sequenced);
        let reached = graph
            .read_field(id, &path[..last], |value, index, in_write| {
                reader.step(value, index, in_write)
            })?
            .expect("update_nodes checks that the node exists");
        let parent = match reached.found {
            Ok(parent) => parent,
            Err(missing) => return Ok(reader.finish(PathEnd::Missing(missing))),
        };
        let in_write = matches!(reached.holder, Holder::Write { .. });
        let has_last = reader.step(parent, last, in_write)?.is_some();
        let end = match reached.holder {
            Holder::Write { path_len } => {
                reader.add_written_item(path_len);
                PathEnd::InWrite {
                    path_len,
                    exists: has_last,
                }
            }
            Holder::Node { writes } => {
                let write = writes.and_then(|writes| writes.write_at(path));
                PathEnd::InNode(NodeValue::new(has_last, write))
            }
        };
        Ok(reader.finish(end))
    }

    /// Record a write that puts back what the path holds,
    /// before the write. A list item comes back with its
    /// position.
    ///
    /// # Errors
    ///
    /// A key names two items.
    pub(crate) fn record_backward(
        &mut self,
        sequenced: &SequencedUpdate<'_>,
        backward: &mut FieldBackward,
    ) -> Result<()> {
        let update = sequenced.update;
        let current = field_value(
            &self.graph,
            &mut self.lists,
            update.id.as_str(),
            &update.path,
            &sequenced.context,
        )?;
        backward.add(update, current.as_deref());
        Ok(())
    }

    /// Check that a write inside a list item left the item a
    /// position.
    fn check_positions_kept(
        &mut self,
        sequenced: &SequencedUpdate<'_>,
        update_target: &UpdateTarget,
    ) -> Result<()> {
        let id = sequenced.update.id.as_str();
        let path = &sequenced.update.path;
        let context = sequenced.context;
        for item in update_target.list_items.iter().rev() {
            let item_path = &path[..=item.segment];
            let value = field_value(&self.graph, &mut self.lists, id, item_path, &context)?;
            if !value.is_some_and(|value| item.keyed.has_position(&value)) {
                bail!(
                    "{context}: {}",
                    ListProblem::Unpositioned(&item.keyed.position)
                );
            }
        }
        Ok(())
    }

    /// Write or delete the last segment of the path, after
    /// [`Self::find_update_target`].
    ///
    /// # Errors
    ///
    /// The pending patch cannot reach the assignment parent.
    pub(crate) fn write_update(
        &mut self,
        sequenced: &SequencedUpdate<'_>,
        update_target: &UpdateTarget,
        value: FlowValue,
    ) -> Result<()> {
        let update = sequenced.update;
        let id = update.id.as_str();
        let path = &update.path;
        if update.is_delete() && !update_target.exists() {
            // A delete that finds nothing writes nothing.
            return Ok(());
        }
        let write = if update.is_delete() {
            FieldWrite::Remove
        } else {
            FieldWrite::Set(value)
        };
        let writes = self.graph.writes_mut(id);
        match update_target.end {
            PathEnd::InWrite { path_len, .. } => writes.edit(path, path_len, write),
            // The value is only the batch's own write at the
            // path.
            PathEnd::InNode(NodeValue::Added) if update.is_delete() => {
                writes.drop_write(path);
                Ok(())
            }
            _ => writes.set(path, write),
        }
        .map_err(|_| {
            invalid!(
                "{}: cannot write to path {}",
                sequenced.context,
                path_label(path)
            )
        })
    }
}

/// Reads a field update's path one segment at a time. It checks
/// each segment against the value it reads, and keeps the keyed
/// lists on the way.
struct PathReader<'r, 'g> {
    graph: &'g Graph,
    lists: &'r mut Lists,
    sequenced: &'r SequencedUpdate<'r>,
    /// Only a stored node's lists keep their index between
    /// reads.
    stored: bool,
    list_items: Vec<ListItemOnPath>,
    last_list: Option<&'static KeyedList>,
    list_problem: Option<ListProblemAt>,
}

impl<'r, 'g> PathReader<'r, 'g> {
    fn new(graph: &'g Graph, lists: &'r mut Lists, sequenced: &'r SequencedUpdate<'r>) -> Self {
        Self {
            graph,
            lists,
            sequenced,
            stored: graph.is_stored_node(&sequenced.update.id),
            list_items: Vec::new(),
            last_list: None,
            list_problem: None,
        }
    }

    /// Read `path[index]` under `value`. `in_write` is true
    /// inside a write's value, whose lists have no index.
    fn step(
        &mut self,
        value: &'g FlowValue,
        index: usize,
        in_write: bool,
    ) -> Result<Option<&'g FlowValue>> {
        let sequenced = self.sequenced;
        let context = sequenced.context;
        match &sequenced.update.path[index] {
            Segment::Key(key) => {
                let FlowValue::Object(map) = value else {
                    bail!(
                        "{context}.path[{index}]: {} reads a key of a value that is not an object",
                        quoted(key)
                    );
                };
                Ok(map.get(key))
            }
            Segment::Item(key) => self.item(value, index, key, in_write),
        }
    }

    /// Read the item with `key` of the list `value`, which
    /// `path[index]` names.
    fn item(
        &mut self,
        value: &'g FlowValue,
        index: usize,
        key: &str,
        in_write: bool,
    ) -> Result<Option<&'g FlowValue>> {
        let sequenced = self.sequenced;
        let id = sequenced.update.id.as_str();
        let path = &sequenced.update.path;
        let keyed = keyed_list(self.graph, sequenced, index, value)?;
        let items = value.as_array().unwrap_or_default();
        let built;
        let list_index = if self.stored && !in_write {
            &*self.lists.index(id, &path[..index], keyed, items)
        } else {
            built = ListIndex::build(keyed, items);
            &built
        };
        if self.list_problem.is_none() {
            self.list_problem = list_index.problem().map(|problem| ListProblemAt {
                segment: index,
                problem,
            });
        }
        let item_index = list_index.find(key, &sequenced.context.segment(index))?;
        if index == path.len() - 1 {
            self.last_list = Some(keyed);
        } else {
            self.list_items.push(ListItemOnPath {
                keyed,
                segment: index,
            });
        }
        Ok(item_index.map(|item_index| &items[item_index]))
    }

    /// Add the item at the end of the write on the way, which
    /// holds the rest of the path. It was checked when it was
    /// written.
    fn add_written_item(&mut self, path_len: usize) {
        let path = &self.sequenced.update.path;
        if let Segment::Item(_) = &path[path_len - 1] {
            self.list_items.push(ListItemOnPath {
                keyed: FLOW_MODEL.listed_at(&path[..path_len - 1]),
                segment: path_len - 1,
            });
            self.list_items.sort_by_key(|item| item.segment);
        }
    }

    fn finish(self, end: PathEnd) -> UpdateTarget {
        UpdateTarget {
            end,
            list_items: self.list_items,
            last_list: self.last_list,
            list_problem: self.list_problem,
        }
    }
}

/// Check that each keyed list the path reads follows the keyed
/// list rules.
fn check_lists_on_path(
    sequenced: &SequencedUpdate<'_>,
    update_target: &UpdateTarget,
) -> Result<()> {
    match &update_target.list_problem {
        Some(at) => bail!("{}: {}", sequenced.context.segment(at.segment), at.problem),
        None => Ok(()),
    }
}

/// Check that a table row written at its key carries a
/// position.
fn check_written_item(sequenced: &SequencedUpdate<'_>, update_target: &UpdateTarget) -> Result<()> {
    let update = sequenced.update;
    let last = update.path.len() - 1;
    let (Segment::Item(_), Change::Set(value)) = (&update.path[last], &update.change) else {
        return Ok(());
    };
    let keyed = update_target
        .last_list
        .expect("the update_target read the last item's list");
    Ok(check_position(
        keyed,
        value,
        &sequenced.context.segment(last),
    )?)
}

/// What a field write's path held before the write.
#[derive(Debug)]
pub(super) enum Before {
    /// Nothing: the write added a value, or a delete found
    /// nothing.
    Nothing,
    /// A value, kept only when [`reads_before`] needs it.
    Value(Option<FlowValue>),
}

/// The keyed list whose item `path[index]` names. Checks that
/// `model.json` declares it keyed and that `value` is a list.
fn keyed_list(
    graph: &Graph,
    sequenced: &SequencedUpdate<'_>,
    index: usize,
    value: &FlowValue,
) -> Result<&'static KeyedList> {
    let id = sequenced.update.id.as_str();
    let context = sequenced.context;
    let list_path = &sequenced.update.path[..index];
    let keyed = list_path.all_keys().then(|| {
        FLOW_MODEL.keyed_list_by(list_path, |field_path, key| {
            let keys: Vec<&str> = field_path
                .iter()
                .filter_map(AsKey::as_key)
                .chain([key])
                .collect();
            graph.node_value(id, &keys)
        })
    });
    let Some(keyed) = keyed.flatten() else {
        bail!(
            "{context}.path[{index}]: list item key on a list the node schema does not declare keyed"
        );
    };
    if !value.is_array() {
        bail!("{context}.path[{index}]: list item key on a value that is not a list");
    }
    Ok(keyed)
}
