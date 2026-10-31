# Shared fixtures

These files are the specification of the flow engine. Each case gives inputs and the expected output. The expected outputs are written data that people review. They are not recordings of an engine. Every engine must meet every case: the Rust crate, its Python and browser bindings, and, until they are deleted, the Python engine and the editor's TypeScript engine.

Each case names the rule it checks in `rule`. A rule is one decision of the design docs. The table below lists every rule and the doc section that decides it. Every runner fails on a case without a `rule`, and the Rust runner also fails on a rule that this table does not list.

## Add or change a case

1. Find the rule that the case checks in the table below. If the case checks a new decision, add a row for its rule, with the doc section that decides it.
2. Write the case by hand in the file of the function it calls: its `name`, its `rule`, its inputs and its expected output. Write the output that the rule decides, not the output that an engine gives.
3. Run the runners of every runtime (see `../README.md`) and the checkers (see `tools/README.md`). Each difference is an engine that does not meet the rule yet.

A rule change is a reviewed edit to the cases of that rule. The edit and the doc change go in the same review. No tool writes a fixture file.

## Conventions

- A graph whose number text matters (a number that JavaScript reads as Infinity, or `1.0` against `1`) is stored as JSON text in a `*_json` field. A runner gives the engine that exact text.
- An id that the engine draws at random is stored as `<generated edge id>` or `<generated row id>`. A runner accepts any id of that shape there.
- The property sequences in `property_cases.json` are fixed cases too. Their invariants are data: every transaction applies, and the final graph has the hash `graph_hash`. No runner or tool draws random sequences.

## Rules

The doc names refer to the notes in `plans/multiplayer/` of the design vault.

| Rule | Decision | Decided in |
| --- | --- | --- |
| `graph-structure` | Flow data is an object. `nodes` and `edges` are lists of objects. Node and edge ids are present and unique. An edge names existing nodes. Repair fixes each of these one way. | ops-history, "The engine is the validator" and "Repair" |
| `node-objects` | A node's `data`, `data.node` and `data.node.template` are objects for its whole life. No write replaces them whole. | ops-history, "The engine is the validator" |
| `base-graph-checked` | Apply and validation check the stored graph before they apply or compare anything, even for an empty batch. | ops-history, "The engine is the validator" |
| `finite-numbers` | NaN, Infinity and an integer too large for a double are violations. Repair writes `null` in their place. | ops-history, "Types and canonical equality" and "Repair" |
| `violations-reported` | Validation reports every violation once, in document order. The edge rules run only on a sound structure. | ops-history, "The engine is the validator" |
| `canonical-numbers` | The canonical form prints a number as JavaScript prints it (RFC 8785). | ops-history, "Types and canonical equality" |
| `canonical-form` | The canonical form sorts object keys by UTF-16 code units and escapes only what JSON requires (RFC 8785). | ops-history, "Types and canonical equality" |
| `canonical-equality` | Two values are equal when their canonical forms are equal: `1` and `1.0` are equal, `true` and `1` are not. | ops-history, "Types and canonical equality" |
| `node-edge-order` | The array order of nodes and edges is not state. | ops-history, "Node and edge order" |
| `view-state` | View state is kept in a save, but it is not recorded, diffed or compared. Positions are state. | ops-history, "View state" |
| `no-update-metadata` | Every top-level key other than `nodes` and `edges` is view state. There is no `update_metadata`. | oplog-engine-cleanup, "No update_metadata" |
| `handle-parsing` | A handle string is JSON with `œ` for `"`. It parses to an object, or to nothing. | ops-history, "Edge rules" |
| `handle-respelling` | Two spellings of one handle are one handle. A respelling records nothing. | operation-protocol-multiplayer-proposal, "Edge identity" |
| `type-change-is-a-write` | The types are the six JSON types. A change of type is a plain write, with no type precondition. | ops-history, "Types and canonical equality"; oplog-engine-cleanup, "No from_type, no expect" |
| `operation-types` | What each operation does: `add_nodes`, `delete_nodes`, `update_nodes`, `add_edges` and `delete_edges`. An operation reads what earlier operations of its batch wrote. | operation-protocol-one-pager, "Operation types" |
| `operation-paths` | A path segment is an object key, or `{"key": ...}` in a keyed list. A path has no integer segment, and its keys before the last must exist. | operation-protocol-multiplayer-proposal, "Lists: ids and positions" |
| `existence-preconditions` | An update must find its node, field, output or row, and an added edge must find its nodes. If one does not, the whole batch is refused. | operation-protocol-multiplayer-proposal, "Concurrency semantics" |
| `records-only-changes` | A batch records only what changed. A diff of equal graphs is empty. A delete that finds nothing records nothing. | ops-history, "Diff and protocol work needed" |
| `secrets-not-in-operations` | Operations carry no secret parts. Only the history service stores them. | oplog-engine-cleanup, "Secret class on stored writes" |
| `keyed-list-items-by-key` | Outputs are keyed by `name`, tool actions by `tags[0]` and table rows by `__id__`. `{"key": ...}` selects an item. An item's key cannot change. | operation-protocol-multiplayer-proposal, "Node structure schema" and "Lists: ids and positions" |
| `schema-units` | The diff writes whole units of `node_schema.json`: the value, the run-time definition, each toggle, a field, a key outside the template. Units never mix. | operation-protocol-multiplayer-proposal, "Node structure schema" |
| `diff-operation-order` | A diff gives at most one operation of each type, in the order `delete_edges`, `delete_nodes`, `add_nodes`, `update_nodes`, `add_edges`. | ops-history, "Diff and protocol work needed" |
| `edge-handle-forms` | Every edge carries each handle as an object under `data` and as a string. The string parses to the object. Repair derives a missing form from the other. | ops-history, "Edge rules" and "Repair" |
| `edge-handle-endpoint` | A source handle names an output of its source. A target handle names exactly one of a field of its target, or an output that allows loops. Group nodes have no exemption. | ops-history, "Edge rules" |
| `edge-target-occupied` | A field that is not a list, and a loop output, take at most one edge. | ops-history, "Edge rules" |
| `edge-touches-note` | No edge has a note at either end. Repair drops such an edge. | ops-history, "Edge rules" and "Repair" |
| `edge-rules-scope` | The edge rules check the edges that a write adds or changes, and the edges it keeps while it removes their field or output. They do not check the other stored edges. | ops-history, "Edge rules" |
| `edge-change-delete-add` | An edge changes by a delete and an add. There is no `update_edges`. The added edge is checked as a new edge. | operation-protocol-multiplayer-proposal, "Edge identity" |
| `edge-cascade` | A write that removes a field, an output or a node deletes their edges in the same apply. | ops-history, "Edge rules" |
| `table-row-keys` | Each row of a table that a write adds or changes is an object with a unique `__id__` and a finite numeric `__pos__`. Tool actions are not a table. | operation-protocol-multiplayer-proposal, "Lists: ids and positions" |
| `table-row-order` | Rows are ordered by `(__pos__, __id__)`. The array order is not state, and nothing sorts a stored table. | operation-protocol-multiplayer-proposal, "Lists: ids and positions"; oplog-engine-cleanup, "Row order: numeric positions, stored unsorted" |
| `table-row-positions` | Positions for new rows: one past the last, one before the first, or spread between two neighbours. The server never renumbers. The editor renumbers a table `1..n` when a gap has no room left. | operation-protocol-multiplayer-proposal, "Lists: ids and positions"; oplog-engine-cleanup, "Row order: numeric positions, stored unsorted" |
| `table-row-ids-assigned` | A new row gets a random id. A row equal to a stored row keeps its id. A duplicate id is replaced. | operation-protocol-multiplayer-proposal, "Lists: ids and positions" |
| `table-column-reserved` | No column of a table that a write adds or changes is named `__id__` or `__pos__`. | operation-protocol-multiplayer-proposal, "Lists: ids and positions" |
| `legacy-tables` | A table without row ids stays as stored until a write changes it. Its array order is its order. Its first change writes it whole, with ids. | operation-protocol-multiplayer-proposal, "Lists: ids and positions" |
| `row-keys-stripped` | Readers strip `__id__` and `__pos__` and hand out rows in order. A group's embedded flow is not touched. | operation-protocol-multiplayer-proposal, "Lists: ids and positions" |
| `repair-direct-only` | Repair fixes only the violations that have one fix. The others go back to the client, and repair changes nothing for them. | ops-history, "Repair" |
| `repair-on-request` | A save repairs only when the request asks for it. Without the request, a violation refuses the save. | ops-history, "Repair" |
| `save-path` | A save checks the submitted graph against the stored graph and records the diff. A flow without data starts from an empty graph. | ops-history, "Accepted-write algorithm" |
| `restore-fixes` | A restore takes only the edge fixes that address its violations: a delete, or a handle rewrite. The editor's fixes are what its preview changed. | ops-history, "Repair"; oplog-engine-cleanup, "Restore with client fixes" |
| `last-writer-wins` | Of two writes to one path, the later wins. Writes to different paths both land. | operation-protocol-multiplayer-proposal, "Concurrency semantics" |
| `inverses` | Applying the inverses of a batch, last first, gives back the graph before the batch. | ops-history, "API and UI progression" (playback) |
| `replay-same-hash` | Every engine replays the same accepted transactions to the same graph hash. | ops-history, "Diff and protocol work needed"; rust-flow-engine-plan, "Hashes must not change" |
| `lone-surrogates` | A string with a lone surrogate is refused. A surrogate pair is one character. | rust-flow-engine-investigation, "Drift between the two engines today" |
| `depth-limit` | JSON nested deeper than 127 levels is refused, in every runtime. | rust-flow-engine-plan, "Rough Sizing & Key Risks" (deep flows) |
