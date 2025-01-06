---
title: Components overview
slug: /components-overview
---

import Icon from "@site/src/components/icon";

A component is a single building block within a flow with inputs, outputs, functions, and parameters that define its functionality. A single component is like a class within a larger application.

To add a component to a flow, drag it from the **Component** menu to the **Workspace**.

Learn more about components and how they work on this page.

## Component menu

Each component is unique, but all have a menu bar at the top that looks something like this.

<img src="/img/openai-model-component.png" alt="Open AI component" style={{display: 'block', margin: 'auto', width: 300}} />

Use these controls to do the following:

- **Code** — Modify the component's Python code and save your changes.
- **Controls** — Adjust all component parameters.
- **Freeze Path** — After a component runs, lock its previous output state to prevent it from re-running.

Click <Icon name="Ellipsis" aria-label="Horizontal ellipsis" /> **All** to see additional options for a component.

To view a component’s output and logs, click the <Icon name="View" aria-label="View icon" />**Visibility** icon.

To run a single component, click ▶️ **Play**. A ✅**Check** indicates that the component ran successfully.

## Component ports

Handles (<Icon name="Circle" size="16" aria-label="A circle on the side of a component" />) on the side of a component indicate the types of inputs and outputs that can be connected at that port. Hover over a handle to see connection details.

<img src="/img/prompt-component.png" alt="Prompt component" style={{display: 'block', margin: 'auto', width: 300}} />

### Component port data type colors

The following table lists the handle colors and their corresponding data types:

| Data Type | Handle Color | Hex Code |
|-----------|--------------|----------|
| BaseLanguageModel | Fuchsia | #c026d3 |
| Data | Red | #dc2626 |
| Document | Lime | #65a30d |
| Embeddings | Emerald | #10b981 |
| LanguageModel | Fuchsia | #c026d3 |
| Message | Indigo | #4f46e5 |
| Prompt | Violet | #7c3aed |
| str | Indigo | #4F46E5 |
| Text | Indigo | #4F46E5 |
| unknown | Gray | #9CA3AF |


## Freeze Path

After a component runs, **Freeze Path** locks the component's previous output state to prevent it from re-running.

If you’re expecting consistent output from a component and don’t need to re-run it, click **Freeze Path**.

Enabling **Freeze Path** freezes all components downstream of the selected component.


## Additional component options

Click <Icon name="Ellipsis" aria-label="Horizontal ellipsis" /> **All** to see additional options for a component.

To modify a component's name or description, double-click in the **Name** or **Description** fields. Component descriptions accept markdown syntax.

### Component shortcuts

The following keyboard shortcuts are available when a component is selected.

| Menu Item | Mac Shortcut | Description |
|-----------|----------|-------------|
| Code | ⌘ + C | Opens the code editor for the component. |
| Advanced | ⌘ + A | Opens advanced settings for the component. |
| Save | ⌘ + S | Saves the current state of the component to Saved components in the sidebar. |
| Duplicate | ⌘ + D | Creates a duplicate of the component. |
| Copy | ⌘ + C | Copies the selected component. Paste it in the workspace with ⌘ + V. |
| Docs | ⌘ + D | Opens related documentation. |
| Minimize | ⌘ + Q | Minimizes the current component. |
| Freeze | ⌘ + F | Freezes the current component state. |
| Freeze Path | ⌘ + F | Freezes the current component state and all upstream components. |
| Download | ⌘ + D | Downloads the current component as a JSON file. |
| Delete | ⌘ + ⌫ | Deletes the component. |

## Group components in the workspace

Multiple components can be grouped into a single component for reuse. This is useful when combining large flows into single components (like RAG with a vector database, for example) and saving space.

1. Hold **Shift** and drag to select components.
2. Select **Group**.
3. The components merge into a single component.
4. Double-click the name and description to change them.
5. Save your grouped component to in the sidebar for later use.

## Component version

A component's state is stored in a database, while sidebar components are like starter templates. As soon as you drag a component from the sidebar to the workspace, the two components are no longer in parity.

The component will keep the version number it was initialized to the workspace with. Click the **Update Component** icon (exclamation mark) to bring the component up to the `latest` version. This will change the code of the component in place so you can validate that the component was updated by checking its Python code before and after updating it.


