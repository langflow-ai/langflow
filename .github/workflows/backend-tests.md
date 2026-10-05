# Backend CI performance and reliability

`python_test.yml` delegates the complete backend unit suite to
`backend-unit-tests.yml`. Integration, LFX, bundle and CLI jobs remain separate.
Both supported Python endpoints run the full unit selection. Python 3.10 also
collects coverage and publishes the existing Codecov report.

## Timing baselines

Every run journals setup, call and teardown reports in `events.jsonl`, writes
JUnit XML, and uploads the evidence even after test failure. The journal is
line-buffered so completed reports survive a later test or worker crash.
`summary.json` includes elapsed time, phase totals, missing duration entries,
retries, crashes and the slowest phases. Aggregate summaries show shard imbalance.
Per-worker `stacks-*.txt` files capture all thread stacks at 80% of each test's
configured timeout, before pytest-timeout can discard worker-local output by
exiting. These diagnostic timers leave the timeout and test result unchanged.

Before any shard starts, CI restores one timing baseline and distributes that
same file to every shard. Cache keys distinguish the target branch, runner,
Python version, coverage mode, worker count and scheduling algorithm. A cold
cache falls back to `src/backend/tests/.test_durations`.

The reducer publishes new timings only when all shards finish successfully,
their selections do not overlap, and every selected test has a teardown report.
Retried tests are excluded from timing measurements. Failed, interrupted or
crashed runs retain diagnostics but cannot replace the baseline. GitHub's normal
cache branch isolation also applies, so pull requests cannot overwrite the
default branch's cache.

`Store pytest durations` refreshes the default branch and newest release branch
weekly. It runs the same reusable workflow, with separate coverage and noncoverage
measurements. There is no timing-only PR waiting to be merged. Its dispatch inputs
also support measuring a specific branch and benchmarking different configurations.

## Fixture isolation

The ordinary `client` fixture runs real schema creation and migrations once per
worker, then captures the database **before** users and application data are
seeded. Every test receives its own SQLite backup of that template, fresh app,
service manager and connection pool. SQLite's backup API includes committed WAL
pages. User creation and the remainder of the real application lifespan still
run for each test.

Starter-project file locks use that test database's directory, so another
worker cannot cause startup to skip seeding an independent database.

Tests under `alembic` and `initial_setup` always use a fresh schema. Add
`@pytest.mark.full_database_init` to other tests that need schema creation or
migrations during client startup. Tests that create their own apps or call the
database initializer directly always execute the real initializer.
`LANGFLOW_TEST_DATABASE_TEMPLATE=0` disables template reuse for comparisons.

## Retry policy

There is no whole-shard retry, and ordinary tests have zero retries. A known
flake may receive one retry with a tracked issue:

```python
@pytest.mark.flaky(reruns=1, reason="https://github.com/langflow-ai/langflow/issues/12345")
def test_example():
    ...
```

CI rejects flaky markers without that limit and issue reference. Remove the
marker when the issue is fixed. The first failure remains in the event journal
even if the retry passes. Worker restarts are capped at one, and a crash prevents
timing publication. All matrix shards continue after a failure to preserve the
complete failure picture.

## Benchmarking

Use the same commit, Python version and coverage mode for each comparison.
Dispatch `Store pytest durations` with `shards`, `workers` and `distribution`:

```bash
gh workflow run store_pytest_durations.yml --ref YOUR_BRANCH \
  -f python-versions='["3.10"]' -f shards=5 -f workers=2 -f distribution=load
gh workflow run store_pytest_durations.yml --ref YOUR_BRANCH \
  -f python-versions='["3.10"]' -f shards=5 -f workers=4 -f distribution=worksteal
```

Compare elapsed time, summed phase time, total runner minutes, memory pressure,
failure counts and collection size. Run both cold-cache and warm-cache comparisons.
More workers or shards are adopted only after those measurements show a benefit.
Local worker benchmarks should run sequentially to avoid competing for CPU.

The default is ten shards with two workers each. The initial Linux/Python 3.10
comparison on the same commit reduced the longest test job from approximately
23 minutes (five shards, two workers) to 13 minutes (ten shards, two workers).
Five shards with four workers took approximately 17 minutes and exposed a
background-job deadline failure. These first runs also exposed test isolation
bugs, so they are performance measurements, not successful validation runs.

Scheduled timing refreshes retain their failure notification. Manual benchmarks
report their results in Actions and do not send that notification. The workflow does not publish benchmark
coverage to Codecov. It does not change the test selection to obtain a faster result.
