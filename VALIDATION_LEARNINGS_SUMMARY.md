# Key Validation Learnings for Development Agents

## 🎯 Core Principles Learned

### 1. **Always Verify Primary Sources**
- ❌ Never trust issue descriptions or user reports alone
- ✅ Always check actual code, PR diffs, and GitHub API responses
- ✅ Use `gh pr view`, `gh issue view`, `Read`, `Grep` to verify claims

### 2. **Distinguish Facts from Speculation**
- ❌ "This issue was fixed in version X" (without verification)  
- ✅ "PR #1234 was merged on date X, but no release includes it yet"
- ✅ State only what can be directly observed in code/GitHub

### 3. **Validate Technical Claims Against Codebase**
- ❌ User says "completion_tokens causes error" 
- ✅ Check actual code - Anthropic uses "output_tokens" not "completion_tokens"
- ✅ Find exact line numbers and implementation details

### 4. **Check Timeline Consistency** 
- ❌ "Fixed in May 25, 2025" when issue created March 12, 2025
- ✅ Verify dates: release dates, PR merge dates, issue creation dates
- ✅ Ensure chronological sequence makes sense

### 5. **Verify PR Status Thoroughly**
- ❌ "Fixed in PR #123" (check if actually merged!)
- ✅ Check `mergedAt` field - `null` means closed but not merged
- ✅ Distinguish between closed and merged PRs

### 6. **Include Real Community Feedback**
- ❌ "Based on Discord discussions" (unverifiable)
- ✅ Quote actual GitHub comments with author attribution
- ✅ Use `gh api repos/owner/repo/issues/N/comments` to get real quotes

### 7. **Acknowledge Uncertainty Explicitly**
- ❌ Guessing or making confident claims without evidence
- ✅ "I cannot verify this claim in the current codebase"
- ✅ "The PR title suggests X, but I need to check the actual diff"

### 8. **Provide Concrete Evidence**
- ✅ File paths with line numbers: `src/file.py:123`
- ✅ Exact function signatures and configurations
- ✅ Commands others can run to verify claims
- ✅ Screenshots of actual code or API responses

## 🛠️ Essential Verification Tools

### GitHub CLI Commands
```bash
gh issue view NUMBER --repo owner/repo
gh pr view NUMBER --repo owner/repo  
gh pr diff NUMBER --repo owner/repo
gh api repos/owner/repo/issues/N/comments
gh release list --repo owner/repo
```

### Codebase Analysis
```bash
Read file_path  # Check actual implementation
Grep "pattern" # Find code patterns
Glob "**/*.py" # Find relevant files
```

### Verification Workflow
1. **Verify existence**: Does issue/PR exist?
2. **Check status**: Open/closed/merged status
3. **Analyze content**: What was actually changed/requested?
4. **Cross-reference**: Does code match claims?
5. **Timeline check**: Do dates make sense?
6. **Community input**: What do actual users say?

## 🚫 Common Pitfalls Avoided

1. **Assuming PR titles match implementation**
2. **Confusing closed with merged PRs** 
3. **Mixing API terminologies** (OpenAI vs Anthropic)
4. **Speculating about team decisions or timelines**
5. **Not checking if "fixes" actually work**
6. **Making version-specific claims without verification**

## ✅ Success Indicators

- **90%+ claims backed by evidence**
- **Zero hallucinations or speculation**
- **Specific file paths and line numbers provided**
- **Real community quotes with attribution**
- **Honest acknowledgment of uncertainties**
- **Reproducible verification steps**

This methodology ensures agents provide accurate, evidence-based support while maintaining helpful and proactive assistance.