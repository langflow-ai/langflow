# Testing

Conventions for backend tests. Frontend testing follows the standard Jest/Playwright patterns documented in `src/frontend/`.

## Project policy: avoid mocking

Prefer real integrations. The pattern of "mocked test passes, production fails" has cost us multiple release cycles — see [ANTI-PATTERNS.md](./ANTI-PATTERNS.md) for the relevant commit history. Use mocks only when:

- The dependency is an LLM and the test exercises pure logic → use `MockLanguageModel` from `tests/unit/mock_language_model.py`.
- The dependency is genuinely unreliable and orthogonal to what's being tested.

Otherwise: hit the real thing, mark the test with `@pytest.mark.api_key_required` if it needs credentials, and let CI gate it.

## Built-in fixtures

### `client` (FastAPI test client)

Defined in `src/backend/tests/conftest.py`. Async `httpx.AsyncClient` connected to the full app via `ASGITransport` + `LifespanManager`. Auto-configured with in-memory SQLite and mocked env vars. Skip with `@pytest.mark.noclient`.

```python
async def test_login_endpoint(client):
    response = await client.post("api/v1/login", data={"username": "foo", "password": "bar"})
    assert response.status_code == 200
```

For authenticated routes, also use the `logged_in_headers` fixture.

## Component test base classes

Located in `src/backend/tests/base.py`.

| Base class | Creates `client`? | Use for |
|---|---|---|
| `ComponentTestBase` | No | Component version testing core logic |
| `ComponentTestBaseWithClient` | Yes | Components that hit backend services during `run()` |
| `ComponentTestBaseWithoutClient` | No | Pure-logic components |

### Required fixtures

Every subclass provides three fixtures:

1. **`component_class`** — the component class under test.
2. **`default_kwargs`** — dict of kwargs to instantiate the component (can be empty).
3. **`file_names_mapping`** — list of `VersionComponentMapping` entries mapping each historical Langflow version (from `src/backend/tests/constants.py::SUPPORTED_VERSIONS`) to module/file names. Use `DID_NOT_EXIST` for versions before the component was added.

```python
from tests.base import ComponentTestBaseWithClient, VersionComponentMapping, DID_NOT_EXIST
from langflow.components.my_namespace import MyComponent

class TestMyComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MyComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"foo": "bar"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            VersionComponentMapping(version="1.1.1", module="my_module", file_name="my_component.py"),
            VersionComponentMapping(version="1.0.19", module="my_module", file_name=DID_NOT_EXIST),
        ]
```

The base class auto-provides:

- `test_latest_version` — instantiates and asserts `run()` doesn't return `None`.
- `test_all_versions_have_a_file_name_defined` — ensures mapping completeness vs `SUPPORTED_VERSIONS`.
- `test_component_versions` (parameterized) — builds the component from source for each supported version and asserts execution.

If you rename or move a component file, you **must** update `file_names_mapping` for every supported version, or saved flows on those versions will fail to load. See [CONTRACTS.md](./CONTRACTS.md) row 3.

## Graph testing pattern

The canonical pattern for tests that exercise the graph engine:

1. Build the graph with connected components.
2. Connect them via `.set()` calls.
3. Call `async_start` and iterate over the results.
4. Validate the results.

Don't poke graph internals. If a test needs to reach into private state, the test is wrong or the API is wrong — fix the right one.

## Async patterns

```python
@pytest.mark.asyncio
async def test_async_component():
    result = await component.async_method()
    assert result is not None
```

**Awaiting conditions, not sleeping:** never use `time.sleep` or `asyncio.sleep` to mask a race. Wait on a condition (`asyncio.wait_for`, an event, a queue read with timeout). Sleep-based tests are flaky by construction.

## Pytest markers

- `@pytest.mark.api_key_required` — needs an external API key; CI skips when absent.
- `@pytest.mark.no_blockbuster` — skip blockbuster plugin.
- `@pytest.mark.noclient` — skip the `client` fixture.
- `@pytest.mark.asyncio` — async test (also `pytest-asyncio` auto-mode in some configs).

## Database tests

`test_database.py` may fail in batch and pass individually. If you touch DB models or migrations, run it sequentially as part of your verification:

```bash
uv run pytest src/backend/tests/unit/test_database.py
```

Never edit a past alembic migration. Run `make alembic-upgrade` end-to-end before claiming a migration works.

## API endpoint tests

```python
async def test_flows_endpoint(client, logged_in_headers):
    flow_data = {"name": "Test", "data": {"nodes": [], "edges": []}}
    response = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)
    assert response.status_code == 201
```

For event-stream endpoints, consume the NDJSON stream and validate event order:

```python
async for line in response.aiter_lines():
    if not line:
        continue
    parsed = json.loads(line)
    # First event should be vertices_sorted; last should be end.
```

## Flow testing with starter JSON

Use `tests/unit/build_utils.py` helpers:

```python
from tests.unit.build_utils import create_flow, build_flow, get_build_events

flow_id = await create_flow(client, json_flow, logged_in_headers)
build_response = await build_flow(client, flow_id, logged_in_headers)
events_response = await get_build_events(client, job_id, logged_in_headers)
```

## Running tests

```bash
make unit_tests                              # All backend unit tests, parallel
make unit_tests async=false                  # Sequential
uv run pytest path/to/test.py                # Single file
uv run pytest path/to/test.py::test_name     # Single test

# lfx tests specifically — must be run after `uv sync` inside src/lfx
cd src/lfx && uv sync && uv run pytest
```

## Verification checklist before claiming "tests pass"

- [ ] You actually ran the command, not just composed it.
- [ ] You ran `test_database.py` sequentially if you touched DB code.
- [ ] You ran the specific test file for any component you changed.
- [ ] No skipped tests without a linked issue.
- [ ] No mocks added at the wrong boundary.
