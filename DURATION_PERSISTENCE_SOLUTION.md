# Duration Persistence Solution Using Content Blocks

## Problem

The "Thought for X.Xs" duration resets to 0.0s on page reload because it's only tracked in React state, not persisted.

## Solution

Use the **existing** `content_blocks` structure to store the thinking duration. Each content block already has a `duration` field in `BaseContent`.

---

## Architecture Overview

### Backend Structure (Already Exists!)

```python
# src/backend/base/langflow/schema/content_types.py

class BaseContent(BaseModel):
    type: str
    duration: int | None = None  # ← Already exists!
    header: HeaderDict | None = None

class TextContent(BaseContent):
    type: Literal["text"] = "text"
    text: str
    duration: int | None = None  # ← Already exists!
```

### Frontend Structure (Already Exists!)

```typescript
// src/frontend/src/types/chat/index.ts

export interface BaseContent {
  type: string;
  duration?: number; // ← Already exists!
  header?: { title?: string; icon?: string };
}

export interface TextContent extends BaseContent {
  type: "text";
  text: string;
  duration?: number; // ← Already exists!
}
```

---

## Current Flow

### 1. Message Structure

```typescript
{
  id: "msg-123",
  text: "AI response text",
  sender: "Machine",
  content_blocks: [
    {
      title: "Thinking",
      contents: [
        {
          type: "text",
          text: "Thinking process...",
          duration: 1234  // ← This is where duration should be stored!
        }
      ]
    },
    {
      title: "Tools",
      contents: [
        {
          type: "tool_use",
          name: "search",
          duration: 567  // ← Tool durations already work!
        }
      ]
    }
  ]
}
```

### 2. How Tool Durations Work (Already Implemented)

The `use-tool-durations.ts` hook:

- Extracts tool content blocks
- Reads `content.duration` from each tool
- Sums them up for total tool duration
- **This already persists across reloads!**

### 3. How Thinking Duration Should Work (To Be Implemented)

Similar to tool durations:

- Extract "thinking" content block
- Read `duration` from the text content
- Use it as the thinking duration
- **Will persist across reloads!**

---

## Implementation Plan

### Step 1: Find or Create Thinking Content Block

When AI response completes, we need to:

1. Find the "thinking" content block (or create one)
2. Set its `duration` field
3. Save the updated message

### Step 2: Load Duration from Content Block

On page load:

1. Check if message has a "thinking" content block
2. Extract its `duration`
3. Use it as the initial value for `useMessageDuration`

---

## Code Changes Needed

### Change 1: Update `useMessageDuration` Hook

**File**: `src/frontend/src/components/core/playgroundComponent/chat-view/chat-messages/hooks/use-message-duration.ts`

```typescript
interface UseMessageDurationProps {
  chatId: string;
  lastMessage: boolean;
  isBuilding: boolean;
  savedDuration?: number; // ← Load from content_blocks
  onDurationFreeze?: (duration: number) => void; // ← Callback to save
}

export function useMessageDuration({
  chatId,
  lastMessage,
  isBuilding,
  savedDuration,
  onDurationFreeze,
}: UseMessageDurationProps) {
  // Initialize with saved duration if available
  const [elapsedTime, setElapsedTime] = useState(savedDuration || 0);
  const frozenDurationRef = useRef<number | null>(savedDuration || null);

  // ... rest of the logic

  // When duration freezes, call the callback
  if (finalDuration > 0 && onDurationFreeze) {
    onDurationFreeze(finalDuration);
  }
}
```

### Change 2: Extract Thinking Duration from Content Blocks

**File**: `src/frontend/src/components/core/playgroundComponent/chat-view/chat-messages/components/bot-message.tsx`

```typescript
// Helper function to get thinking duration from content blocks
const getThinkingDuration = (
  contentBlocks?: ContentBlock[],
): number | undefined => {
  if (!contentBlocks) return undefined;

  // Find the "thinking" or first text content block
  for (const block of contentBlocks) {
    for (const content of block.contents) {
      if (content.type === "text" && content.duration) {
        return content.duration;
      }
    }
  }
  return undefined;
};

// In component
const savedThinkingDuration = getThinkingDuration(chat.content_blocks);

const { displayTime } = useMessageDuration({
  chatId: chat.id,
  lastMessage,
  isBuilding,
  savedDuration: savedThinkingDuration, // ← Load from content blocks
  onDurationFreeze: handleSaveThinkingDuration, // ← Save to content blocks
});
```

### Change 3: Save Thinking Duration to Content Blocks

**File**: `src/frontend/src/components/core/playgroundComponent/chat-view/chat-messages/components/bot-message.tsx`

```typescript
const handleSaveThinkingDuration = useCallback(
  (duration: number) => {
    // Update content_blocks with thinking duration
    const updatedContentBlocks = chat.content_blocks
      ? [...chat.content_blocks]
      : [];

    // Find or create thinking content block
    let thinkingBlockIndex = updatedContentBlocks.findIndex((block) =>
      block.contents.some((c) => c.type === "text"),
    );

    if (thinkingBlockIndex === -1) {
      // Create new thinking block
      updatedContentBlocks.unshift({
        title: "Thinking",
        contents: [
          {
            type: "text",
            text: "",
            duration: duration,
          },
        ],
      });
    } else {
      // Update existing thinking block
      const block = updatedContentBlocks[thinkingBlockIndex];
      const textContentIndex = block.contents.findIndex(
        (c) => c.type === "text",
      );

      if (textContentIndex !== -1) {
        block.contents[textContentIndex] = {
          ...block.contents[textContentIndex],
          duration: duration,
        };
      }
    }

    // Save updated message with new content_blocks
    updateMessageMutation({
      message: {
        id: chat.id,
        files: convertFiles(chat.files),
        sender_name: chat.sender_name ?? "AI",
        text: chat.message.toString(),
        sender: "Machine",
        flow_id,
        session_id: chat.session ?? "",
        content_blocks: updatedContentBlocks, // ← Updated with duration
        properties: chat.properties as any,
      },
      refetch: false,
    });
  },
  [chat, flow_id, updateMessageMutation],
);
```

---

## Why This Solution is Better

### ✅ No Database Migration Needed

- Uses existing `content_blocks` structure
- `duration` field already exists in `BaseContent`
- No schema changes required

### ✅ Consistent with Existing Architecture

- Tool durations already work this way
- Same pattern for thinking duration
- Follows established conventions

### ✅ Works in Both Modes

- Playground mode: content_blocks saved to sessionStorage
- Production mode: content_blocks saved to database
- No special handling needed

### ✅ Backward Compatible

- Old messages without duration still work
- New messages get duration automatically
- No breaking changes

---

## Testing Plan

### Test 1: Duration Persists on Reload

1. Send a message
2. Wait for "Thought for X.Xs" to appear
3. Refresh the page
4. ✅ Duration should still show X.Xs (not 0.0s)

### Test 2: Duration Saved to Storage

1. Send a message
2. Wait for response
3. Check content_blocks in:
   - sessionStorage (playground mode)
   - Database (production mode)
4. ✅ Should see `duration` field in text content

### Test 3: Multiple Messages

1. Send multiple messages
2. Each should have its own duration
3. Refresh page
4. ✅ All durations should persist independently

### Test 4: Backward Compatibility

1. Load old messages (without duration)
2. ✅ Should show "Thought for 0.0s" (not crash)
3. Send new message
4. ✅ New message should have duration

---

## Debug Steps

### 1. Check if content_blocks exist

```javascript
console.log("Content blocks:", chat.content_blocks);
```

### 2. Check if duration is being saved

```javascript
console.log("Saving duration to content_blocks:", duration);
console.log("Updated content_blocks:", updatedContentBlocks);
```

### 3. Check if duration is being loaded

```javascript
const savedDuration = getThinkingDuration(chat.content_blocks);
console.log("Loaded thinking duration:", savedDuration);
```

### 4. Check backend response

```javascript
// In use-get-messages.ts
console.log("Messages from backend:", messages);
console.log("Content blocks:", messages[0]?.content_blocks);
```

---

## Next Steps

1. ✅ Understand the architecture (Done - you're here!)
2. ⏳ Implement `getThinkingDuration` helper
3. ⏳ Update `useMessageDuration` to accept `savedDuration`
4. ⏳ Implement `handleSaveThinkingDuration` callback
5. ⏳ Test in playground mode
6. ⏳ Test in production mode
7. ⏳ Test backward compatibility

---

## Questions to Answer

### Q: Where exactly is the thinking duration stored?

A: In `content_blocks[].contents[].duration` where `type === "text"`

### Q: Do we need to modify the database?

A: No! The `content_blocks` column already exists and stores JSON

### Q: Will this work for old messages?

A: Yes! Old messages without duration will show 0.0s, new messages will persist

### Q: How is this different from tool durations?

A: Same pattern! Tools use `type === "tool_use"`, thinking uses `type === "text"`

### Q: What if there are multiple text content blocks?

A: Use the first one, or create a specific "thinking" block with a title

---

## Alternative: Use Message Properties

If content_blocks approach doesn't work, we could use `message.properties`:

```typescript
// Save
properties: {
  ...chat.properties,
  thinking_duration: duration  // ← Add custom property
}

// Load
const savedDuration = chat.properties?.thinking_duration;
```

But content_blocks is the recommended approach since it's more structured.
