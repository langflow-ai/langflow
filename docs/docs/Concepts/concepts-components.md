---
title: Components
slug: /concepts-components
---

import Icon from "@site/src/components/icon";

# Langflow components overview

A component is a single building block within a flow with inputs, outputs, functions, and parameters that define its functionality. A single component is like a class within a larger application.

To add a component to a flow, drag it from the **Component** menu to the **Workspace**.

Learn more about components and how they work on this page.

## Component menu

Each component is unique, but all have a menu bar at the top that looks something like the following:

<img src="/img/openai-model-component.png" alt="Open AI component" style={{display: 'block', margin: 'auto', width: 300}} />

Use the component controls to do the following:

- **Code** — Modify the component's Python code and save your changes.
- **Controls** — Adjust all component parameters.
- **Freeze** — After a component runs, lock its previous output state to prevent it from re-running.

Click <Icon name="Ellipsis" aria-label="Horizontal ellipsis" /> **All** to see additional options for a component.

To view a component’s output and logs, click the <Icon name="TextSearch" aria-label="Search and filter" /> icon.

To run a single component, click <Icon name="Play" aria-label="Play button" /> **Play**.

A <Icon name="Check" aria-label="Checkmark" />**Checkmark** indicates that the component ran successfully.

Running a single component with the **Play** button is different from running the entire flow. In a single component run, the `build_vertex` function is called, which builds and runs only the single component with direct inputs provided through the UI (the `inputs_dict` parameter). The  `VertexBuildResult` data is passed to the `build_and_run` method, which calls the component's `build` method and runs it. Unlike running the full flow, running a single component does not automatically execute its upstream dependencies.

## Component ports

Handles (<Icon name="Circle" size="16" aria-label="A circle on the side of a component" />) on the side of a component indicate the types of inputs and outputs that can be connected at that port. Hover over a handle to see connection details.

<img src="/img/prompt-component.png" alt="Prompt component" style={{display: 'block', margin: 'auto', width: 300}} />

### Component port data type colors

The following table lists the handle colors and their corresponding data types:

| Data type | Handle color | Handle |
|-----------|--------------|----------|
| BaseLanguageModel | Fuchsia | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#c026d3' }} /> |
| Data | Red | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#dc2626' }} /> |
| Document | Lime | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#65a30d' }} /> |
| Embeddings | Emerald | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#10b981' }} /> |
| LanguageModel | Fuchsia | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#c026d3' }} /> |
| Message | Indigo | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#4f46e5' }} /> |
| Prompt | Violet | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#7c3aed' }} /> |
| str | Indigo | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#4F46E5' }} /> |
| Text | Indigo | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#4F46E5' }} /> |
| unknown | Gray | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#9CA3AF' }} /> |

## Component code

A component inherits from a base `Component` class that defines its interface and behavior.

For example, the [Recursive character text splitter](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/components/langchain_utilities/recursive_character.py) is a child of the [LCTextSplitterComponent](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/base/textsplitters/model.py) class.

```python
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter, TextSplitter

from langflow.base.textsplitters.model import LCTextSplitterComponent
from langflow.inputs.inputs import DataInput, IntInput, MessageTextInput
from langflow.utils.util import unescape_string

class RecursiveCharacterTextSplitterComponent(LCTextSplitterComponent):
    display_name: str = "Recursive Character Text Splitter"
    description: str = "Split text trying to keep all related text together."
    documentation: str = "https://docs.langflow.org/components-processing"
    name = "RecursiveCharacterTextSplitter"
    icon = "LangChain"

    inputs = [
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            info="The maximum length of each chunk.",
            value=1000,
        ),
        IntInput(
            name="chunk_overlap",
            display_name="Chunk Overlap",
            info="The amount of overlap between chunks.",
            value=200,
        ),
        DataInput(
            name="data_input",
            display_name="Input",
            info="The texts to split.",
            input_types=["Document", "Data"],
        ),
        MessageTextInput(
            name="separators",
            display_name="Separators",
            info='The characters to split on.\nIf left empty defaults to ["\\n\\n", "\\n", " ", ""].',
            is_list=True,
        ),
    ]

    def get_data_input(self) -> Any:
        return self.data_input

    def build_text_splitter(self) -> TextSplitter:
        if not self.separators:
            separators: list[str] | None = None
        else:
            # check if the separators list has escaped characters
            # if there are escaped characters, unescape them
            separators = [unescape_string(x) for x in self.separators]

        return RecursiveCharacterTextSplitter(
            separators=separators,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

```

Components include definitions for inputs and outputs, which are represented in the UI with color-coded ports.

**Input Definition:** Each input (like `IntInput` or `DataInput`) specifies an input's type, name, and display properties, which appear as configurable fields in the component's UI panel.

**Methods:** Components have methods or functions that handle their functionality. This component has two methods.
`get_data_input` retrieves the text data to be split from the component's input. This makes the data available to the class.
`build_text_splitter` creates a `RecursiveCharacterTextSplitter` object by calling its parent class's `build` method. The text is split with the created splitter and passed to the next component.
When used in a flow, this component:

1. Displays its configuration options in the UI.
2. Validates user inputs based on the input types.
3. Processes data using the configured parameters.
4. Passes results to the next component.

## Freeze

After a component runs, **Freeze** locks the component's previous output state to prevent it from re-running.

If you’re expecting consistent output from a component and don’t need to re-run it, click **Freeze**.

Enabling **Freeze** freezes all components upstream of the selected component.

## Additional component options

Click <Icon name="Ellipsis" aria-label="Horizontal ellipsis" /> **All** to see additional options for a component.

To modify a component's name or description, double-click in the **Name** or **Description** fields. Component descriptions accept Markdown syntax.

### Component shortcuts

The following keyboard shortcuts are available when a component is selected.

| Menu item | Windows shortcut | Mac shortcut | Description |
|-----------|-----------------|--------------|-------------|
| Code | Space | Space | Opens the code editor for the component. |
| Advanced Settings | Ctrl + Shift + A | ⌘ + Shift + A | Opens advanced settings for the component. |
| Save Changes | Ctrl + S | ⌘ + S | Saves changes to the current flow. |
| Save Component | Ctrl + Alt + S | ⌘ + Alt + S | Saves the current component to Saved components. |
| Duplicate | Ctrl + D | ⌘ + D | Creates a duplicate of the component. |
| Copy | Ctrl + C | ⌘ + C | Copies the selected component. |
| Cut | Ctrl + X | ⌘ + X | Cuts the selected component. |
| Paste | Ctrl + V | ⌘ + V | Pastes the copied/cut component. |
| Docs | Ctrl + Shift + D | ⌘ + Shift + D | Opens related documentation. |
| Minimize | Ctrl + . | ⌘ + . | Minimizes the current component. |
| Freeze| Ctrl + Shift + F | ⌘ + Shift + F | Freezes component state and upstream components. |
| Download | Ctrl + J | ⌘ + J | Downloads the component as JSON. |
| Delete | Backspace | Backspace | Deletes the component. |
| Group | Ctrl + G | ⌘ + G | Groups selected components. |
| Undo | Ctrl + Z | ⌘ + Z | Undoes the last action. |
| Redo | Ctrl + Y | ⌘ + Y | Redoes the last undone action. |
| Redo (alternative) | Ctrl + Shift + Z | ⌘ + Shift + Z | Alternative shortcut for redo. |
| Share Component | Ctrl + Shift + S | ⌘ + Shift + S | Shares the component. |
| Share Flow | Ctrl + Shift + B | ⌘ + Shift + B | Shares the entire flow. |
| Toggle Sidebar | Ctrl + B | ⌘ + B | Shows/hides the sidebar. |
| Search Components | / | / | Focuses the component search bar. |
| Tool Mode | Ctrl + Shift + M | ⌘ + Shift + M | Toggles tool mode. |
| Update | Ctrl + U | ⌘ + U | Updates the component. |
| Open Playground | Ctrl + K | ⌘ + K | Opens the playground. |
| Output Inspection | O | O | Opens output inspection. |
| Play | P | P | Plays/executes the flow. |
| API | R | R | Opens the API view. |

## Group components in the workspace

Multiple components can be grouped into a single component for reuse. This is useful when combining large flows into single components, for example RAG with a vector database, and saving space.

1. Hold **Shift** and drag to select components.
2. Select **Group**.
The components merge into a single component.
3. Double-click the name and description to change them.
4. Save your grouped component to the sidebar for later use.

## Component version

A component's initial state is stored in a database. As soon as you drag a component from the sidebar to the workspace, the two components are no longer in parity.

A component keeps the version number it is initialized to the workspace with. If a component is at version `1.0` when it is dragged to the workspace, it will stay at version `1.0` until you update it.

Langflow notifies you when a component's workspace version is behind the database version and an update is available.
Click the <Icon name="AlertTriangle" aria-label="Exclamation mark" /> **Update Component** icon to update the component to the `latest` version. This will change the code of the component in place so you can validate that the component was updated by checking its Python code before and after updating it.

## Components sidebar

Components are listed in the sidebar by component type.

Component **bundles** are components grouped by provider. For example, Langchain modules like **RunnableExecutor** and **CharacterTextSplitter** are grouped under the **Langchain** bundle.

The sidebar includes a component **Search** bar, and includes flags for showing or hiding **Beta** and **Legacy** components.

**Beta** components are still being tested and are not suitable for production workloads.

**Legacy** components are available to use but no longer supported.
