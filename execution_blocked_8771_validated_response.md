# Response for Issue #8771: "Execution Blocked" Indicator Bug

Hi @reidab,

Thank you for this detailed bug report about the "Execution Blocked" indicator behavior in If-Else components. I've analyzed the issue and can confirm your root cause analysis and solution are completely accurate.

## Issue Confirmed

You've identified a legitimate UI bug where timing information incorrectly persists when nodes become inactive, preventing the "Execution Blocked ø" indicator from reappearing. This affects the user experience in conditional flows.

## Root Cause Validated

Your analysis is spot-on. The issue is in the `NodeStatus` component (`src/frontend/src/CustomNodes/GenericNode/components/NodeStatus/index.tsx`, lines 408-413):

```typescript
{conditionSuccess && validationStatus?.data?.duration ? (
  <div className="flex rounded-sm px-1 font-mono text-xs text-accent-emerald-foreground transition-colors hover:bg-accent-emerald">
    <span>
      {normalizeTimeString(validationStatus?.data?.duration)}
    </span>
  </div>
) : (
  <div className="flex items-center self-center">
    {iconStatus}
  </div>
)}
```

**The Problem**: `conditionSuccess` is defined as:
```typescript
const conditionSuccess =
  buildStatus === BuildStatus.BUILT ||
  (buildStatus !== BuildStatus.TO_BUILD && validationStatus?.valid);
```

When `buildStatus` is `INACTIVE` (blocked), the second condition `(buildStatus !== BuildStatus.TO_BUILD && validationStatus?.valid)` can still be `true` if the node has `validationStatus?.valid = true` from a previous successful execution. This causes timing information to display instead of the blocked indicator.

## Solution Verified

Your proposed fix is technically perfect:

```typescript
{conditionSuccess && validationStatus?.data?.duration && buildStatus !== BuildStatus.INACTIVE ? (
  // Show timing
) : (
  // Show status icon (including "Execution Blocked ø")
)}
```

This ensures that:
1. **Blocked nodes show blocked status**: When `buildStatus === BuildStatus.INACTIVE`, timing is hidden
2. **Valid nodes show timing**: When not blocked and timing exists, timing is displayed
3. **Consistent behavior**: Matches user expectations for conditional flow visualization

## Implementation Details

**Current Logic Issue**:
- The code already defines `conditionInactive = buildStatus === BuildStatus.INACTIVE`
- However, this isn't used in the timing display condition
- Only `conditionSuccess` is checked, which can be true for inactive nodes with prior validation

**Your Fix**:
- Adds explicit check for `buildStatus !== BuildStatus.INACTIVE`
- Prevents timing display on blocked nodes regardless of previous validation status
- Maintains all existing functionality for active nodes

## Additional Context

As you noted in your follow-up comment, the "Execution Blocked" status currently appears on hover, but the visual indicator (ø icon) doesn't show because timing takes precedence. Your fix addresses this by ensuring blocked nodes always show the appropriate visual state.

dosubot's analysis in the comments confirms the same component locations and approach, validating that this is the correct place for the fix.

## Technical Impact

This is a straightforward frontend fix that:
- Requires only a one-line condition addition
- Improves UX by providing accurate visual feedback
- Maintains backward compatibility
- Follows existing code patterns (`conditionInactive` is already defined)

Your analysis demonstrates excellent understanding of the component architecture and the specific timing vs. status display logic causing this issue.

Would you like to implement this fix, or do you need any additional technical details about the implementation?

Best regards,
Langflow Support