# Core Rules for ALL Langflow Agents

## Version: 2.0.0
## Updated: 2025-08-22

## 🚨 CRITICAL RULES - APPLY TO ALL AGENTS

### 1. GitHub CLI Usage
All agents MUST use `gh` CLI for verification:
```bash
# Available commands:
gh issue view/list --repo langflow-ai/langflow
gh pr view/list --repo langflow-ai/langflow
gh release list --repo langflow-ai/langflow
gh api repos/langflow-ai/langflow/[endpoint]
```

### 2. Version Awareness
- **Current Version**: Dynamically check, don't hardcode
- **Check Methods**:
  1. `gh release view --repo langflow-ai/langflow`
  2. `/src/backend/langflow/version/version.py`
  3. `git describe --tags`

### 3. No Assumptions Policy

#### ❌ NEVER SAY:
- "This will be in version X.Y.Z"
- "The next release will include..."
- "The team plans to..."
- "This should be released soon"
- "Version 1.6 will have this feature"

#### ✅ ALWAYS SAY:
- "This fix is in PR #XXXX (merged on DATE)"
- "Currently in main branch, not yet released"
- "Latest release is X.Y.Z (verified via gh)"
- "Based on the codebase analysis..."
- "According to merged PRs..."

### 4. Fact Verification Protocol

Before making ANY claim:
```python
VERIFY_CHECKLIST = {
    "issue_exists": "gh issue view",
    "pr_status": "gh pr view",
    "in_release": "git tag --contains",
    "current_version": "gh release view",
    "code_exists": "grep/read actual files"
}
```

### 5. Response Framework

```markdown
## [Topic]

### Verified Facts
- Source: [gh command or file]
- Status: [factual state]
- Evidence: [PR/Issue/Commit]

### Current State
- Released Version: [from gh]
- Main Branch: [from git]
- Your Version: [from context]

### [Solution/Analysis]
[Based only on verified information]
```

### 6. Langflow-Specific Context

- **Repository**: `langflow-ai/langflow`
- **Primary Language**: Python
- **Frontend**: React + TypeScript
- **Backend**: FastAPI
- **Database**: PostgreSQL with SQLModel
- **Current Released Version**: CHECK DYNAMICALLY
- **Issue Tracker**: GitHub Issues

### 7. Error Handling

When encountering errors or uncertainties:
1. State what you CAN verify
2. Explain what you CANNOT determine
3. Provide workarounds for current version
4. Never speculate on fixes or timelines

### 8. Testing Claims

Before stating something works:
1. Check if tests exist: `gh pr view --json files | grep test`
2. Look for regression issues: `gh issue list --search regression`
3. Verify in codebase: Read actual implementation

### 9. Documentation References

Always check and reference:
- `/docs/` directory
- `README.md`
- `CONTRIBUTING.md`
- Inline code comments
- Issue discussions

### 10. Communication Standards

- Be precise with version numbers
- Include verification commands used
- Link to PRs/Issues when referenced
- Timestamp observations ("as of DATE")
- Clarify main branch vs release status

## Example Correct Agent Response

```markdown
Based on my analysis using GitHub CLI and codebase inspection:

**Verified Information:**
- Current Release: 1.5.0.post2 (via `gh release view`)
- Issue #9024: OPEN status (via `gh issue view 9024`)
- Fix PR #9393: MERGED on 2025-08-20 (via `gh pr view 9393`)
- Fix Status: In main branch, not in current release

**Solution for your version (1.5.0.post2):**
[Specific workaround that works now]

**Note:** The fix is available in the main branch. Monitor releases via:
`gh release list --repo langflow-ai/langflow --limit 1`
```

## Enforcement

These rules are MANDATORY for all agents:
- langflow-analyzer
- langflow-dev-fixer
- langflow-dev-planner
- langflow-dev-designer
- langflow-dev-coder
- langflow-clone
- langflow-agent-creator
- langflow-agent-enhancer
- langflow-claudemd

Violation of these rules should trigger immediate agent behavior correction.