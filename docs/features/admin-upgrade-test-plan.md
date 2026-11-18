# Administrator upgrade workflow test plan

Run this plan against the exact OSS revision and Enterprise pin handed to QA. Record both revisions and installed package versions. A green checker or repair test does not certify an upgrade and restore route.

## Setup

Use disposable copies of the source databases and storage. Retain a digest of each SQLite file, its journal mode, and its schema revision. For PostgreSQL, record schema and data fingerprints. Keep Editor and Serving databases separate. Do not supply production credentials to fixtures.

Cover the latest published patches of 1.12 and 1.13 for supported routes. Keep 1.10 and 1.11 as best-effort assessment cases. Retain the historical 1.12.6 and 1.13.0 flow fixtures for preservation regressions. Test the target installation both with and without its provider bundles.

Create an active administrator and a regular user. Include an unchanged flow, a safely outdated component, a breaking component, customized code, a retired component, a generated Prompt variable, Run Flow inputs, and MCP Tools arguments. Include missing job history and retained Editor and Serving jobs with success and failure statuses.

## User workflow

| ID | Action | Expected result |
| --- | --- | --- |
| UX-01 | Open Settings > Upgrade reports with no reports. | The page explains how to generate a report and the sequence from assessment through verification. Import stays disabled until a file is selected. |
| UX-02 | Generate a report with the target installation and import the JSON file. | A success message confirms import and explains that flows have not changed. The selected report shows the source, target, time, and assessment. |
| UX-03 | Import malformed JSON, an unsupported format, or a file larger than 20 MiB. | An error describes the problem. Nothing is added to history. The file input identifies its error for assistive technology. |
| UX-04 | Review complete clear, warning, blocking, and incomplete reports. | Each assessment gives a next action. A missing or unverifiable result never appears as confirmed compatibility. A clear report does not claim execution or release certification. |
| UX-05 | Expand What the results mean and a flow's findings. | OK, Needs review, Needs repair, and Could not verify have distinct explanations. Editor and Serving usage remain separate. Missing history stays unknown. |
| UX-06 | Search and filter by owner, name, project, label, result, and unknown edit time. | Only matching rows remain. Pagination and selection remain understandable. Selection is limited to 100 flows. |
| UX-07 | Select flows and preview updates with maintenance off. | Preview changes no flows. Results use flow names and explain ready, manual, missing, and conflict outcomes. Apply remains disabled. |
| UX-08 | Enable maintenance after taking backups and draining work. Review and confirm ready updates. | Apply becomes available only with database maintenance on, migration pause off, and confirmation checked. Only ready items are submitted. |
| UX-09 | Apply, reload, and expand saved outcomes. | Each update has a saved outcome and protected recovery version. Failures and manual cases remain separate. The page asks the administrator to verify updated flows before ending maintenance. |
| UX-10 | Reload a retained report and export it. | The same report remains selected. Exported bytes match the imported file exactly. |
| UX-11 | Use only Tab, Shift+Tab, Space, and Enter. Repeat at 320px width. | Controls have readable names, visible focus, and usable layout. Neither direction traps focus. Status is conveyed in text. |

## Backend and integration regressions

| Finding | Check | Expected result |
| --- | --- | --- |
| F1 | Run the checker and report round-trip with installed provider bundles. | Registry discovery succeeds for supported installed components. Network and unapproved process operations remain blocked. Discovery failures remain explicit. |
| F2 | Run with Editor and optional Serving databases containing retained jobs. | Every flow includes separate usage evidence and coverage limits. CLI help includes the Serving database option. Source data remains unchanged. |
| F3 | Compare the Enterprise pin and exported lock against the tested OSS revision. | The immutable revision matches. Every exact lock delta has a reviewed note. Unknown deltas fail. |
| F4 | Run with JSON output and an output file. | The report records these inputs and the blocked-network policy. URLs never disclose passwords. |
| F5 | Validate the certification matrix and runbook. | Sources use published patches. Platform versions are exact stable releases. The recovery procedure is linked. Missing approved target, control-plane, or operator artifacts block certification. |
| F6 | Update the empty Prompt Template from the 1.13 fixture. | Connected question and context variables survive, as do saved values and edges. A safe classification agrees with the actual update. |
| F7 | Run the full historical compatibility test without deselecting it. | The existing two reviewed MCP limitations are checked against exact fixture and target digests. Every other changed result fails. |
| F8 | Start with a future schema revision, auto-login off, and an unused default user. | Startup refuses and leaves the database bytes, journal mode, schema, and user unchanged. |
| F9 | Start a real v1 run, then enable maintenance before it returns. | The admitted run returns its completed result. Refusal to schedule optional new background work does not turn success into HTTP 500. New work stays blocked. |
| F10 | Access every report route as a regular user with maintenance on and off. | Both states return 403 for unauthorized users, including export. |
| F11 | Run integrity and migration preflight on a newer rollback-journal SQLite database. | Both refuse without changing bytes or creating WAL or SHM files. |
| F12 | Open the documentation sidebar. | Checker, reports, repairs, and maintenance pages are reachable. |

## Commands

Run from the repository root with the package development dependencies installed. Supply a disposable PostgreSQL URL for tests marked as native PostgreSQL coverage. A skip is missing coverage and must be recorded.

```sh
LFX_TEST_ALLOW_LANGFLOW=1 uv run --no-sync pytest src/lfx/tests/unit/upgrade src/lfx/tests/unit/custom/test_update_rebuilt_node.py
uv run --no-sync pytest src/backend/tests/unit/upgrade_check src/backend/tests/unit/services/database/test_revision_guard.py src/backend/tests/unit/cli/test_integrity.py src/backend/tests/unit/cli/test_migration_preflight.py src/backend/tests/unit/api/v1/test_maintenance_review.py src/backend/tests/unit/api/v1/test_upgrade_reports.py
cd src/frontend
./node_modules/.bin/jest --runInBand --runTestsByPath src/pages/SettingsPage/pages/UpgradeReportsPage/__tests__/page.test.tsx src/locales/__tests__/locale-parity.test.ts
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test tests/a11y/upgrade-reports.a11y.spec.ts --project=chromium --workers=1
RUN_A11Y=true RUN_A11Y_ASSERT=true npx playwright test --config playwright.upgrade-qa.config.ts --project=chromium
```

The Playwright configuration starts servers on ports 3000 and 7860. Use an isolated configuration when those ports belong to another installation. Do not reuse a live installation for this plan.

The separate `playwright.upgrade-qa.config.ts` starts its own backend, temporary database, and frontend on ports 7881 and 3011. It refuses to reuse an existing server. The real maintenance and repair journey lives under `tests/live` and is excluded from the normal parallel suite. Its checks cover unchanged preview data, the maintenance and confirmation gates, persisted input preservation, canonical replacement code, and retained recovery outcomes after reload.

## Release qualification

After these checks, run the Enterprise upgrade and restore matrix using approved published artifacts and deployment bindings. Cover every declared execution context and every staged hop. Verify repaired graphs, owner access, storage, both databases, and restored old artifacts before reopening traffic. Record the actual Langflow, control-plane, and operator versions in the result. Template validation and local tests do not supply that evidence.

## Evidence record

Record the build revisions, commands, counts, skipped cases, UI screenshots, source fingerprints, and each finding's disposition in the QA handoff. Keep unresolved artifact or version requirements visible. Do not change a failed case to passed based only on an implementation change.
