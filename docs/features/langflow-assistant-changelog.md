---

## 28. Replace header dropdown with direct "+ New session" button

**File:** `src/frontend/src/components/core/assistantPanel/components/assistant-header.tsx`
**Change:** Removed the `...` (MoreVertical) dropdown menu entirely. Replaced it with a direct "+ New session" ghost button in the header, next to the X close button. Removed `DropdownMenu*` imports.
**Why:** The dropdown added an unnecessary click to reach "New session" — the only action it contained. A direct button is faster and more discoverable.

---

## 29. Add "A" keyboard shortcut to toggle assistant panel

**File:** `src/frontend/src/pages/FlowPage/index.tsx`
**Change:** Added `useHotkeys("a", ...)` to toggle the assistant panel open/closed. Uses `enableOnFormTags: false` so it only fires when focus is on the canvas, not inside text inputs.
**Why:** Power users need a fast way to summon the assistant without clicking. Pressing A opens the panel; pressing A again (when not typing) closes it.

---

## 30. Add Escape keyboard shortcut to close assistant panel

**File:** `src/frontend/src/pages/FlowPage/index.tsx`
**Change:** Added `useHotkeys("escape", ...)` with `enableOnFormTags: true` to close the assistant panel from anywhere — canvas or inside the input.
**Why:** Standard UX pattern for dismissing overlays. Works even when the user is focused inside the assistant's textarea.

---

## 31. Auto-focus input when assistant panel opens

**Files:** `assistant-input.tsx`, `assistant-panel.tsx`
**Change:** Added `autoFocus` prop to `AssistantInput` and `AssistantInputWithScroll`. When `autoFocus={isOpen}`, the textarea is focused on mount (if not disabled/processing). Also added Escape key handler in the textarea to blur it (so the Escape hotkey from #30 can then close the panel).
**Why:** Users pressing A to open the assistant should be able to start typing immediately without clicking the input field.

---

## 32. Show "Working on it..." placeholder during generation

**File:** `src/frontend/src/components/core/assistantPanel/components/assistant-input.tsx`
**Change:** Changed the placeholder logic: when `isProcessing` is true, show `"Working on it..."` instead of the random suggestion text (e.g., "Build a document parser..."). The animated spinner placeholder for post-generation steps (extracting, validating) remains unchanged.
**Why:** Showing a random prompt suggestion while the assistant is actively generating is misleading — it looks like the input is idle and waiting for user input.

---

## 33. Detect component code in streaming content to show progress card

**File:** `src/frontend/src/components/core/assistantPanel/components/assistant-message.tsx`
**Change:** Added `contentLooksLikeComponentCode` check: a regex that matches ` ```python ` blocks containing `class ... Component` in the streaming content. When matched, `isComponentGeneration` becomes true regardless of the backend's intent classification, causing the progress card (ReasoningUI) to render instead of raw markdown.
**Why:** When the backend misclassifies a component generation request as "question", tokens stream as raw code in the chat. This frontend-side detection catches that case and hides the code, showing the progress card instead.

---

## 34. Add component generator prompt rules to LangflowAssistant.json

**File:** `src/backend/base/langflow/agentic/flows/LangflowAssistant.json`
**Change:** Added three rules to the Component Generation Rules section of the system prompt:
- Each Output must have its own method returning a single value. Never return tuples. Never point two outputs to the same method.
- Output type annotation must match the returned object (e.g., DataFrame output must return DataFrame, not Data).
- DataFrame is a Langflow type from `lfx.schema`, not pandas. It wraps a list of dicts: `DataFrame([{"key": "value"}, ...])`.

**Why:** The component generator was producing invalid multi-output patterns (returning tuples, two outputs pointing to the same method) and confusing Langflow's DataFrame with pandas DataFrame.

---

## 35. Improve intent classification for follow-up modifications

**File:** `src/backend/base/langflow/agentic/flows/translation_flow.py`
**Change:** Expanded the TranslationFlow prompt to recognize modification and follow-up patterns ("use X instead", "add Y", "change Z", "can you also...") as `generate_component`. Added three new few-shot examples. Also set `should_store_message=False` on ChatInput and ChatOutput to prevent cross-flow session contamination.
**Why:** Follow-up requests like "can you use dataframe output instead?" were classified as "question" because the prompt only recognized explicit creation verbs. The stateless flag prevents TranslationFlow messages from polluting the assistant's conversation memory.

---

## 36. Intent-independent code extraction in assistant service

**File:** `src/backend/base/langflow/agentic/services/assistant_service.py`
**Change:** Removed the early return that skipped code extraction for "question" intent. Now always extracts and checks for component code in every response (`"class " in code and "Component" in code`). Also passes `session_id=None` to `classify_intent` to isolate TranslationFlow from the assistant's session.
**Why:** Even with improved intent classification, edge cases exist. This fallback ensures any response containing valid component code gets extracted, validated, and shown as a component card — regardless of what the intent classifier decided.

---

## 37. Frontend-owned session persistence for conversation memory

**File:** `src/frontend/src/components/core/assistantPanel/hooks/use-assistant-chat.ts`
**Change:** Added `sessionIdRef` (generated once via `useRef`) that is sent with every `postAssistStream` request. On "New session" (`handleClearHistory`), a new `session_id` is generated.
**Why:** The assistant had no conversation memory — the backend generated a new UUID per request, so the Agent's memory component never found previous messages. A stable frontend-owned session ID enables multi-turn conversations.

---

## 38. Fixed-width zoom percentage display

**File:** `src/frontend/src/components/core/canvasControlsComponent/CanvasControlsDropdown.tsx`
**Change:** Applied `w-11 text-center` to the zoom percentage text. Reduced button padding to `px-0.5` and added `gap-0.5` between percentage and chevron.
**Why:** The zoom percentage (e.g., "65%" vs "150%") caused the controls bar to shift width. Fixed width eliminates the layout jump.

---

## 39. GPU-accelerated panel open transition

**File:** `src/frontend/src/components/core/assistantPanel/assistant-panel.tsx`
**Change:** Replaced `transition-all duration-300` with `transition-[opacity,transform] duration-200` and added `will-change-[opacity,transform]`.
**Why:** `transition-all` forced the browser to animate every CSS property across the entire message DOM on open/close, causing sluggishness with many messages.

---

## 40. Update assistant documentation

**File:** `docs/features/langflow-assistant.md`
**Change:** Added 4 new behavior scenarios (keyboard shortcuts, placeholder during generation, streaming code detection), updated "New session" scenario to reflect direct button, added 3 new smoke tests, added ADRs 5-9. Updated date.
**Why:** Documentation should reflect the current implementation.
