# Langflow Message Flow Architecture

## Overview

This document explains how messages are created, stored, fetched, and displayed in Langflow.

---

## 1. Message Storage: Two Modes

### Mode A: Playground Mode (sessionStorage)

- **When**: Testing flows in the playground without saving to database
- **Storage**: Browser's `sessionStorage`
- **Key**: `flow_id`
- **Value**: Array of message objects
- **Persistence**: Lost when browser tab closes
- **Location**: `use-get-messages.ts` checks sessionStorage first

### Mode B: Production Mode (PostgreSQL Database)

- **When**: Running flows in production or when explicitly saving
- **Storage**: PostgreSQL database via backend API
- **Table**: `message` table
- **Persistence**: Permanent until deleted
- **Location**: Backend at `src/backend/base/langflow/services/database/models/message/model.py`

---

## 2. Message Creation Flow

### Step 1: User Sends Message

**File**: `src/frontend/src/components/core/playgroundComponent/chat-view/chat-input/`

1. User types in chat input
2. Message is created with:
   - `id`: UUID
   - `text`: User's message
   - `sender`: "User"
   - `sender_name`: User's name
   - `session_id`: Current session ID
   - `flow_id`: Current flow ID
   - `timestamp`: Current time

### Step 2: Message Saved to Storage

**File**: `src/frontend/src/stores/messagesStore.ts` or direct API call

**Playground Mode**:

```javascript
// Save to sessionStorage
const messages = JSON.parse(sessionStorage.getItem(flow_id) || "[]");
messages.push(newMessage);
sessionStorage.setItem(flow_id, JSON.stringify(messages));
```

**Production Mode**:

```javascript
// POST to backend API
POST / api / v1 / monitor / messages;
Body: {
  message: newMessage;
}
```

### Step 3: AI Response Generated

**Backend**: Flow execution creates AI response

1. Flow processes user message
2. AI generates response
3. Response streamed back to frontend
4. Message object created with:
   - `sender`: "Machine"
   - `text`: AI response
   - `content_blocks`: Tool calls, thinking steps, etc.

### Step 4: AI Message Saved

Same as Step 2, but for AI message

---

## 3. Message Fetching Flow (On Page Load)

### Entry Point: `use-chat-history.ts`

**File**: `src/frontend/src/components/core/playgroundComponent/chat-view/chat-messages/hooks/use-chat-history.ts`

```
Page Load
    ↓
use-chat-history.ts
    ↓
useGetMessagesQuery() ← Calls use-get-messages.ts
    ↓
Checks sessionStorage first
    ↓
If found → Return from sessionStorage
If not found → Fetch from backend API
    ↓
Messages stored in React Query cache
    ↓
Messages displayed in chat
```

### Detailed Flow:

#### Step 1: Check sessionStorage

**File**: `src/frontend/src/controllers/API/queries/messages/use-get-messages.ts`

```javascript
// Check if messages exist in sessionStorage
const storageKey = id; // flow_id
const storedMessages = sessionStorage.getItem(storageKey);

if (storedMessages) {
  // Return messages from sessionStorage (Playground Mode)
  return JSON.parse(storedMessages);
}
```

#### Step 2: Fetch from Backend (if not in sessionStorage)

```javascript
// GET request to backend
GET /api/v1/monitor/messages?flow_id={flow_id}

// Backend queries PostgreSQL
SELECT * FROM message WHERE flow_id = {flow_id}
```

#### Step 3: Store in React Query Cache

**File**: `use-chat-history.ts`

```javascript
// React Query automatically caches the result
const sessionCacheKey = [
  "useGetMessagesQuery",
  { id: currentFlowId, session_id: visibleSession }
];

// Cache structure:
{
  "useGetMessagesQuery": {
    "id": "flow-123",
    "session_id": "session-456"
  }: [
    { id: "msg-1", text: "Hello", sender: "User", ... },
    { id: "msg-2", text: "Hi!", sender: "Machine", ... }
  ]
}
```

#### Step 4: Transform and Display

**File**: `use-chat-history.ts` → `messages.tsx` → `bot-message.tsx`

```javascript
// Transform Message → ChatMessageType
const chatHistory = messages.map((message) => ({
  isSend: message.sender === "User",
  message: message.text,
  sender_name: message.sender_name,
  files: message.files,
  id: message.id,
  timestamp: message.timestamp,
  session: message.session_id,
  flow_id: message.flow_id,
  content_blocks: message.content_blocks,
  properties: message.properties,
  // ... other fields
}));
```

---

## 4. React Query Cache: The Single Source of Truth

### What is React Query Cache?

- In-memory storage managed by `@tanstack/react-query`
- Stores fetched data with keys
- Automatically updates UI when cache changes
- Survives component re-renders but NOT page reloads

### Cache Key Structure:

```javascript
[
  "useGetMessagesQuery",
  {
    id: "flow_id",
    session_id: "session_id",
  },
];
```

### How to Update Cache:

```javascript
const queryClient = useQueryClient();

// Get current data
const messages = queryClient.getQueryData(cacheKey);

// Update data
const updatedMessages = messages.map((msg) =>
  msg.id === targetId ? { ...msg, text: newText } : msg,
);

// Set new data (triggers re-render)
queryClient.setQueryData(cacheKey, updatedMessages);
```

---

## 5. Message Update Flow

### Updating Message Text (e.g., Edit)

**File**: `src/frontend/src/controllers/API/queries/messages/use-put-update-messages.ts`

```
User edits message
    ↓
updateMessageMutation() called
    ↓
Update React Query cache (immediate UI update)
    ↓
PUT /api/v1/monitor/messages/{message_id}
    ↓
Backend updates database
    ↓
Success → Cache stays updated
Error → Rollback cache
```

### Code Example:

```javascript
const { mutate: updateMessageMutation } = useUpdateMessage();

updateMessageMutation({
  message: {
    id: messageId,
    text: newText,
    // ... other fields
  },
  refetch: false, // Don't refetch, trust cache update
});
```

---

## 6. Key Files Reference

### Frontend - Data Fetching:

1. **`use-get-messages.ts`**: Fetches messages (checks sessionStorage → backend)
2. **`use-chat-history.ts`**: Manages React Query cache, transforms messages
3. **`messagesStore.ts`**: Zustand store for message state

### Frontend - Display:

4. **`messages.tsx`**: Renders list of messages
5. **`bot-message.tsx`**: Renders individual AI message
6. **`user-message.tsx`**: Renders individual user message

### Frontend - Updates:

7. **`use-put-update-messages.ts`**: Updates message via API
8. **`use-post-messages.ts`**: Creates new message via API

### Backend - Database:

9. **`model.py`**: SQLModel definition for `message` table
10. **`monitor.py`**: API endpoints for message CRUD operations

---

## 7. Debugging Tips

### Check sessionStorage:

```javascript
// In browser console
const flowId = "your-flow-id";
const messages = JSON.parse(sessionStorage.getItem(flowId) || "[]");
console.log(messages);
```

### Check React Query Cache:

```javascript
// In browser console (with React DevTools)
// Or add this in your component:
const queryClient = useQueryClient();
const cache = queryClient.getQueryData([
  "useGetMessagesQuery",
  { id: flowId, session_id: sessionId },
]);
console.log(cache);
```

### Check Backend Database:

```sql
-- In PostgreSQL
SELECT * FROM message WHERE flow_id = 'your-flow-id';
```

### Add Debug Logs:

```javascript
// In use-chat-history.ts
useEffect(() => {
  console.log("📦 Messages from cache:", sessionMessages);
}, [sessionMessages]);

// In use-get-messages.ts
console.log("🔍 Checking sessionStorage for:", id);
console.log("🔍 Found in sessionStorage:", storedMessages);
```

---

## 8. Common Scenarios

### Scenario 1: Message Appears Then Disappears on Reload

**Cause**: Message saved to React Query cache but not persisted to storage
**Solution**: Ensure message is saved to sessionStorage OR backend database

### Scenario 2: Message Doesn't Update in UI

**Cause**: React Query cache not updated after mutation
**Solution**: Update cache manually with `queryClient.setQueryData()`

### Scenario 3: Duplicate Messages

**Cause**: Message saved to both sessionStorage and database
**Solution**: Check `use-get-messages.ts` logic - should prioritize one source

### Scenario 4: Messages Lost on Refresh

**Cause**: Only in React Query cache, not persisted
**Solution**: Save to sessionStorage (playground) or database (production)

---

## 9. Duration Persistence Challenge

### Current Issue:

Duration is tracked in memory (`useMessageDuration` hook) but not persisted.

### Why It Resets:

1. Duration stored in React state (lost on unmount)
2. Not saved to message object in storage
3. On reload, duration starts from 0

### Solution Approach:

1. Add `duration` field to message object
2. Save duration when AI response completes
3. Load duration from persisted message on reload
4. Pass to `useMessageDuration` hook as initial value

### Implementation:

```javascript
// When AI completes
const handleDurationFreeze = (duration) => {
  // Update message in cache
  const messages = queryClient.getQueryData(cacheKey);
  const updated = messages.map((msg) =>
    msg.id === chatId ? { ...msg, duration } : msg,
  );
  queryClient.setQueryData(cacheKey, updated);

  // Save to storage (sessionStorage or backend)
  if (inPlaygroundMode) {
    sessionStorage.setItem(flowId, JSON.stringify(updated));
  } else {
    updateMessageAPI({ id: chatId, duration });
  }
};

// On load
const { displayTime } = useMessageDuration({
  chatId,
  lastMessage,
  isBuilding,
  savedDuration: chat.duration, // Load from persisted message
});
```

---

## 10. Next Steps for Investigation

To understand your specific setup:

1. **Check which mode you're in**:

   ```javascript
   // Add to bot-message.tsx
   console.log("Storage check:", {
     sessionStorage: sessionStorage.getItem(flow_id),
     playgroundPage: playgroundPage,
   });
   ```

2. **Trace message creation**:
   - Set breakpoint in chat input component
   - Follow message through stores/API
   - See where it's saved

3. **Trace message loading**:
   - Set breakpoint in `use-get-messages.ts`
   - See if it loads from sessionStorage or API
   - Check React Query cache contents

4. **Check database**:
   - Query `message` table directly
   - See if messages are actually saved
   - Check if `duration` column exists (it doesn't yet!)

Would you like me to add specific debug code to trace the flow in your application?
