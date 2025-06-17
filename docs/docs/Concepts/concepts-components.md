---
title: Components
slug: /concepts-components
---

import Icon from "@site/src/components/icon";

A component is a single building block within a flow with inputs, outputs, functions, and parameters that define its functionality. A single component is like a class within a larger application.

## Component menu

To add a component to a flow, drag it from the **Components** menu to the **Workspace**.

Each component is unique, but all have a menu bar at the top that looks something like the following:

![Agent component](/img/agent-component.png)

Use the component controls to do the following:

- **Code** — Modify the component's Python code and save your changes.
- **Controls** — Adjust all component parameters.
- **Tool Mode** — Enable this option to connect the component to an Agent.

To view additional options for a component, click <Icon name="Ellipsis" aria-hidden="true" /> **Show More**.

To view a component's output and logs, click <Icon name="TextSearch" aria-hidden="true" />  **Inspect Output**.

To run a single component, click <Icon name="Play" aria-label="Play button" /> **Run component**.

A **Last Run** value indicates that the component ran successfully.

Running a single component with the **Run component** button is different from running the entire flow. In a single component run, the `build_vertex` function is called, which builds and runs only the single component with direct inputs provided through the UI (the `inputs_dict` parameter). The  `VertexBuildResult` data is passed to the `build_and_run` method, which calls the component's `build` method and runs it. Unlike running the full flow, running a single component does not automatically execute its upstream dependencies.

## Component ports

Handles (<Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#4f46e5', fill: '#4f46e5' }}/>) on the side of a component indicate the types of inputs and outputs that can be connected at that port. Hover over a handle to see connection details.

![Prompt component with multiple inputs](/img/prompt-component.png)

Some components have ports that are dynamically added or removed.
For example, the **Prompt** component accepts inputs within curly braces, and new ports are opened when a value within curly braces is detected in the **Template** field.

![Prompt component with multiple inputs](/img/prompt-component-with-multiple-inputs.png)

### Component port data type colors

The following table lists the handle colors and their corresponding data types:

| Data type | Handle color | Handle |
|-----------|--------------|----------|
| Data | Red | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#dc2626', fill: '#dc2626' }} /> |
| DataFrame | Pink | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#ec4899', fill:'#ec4899' }} /> |
| Embeddings | Emerald | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#10b981', fill: '#10b981' }} /> |
| LanguageModel | Fuchsia | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#c026d3', fill: '#c026d3' }} /> |
| Memory | Orange | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#f97316', fill: '#f97316' }} /> |
| Message | Indigo | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#4f46e5', fill: '#4f46e5' }} /> |
| Text | Indigo | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#4f46e5', fill: '#4f46e5' }} /> |
| Tool | Cyan | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#06b6d4', fill: '#06b6d4' }} /> |
| unknown | Gray | <Icon name="Circle" size="16" aria-label="A circle on the side of a component" style={{ color: '#9CA3AF', fill: '#9CA3AF' }} /> |

## Component code

A component inherits from a base `Component` class that defines its interface and behavior.

For example, the [Recursive character text splitter](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/components/langchain_utilities/recursive_character.py) is a child of the [LCTextSplitterComponent](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/base/textsplitters/model.py) class.

<details>
<summary>Recursive character text splitter code</summary>

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

</details>

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

If you're expecting consistent output from a component and don't need to re-run it, click **Freeze**.

Enabling **Freeze** freezes all components upstream of the selected component.

## Additional component options

Click <Icon name="Ellipsis" aria-label="Horizontal ellipsis" /> **All** to see additional options for a component.

To modify a component's name or description, click the <Icon name="PencilLine" aria-label="Pencil line"/> icon. Component descriptions accept Markdown syntax.

### Component shortcuts

The following keyboard shortcuts are available when a component is selected.

| Menu item | Windows shortcut | Mac shortcut | Description |
|-----------|-----------------|--------------|-------------|
| Code | <kbd>Space</kbd> | <kbd>Space</kbd> | Opens the code editor for the component. |
| Advanced Settings | <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>A</kbd> | <kbd>⌘</kbd> + <kbd>Shift</kbd> + <kbd>A</kbd> | Opens advanced settings for the component. |
| Save Changes | <kbd>Ctrl</kbd> + <kbd>S</kbd> | <kbd>⌘</kbd> + <kbd>S</kbd> | Saves changes to the current flow. |
| Save Component | <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>S</kbd> | <kbd>⌘</kbd> + <kbd>Alt</kbd> + <kbd>S</kbd> | Saves the current component to Saved components. |
| Duplicate | <kbd>Ctrl</kbd> + <kbd>D</kbd> | <kbd>⌘</kbd> + <kbd>D</kbd> | Creates a duplicate of the component. |
| Copy | <kbd>Ctrl</kbd> + <kbd>C</kbd> | <kbd>⌘</kbd> + <kbd>C</kbd> | Copies the selected component. |
| Cut | <kbd>Ctrl</kbd> + <kbd>X</kbd> | <kbd>⌘</kbd> + <kbd>X</kbd> | Cuts the selected component. |
| Paste | <kbd>Ctrl</kbd> + <kbd>V</kbd> | <kbd>⌘</kbd> + <kbd>V</kbd> | Pastes the copied/cut component. |
| Docs | <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>D</kbd> | <kbd>⌘</kbd> + <kbd>Shift</kbd> + <kbd>D</kbd> | Opens related documentation. |
| Minimize | <kbd>Ctrl</kbd> + <kbd>.</kbd> | <kbd>⌘</kbd> + <kbd>.</kbd> | Minimizes the current component. |
| Freeze| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>F</kbd> | <kbd>⌘</kbd> + <kbd>Shift</kbd> + <kbd>F</kbd> | Freezes component state and upstream components. |
| Download | <kbd>Ctrl</kbd> + <kbd>J</kbd> | <kbd>⌘</kbd> + <kbd>J</kbd> | Downloads the component as JSON. |
| Delete | <kbd>Backspace</kbd> | <kbd>Backspace</kbd> | Deletes the component. |
| Group | <kbd>Ctrl</kbd> + <kbd>G</kbd> | <kbd>⌘</kbd> + <kbd>G</kbd> | Groups selected components. |
| Undo | <kbd>Ctrl</kbd> + <kbd>Z</kbd> | <kbd>⌘</kbd> + <kbd>Z</kbd> | Undoes the last action. |
| Redo | <kbd>Ctrl</kbd> + <kbd>Y</kbd> | <kbd>⌘</kbd> + <kbd>Y</kbd> | Redoes the last undone action. |
| Redo (alternative) | <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>Z</kbd> | <kbd>⌘</kbd> + <kbd>Shift</kbd> + <kbd>Z</kbd> | Alternative shortcut for redo. |
| Share Component | <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>S</kbd> | <kbd>⌘</kbd> + <kbd>Shift</kbd> + <kbd>S</kbd> | Shares the component. |
| Share Flow | <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>B</kbd> | <kbd>⌘</kbd> + <kbd>Shift</kbd> + <kbd>B</kbd> | Shares the entire flow. |
| Toggle Sidebar | <kbd>Ctrl</kbd> + <kbd>B</kbd> | <kbd>⌘</kbd> + <kbd>B</kbd> | Shows/hides the sidebar. |
| Search Components | <kbd>/</kbd> | <kbd>/</kbd> | Focuses the component search bar. |
| Tool Mode | <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>M</kbd> | <kbd>⌘</kbd> + <kbd>Shift</kbd> + <kbd>M</kbd> | Toggles tool mode. |
| Update | <kbd>Ctrl</kbd> + <kbd>U</kbd> | <kbd>⌘</kbd> + <kbd>U</kbd> | Updates the component. |
| Open Playground | <kbd>Ctrl</kbd> + <kbd>K</kbd> | <kbd>⌘</kbd> + <kbd>K</kbd> | Opens the playground. |
| Output Inspection | <kbd>O</kbd> | <kbd>O</kbd> | Opens output inspection. |
| Play | <kbd>P</kbd> | <kbd>P</kbd> | Plays/executes the flow. |
| API | <kbd>R</kbd> | <kbd>R</kbd> | Opens the API view. |

## Group components in the workspace

Multiple components can be grouped into a single component for reuse. This is useful when combining large flows into single components, for example RAG with a vector database, and saving space.

1. Hold <kbd>Shift</kbd> and drag to select components.

The components merge into a single component.

2. To modify the name and description of the single grouped component, in the grouped component, click the <Icon name="PencilLine" aria-label="Pencil line"/> icon.
3. Save your grouped component to the sidebar for later use.

## Component version

A component's initial state is stored in a database. As soon as you drag a component from the sidebar to the workspace, the two components are no longer in parity.

A component keeps the version number it is initialized to the workspace with. If a component is at version `1.0` when it is dragged to the workspace, it will stay at version `1.0` until you update it.

Langflow notifies you when a component's workspace version is behind the database version and an update is available.

### Review and update components

When a component's workspace version is behind the database version and an update is available, the component displays a notification.
If there are potentially breaking changes in the component updates, Langflow notifies you with an additional dialog.

Breaking changes modify component inputs and outputs, and may break your flows or require you to re-connect component edges.

An **Update ready** notification on a component indicates the component update contains no breaking changes. To update a single component, click **Update**.

An **Update available** notification indicates the component update contains potentially breaking changes.

1. To review all components with pending updates, in the component or in the dialog, click **Review**.
The **Update components** pane appears.
This pane lists components in your flow with breaking changes, and includes an option to save a flow snapshot before updating.
2. To save your flow before updating individual components, enable the **Create backup flow before updating** option.
3. To update individual components, select them in the list, and then click **Update Component**.
Your components are updated to the current version.
If you created a backup flow, it's available in the same project folder as the original flow, with `(backup)` added to its name.

## Components sidebar

Components are listed in the sidebar by component type.

**Bundles** are components grouped by provider. For example, Langchain modules like **RunnableExecutor** and **CharacterTextSplitter** are grouped under the **Langchain** bundle.

**Beta** components are still being tested and are not suitable for production workloads.

**Legacy** components are available for use but are no longer supported. By default, legacy components are hidden in the sidebar.

The sidebar includes a component **Search** bar with options for showing or hiding **Beta** and **Legacy** components.
To change the sidebar's behavior, click <Icon name="SlidersHorizontal" aria-hidden="true" /> **Component Settings**, and then show or hide **Legacy** or **Beta** components.




