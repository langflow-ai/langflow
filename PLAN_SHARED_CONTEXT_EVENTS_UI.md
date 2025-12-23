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

## Dual-Location Implementation: Canvas + Playground

The events UI needs to be available in **both** locations:

### Location 1: Canvas Panel

**Pattern**: Follow `LogCanvasControls` pattern (`src/frontend/src/components/core/logCanvasControlsComponent/`)

**Implementation**:

```
src/frontend/src/components/core/sharedContextCanvasControls/
├── index.tsx                    # Panel with button trigger
└── SharedContextEventsModal.tsx # Modal with events display
```

**index.tsx** - Canvas Panel Button:
```tsx
import { Panel } from "@xyflow/react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import SharedContextEventsModal from "./SharedContextEventsModal";

const SharedContextCanvasControls = () => {
  return (
    <Panel
      data-testid="shared_context_controls"
      className="react-flow__controls !m-2 rounded-md"
      position="bottom-left"  // Position next to Logs button
    >
      <SharedContextEventsModal>
        <Button variant="primary" size="sm" className="flex items-center !gap-1.5">
          <ForwardedIconComponent name="Database" className="text-primary" />
          <span className="text-mmd font-normal">Context</span>
        </Button>
      </SharedContextEventsModal>
    </Panel>
  );
};

export default SharedContextCanvasControls;
```

**Integration Point**: Add to `MemoizedComponents.tsx`:
```tsx
export const MemoizedSharedContextControls = memo(() => <SharedContextCanvasControls />);
```

Then render in `PageComponent/index.tsx` alongside `MemoizedLogCanvasControls`.

---

### Location 2: Playground Panel

**Pattern**: Extend `SidebarOpenView` or add a new tab in the playground sidebar

**Option A: New Tab in Playground Sidebar**

Modify `src/frontend/src/modals/IOModal/components/sidebar-open-view.tsx` to include a "Context" tab that shows SharedContext events for the current session.

```tsx
// Add to SidebarOpenView tabs
<TabsTrigger value="context">
  <ForwardedIconComponent name="Database" className="h-4 w-4" />
  Context
</TabsTrigger>

// Add TabsContent
<TabsContent value="context">
  <SharedContextEventsDisplay events={contextEvents} />
</TabsContent>
```

**Option B: Inline with Chat Messages (via ContentBlocks)**

Events automatically appear in the chat view as ContentBlocks when the flow includes SharedContext operations. This uses the existing `ContentBlockDisplay` infrastructure.

**Option C: Dedicated Right Panel**

Add a collapsible panel on the right side of the playground (next to chat) that shows real-time context events.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Playground                                                          │
├──────────────────────────────────┬──────────────────────────────────┤
│                                  │  Context Events      [collapse]  │
│     Chat Messages                │  ● SET task_data     12:34:56   │
│                                  │  ● GET task_data     12:34:58   │
│     [ContentBlockDisplay         │  ● APPEND reviews    12:35:02   │
│      with agent steps]           │  ● GET reviews       12:35:10   │
│                                  │                                  │
│                                  │  Keys: task_data, reviews        │
│                                  │  Total ops: 4                    │
└──────────────────────────────────┴──────────────────────────────────┘
```

---

### Real-Time Event Streaming

**Backend**: Emit SharedContext events via the existing event streaming system

Modify `src/lfx/src/lfx/components/agent_blocks/shared_context.py`:
```python
def _record_event(self, operation: str, key: str | None = None) -> None:
    """Record an operation event and emit to event manager if available."""
    event = {
        "operation": operation,
        "key": key or "",
        "namespace": self.namespace or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component_id": self._id,
    }

    # Store in context
    if self.EVENTS_KEY not in self.ctx:
        self.ctx[self.EVENTS_KEY] = []
    self.ctx[self.EVENTS_KEY].append(event)

    # Emit via event manager for real-time UI updates
    if hasattr(self, '_event_manager') and self._event_manager:
        self._event_manager.emit_shared_context_event(event)
```

**Frontend**: Listen for shared context events in the build process

Modify `src/frontend/src/utils/buildUtils.ts` to handle a new event type:
```typescript
case "shared_context_event":
  // Update a shared context events store
  useSharedContextStore.getState().addEvent(eventData);
  break;
```

**New Zustand Store**: `src/frontend/src/stores/sharedContextStore.ts`
```typescript
interface SharedContextEvent {
  operation: string;
  key: string;
  namespace: string;
  timestamp: string;
  component_id: string;
}

interface SharedContextState {
  events: SharedContextEvent[];
  addEvent: (event: SharedContextEvent) => void;
  clearEvents: () => void;
}

export const useSharedContextStore = create<SharedContextState>((set) => ({
  events: [],
  addEvent: (event) => set((state) => ({ events: [...state.events, event] })),
  clearEvents: () => set({ events: [] }),
}));
```

---

### API Endpoint for Historical Events

Add endpoint to retrieve SharedContext events from a completed flow run:

**Backend**: `src/backend/base/langflow/api/v1/shared_context.py`
```python
@router.get("/flows/{flow_id}/shared-context-events")
async def get_shared_context_events(
    flow_id: UUID,
    session_id: str | None = None,
) -> list[dict]:
    """Get SharedContext events from a flow's graph context."""
    # Retrieve from cached graph or stored execution data
    ...
```

---

### Component Files to Create/Modify

**New Files**:
1. `src/frontend/src/components/core/sharedContextCanvasControls/index.tsx`
2. `src/frontend/src/components/core/sharedContextCanvasControls/SharedContextEventsModal.tsx`
3. `src/frontend/src/components/core/chatComponents/SharedContextEventsDisplay.tsx`
4. `src/frontend/src/stores/sharedContextStore.ts`
5. `src/backend/base/langflow/api/v1/shared_context.py`

**Modified Files**:
1. `src/frontend/src/pages/FlowPage/components/PageComponent/MemoizedComponents.tsx` - Add SharedContext panel
2. `src/frontend/src/pages/FlowPage/components/PageComponent/index.tsx` - Render panel
3. `src/frontend/src/modals/IOModal/components/sidebar-open-view.tsx` - Add Context tab
4. `src/frontend/src/utils/buildUtils.ts` - Handle shared_context_event
5. `src/frontend/src/types/chat/index.ts` - Add types
6. `src/frontend/src/components/core/chatComponents/ContentDisplay.tsx` - Handle shared_context type
7. `src/lfx/src/lfx/components/agent_blocks/shared_context.py` - Emit events

---

## Updated Implementation Order

### Phase 1: Core Infrastructure
1. Create `SharedContextEventsDisplay` component (reusable)
2. Create `sharedContextStore` Zustand store
3. Add `SharedContextEvent` TypeScript types

### Phase 2: Canvas Integration
4. Create `SharedContextCanvasControls` panel
5. Create `SharedContextEventsModal` modal
6. Integrate into `PageComponent`

### Phase 3: Playground Integration
7. Add "Context" tab to playground sidebar
8. Connect to `sharedContextStore` for real-time updates

### Phase 4: Backend Event Streaming
9. Modify SharedContext to emit events via EventManager
10. Add handler in buildUtils for `shared_context_event`
11. Clear store on new build start

### Phase 5: Polish & Testing
12. Add unit tests
13. Add animations and loading states
14. Test with multi-agent flows
15. Documentation

---

## Questions to Consider

1. Should events be displayed automatically after each operation, or only when explicitly requested?
2. Should there be a maximum number of events displayed (with pagination)?
3. Should the component ID be shown as the actual component name (requires lookup)?
4. Should there be a "clear events" action?
