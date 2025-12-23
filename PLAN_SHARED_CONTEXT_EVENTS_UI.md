# Plan: SharedContext Events UI Display

## Overview

Add a UI component to display events from the SharedContext component, enabling users to visualize and debug multi-agent collaboration in their flows.

## Current State Analysis

### Backend: SharedContext Component
Location: `src/lfx/src/lfx/components/agent_blocks/shared_context.py`

The SharedContext component already tracks events via the `_record_event()` method:
```python
event = {
    "operation": operation,      # get, set, append, delete, keys, has_key
    "key": key or "",
    "namespace": self.namespace or "",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "component_id": self._id,
}
```
Events are stored in the graph context under `EVENTS_KEY = "shared_ctx:_events"`.

### Frontend: Existing Patterns
1. **ContentBlockDisplay** (`src/frontend/src/components/core/chatComponents/ContentBlockDisplay.tsx`)
   - Expandable blocks with header, icon, and duration
   - Uses Framer Motion for animations
   - Shows "partial" state during execution, "complete" when finished

2. **ContentDisplay** (`src/frontend/src/components/core/chatComponents/ContentDisplay.tsx`)
   - Handles content types: text, code, json, error, tool_use, media
   - Renders headers with icons and duration badges

3. **ContentType** schema (`src/frontend/src/types/chat/index.ts`)
   - Union of typed content interfaces
   - Each has `type`, optional `duration`, and optional `header`

## Proposed Solution

### Approach: New "shared_context" ContentType + Timeline Panel

Create a new content type for SharedContext events that integrates with the existing content block system, plus an optional dedicated timeline panel for detailed visualization.

### Part 1: Backend Changes

#### 1.1 Add SharedContextContent type
Location: `src/backend/base/langflow/schema/content_types.py`

```python
class SharedContextContent(BaseContent):
    """Content type for shared context events."""
    type: Literal["shared_context"] = "shared_context"
    events: list[dict]  # List of event dicts with operation, key, namespace, timestamp, component_id
```

#### 1.2 Emit events as ContentBlock
Location: `src/lfx/src/lfx/components/agent_blocks/shared_context.py`

Modify the SharedContext component to emit events as a ContentBlock when an aggregation operation is performed, or add a dedicated `emit_events()` method:

```python
def _emit_events_as_content_block(self) -> ContentBlock:
    """Create a ContentBlock with all recorded events for UI display."""
    events = self.get_events(self.ctx)
    return ContentBlock(
        title="Shared Context Activity",
        contents=[SharedContextContent(type="shared_context", events=events)]
    )
```

### Part 2: Frontend Changes

#### 2.1 Add SharedContextContent type
Location: `src/frontend/src/types/chat/index.ts`

```typescript
export interface SharedContextContent extends BaseContent {
  type: "shared_context";
  events: SharedContextEvent[];
}

export interface SharedContextEvent {
  operation: "get" | "set" | "append" | "delete" | "keys" | "has_key";
  key: string;
  namespace: string;
  timestamp: string;
  component_id: string;
}
```

Update the `ContentType` union:
```typescript
export type ContentType =
  | ErrorContent
  | TextContent
  | MediaContent
  | JSONContent
  | CodeContent
  | ToolContent
  | SharedContextContent;  // Add this
```

#### 2.2 Create SharedContextEventsDisplay component
Location: `src/frontend/src/components/core/chatComponents/SharedContextEventsDisplay.tsx`

New component to render shared context events as a timeline:

```tsx
interface SharedContextEventsDisplayProps {
  events: SharedContextEvent[];
}

export function SharedContextEventsDisplay({ events }: SharedContextEventsDisplayProps) {
  // Group events by namespace
  // Render as vertical timeline with:
  // - Colored operation badges (get=blue, set=green, append=yellow, delete=red)
  // - Key name
  // - Relative timestamp
  // - Component ID (collapsible)
}
```

**UI Design:**
```
┌─────────────────────────────────────────────────────────┐
│ 📊 Shared Context Activity                    ▼ Expand  │
├─────────────────────────────────────────────────────────┤
│ Timeline:                                               │
│                                                         │
│ ● SET   task_data          12:34:56    [PRFetcher]      │
│ │                                                       │
│ ● GET   task_data          12:34:58    [CodeReviewer]   │
│ │                                                       │
│ ● APPEND reviews           12:35:02    [CodeReviewer]   │
│ │                                                       │
│ ● GET   task_data          12:35:04    [TestReviewer]   │
│ │                                                       │
│ ● APPEND reviews           12:35:08    [TestReviewer]   │
│ │                                                       │
│ ● GET   reviews            12:35:10    [Aggregator]     │
│                                                         │
│ Summary: 2 sets, 2 appends, 3 gets                      │
└─────────────────────────────────────────────────────────┘
```

#### 2.3 Update ContentDisplay to handle new type
Location: `src/frontend/src/components/core/chatComponents/ContentDisplay.tsx`

Add case for "shared_context" type:
```tsx
case "shared_context":
  contentData = <SharedContextEventsDisplay events={content.events} />;
  break;
```

### Part 3: Optional Enhancements

#### 3.1 Dedicated Events Panel (Sidebar)
Location: `src/frontend/src/components/core/sharedContextPanel/`

For users who want persistent visibility into shared context activity:
- Floating panel on the canvas (like LogCanvasControls)
- Shows live events as they occur during flow execution
- Filterable by namespace and operation type

#### 3.2 Key-Value Inspector
Add ability to inspect current values in the shared context:
- Expandable tree view of all keys
- Shows current value for each key
- Real-time updates during execution

## File Changes Summary

### New Files
1. `src/backend/base/langflow/schema/content_types.py` - Add SharedContextContent class
2. `src/frontend/src/components/core/chatComponents/SharedContextEventsDisplay.tsx` - Events timeline component

### Modified Files
1. `src/lfx/src/lfx/components/agent_blocks/shared_context.py` - Emit events as ContentBlock
2. `src/frontend/src/types/chat/index.ts` - Add SharedContextContent interface
3. `src/frontend/src/components/core/chatComponents/ContentDisplay.tsx` - Handle shared_context type
4. `src/backend/base/langflow/schema/content_block.py` - Include SharedContextContent in ContentType union

## Implementation Order

1. **Phase 1: Types & Schema** (Backend + Frontend)
   - Add SharedContextContent to backend content types
   - Add SharedContextContent interface to frontend types
   - Update ContentType unions

2. **Phase 2: Event Emission** (Backend)
   - Modify SharedContext component to emit events as ContentBlock
   - Add method to retrieve events for display

3. **Phase 3: UI Component** (Frontend)
   - Create SharedContextEventsDisplay component
   - Integrate into ContentDisplay switch statement
   - Add styling and animations

4. **Phase 4: Polish & Testing**
   - Add unit tests for new content type
   - Test with multi-agent flows
   - Add documentation

## Design Considerations

### Operation Color Coding
- `get` - Blue (reading)
- `set` - Green (writing)
- `append` - Yellow/Orange (adding)
- `delete` - Red (removing)
- `keys` - Gray (listing)
- `has_key` - Gray (checking)

### Timeline vs Table
- Timeline view: Better for understanding flow sequence
- Table view: Better for filtering/searching many events
- Default: Timeline, with option to switch to table

### Namespace Grouping
- Group events by namespace for multi-tenant flows
- Collapsible namespace sections
- Show "default" namespace if none specified

## Questions to Consider

1. Should events be displayed automatically after each operation, or only when explicitly requested?
2. Should there be a maximum number of events displayed (with pagination)?
3. Should the component ID be shown as the actual component name (requires lookup)?
4. Should there be a "clear events" action?
