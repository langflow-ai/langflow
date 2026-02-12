# Assistant UI Branch - Change Log

This document tracks all UI adjustments made to the `cz/assistant-v0` branch, with rationale for each change.

---

## 1. Lower canvas controls toolbar position

**File:** `src/frontend/src/components/core/canvasControlsComponent/CanvasControls.tsx`

**Change:** Removed the `!bottom-4` override entirely, letting the panel sit at its default position.

**Why:** The canvas controls toolbar (assistant, undo/redo, zoom, help, lock) was sitting too high compared to where the equivalent controls (zoom options) lived in the main branch. Removing the bottom offset lets the toolbar sit at the natural react-flow panel position, matching the previous layout.

---

## 2. Make assistant model dropdown match node parameter model dropdown pattern

**File:** `src/frontend/src/components/core/assistantPanel/components/model-selector.tsx`

**Change:** Aligned the assistant panel's model selector to follow the exact same rendering pattern as the node parameter `ModelInputComponent`:
- **Provider header**: Removed the icon from the group header — now plain text only (matching the reference's `text-xs font-semibold` style).
- **Model items**: Added provider icon next to each individual model name (`h-4 w-4 shrink-0 text-primary ml-2`).
- **Check mark**: Changed from conditional rendering (`{isSelected && ...}`) to always-rendered with opacity toggle (`opacity-100` / `opacity-0`), matching the reference exactly.
- **Layout**: Updated item structure to use `flex w-full items-center gap-2` with `ml-auto` for the check, same as the reference.

**Why:** Both dropdowns select models from the same data. They should look and behave identically for consistency. The reference pattern (ModelInputComponent) shows icons per item and plain text headers — the assistant dropdown was doing the opposite.

---

## 3. Move close button out of dropdown menu into a visible X button

**File:** `src/frontend/src/components/core/assistantPanel/components/assistant-header.tsx`

**Change:** Removed the `...` dropdown menu entirely. Added a visible X close button to the header. Moved the "Clear history" trash icon into the text input field (top-right corner, small), and it only appears after the first message is sent.

**Files:**
- `assistant-header.tsx` — removed dropdown and `onClearHistory`/`disabled` props; header now shows: view mode toggle, X button.
- `assistant-input.tsx` — added `onClearHistory` and `hasMessages` props; renders a small trash icon at the top-right of the textarea when messages exist.
- `assistant-panel.tsx` — passes `onClearHistory` and `hasMessages` through to the input component.

**Why:** The assistant panel is a distracting overlay that users need to open and close quickly. Burying close inside a dropdown added unnecessary clicks. The trash icon in the header was visually heavy — moving it inside the input field keeps it accessible but unobtrusive, and hiding it until messages exist avoids showing a useless action on an empty conversation.

---

## 4. Simplify header: single view-mode toggle icon, remove dead space

**File:** `src/frontend/src/components/core/assistantPanel/components/assistant-header.tsx`

**Change:** Replaced the two-button toggle (sidebar + floating) with a single icon that switches to the other mode. Removed `gap-1` between header buttons to eliminate dead non-clickable space.

**Why:** If you're already in floating mode, you only need a button to switch to sidebar (and vice versa). Two buttons showing the current state as "selected" is redundant. Removing the gap ensures the entire header action area is clickable.

---

## 5. Restructure header: `...` dropdown with "New session" + X close

**File:** `src/frontend/src/components/core/assistantPanel/components/assistant-header.tsx`

**Change:** Brought back the `...` dropdown menu containing "New session" (replaces "Clear history") and "Sidebar/Floating view" toggle. X close button remains directly visible. "New session" is disabled when there are no messages.

**Why:** The `...` menu is extensible for future actions. "New session" is clearer intent than "Clear history". The X button stays directly accessible for fast open/close workflow.

---

## 6. Close panel on click outside

**File:** `src/frontend/src/components/core/assistantPanel/assistant-panel.tsx`

**Change:** Added a `pointerdown` event listener (capture phase) on `document` that closes the assistant when clicking outside the panel. Excludes clicks on dropdown portals and radix popper content to prevent false closes.

**Why:** The assistant is a transient overlay that users open and close frequently. Clicking on the canvas should dismiss it, matching standard popover/panel behavior and reducing friction.

---

## 7. Reduce assistant panel gap between messages and input

**Files:** `assistant-panel.tsx`, `assistant-input.tsx`

**Change:** Reduced messages area bottom padding from `py-6` to `pt-4 pb-0`. Reduced input wrapper bottom padding from `pb-2.5` to `pb-1`. Reduced inner input gap from `gap-4` to `gap-1` (compact mode).

**Why:** Space is scarce in the assistant panel — every pixel of vertical space matters for showing more message content.

---

## 8. Compact input in conversation mode, roomier input on initial view

**Files:** `assistant-input.tsx`, `assistant-panel.tsx`

**Change:** Added a `compact` prop to `AssistantInput`. When `compact=true` (conversation mode): single-line textarea, `gap-1`, `min-h-0`. When `compact=false` (initial view): two-line textarea, `gap-4`, `min-h-[60px]`. Floating panel width is `520px` on initial view, `620px` with messages.

**Why:** The initial view is a simple prompt that benefits from a larger, more inviting input area. Once in conversation, space should be maximized for messages, so the input shrinks to a compact single line.

---

## 9. Expand floating panel size for conversation mode

**File:** `src/frontend/src/components/core/assistantPanel/assistant-panel.tsx`

**Change:** Increased floating panel width from `520px` to `620px` and height from `500px` to `600px` when messages are present. Sidebar width also set to `620px`.

**Why:** Code blocks and longer responses were getting truncated at the previous width. The extra space improves readability for code-heavy assistant responses.

---

## 10. Equalize user and assistant message avatar sizes

**File:** `src/frontend/src/components/core/assistantPanel/components/assistant-message.tsx`

**Change:** Reduced both user and assistant avatar sizes from `h-8 w-8` to `h-7 w-7`. Changed assistant avatar border radius from `rounded-xl` to `rounded-lg`.

**Why:** The user avatar (circular) appeared visually larger than the assistant avatar (rounded square) at the same pixel size. Matching them at a slightly smaller size creates visual consistency.

---

## 11. Make input dead space clickable to focus textarea

**File:** `src/frontend/src/components/core/assistantPanel/components/assistant-input.tsx`

**Change:** Added `cursor-text` and `onClick` handler to the input container div that focuses the textarea when clicking anywhere in the input area.

**Why:** Clicking the empty space around the textarea felt unresponsive. Users expect the entire input box to be clickable for text entry, matching standard text editor behavior.

---

## 12. Keep panel expanded after "New session"

**File:** `src/frontend/src/components/core/assistantPanel/assistant-panel.tsx`

**Change:** Added `hasExpandedOnce` state that tracks whether the panel has ever shown messages. After "New session" clears messages, the panel stays at the expanded size (620px/600px) instead of shrinking back to the initial compact view. Resets only when the panel is fully closed.

**Why:** Starting a new session should feel like a clean slate in the same workspace, not a jarring resize. The user already committed to the expanded view and expects it to stay.

---

## 13. Remove separator dead space in canvas controls toolbar

**File:** `src/frontend/src/components/core/canvasControlsComponent/CanvasControls.tsx`

**Change:** Removed the `<Separator>` element between the zoom dropdown and the help icon.

**Why:** The vertical separator created a visible blue line and non-interactive dead space between controls. Removing it keeps the toolbar compact and consistent.

---

## 14. Fix "New" badge clipping and show only when assistant is closed

**Files:** `CanvasControls.tsx`, `App.css`

**Change:** Added `!overflow-visible` to the Panel className and a CSS rule forcing `overflow: visible` on `.react-flow__controls`. The "New" badge is now hidden when the assistant is open (`assistantSidebarOpen`), only appearing on hover when closed.

**Why:** The badge was being clipped by the react-flow controls container's `overflow: hidden`. Hiding it when the panel is open avoids redundancy — the user already knows about the assistant if they're using it.

---

## 15. Fix click-outside closing when interacting with canvas controls

**File:** `src/frontend/src/components/core/assistantPanel/assistant-panel.tsx`

**Change:** Added exclusion for `[data-testid='main_canvas_controls']` in the click-outside handler, so clicking the assistant toggle button doesn't race with the close handler.

**Why:** The pointerdown capture handler was closing the panel before the button's onClick could toggle it, making the button unable to close the panel (it would close then immediately reopen).

---

## 16. Fix Anthropic model truncation — default max_tokens in get_llm()

**File:** `src/lfx/src/lfx/base/models/unified_models.py`

**Change:** When no valid `max_tokens` is provided (None, 0, or empty string), `get_llm()` now defaults to `16384` instead of omitting the parameter entirely.

**Why:** The LangflowAssistant flow has `max_tokens: 0` which gets converted to `None`. Without an explicit `max_tokens`, Anthropic's ChatAnthropic defaults to a low token limit, causing generated component code to be truncated. OpenAI was unaffected because it handles missing `max_tokens` with a higher default. Setting a code-level default of 16384 ensures all providers get sufficient output tokens regardless of flow configuration.

---

## 17. Align typing cursor with text baseline

**File:** `src/frontend/src/components/core/assistantPanel/components/assistant-loading-state.tsx`

**Change:** Reduced cursor height from `h-4` to `h-3.5`, added `align-text-bottom` and `translate-y-px` for proper baseline alignment.

**Why:** The blinking cursor element was slightly taller than the text line and positioned above the baseline, making it look misaligned with the loading step text.

---

## 18. Remove dead space between messages and input in conversation view

**File:** `src/frontend/src/components/core/assistantPanel/assistant-panel.tsx`

**Change:** Removed `flex-1` from `StickToBottom.Content`, so the messages area only takes as much space as content requires instead of stretching to fill the panel.

**Why:** After a component result card, there was a large empty gap before the input. The `flex-1` was forcing the content area to expand, pushing the input far below the last message.

---

## 19. Randomize input placeholder text

**File:** `src/frontend/src/components/core/assistantPanel/assistant-panel.constants.ts`

**Change:** Replaced the static `ASSISTANT_PLACEHOLDER` string with a random selection from a pool of suggestions (e.g. "Build a RAG pipeline...", "Make a chatbot with memory...", "Ask me anything about Langflow...").

**Why:** A static placeholder feels repetitive. Randomized suggestions give the user ideas of what the assistant can do and make the experience feel more dynamic.

---

## 20. Close assistant panel on component approve

**File:** `src/frontend/src/components/core/assistantPanel/assistant-panel.tsx`

**Change:** Wrapped `handleApprove` with `handleApproveAndClose` that calls both `handleApprove(messageId)` and `onClose()`, so the panel dismisses after approving a component.

**Why:** After approving a generated component, the user wants to see it on the canvas. Keeping the assistant panel open blocks the view. Auto-closing gives immediate visual feedback that the component was added.

---

## 21. Replace hardcoded features with real component description, inputs, and outputs

**File:** `src/frontend/src/components/core/assistantPanel/components/assistant-component-result.tsx`

**Change:** Replaced the static "Features" section (hardcoded "Input/Output handling with type validation", "Error handling and logging", "Customizable parameters") with dynamically parsed component info extracted from the generated Python code. Now shows:
- **Description**: parsed from `description = "..."` in the component class
- **Inputs**: extracted from Input type declarations (e.g. `MessageTextInput`, `StrInput`, etc.) with display names shown as chips
- **Outputs**: extracted from `Output(display_name="...")` declarations shown as chips

**Why:** The hardcoded text was misleading — it showed the same generic features for every component regardless of what was actually generated. Showing real description, inputs, and outputs gives the user accurate information to decide whether to approve the component.

---

## 22. Cap component result card width and improve spacing

**File:** `src/frontend/src/components/core/assistantPanel/components/assistant-component-result.tsx`

**Change:** Added `max-w-[80%]` to the card container so it doesn't stretch the full message width. Reverted inputs/outputs to stacked layout (not side by side). Increased spacing between sections (`gap-3`, `mb-5`, `mb-1.5`).

**Why:** The card was taking up the full width of the message area, making it look oversized. Stacked inputs/outputs are easier to scan. More breathing room between sections improves readability.

---

## 23. Show data types for inputs and outputs on component card

**File:** `src/frontend/src/components/core/assistantPanel/components/assistant-component-result.tsx`

**Change:** Updated the code parser to extract type info:
- **Inputs**: show the input class type formatted as a label, e.g. `Text Input (Text)`, `API Key (SecretStr)`. The raw class name (e.g. `MessageTextInput`) is cleaned up by removing `Input` suffix and `Message` prefix.
- **Outputs**: resolve the actual return type from the method's `-> ReturnType` annotation in the Python code, e.g. `Result (Message)` or `Output (Data)`. Previously showed the method name (`build_result`) which was meaningless.

**Why:** Knowing the data type of each input/output helps the user understand how the component will connect to others in the flow — a `Message` output connects differently than a `Data` output.

---

## 24. Prevent click-outside close when assistant dropdowns are open

**File:** `src/frontend/src/components/core/assistantPanel/assistant-panel.tsx`

**Change:** Added a DOM-level check in the click-outside handler: if any `[data-radix-popper-content-wrapper]` exists in the document, the handler skips closing the panel. Previously it only checked if the click *target* was inside a popper — but clicking the canvas means the target is the canvas, not the dropdown portal.

**Why:** When a dropdown (model selector or `...` menu) is open inside the assistant, clicking on the canvas would close the entire panel because the pointerdown capture handler fired before the dropdown's own dismiss logic. The canvas also shows React Flow's grab cursor in these areas, making the interaction feel broken. Now the panel stays open as long as any of its dropdowns are open.

---

## 25. Remove sidebar view mode — floating only

**Files:** `assistant-panel.tsx`, `assistant-header.tsx`, `assistant-panel.types.ts`, `hooks/index.ts`, `hooks/use-assistant-view-mode.ts`, `index.ts`, `pages/FlowPage/index.tsx`, `stores/assistantManagerStore.ts`, `types/zustand/assistantManager/index.ts`

**Change:** Removed the sidebar view mode entirely. The assistant now always uses the floating panel. Removed:
- "Sidebar view" / "Floating view" toggle from the `...` dropdown menu
- `AssistantViewMode` type, `useAssistantViewMode` hook, and all `viewMode` props
- `assistantViewMode` / `setAssistantViewMode` from the Zustand store and its type definition
- Sidebar spacer div and sidebar-conditional CSS classes from FlowPage
- `AssistantEmptyState` component usage (was only shown in sidebar initial view)

**Why:** The floating panel with dynamic open/close and size expansion works amazingly well as a first version — it stays out of the way, doesn't conflict with other areas of Langflow (sidebar, playground, canvas), and the open/close/resize behavior feels natural and responsive. The sidebar mode added complexity (spacer divs, negative margins, conditional styling) for a view that wasn't needed. Shipping floating-only keeps the feature focused and polished.

---

## 26. Fix model selector jiggle on dropdown open

**File:** `src/frontend/src/components/core/assistantPanel/components/model-selector.tsx`

**Change:** Added `active:!scale-100` to the model selector trigger button to override the global `active:scale-[0.97]` applied by the `Button` component.

**Why:** The `Button` component applies a 3% scale-down on `:active` (mousedown) as press feedback. On dropdown triggers this causes a visible jiggle — the text shrinks briefly on click then snaps back when the dropdown opens. Dropdown triggers shouldn't have press feedback since they immediately open a menu overlay.

---

## 27. Fix grab cursor showing when assistant dropdowns are open

**File:** `src/frontend/src/App.css`

**Change:** Added a CSS rule using `:has()` selector: when any `[data-radix-popper-content-wrapper]` exists in the DOM, the `.react-flow__pane` cursor is overridden from `grab` to `default`.

**Why:** When opening a dropdown inside the assistant (model selector or `...` menu), the React Flow canvas grab cursor was bleeding through to all areas outside the dropdown content. This made the interaction feel broken — the cursor showed an open hand instead of the default pointer.

---

## Known Issues

### Icon jiggle on assistant button hover

**File:** `src/frontend/src/components/core/canvasControlsComponent/CanvasControls.tsx`

**Issue:** Hovering over the assistant button causes neighboring icon buttons (undo, redo, help, lock) to visually jiggle/shift by sub-pixels. Text elements like the zoom percentage are unaffected. Attempted fixes (opacity-only transitions instead of display swap, removing scale transforms from the "New" badge, explicit wrapper sizing) did not resolve the issue. Likely a browser sub-pixel rendering artifact triggered by hover state changes within the react-flow controls panel. Needs further investigation.

---

## Suggested Improvements

### Better visibility on intermediate steps during component generation

**Problem:** The loading state during component generation shows only generic animated messages ("Examining the component structure...", "Building the component code..."). The user waits with no visibility into what's actually happening — no code preview, no validation errors, no tool usage info. Overall, intermediate steps need much better visibility to make the experience feel responsive and transparent.

**What the backend already sends but the frontend ignores:**
- `validation_failed` progress events include `component_code`, `error`, and `class_name`
- `retrying` progress events include the `error` that caused the retry
- The frontend's `AgenticProgressEvent` type only captures `step`, `attempt`, `max_attempts` — all other fields are silently dropped in the `onProgress` handler

**Proposed changes:**

1. **Frontend — update types** (`controllers/API/queries/agentic/types.ts`): Add optional `error`, `class_name`, and `component_code` fields to `AgenticProgressEvent`. Add matching fields to `AgenticProgressState`.

2. **Frontend — capture data in hook** (`hooks/use-assistant-chat.ts`): Update the `onProgress` handler to extract and store `component_code` and `error` from progress events into the message state.

3. **Frontend — show code preview in loading state** (`components/assistant-loading-state.tsx`): Add a collapsible code preview panel below the animated messages. Show it as soon as `component_code` is available. During retries, also show the validation error that caused the retry.

4. **Backend — send code earlier** (`agentic/services/assistant_service.py`): Include `component_code` in the `validating` progress event (not just `validation_failed`), so the code is visible as soon as it's extracted — even during the first validation attempt.

**Code availability timeline:**
| Step | Code available? | Error available? |
|------|----------------|-----------------|
| `generating_component` | No (LLM thinking) | No |
| `extracting_code` | No (parsing) | No |
| `validating` | Yes (needs backend change) | No |
| `validation_failed` | Yes (already sent, ignored) | Yes (already sent, ignored) |
| `retrying` | No | Yes (already sent, ignored) |

### Remove lock flow icon from canvas controls toolbar

**Current state:** The lock flow icon (padlock) is always visible in the canvas controls toolbar. However, "Lock Flow" is already accessible in the flow settings modal with a clear description ("Lock your flow to prevent edits or accidental changes") and a toggle switch.

**Suggestion:** Remove the lock icon from the canvas controls toolbar. It's a rarely used action that takes up space in a compact toolbar. Keeping it only in the flow settings modal is sufficient — it's a "set and forget" preference, not something users toggle frequently enough to justify a persistent toolbar icon. This would also make the toolbar cleaner and leave more room for the assistant and other frequently used controls.

**Important caveat:** Users must still have a clear visual indicator when a flow is locked — burying it in the settings modal alone makes it too easy to miss. If the toolbar icon is removed, an alternative indicator is needed (e.g. a subtle locked badge on the canvas, a different toolbar color/state, or a persistent banner). The goal is to remove the *toggle* from the toolbar, not the *visibility* of the locked state.

### Allow user to resize the assistant panel

**Current state:** The floating assistant panel has fixed sizes — 520x auto (initial) and 620x600 (conversation mode). Users can't adjust the size to their preference.

**Suggestion:** Allow the user to resize the panel by dragging from the top corners (or edges). This would let users expand the panel when reading long code blocks or shrink it when they want more canvas visibility. The panel could remember the user's preferred size in localStorage. A drag handle or subtle resize cursor on the corners would signal the affordance.

### ⚠️ IMPORTANT: Agent needs session memory — currently one-shot only

**Current state:** The assistant has no conversation memory. Each message is treated as an independent one-shot request — the agent has no awareness of previous messages in the session. The UI displays messages in a chat-like thread, but the backend processes each request in isolation. This means the user cannot:
- Ask follow-up questions ("make that component also handle PDFs")
- Request modifications to a previously generated component ("add an error handling input")
- Reference earlier context ("use the same approach but for a different API")

**Suggestion:** The agent needs a proper session with message history. Each request should include prior conversation context so the LLM can understand follow-ups and refine previous outputs. This is critical for making the assistant feel like a real collaborator rather than a stateless tool. The `session_id` field already exists in `AgenticAssistRequest` — the backend needs to persist and replay conversation history per session, and the frontend needs to pass accumulated messages with each request.
