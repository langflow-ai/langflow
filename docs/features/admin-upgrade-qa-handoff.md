# Administrator upgrade QA handoff

The target code branch is `release-1.14.0`. Follow the [structured test plan](./admin-upgrade-test-plan.md) for the next QA pass. This handoff separates the implemented fixes from release qualification with published artifacts.

## Findings

| Finding | Disposition |
| --- | --- |
| F1 | The PostgreSQL extra now installs binary Psycopg, avoiding its import-time `pg_config` subprocess. Guarded metadata discovery accepts macOS's existing text-encoding setting. The full frozen bundles installation passed the installed checker and exact report/API round-trip. Unapproved network and process operations remain refused. |
| F2 | The consolidated checker now includes the retained-job usage reader and Serving database option. Editor and Serving evidence remain separate. Missing or unreadable history stays unknown, including missing drivers and unavailable WAL files. |
| F3 | Enterprise follows the final immutable OSS revision and has exact acknowledgments for the 11 current lock changes. A changed or unacknowledged lock still fails. |
| F4 | Reports record output and JSON options and the blocked-network policy. Database identities remain redacted. |
| F5 | Sources now use published patches 1.12.10 and 1.13.1. The Langflow target is 1.14.0. Validation rejects placeholder or nonstable platform versions. The runbook links account recovery. Approved control-plane and operator releases and published target image digests remain required release inputs. |
| F6 | Empty Prompt templates retain their saved generated variables during component rebuilding. Exact helper and API regressions cover question and context preservation. |
| F7 | The historical test runs without deselection. It uses the existing reviewed MCP limitation ledger and checks exact fixture and target digests while retaining the original expectations. |
| F8 | Refused startup skips initialized-instance cleanup. A real CLI probe preserved the database digest, unused default user, rollback journal mode, and sidecar inventory. |
| F9 | Admitted execution retains its completed result when maintenance refuses optional new Memory Base work. Real HTTP regressions cover v1, v1 advanced, and v2 synchronous runs. New work remains refused. The same narrow handling applies to editor and background completion. |
| F10 | Report export checks administrator authorization before the maintenance write guard. Unauthorized access returns 403 with maintenance on or off. |
| F11 | Integrity and migration-preflight diagnostics avoid persistent SQLite connection pragmas. Future-revision refusal leaves rollback-journal files unchanged. |
| F12 | The documentation sidebar links the report and repair pages. |

The latest release merge also left two migration heads. A no-op merge joins them and allows a fresh installation to start.

## User-facing review

The page now explains report generation, import, assessment, preview, maintenance, repair, and verification. Import success explicitly says flows have not changed. Complete clear, review, blocking, and incomplete assessments have separate explanations and next actions. Result labels have a readable legend. Preview and apply completion use different messages and show flow names alongside outcomes. All eight locales include the new guidance.

A real browser journey imported a report, previewed a stored flow without changing it, enabled maintenance, confirmed and applied an update, checked saved input and canonical component code, and found the protected recovery outcome after reload. It runs through a separate configuration with its own database and servers. It is excluded from the normal parallel browser suite.

## Observed verification

Counts below are separate suites and overlap. They should not be added together.

| Command or check | Result |
| --- | --- |
| LFX upgrade, rebuilding, substitution, and historical-ledger suites | 399 passed, including the historical test. |
| Revision, diagnostic CLI, maintenance, and report suites | 198 passed, 3 skipped. |
| Real admitted-run HTTP regression across three routes | 3 passed. |
| Native legacy/revision tests on PostgreSQL 18.6 and SQLite | 8 passed, zero skips. |
| Normal default-user teardown behavior | 5 passed, 3 PostgreSQL cases skipped in that separate run. |
| Full frozen bundles CLI and native source/usage checks | 13 passed, zero skips. |
| Fast checker, reader, offline, and usage regression | 237 passed, 1 skipped, 1 deselected. The skipped native reader path passed in the separate full-install run. |
| Installed checker report/API byte round-trip with bundles | 1 passed. |
| Full-bundles negative CLI case | 1 passed in 38.24 seconds with an explicit 300-second test timeout. |
| Prompt component API preservation suite | 15 passed. |
| Upgrade page and locale parity Jest suites | 27 passed, including axe assertions. |
| Existing browser report scenarios | 3 passed with eight IBM assertions, covering import/reload/export, selection and keyboard behavior, and empty/error states. |
| Isolated real repair browser journey | 1 passed with two IBM assertions. |
| Frontend production build | Passed. |
| Enterprise certification, air-gap, and lock suites | 127 passed, 1 approved-media skip. |
| Enterprise target-template follow-up | 58 passed. |
| Canonical frontend type check | Failed with 252 errors in 88 files. No diagnostics named the changed page files. The live browser spec is outside that check. Full TypeScript approval is not claimed. |

Exact commands for the main groups follow.

```sh
PYTHONPATH=scripts/ci LFX_TEST_ALLOW_LANGFLOW=1 uv run --no-sync pytest src/lfx/tests/unit/upgrade src/lfx/tests/unit/custom/test_update_rebuilt_node.py src/lfx/tests/unit/utils/test_component_substitution_warning.py scripts/ci/test_historical_compatibility_gate.py -q --no-header --tb=short -o log_cli=false
uv run --no-sync pytest src/backend/tests/unit/services/database/test_revision_guard.py src/backend/tests/unit/cli/test_integrity.py src/backend/tests/unit/cli/test_migration_preflight.py src/backend/tests/unit/api/v1/test_maintenance.py src/backend/tests/unit/api/v1/test_maintenance_review.py src/backend/tests/unit/api/v1/test_upgrade_reports.py -q --no-header --tb=short -o log_cli=false
uv run --no-sync pytest src/backend/tests/unit/api/v1/test_maintenance_review.py::test_admitted_run_returns_its_completed_result_when_maintenance_starts -q --no-header --tb=short -o log_cli=false
uv run --no-sync --with 'psycopg[binary]' pytest src/backend/tests/unit/services/database/test_legacy_revision_upgrade.py -q -rs --no-header --tb=short -o log_cli=false
cd src/frontend
./node_modules/.bin/jest --runInBand --runTestsByPath src/pages/SettingsPage/pages/UpgradeReportsPage/__tests__/page.test.tsx src/locales/__tests__/locale-parity.test.ts
RUN_A11Y=true RUN_A11Y_ASSERT=true ./node_modules/.bin/playwright test --config playwright.upgrade-qa.config.ts --project=chromium
npm run type-check
npm run build
```

Native runs supplied a disposable local PostgreSQL URL through each suite's documented environment variable. The Enterprise verification and final OSS pin are recorded in its PR. Local results do not certify deployment artifacts or replace QA acceptance.

An attempted full-bundles checker suite exceeded its default 120-second timeout while waiting for a CLI subprocess. The exact case passed with a 300-second timeout. The full slow CLI suite was not completed under that profile. A separate full-bundles API fixture also exceeded its startup timeout. The installed round-trip passed under that profile, and all 15 prompt API cases passed in the ordinary development environment.
