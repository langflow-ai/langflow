# MCP Duplicate Output Issue #9036 - Verified Response

## Issue Summary

**Reporter**: @sarabjitgandhi  
**Issue**: MCP tool called twice - duplicate output in MCP Inspector  
**Version**: Langflow 1.5.0 / User has 1.5.0.post2  
**Date**: July 14, 2025  

## Verified Facts

### Pull Request Status (Verified 2025-08-22)

**✅ PR #8918**: `fix: prevent message duplication in ProjectMCPServer and handle_call_tool`
- **Status**: MERGED on 2025-07-07 at 20:57:49Z
- **Commit**: fd92d16553
- **Included in**: 1.5.0, 1.5.0.post1, 1.5.0.post2
- **User has this fix**: YES

**⏳ PR #8834**: `fix: mcp duplicate output`  
- **Status**: OPEN (as of 2025-08-22)
- **Author**: @phact
- **Assignee**: @edwinjosechittilappilly
- **Auto-merge**: Enabled
- **Contains**: Comprehensive deduplication logic prioritizing results over messages

### Release Information (Verified)

- **Latest Release**: 1.5.0.post2 (published 2025-08-14T18:54:39Z)
- **User Version**: 1.5.0.post2 (latest available)
- **Next Version**: TBD (waiting for PR #8834 merge)

## Root Cause Analysis

### Technical Details

The duplicate output occurs because MCP Inspector processes both `results` and `messages` from tool responses:

1. **Current Implementation**: Processes both channels independently
2. **PR #8918 Fix**: Added deduplication using `processed_texts` set in `mcp_utils.py:233-238`
3. **PR #8834 Enhancement**: Prioritizes `results` over `messages`, only processing messages when no results exist

### Code Location

- **File**: `/src/backend/base/langflow/api/v1/mcp_utils.py`
- **Function**: `handle_call_tool()` lines 232-250
- **Logic**: Deduplication via `add_result()` helper function

## Current Status for User

### What's Fixed
- Basic message deduplication (PR #8918) ✅
- Single-source processing within components ✅

### What's Pending  
- Complete channel prioritization (PR #8834) ⏳
- Edge cases in result/message handling ⏳

## Response to User

Hi @sarabjitgandhi,

Your detailed bug report is excellent. Based on verified facts from the current codebase:

### Confirmed Facts:

**✅ PR #8918**: MERGED on 2025-07-07, included in your version 1.5.0.post2  
**⏳ PR #8834**: Currently OPEN, contains additional deduplication fixes  
**📅 Your Version**: 1.5.0.post2 (latest available) includes the first fix  

### Why You Still See Duplication:

You have the latest version with PR #8918's fix, but **PR #8834 is still pending** and contains the comprehensive solution for remaining duplication cases.

### Current Status:

- **Partial fix applied** in your version
- **Complete fix waiting** for PR #8834 to merge  
- Issue persists because the comprehensive fix hasn't been released yet

### Next Steps:

Monitor PR #8834 for merge status. Once merged, the next release will contain the complete fix.

Your analysis is correct - this is an MCP Inspector display issue, not your component code.

## Verification Commands Used

```bash
# Check PR status
gh pr view 8834 --repo langflow-ai/langflow
gh pr view 8918 --repo langflow-ai/langflow

# Check releases
gh release list --repo langflow-ai/langflow --limit 10

# Verify commits in releases
git tag --contains fd92d16553
git log --oneline fd92d16553
```

## Conclusion

The user's issue is legitimate. While a partial fix exists in their current version (1.5.0.post2), the comprehensive solution awaits PR #8834 merge. The user should continue monitoring the PR for resolution.