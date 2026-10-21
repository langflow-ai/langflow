# Component compatibility data

A saved node is breaking when updating it to the current component drops a connection, drops a value, or needs input nobody gave. Two copies of that rule exist: `has_breaking_change` in `src/lfx/src/lfx/upgrade/checker.py` and `checkCodeValidity` in `src/frontend/src/CustomNodes/helpers/check-code-validity.ts`. The files here keep them in agreement.

## `cases.json`

The shared case table. Both test suites read it:

- `src/lfx/tests/unit/upgrade/test_component_compat.py`
- `src/frontend/src/CustomNodes/helpers/__tests__/check-code-validity.test.ts`

Each case holds:

- `name` and `description`.
- `saved_node`: the node as a flow saves it (`data.node`).
- `connected_fields`: the fields of the saved node that an edge goes into. A narrowed or emptied input is breaking only when it is connected, and so is a field that, on a node in tool mode, the component now marks `tool_mode`. A field whose type changed is breaking when it is connected or holds a value. Both tests turn this list into edges.
- `component`: the current component (its registry or template entry), or `null` when no component has that type.
- `expected`: the status `lfx upgrade` reports, one of `ok`, `outdated_safe`, `outdated_breaking`, `blocked`, `retired`.

The editor returns flags instead of a status. The Jest test maps them like this, and the first row that applies wins:

| Editor result | Status |
|---|---|
| `blocked` | `blocked` |
| `retired` | `retired` |
| not `outdated` | `ok` |
| `outdated` and `breakingChange` | `outdated_breaking` |
| `outdated`, no `breakingChange` | `outdated_safe` |

## `expected_statuses.json`

Whether every node saved on each supported source release needs action, checked against the component index bundled on this branch. `ok` and `outdated_safe` are both recorded as `no_action`, so a component change that keeps saved flows working does not touch this file. Every other status is recorded as it is. The layout is release, then source, then node key:

- `starter_flows`: the starter projects at the release tag. Key: `<flow file>::<node id>`.
- `component_index`: every entry of the release's own component index, treated as a node saved on that release. Key: `<category>.<component type>`.
- `hard_flows`: the flows in `hard_flows/<release>/`. Key: `<flow file>::<node id>`.

The test fails when a node starts or stops needing action. If the change is intended, regenerate the file and review its diff:

```bash
cd src/lfx
UPDATE_COMPAT_EXPECTED=1 uv run pytest tests/unit/upgrade/test_component_compat.py -k source_release
```

The test reads the releases from git tags. If a tag is missing, the test skips locally and fails in CI. Fetch the tags with:

```bash
git fetch origin --force tag v1.12.6 tag v1.13.0
```

## `hard_flows/<release>/`

Flows built and exported on that release, for cases the starter flows do not cover. Add a flow, then regenerate `expected_statuses.json`.

The saved code of most hard-flow nodes equals the bundled code, so `expected_statuses.json` alone never runs the rule on them. `test_hard_flow_status_after_a_component_change` gives one component new code, plus a change a later release could make (an emptied `input_types` list, dropped `Data` type names, no tool-mode input), and pins the status of every node of that type in a hard flow.

`v1.12.6` was built on `langflow==1.12.6` (with `langflow-base` and `lfx` 1.12.6), and `v1.13.0` on `langflow==1.13.0rc2`. Each server ran with its own home and database. The flows were built through the server API: the same field updates the editor sends, and edge handles made by `lfx.graph.flow_builder`. Both folders hold these seven flows:

- `run_flow_inputs.json`: Run Flow with the inputs of the selected flow added as fields, one fed by an edge. Fields the component adds while editing count as removed fields.
- `mcp_tools_arguments.json`: MCP Tools with a selected tool whose arguments became fields, one fed by an edge. The tool came from a local stdio server; its path is shortened to `mcp_greeter_server.py`.
- `nested_groups.json`: a group inside a group, grouped the way the editor does, with edges into proxied fields at both levels. An edge into a group field reaches the inner field its proxy names.
- `tool_mode.json`: an Agent with two components switched to tool mode.
- `provider_fields.json`: Language Model and Agent switched to a non-default provider, and an edge into a Parser field that its mode can hide.
- `prompt_variables.json`: a Prompt Template with two variables, each fed by an edge. The node lists them in `custom_fields`, so they are not removed fields.
- `type_names.json`: edges whose handles carry `Data`, `JSON`, `DataFrame` and `Table`.

`v1.12.6` also holds four flows saved with lfx-bundles 1.1.38 installed, one per component that 1.13 retired: `altk_agent.json`, `chroma_ext_type.json`, `chroma_legacy_type.json` (the older `Chroma` type) and `local_db.json`. The core index leaves these components out, because lfx-bundles discovers them at runtime. The test builds their templates from lfx's own classes, so these nodes read as retired instead of blocked.
