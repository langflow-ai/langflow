# CI/CD Pipeline Templates

Ready-to-use workflow files for the Flow DevOps Toolkit.
Copy the files you need into your project's CI configuration.

## GitHub Actions

| File | Trigger | Secrets needed |
|------|---------|----------------|
| [`github-actions/langflow-validate.yml`](github-actions/langflow-validate.yml) | PR touching `flows/**/*.json` | None |
| [`github-actions/langflow-test.yml`](github-actions/langflow-test.yml) | PR touching flows or tests | `LANGFLOW_STAGING_API_KEY` |
| [`github-actions/langflow-push.yml`](github-actions/langflow-push.yml) | Push to `main` touching flows | `LANGFLOW_PROD_API_KEY` |

### Quick start

```bash
mkdir -p .github/workflows
cp github-actions/langflow-validate.yml \
   github-actions/langflow-test.yml \
   github-actions/langflow-push.yml \
   .github/workflows/
```

Configure these in **Settings → Environments**:

**`staging`** environment (used by `langflow-test.yml`):
| Name | Type | Value |
|------|------|-------|
| `LANGFLOW_STAGING_URL` | Variable | `https://staging.langflow.example.com` |
| `LANGFLOW_STAGING_API_KEY` | Secret | your staging API key |

**`production`** environment (used by `langflow-push.yml`):
| Name | Type | Value |
|------|------|-------|
| `LANGFLOW_PROD_URL` | Variable | `https://langflow.example.com` |
| `LANGFLOW_PROD_API_KEY` | Secret | your production API key |
| `LANGFLOW_PROJECT_NAME` | Variable | `Production Flows` *(optional)* |

Add **Required reviewers** to the `production` environment to gate every deploy
behind a manual approval step.

---

## GitLab CI

| File | Description |
|------|-------------|
| [`gitlab-ci/langflow.yml`](gitlab-ci/langflow.yml) | Three-stage template: validate → test → deploy |

### Quick start

```bash
mkdir -p .gitlab/ci
cp gitlab-ci/langflow.yml .gitlab/ci/
```

Add to your `.gitlab-ci.yml`:

```yaml
include:
  - local: .gitlab/ci/langflow.yml
```

Configure these in **Settings → CI/CD → Variables**:

| Variable | Protected | Masked | Description |
|----------|-----------|--------|-------------|
| `LANGFLOW_STAGING_URL` | ✓ | ✗ | Staging instance URL |
| `LANGFLOW_STAGING_API_KEY` | ✓ | ✓ | Staging API key |
| `LANGFLOW_PROD_URL` | ✓ | ✗ | Production instance URL |
| `LANGFLOW_PROD_API_KEY` | ✓ | ✓ | Production API key |
| `LANGFLOW_PROJECT_NAME` | ✗ | ✗ | Project folder name *(optional)* |

---

## How it all fits together

```
PR opened
  │
  ├── langflow-validate  ──── lfx validate flows/ --level 4
  │                           ↳ blocks merge if any flow is malformed
  │
  └── langflow-test  ──────── pytest tests/ --langflow-env staging
                              ↳ skips gracefully if staging is unavailable

Merge to main
  │
  └── langflow-push  ──────── lfx push --dir flows/ --env production
                              ↳ upserts every flow by stable ID
                              ↳ idempotent: safe to re-run
```

## Writing integration tests

Install the testing extra:

```bash
pip install "langflow-sdk[testing]"
```

Create `tests/test_flows.py`:

```python
def test_rag_flow(flow_runner):
    response = flow_runner("rag-endpoint", "What is Langflow?")
    assert "Langflow" in response.first_text_output()

async def test_async_flow(async_flow_runner):
    response = await async_flow_runner("my-endpoint", "Hello!")
    assert response.first_text_output() is not None
```

Run locally against staging:

```bash
LANGFLOW_URL=https://staging.langflow.example.com \
LANGFLOW_API_KEY=<key> \
pytest tests/ -m integration
```
