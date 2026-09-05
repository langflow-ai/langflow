# GA-swap procedure: moving one action from SDK/REST to a pinned MCP server

Status: accepted
Owners (sign-off roles): lfx owner, release owner
Last verified: 2026-09-04

This is INT-9's second half: the written procedure a provider bundle follows when a provider's official MCP server
reaches GA and one action should run on it instead of on the bundle's SDK or REST adapter. The promise the procedure
has to keep is narrow and testable: **the component identity and the saved-flow schema do not change**. A flow saved
before the swap keeps working, by the same node, with the same fields, after it.

The engine that makes the swap safe is the pinned mode in `src/lfx/src/lfx/base/mcp/pinned.py` and
`src/lfx/src/lfx/base/mcp/preset.py` (`MCPPresetComponent._pinned_spec`). The pin itself is manifest data
(`IntegrationCapability.mcp_pin`), which is what keeps the swap out of the component's identity.

## What the swap may and may not change

| Must not change | May change |
|---|---|
| Component class `name` (the registry key saved flows store) | The class's base (`Component` to `MCPPresetComponent`) |
| `display_name`, `icon`, palette group, `documentation` | The body of the action method |
| Input names, input types, requiredness, defaults, and order | How those inputs are turned into a provider call |
| Output names, types, and the method they bind to | Which transport and credential header the call uses |
| The `migration_table.json` row for the component | — |
| Capability `id`, `policy_keys`, `auth_profile_id`, `identity`, `required_scopes`, `component_ref`, `risk`, `maturity`, `deployment_contexts` | Capability `substrate`, and the new `mcp_tool` and `mcp_pin` |

Two consequences worth stating plainly, because both are easy to get wrong:

- **A pinned single-action component does not declare `preset_control_inputs`.** Those inputs (Tool dropdown, raw
  JSON arguments, timeout, SSL toggle) are for a *picker* component. Adding them during a swap would add fields to
  every saved node, which is exactly the schema change the procedure forbids. A pinned single-action component sets
  the tool from its pin and builds the arguments from its own declared inputs.
- **The provider's argument names are not the flow's field names.** The pinned input schema is provider-shaped; the
  saved flow is Langflow-shaped. The mapping between them lives in the component, and it is the component author's
  job to keep the flow-facing names identical across the swap even when the provider's differ.

## Procedure

1. **Capture the evidence.** Obtain a dated, authenticated `tools/list` from the official server with the app the
   bundle actually uses, and record, per candidate action: server URL, `InitializeResult.serverInfo` (name and
   version, if any), the exact tool identifier, the raw `inputSchema`, the raw `outputSchema`, and the authorization
   exchange the server accepted. Store it under `design/dedicated-integrations/evidence/`. This capture is the
   re-open trigger in the provider's substrate decision record; without it, stop here.
2. **Re-open the substrate decision.** Amend `decisions/substrate-<provider>.md` (new dated amendment section, facts
   with citations, `Status: accepted` by the release owner) and add `mcp` to `substrate_decision.chosen` in
   `matrices/<provider>.json`. Flip the action's row to `substrate: "mcp"` with a source whose `kind` is
   `mcp_tools_list` pointing at the capture. Run `scripts/ci/check_capability_matrices.py`; it rejects an included
   action whose substrate is outside `chosen`, and rejects `confidence: high` on a non-GA MCP row.
3. **Pin every tool the server exposes, not just the one you use.** Add `mcp_tool` and `mcp_pin` to each MCP
   capability in the bundle's capability manifest. `pinned_spec_from_capabilities()` unions the MCP capabilities that
   share one server into the complete tool set the component may see, so a tool that is present on the server but
   absent from the manifest is an *added* tool and fails closed. All capabilities on one server must agree on
   `server_url`, `transport`, `tools_list_hash`, `server_name`, and `server_version`.
4. **Compute the pin values from the capture.** `tools_list_hash` is
   `lfx.base.mcp.pinned.tools_list_digest(recording["result"]["tools"])` — the helper accepts the raw recorded
   entries. Set `server_name`/`server_version` only if the server actually publishes `serverInfo`; a pinned version
   that the server later stops sending fails closed, by design.
5. **Swap the adapter.** Rebase the component on `MCPPresetComponent`, keep the class `name`, inputs, and outputs
   byte-identical, set `add_tool_output = False` if the pre-swap node had no Toolset output, implement
   `_pinned_spec()` to return the manifest pin, implement `_mcp_server_config()` to return the credential headers
   (`Authorization: Bearer {await lease.get_token()}` per `connection-contract.md` section 6 — the pinned mode
   supplies the URL and transport itself), and expose the tool name and arguments from the component's own inputs.
6. **Keep the action method.** The output method the saved flow binds to keeps its name and its return type; its
   body becomes `return await self.run_tool()`.
7. **Prove the invariants.** Add a swap-equivalence test in the bundle: identity fields equal, input/output shapes
   equal, one saved-flow value set producing the same rows on both halves, and the manifest diff limited to
   `substrate`, `mcp_tool`, `mcp_pin`. `src/lfx/tests/unit/base/mcp/test_ga_swap_procedure.py` is the worked
   example.
8. **Prove it fails closed.** Add drift tests driven by a copy of the capture: a tool added, a tool removed, a tool
   renamed, an argument schema widened, a result schema drifted, a server version moved. Each must raise
   `IncompatibleToolError` (`incompatible-tool`) and none may return a partial toolset.
9. **Release the bundle.** Bump the bundle version through `scripts/ci/bundle_release_plan.py`, raise the bundle's
   `lfx` floor through `scripts/ci/sync_bundle_lfx_pin.py` (pinned mode is new lfx surface), and add the
   `BUNDLE_API.md` changelog line if the bundle's own public surface moved.
10. **Update the estimate and the matrices' `last_verified`** so the record and the code agree on the same date.

## Failure behavior and the support answer

Drift does not degrade: it raises `IncompatibleToolError`, whose `code` is `incompatible-tool` and whose sanitized
`details` name what was added, removed, renamed, changed, and which server pin failed. The remedy is a bundle
release whose pin matches the server (or a provider-side rollback) — there is no operator override, because an
override would silently reintroduce exactly the drift the pin exists to catch. Support answer: "this action's
provider tools changed; upgrade the provider bundle."

Three deliberate boundaries:

- The digest covers tool identity and schemas, not descriptions. Descriptions are prompt material that providers
  edit routinely; folding them in would turn a copy edit into an outage. Descriptions still pass through the MCP
  redaction path.
- The pin fails on *any* input or output schema difference, including a new optional property. Relaxing that (for
  example, tolerating additive optional inputs) is a later decision record, not a runtime option.
- The transport is part of the pin: pinned server configs set `allow_sse_fallback=False`, so an endpoint that only
  answers on the legacy transport surfaces as a failure rather than a silent downgrade.

## What was exercised for 1.13, and what was not

The release owner's 2026-09-04 decision puts INT-9 in 1.13 (see `estimate.md` and the amendment in
`decisions/substrate-slack.md`). The engine and this procedure ship; the *Slack adoption* does not, because step 1's
capture does not exist and cannot be manufactured.

So the procedure is exercised end to end on a **sample action belonging to a fictional `example` provider**, against
a recorded `tools/list` fixture at `src/lfx/tests/unit/base/mcp/fixtures/slack-mcp-tools-list.synthetic.json`. That
fixture is Slack-*shaped* and clearly labeled synthetic inside the file: its tool identifiers and schemas are
invented, it is not a capture, and it is not stored under `evidence/` because it is not evidence. The exercise is in
`src/lfx/tests/unit/base/mcp/test_ga_swap_procedure.py`: it swaps one action, holds every invariant in the table
above, runs the swapped action, and fails closed on six kinds of drift.

Not exercised in 1.13, and honestly so: a live end-to-end run against an official server (no capture, and Slack MCP
admits only directory-published or internal apps — `decisions/substrate-slack.md` fact 2), and any real provider
action running on MCP.

## How `lfx-slack` adopts this

`lfx-slack` (INT-12) ships all seven actions on the Slack Web API in 1.13; `matrices/slack.json`
`substrate_decision.chosen` stays `["rest"]`. When the capture in step 1 exists, the first adoption is expected to
be `slack.user.search`, and it touches exactly these files:

- `design/dedicated-integrations/evidence/slack-mcp-tools-list-<date>.json` (new; the capture)
- `design/dedicated-integrations/decisions/substrate-slack.md` (amendment re-opening the substrate)
- `design/dedicated-integrations/matrices/slack.json` (`chosen` gains `mcp`; the `slack.user.search` row moves to
  `substrate: "mcp"` with an `mcp_tools_list` source)
- `src/bundles/slack/src/lfx_slack/integrations/capabilities.json` (or wherever INT-12 puts the capability
  manifest): every Slack MCP capability gains `mcp_tool` and `mcp_pin`
- the Slack search component: same class name, same inputs and output, rebased on `MCPPresetComponent` with
  `_pinned_spec()` returning the manifest pin and `_mcp_server_config()` returning the Bearer header from the
  connection lease
- the bundle's swap-equivalence and drift tests, modeled on the worked example above
- bundle version bump and `lfx` floor pin

Two Slack-specific facts the capture must settle before that PR is written: whether `https://mcp.slack.com/mcp`
accepts the user token minted by INT-5's `oauth.v2.user.access` exchange as a Bearer, or requires its own
authorization flow tied to the app's fixed app id (`decisions/substrate-slack.md` fact 9); and whether the pinned
tool schemas map onto the REST-shaped inputs INT-12 ships without changing a single flow-facing field name. If they
do not, the swap needs an argument-mapping layer in the component and the "no saved-flow change" promise must be
re-proved by the equivalence test before the PR merges.

## Open items handed on

- The client-facing error mapping for `incompatible-tool` is INT-6's `IntegrationError` branch in
  `src/backend/base/langflow/api/utils/execution_errors.py`; until it lands, the typed code does not reach an API
  client. INT-9 only adds the code to `INTEGRATION_ERROR_CODES`.
- The frontend keys its call to action on `code` (`connection-contract.md` section 7). `frontend-surfaces.md` has no
  MCP-drift row; INT-8 should add one whose action is "upgrade the provider bundle", not "reconnect".
- Token rotation on a pinned server still orphans the MCP session, because `_get_server_key` hashes `url|headers`
  (`connection-contract.md` open question 12.a.7). Pinned mode tolerates it; the session is reclaimed by idle
  cleanup.

## Sign-off

| Role | Name | Date | PR |
|------|------|------|----|
| lfx owner | | | |
| release owner | Eric Hare | 2026-09-04 | release owner decision, 2026-09-04 |
