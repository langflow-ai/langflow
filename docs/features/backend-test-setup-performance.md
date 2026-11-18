# Backend API fixture setup and CI resource evidence

## Measured setup cost

On November 12, 2026, the 16 tests in
`src/backend/tests/unit/api/v1/test_scoped_api_keys.py` were profiled on macOS
ARM64 with Python 3.14.9. The profile identified repeated bcrypt work for the
fixture's fixed bootstrap and active-user passwords: 32 hashes took 6.17 seconds
and 15 password checks took 2.70 seconds. After the first app, app construction
took a median 0.049 seconds, so reusing the application was not the target.

The same tests and instrumentation were run before and after the change:

| Measurement | Before | After |
| --- | ---: | ---: |
| Median setup, excluding the first test | 0.953 s | 0.621 s |
| Sum of test setup time | 24.16 s | 18.70 s |
| Pytest elapsed time | 27.53 s | 21.92 s |
| Median warm service initialization | 0.208 s | 0.017 s |
| Result | 16 passed | 16 passed |

This is one local comparison, not a CI speedup claim. Cold imports, migrations,
starter loading, password verification, and runner variability still contribute
to elapsed time.

## Fixture behavior

`tests.fixture_passwords.FixturePasswords` keeps the real bcrypt cost-12 hashes
of the two fixed fixture passwords for the lifetime of one pytest worker.
The shared client uses the cached bootstrap hash only during startup and restores
the normal hasher before yielding. The active-user fixtures use the cached user
hash when inserting their fresh rows.

Password verification, application requests, and passwords other than the fixed
fixture values use the real implementation. Custom authentication services and
replaced password contexts bypass the cache. Tests marked `full_database_init`
retain the real database initialization and bootstrap hashing path.

Each test still creates a fresh application and database. The existing database
template contains only the migrated schema; user rows and mutable application
state are not shared.

## Periodic CI measurements

The backend unit-test step starts `scripts/ci/log_runner_resources.py` before
pytest. The sampler is a separate process, writes immediately, and repeats every
15 seconds. Its line-buffered `test-results/resources.jsonl` is uploaded by the
existing unconditional artifact step, including on failure or timeout.

Samples contain host CPU counters (including Linux steal and I/O wait), load,
memory and swap, disk counters and free space, Linux pressure and cgroup counters
when available, and CPU time, resident memory, and thread counts for the test
process tree. Process details are limited to the 20 largest resident sets. The
first record identifies the runner image, platform, and CPU count. Command lines
and process environments are not collected.

CPU and I/O counters are cumulative; compare adjacent samples to calculate rates.
Summed process resident memory can count shared pages more than once. The existing
`resources.txt` remains the final `/usr/bin/time` report, while the JSONL samples
survive a run that never reaches that final report. A shell exit trap stops the
sampler without changing the test command's exit status.

## Verification

The local commands use `UV_CACHE_DIR=/private/tmp/langflow-ci-fixture-uv`.

```bash
uv sync --frozen --group dev --package langflow-base --inexact

uv run --no-sync python -m pytest \
  scripts/ci/test_log_runner_resources.py \
  scripts/ci/test_backend_test_metrics.py \
  scripts/ci/test_database_template.py \
  -q --no-cov -o log_cli=false --tb=short
```

The CI utility tests passed: 27 tests. The resource tests require permission to
inspect processes. They read samples while the sampler is running and verify
that evidence remains readable after graceful termination and a forced kill.

```bash
uv run --no-sync python -m pytest \
  src/backend/tests/unit/test_login.py \
  src/backend/tests/unit/test_setup_superuser.py \
  src/backend/tests/unit/test_setup_superuser_flow.py \
  src/backend/tests/unit/test_initial_setup.py \
  src/backend/tests/unit/api/v1/test_users.py \
  src/backend/tests/unit/api/v1/test_projects.py \
  src/backend/tests/unit/services/auth/test_auth_service.py \
  src/backend/tests/unit/services/auth/test_pluggable_auth.py \
  src/backend/tests/unit/test_client_fixture_isolation.py \
  src/backend/tests/unit/test_fixture_passwords.py \
  src/backend/tests/unit/test_database_template.py \
  -n 2 --dist load --no-cov -q -m 'not api_key_required' \
  -o log_cli=false --tb=short
```

This run reported 382 passed, 10 skipped, and two filesystem-sync failures from
`PermissionError` under the local filesystem sandbox. Both failed tests passed
when rerun with a writable config directory:

```bash
LANGFLOW_CONFIG_DIR=/private/tmp/langflow-fixture-profile/config \
uv run --no-sync python -m pytest \
  src/backend/tests/unit/test_initial_setup.py::test_sync_flows_from_fs \
  src/backend/tests/unit/test_initial_setup.py::test_sync_flows_from_fs_applies_falsy_values \
  -q --no-cov -o log_cli=false --tb=short
```

The focused fixture-isolation, password-cache, database-template, and pluggable
authentication run also passed all 20 tests. Repository pre-commit checks passed
on the changed files, including Ruff and secret detection. Secret detection
refreshed existing fixture entries' line numbers in `.secrets.baseline`.

The workflow parses as YAML, and `bash -n` accepts the unit-test step. The updated
shell was also exercised with a command that exits with status 7: eight samples
were flushed, the sampler stopped, and the shell preserved status 7. The updated
GitHub Actions workflow has not been run remotely. The complete backend suite
was not run locally.
