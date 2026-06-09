# Anti-Patterns and Scar Tissue

These are battle scars. Every rule here cites a real recurring failure: a commit, a revert, or an explicit project lesson. Read this file when you're about to "just" change something — most of the don't/do rules below started as a one-line "small fix" that broke production.

## Don't / Do (with why)

1. **Don't add or rename a field on a component without regenerating starter projects AND the component index.**
   *Why:* commits `1a9f4548c`, `5987421bd`, `bbe1dad7c`, `69d29a4c6`, `67af71450`, `4f9beebc0` are all `fix:` commits cleaning up the same "I added a field and shipped" mistake. CI (`9dad1965c`) now syncs the index on label addition — that's a backstop, not a substitute.

2. **Don't rename a component class, display name, or module path.** If unavoidable, add the new component alongside the old one, set `legacy = True` + `replacement = ["<category>.<NewClassName>"]` on the old class, and update every supported version's `file_names_mapping` in tests.
   *Why:* class names key saved flows. There is no class-rename map in `setup.py` — the `type_migrations` map there only handles output type strings (`Data` → `JSON`, `DataFrame` → `Table`). See `2a7c56e84` (`IngestionDescriberComponent` → `FileDescriptionGeneratorComponent`) and `f5a0d52197` (starter project rename) for the cleanup churn. See [CONTRACTS.md](./CONTRACTS.md) for the full list.

3. **Don't mock at a different boundary than production calls.** If production uses `subprocess.Popen`, mock `Popen` — not `run`.
   *Why:* `a747135d1`, `bc433c375` — mocked tests passed; production failed. **Better: don't mock at all** — project policy is "Avoid mocking in tests." Use real integrations or `MockLanguageModel` for pure-logic LLM paths.

4. **Don't write a Graph test by poking internals.**
   *Why:* the canonical pattern is build → connect via `.set()` → call `async_start` → iterate results → validate. Tests that bypass this don't exercise the graph the way users do.

5. **Don't add a retry, broaden an except, or widen a type to make a symptom go away.**
   *Why:* "It is not a fix if you didn't have evidence of the change fixing something." See revert chain `9cdbf1b23`, `35aad2f2e`, `e3b90b7351` — fixes that masked rather than solved, then had to be reverted.

6. **Don't bump a dependency speculatively.** Confirm the conflict reproduces locally and the new version actually resolves it.
   *Why:* `cf659f0d0`, `ef6a303406`, `38d142a72`, `9029c4b61` — repeated dep-conflict cleanup.

7. **Don't invent model IDs, MCP tool names, or API surface.** Read the registry, the batch dispatcher, and `models.py` first.
   *Why:* `9f1402ed9` (`remove fictional gpt-5.3 ids`), `cecc4a6c2` (`expose layout tool as layout_flow to match batch dispatch`).

8. **Don't use raw `langflow run` / `python` when a `uv` command exists.** Always `uv run`. For lfx tests specifically: `uv sync` inside `src/lfx` (not `src/lfx/src/lfx`) to avoid pulling in langflow.
   *Why:* lfx must be testable without langflow installed; mixing them masks dependency leaks.

9. **Don't add a database migration without running `make alembic-upgrade` end to end** and `uv run pytest src/backend/tests/unit/test_database.py` sequentially.
   *Why:* `d8b9cc38f`, `c30150a2d`, `6585fe661`. `test_database.py` may pass in batch and fail individually — agents have stopped running it.

10. **Don't claim a race condition is fixed without an integration test that reproduced it.** Agent double-execution and queue leaks keep coming back.
    *Why:* `8a993ac90`, `42e84d0fd`, `749865b31`, `f30b291f8`.

11. **Don't add `tool_mode=True` to outputs that confuse agents** (e.g., dataframe surfaces).
    *Why:* `cbc54108` (`remove tool_mode=True for as_dataframe`), `35aad2f2e` (revert of the original disable). Output tool exposure is a user contract — don't toggle it back and forth.

12. **Don't widen the scope of a PR.** Closely related follow-ups belong in the existing open PR, not a new stacked PR.

13. **Don't ship without running the tests locally.** Typing the test command in the chat is not running it.

14. **Don't make incremental "wip" commits.** One coherent commit per logical change, after everything is done and tested.

15. **Don't push or open PRs without explicit user confirmation.** Pushing during active CI iteration on an already-open PR is fine; opening a new PR or pushing new branches is not.

## Things that look like a fix but aren't

- Adding `try/except Exception: pass` around a flaky call.
- Adding a `time.sleep` to dodge a race instead of awaiting a condition.
- Bumping a dependency version "just in case."
- Marking a failing test `@pytest.mark.skip` without a linked issue.
- Switching `# type: ignore` instead of fixing the type.
- Reverting symptoms (a UI flag, a tool flag) instead of finding the root.
- "Fixing" a test by changing its assertion to match wrong output.

## Before claiming done

- [ ] `make format_backend` and `make lint` clean.
- [ ] Tests for the changed surface ran and passed locally — not just typed out.
- [ ] If a component field/output changed: starter projects regenerated and `component_index.json` rebuilt.
- [ ] If a class/module renamed: old class kept with `legacy=True` + `replacement=[...]`; `file_names_mapping` updated for every supported version.
- [ ] No incremental "wip" commits. One coherent commit per logical change.
- [ ] No "Generated with Claude Code" / `Co-Authored-By: Claude` trailers.
- [ ] No `--no-verify` unless explicitly authorized.
- [ ] PR not pushed and PR not opened until the user explicitly asks.
- [ ] PR description has no test-plan checklist, no Jira links/IDs.

## Where to look for context — don't invent it

- **Starter projects:** `src/backend/base/langflow/initial_setup/starter_projects/`. Any field/output change must regenerate these.
- **Component index:** `src/lfx/src/lfx/_assets/component_index.json` (rebuilt via the index sync workflow added in `9dad1965c`).
- **Output type migrations:** `src/backend/base/langflow/initial_setup/setup.py` `type_migrations` map — handles renames of *output type strings* (e.g., `Data` → `JSON`). It does NOT remap component class names; for class renames use `legacy=True` + `replacement=[...]`.
- **Version mapping for component tests:** `src/backend/tests/constants.py::SUPPORTED_VERSIONS` and each test's `file_names_mapping`.
- **Release notes / changelog:** `docs/docs/Support/release-notes/` — check before claiming behavior is "new"; many features predate the current task.
- **MCP tool catalog:** dispatched via the batch tool — names must match (`cecc4a6c2` is the canonical "I guessed the tool name" failure).
- **Models / providers:** real model IDs come from the provider's listing endpoint or our adapter, never from training-data memory (`9f1402ed9`).
- **Migrations:** `src/backend/base/langflow/alembic/versions/` — always read the latest two before adding a new one.
