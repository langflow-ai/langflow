# Langflow E2E Selector Catalog

This is the canonical reference for `data-testid` selectors used in Langflow E2E tests. When adding new interactive elements, follow these naming conventions and add the element to this catalog.

## Naming Convention

All `data-testid` values use kebab-case with a prefix that indicates the element type:

| Prefix | Element Type | Example |
|--------|-------------|---------|
| `input-` | Text inputs | `input-chat-playground`, `input-flow-name` |
| `button-` / `button_` | Action buttons | `button-send`, `button_run_chat output` |
| `icon-` | Icon buttons | `icon-Globe`, `icon-Lock`, `icon-ChevronLeft` |
| `popover-anchor-input-` | Component parameter fields | `popover-anchor-input-openai_api_key` |
| `add-component-button-` | Drag-to-add buttons | `add-component-button-chat-output` |
| `card-` | Flow/component cards | `card-my-flow-name` |
| `title-` | Node titles on canvas | `title-OpenAI`, `title-Chat Output` |
| `handle-` | Connection handles | `handle-{component}-{shownode}-{field}-{direction}` |
| `div-chat-message` | Chat messages | `div-chat-message` |
| `show` | Field visibility toggles | `showmodel_name`, `showtemperature` |

## Canvas & Navigation

| Selector | Element | Notes |
|----------|---------|-------|
| `blank-flow` | "New Blank Flow" button | On project creation modal |
| `sidebar-search-input` | Component search input | Sidebar search bar |
| `sidebar-nav-add_note` | Sticky note button | Sidebar navigation |
| `sidebar-add-sticky-note-button` | Add sticky note (new) | Updated button name |
| `react-flow-id` | ReactFlow canvas container | Use for drag targets |
| `canvas_controls_dropdown` | Canvas controls dropdown | Opens zoom/fit/inspector menu |
| `fit_view` | Fit view button | Inside canvas controls |
| `zoom_out` | Zoom out button | Inside canvas controls |
| `zoom_in` | Zoom in button | Inside canvas controls |
| `inspector-toggle` | Inspection panel toggle | Inside canvas controls dropdown |

## Component Fields

| Selector | Element | Notes |
|----------|---------|-------|
| `popover-anchor-input-{name}` | Component input field | `name` matches the field's `name` attribute |
| `popover-anchor-input-openai_api_key` | OpenAI API key field | Only visible when no global variable selected |
| `input_output{component}` | Output connection handle area | e.g., `input_outputChat Output` |

**Important**: When `load_from_db: true` and a global variable is selected, the field renders as a **badge** (not an `<input>`). The `popover-anchor-input-{name}` selector will NOT exist in the DOM for those fields.

## Actions & Buttons

| Selector | Element | Notes |
|----------|---------|-------|
| `button-send` | Send message button | Playground chat |
| `button_run_{component}` | Run component button | e.g., `button_run_chat output` |
| `publish-button` | Publish/deploy flow | Top toolbar |
| `save-flow-button` | Save flow | Top toolbar |
| `edit-fields-button` | Toggle field editor | Inspection panel — requires `enableInspectPanel()` first |
| `playground-btn-flow-io` | Playground button | Use `dispatchEvent("click")` to close (not `.click()`) |
| `manage-model-providers` | Model providers button | Settings |

## Modals & Panels

| Selector | Element | Notes |
|----------|---------|-------|
| `modal-title` | Modal heading | Generic modal title |
| `edit-button-modal` | Edit button (legacy) | Old modal pattern |
| `edit-button-close` | Close edit modal | Old modal pattern |
| `lock-flow-switch` | Flow lock toggle | Flow settings |
| `input-flow-name` | Flow name input | Flow settings modal |
| `input-flow-description` | Flow description input | Flow settings modal |
| `session-selector` | Session selector | Playground session switcher |

## Icons (as buttons)

| Selector | Action |
|----------|--------|
| `icon-Globe` | Open global variables |
| `icon-Lock` | Toggle flow lock |
| `icon-ChevronLeft` | Navigate back |
| `icon-Trash2` | Delete action |
| `icon-Plus` | Add/create action |

## Inspection Panel Field Toggles

These selectors toggle field visibility in the inspection panel. The format is `show{fieldname}` (no separator):

| Selector | Field |
|----------|-------|
| `showmodel_name` | Model name field |
| `showtemperature` | Temperature field |
| `showmax_tokens` | Max tokens field |
| `showopenai_api_key` | OpenAI API key field |

## When to Add New data-testid

Add `data-testid` to an element when:
1. E2E tests need to interact with it (click, fill, assert visibility)
2. The element has no stable `role` or `text` alternative
3. The element is dynamically rendered and needs a stable anchor

Format: `{type}-{descriptive-name}` in kebab-case. Keep it descriptive enough that a test author understands the element without reading the component source.

```tsx
// Right — descriptive, kebab-case
<button data-testid="save-flow-button">Save</button>
<input data-testid="input-flow-name" />
<div data-testid="card-flow-summary" />

// Wrong — too generic
<button data-testid="btn1">Save</button>
<input data-testid="input" />
<div data-testid="wrapper" />
```
