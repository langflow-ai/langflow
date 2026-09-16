# Release Branch Protection Automation

## Overview

This document describes the automated branch protection setup for release branches in the Langflow repository.

## Problem Statement

GitHub's branch protection rules do not support wildcard patterns (e.g., `release-*`) when merge queues are enabled. This limitation requires manual configuration of protection rules for each new release branch, which is error-prone and time-consuming.

**Reference:** [GitHub Community Discussion #154383](https://github.com/orgs/community/discussions/154383#discussioncomment-13352281)

## Solution

We've implemented a GitHub Action workflow that automatically detects when a new release branch is created and applies the appropriate branch protection rules.

### Workflow: `setup-release-branch-protection.yml`

**Trigger:** Automatically runs when a branch matching the pattern `release-*` is created.

**Permissions Required:**
- `contents: read` - To access repository information
- `administration: write` - To modify branch protection settings

### Branch Protection Rules Applied

When a release branch is created, the following protection rules are automatically configured:

#### Required Status Checks
- **Strict mode enabled** - Branch must be up to date before merging
- **Required checks:**
  - CI / Run Unit Tests
  - CI / Run Integration Tests
  - CI / Lint Backend
  - CI / Lint Frontend
  - CI / Type Check

#### Pull Request Reviews
- **Required approving reviews:** 2
- **Code owner reviews required:** Yes
- **Dismiss stale reviews:** Yes
- **Require last push approval:** Yes

#### Additional Protections
- **Conversation resolution required:** Yes
- **Force pushes:** Blocked
- **Branch deletion:** Blocked
- **Linear history:** Not required (allows merge commits)

#### Merge Queue (Optional)
- **Enabled:** If supported by repository settings
- **Merge method:** Squash
- **Timeout:** 60 minutes
- **Grouping strategy:** ALLGREEN

## Usage

### Automatic Setup

1. Create a new release branch following the naming convention:
   ```bash
   git checkout -b release-1.11.0
   git push origin release-1.11.0
   ```

2. The workflow will automatically trigger and apply protection rules within a few seconds.

3. Check the Actions tab to verify successful execution.

### Manual Verification

To verify the protection rules were applied:

1. Navigate to: `Settings` → `Branches` → `Branch protection rules`
2. Find the rule for your release branch (e.g., `release-1.11.0`)
3. Verify all settings match the configuration above

## Troubleshooting

### Workflow Fails with Permission Error

**Symptom:** Workflow fails with "Resource not accessible by integration" error.

**Solution:** Ensure the repository has the following settings:
- Go to `Settings` → `Actions` → `General`
- Under "Workflow permissions", select "Read and write permissions"
- Enable "Allow GitHub Actions to create and approve pull requests"

### Merge Queue Not Enabled

**Symptom:** Workflow completes but merge queue is not enabled.

**Reason:** Merge queues require:
- GitHub Enterprise Cloud or GitHub Enterprise Server
- Repository admin permissions
- Specific repository settings

**Action:** This is expected behavior for repositories without merge queue support. All other protection rules will still be applied.

### Status Check Names Don't Match

**Symptom:** Required status checks don't appear or PRs can't be merged.

**Solution:** Update the status check names in the workflow file to match your CI/CD pipeline:

```yaml
contexts: [
  'CI / Run Unit Tests',
  'CI / Run Integration Tests',
  # Add or modify check names here
]
```

## Maintenance

### Updating Protection Rules

To modify the default protection rules for future release branches:

1. Edit `.github/workflows/setup-release-branch-protection.yml`
2. Update the `updateBranchProtection` parameters
3. Commit and push changes
4. New release branches will use the updated configuration

### Testing Changes

To test workflow changes without creating a real release branch:

1. Create a test branch: `git checkout -b release-test-1.0.0`
2. Push to trigger the workflow
3. Verify the protection rules
4. Delete the test branch when done

## Security Considerations

- The workflow uses `GITHUB_TOKEN` which has limited permissions
- Admin permissions are only used for branch protection configuration
- No sensitive data is exposed in workflow logs
- Protection rules prevent unauthorized force pushes and deletions

## Related Documentation

- [GitHub Branch Protection Rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Actions Permissions](https://docs.github.com/en/actions/security-guides/automatic-token-authentication#permissions-for-the-github_token)
- [Merge Queues Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)