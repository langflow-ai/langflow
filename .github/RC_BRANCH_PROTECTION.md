# Release Candidate Branch Protection Settings

This document outlines the required GitHub branch protection and repository settings for release candidate (RC) branches.

## Branch Protection Rules Required

The following branch protection rules must be configured via GitHub's web interface for the pattern `release-*`:

### 1. Branch Protection Rules
- **Branch name pattern**: `release-*`
- **Restrict pushes that create files**: ❌ (Allow)
- **Restrict push/merges**: ✅ (Required)
- **Require a pull request before merging**: ✅ (Required)
  - **Require approvals**: ✅ (1 approval minimum)
  - **Dismiss stale PR approvals when new commits are pushed**: ✅
  - **Require review from code owners**: ✅ (if CODEOWNERS exists)
  - **Restrict reviews to users with write access**: ✅
- **Require status checks to pass before merging**: ✅ (Required)
  - **Require branches to be up to date before merging**: ✅
  - **Required status checks**:
    - `ci / CI Success` (includes RC nightly tests for release branches)
    - `validate-pr / Validate PR` (from conventional-labels.yml)
- **Require conversation resolution before merging**: ✅
- **Require signed commits**: ✅ (Recommended)
- **Include administrators**: ✅ (Apply rules to admins)

### 2. Repository Settings
- **Allow squash merging**: ✅ (Required for RC branches)
- **Allow merge commits**: ❌ (Disable for RC branches)  
- **Allow rebase merging**: ❌ (Disable for RC branches)
- **Default merge type**: Squash and merge
- **Delete head branches**: ✅ (Recommended)

## Automated Label Requirements

RC branch PRs will be automatically labeled with:
- `type:release` - Applied automatically by the `add-labels.yml` workflow
- Manual labels may be required based on PR content

## CI Requirements

RC branches trigger enhanced CI pipeline:
1. **Standard CI tests** (same as main branch):
   - Backend tests (Python unit tests)
   - Frontend unit tests  
   - Linting and code quality checks
   - Template tests (if modified)
   - Documentation build tests

2. **RC-specific comprehensive tests** (integrated into main CI):
   - Frontend tests (full suite with release=true)
   - Backend tests (all Python versions: 3.10, 3.11, 3.12, 3.13)
   - Integration tests (with API keys)
   - **These run as part of the main CI workflow, not separately**

3. **Optional tests**:
   - Smoke tests (with smoke-test label)

## Important Notes

- **Nightly builds are disabled** on release branches to prevent accidental releases
- **RC nightly tests are integrated** into the main CI workflow for release branches
- **CI Success depends on** both standard tests AND comprehensive RC tests passing

## Implementation Steps

### Via GitHub Web Interface:
1. Go to Repository Settings → Branches
2. Click "Add rule" 
3. Enter branch name pattern: `release-*`
4. Configure all the protection rules listed above
5. Save the rule

### Via GitHub CLI:
```bash
gh api repos/{owner}/{repo}/branches/release-*/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["ci / CI Success","rc-tests-success / RC Tests Success","validate-pr / Validate PR"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true,"require_code_owner_reviews":true}' \
  --field restrictions=null
```

### Repository Settings via Web Interface:
1. Go to Repository Settings → General
2. Under "Pull Requests" section:
   - ✅ Allow squash merging
   - ❌ Allow merge commits  
   - ❌ Allow rebase merging
3. Set "Default merge type" to "Squash and merge"

## Validation

To verify the configuration is working:

1. **Create a test RC branch**: `release-test-config`
2. **Open a PR** against the RC branch
3. **Verify automatic labeling**: PR should get `type:release` label
4. **Verify CI execution**: Full CI and RC nightly tests should run
5. **Verify merge restrictions**: Only squash & merge should be available
6. **Verify protection**: PR should require approval and passing status checks

## Troubleshooting

### CI not running on RC PRs:
- Ensure PR has `type:release` label (should be automatic)
- Check that the RC branch follows `release-*` naming pattern
- Verify the CI condition logic in `.github/workflows/ci.yml`

### Merge button not showing squash option:
- Check repository settings for allowed merge types
- Verify branch protection rules are applied to the pattern

### Tests not comprehensive enough:
- RC branches run the new `rc-nightly-tests.yml` workflow
- This includes full frontend, backend, and integration test suites
- Check workflow logs for any skipped tests