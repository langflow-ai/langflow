# DB Migration Validation Workflow - Implementation Summary

## Jira Ticket
**LE-1259**: Implement DB migration validation workflow in Langflow-Nightly CI

## Overview
Implemented automated database migration testing in the nightly build pipeline to ensure safe upgrades from stable to nightly versions.

## What Was Implemented

### 1. New Workflow: `db-migration-validation.yml`
Location: `.github/workflows/db-migration-validation.yml`

**Purpose**: Validates that database migrations work correctly when upgrading from stable Langflow to nightly builds.

**Test Scenarios**:

#### Scenario 1: pip/venv Migration
- Installs latest stable `langflow[postgresql]` in a Python virtual environment
- Initializes PostgreSQL database with stable version
- Creates "witness" test data (flows and credentials)
- Upgrades to `langflow-nightly[postgresql]` in the same venv
- Verifies Langflow starts successfully after migration
- Confirms witness data persists after upgrade

#### Scenario 2: Docker Compose Migration
- Starts `langflowai/langflow:latest` via Docker Compose
- Creates witness test data via API
- Stops Langflow container (keeps PostgreSQL volume)
- Updates to `langflowai/langflow-nightly:latest`
- Starts nightly version against same PostgreSQL volume
- Verifies successful startup and data persistence

### 2. Integration with Nightly Build
Modified: `.github/workflows/nightly_build.yml`

**Changes**:
- Added `db-migration-validation` job that runs after `release-nightly-build` succeeds
- Updated Slack notifications to include migration test results
- Migration tests run automatically on every nightly build

### 3. Execution Schedule
- **Automatic**: Runs daily at 3:00 AM UTC (after nightly Docker images are built)
- **Manual**: Can be triggered via workflow_dispatch
- **On-demand**: Called by nightly_build.yml after successful Docker build

## Key Features

### Data Persistence Validation
- Creates "witness flows" before migration
- Verifies flows exist after migration
- Ensures no data loss during upgrade process

### Comprehensive Logging
- Captures Langflow startup logs
- Saves API responses for debugging
- Uploads artifacts on failure (logs, JSON responses)
- Retention: 7 days for failure artifacts

### Slack Notifications
- Reports success/failure of both migration scenarios
- Includes links to full logs and artifacts
- Integrated with existing nightly build notifications

### Error Handling
- Timeouts for startup (120-180 seconds)
- Health check validation before proceeding
- Detailed error messages with container logs
- Graceful cleanup on failure

## Testing Matrix

| Scenario | Install Method | Database | Upgrade Path | Data Validation |
|----------|---------------|----------|--------------|-----------------|
| pip/venv | uv pip install | PostgreSQL 16 | stable → nightly | ✅ Witness flows |
| Docker Compose | Docker image | PostgreSQL 16 (volume) | latest → nightly:latest | ✅ Witness flows |

## Environment Variables

### Required Secrets
- `LANGFLOW_ENG_SLACK_WEBHOOK_URL` - For notifications

### Database Configuration
- `POSTGRES_DB`: langflow_test
- `POSTGRES_USER`: langflow
- `POSTGRES_PASSWORD`: langflow_test_pass
- `POSTGRES_VERSION`: 16

### Langflow Configuration
- `LANGFLOW_SUPERUSER`: admin
- `LANGFLOW_SUPERUSER_PASSWORD`: admin123 / testpass123
- `LANGFLOW_DATABASE_URL`: Auto-configured per scenario

## Success Criteria

Both scenarios must pass for the workflow to succeed:
1. ✅ Langflow starts successfully after migration
2. ✅ Health check endpoint responds (200 OK)
3. ✅ Witness flows are retrievable via API
4. ✅ No database errors in logs

## Failure Handling

On failure, the workflow:
1. Captures all relevant logs (Langflow, Docker, PostgreSQL)
2. Saves API responses and flow data
3. Uploads artifacts to GitHub Actions
4. Sends detailed Slack notification with failure reason
5. Provides direct link to logs and artifacts

## Future Enhancements (Not in Scope)

The following were discussed but are NOT part of LE-1259:
- ❌ E2E test suite integration (still being assessed by QA)
- ❌ Playwright test automation in nightly builds
- ❌ Full regression test suite execution

These will be addressed in future tickets once QA completes their assessment.

## Testing the Workflow

### Manual Trigger
```bash
# Via GitHub UI: Actions → DB Migration Validation → Run workflow
# Or via gh CLI:
gh workflow run db-migration-validation.yml \
  --ref feature/qa-nightly-integration \
  -f nightly_tag=langflowai/langflow-nightly:latest
```

### Automatic Execution
- Runs automatically after every successful nightly build
- Triggered at 3:00 AM UTC daily via cron schedule

## Monitoring

### Success Indicators
- ✅ Both migration scenarios pass
- ✅ Slack notification shows success
- ✅ No artifacts uploaded (only on failure)

### Failure Indicators
- ❌ Slack notification shows failure
- ❌ Artifacts available for download
- ❌ Workflow run shows red status

## Branch Information
- **Branch**: `feature/qa-nightly-integration`
- **Base**: `release-1.10.0`
- **Files Changed**: 2
  - `.github/workflows/db-migration-validation.yml` (new)
  - `.github/workflows/nightly_build.yml` (modified)

## Next Steps

1. **Review**: Team review of the implementation
2. **Test**: Manual trigger to validate workflow execution
3. **Merge**: Merge to release-1.10.0 after approval
4. **Monitor**: Watch first automatic run in production
5. **Document**: Update team documentation with new workflow

## References
- Jira: https://datastax.jira.com/browse/LE-1259
- Reference Implementation: https://github.com/oriontech-me/langflow-e2e/actions/workflows/migration-test.yml
