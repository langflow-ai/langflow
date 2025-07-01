---
title: Components overview
slug: /concepts-components
---

import Icon from "@site/src/components/icon";

Components are the building blocks of your flows.
Like classes in an application, each component is designed for a specific use case or integration.

:::tip
Langflow provides keyboard shortcuts for the **Workspace**.

In the Langflow header, click your profile icon, select **Settings**, and then click **Shortcuts** to view the available shortcuts.
:::

## Add a component to a flow {#component-menus}

To add a component to a flow, drag the component from the **Components** menu to the [**Workspace**](/concepts-overview).

The **Components** menu is organized by component type, and some components are hidden by default:

* **Beta components**: These are Langflow's core components. They are grouped by purpose, such as **Inputs** or **Data**. Be aware that these components are in beta and not suitable for production workloads.
* **Legacy components**: You can still use these components, but they are no longer supported. Legacy components are hidden by default; click <Icon name="SlidersHorizontal" aria-hidden="true" /> **Component settings** to expose legacy components.
* **Bundles**: These components support specific integrations, and they are grouped by provider.

### Configure a component

After adding a component to a flow, configure the component's parameters and connect it to the other components in your flows.

Each component has inputs, outputs, parameters, and controls related to the component's purpose.
By default, components show only required and common options.
To access additional settings and controls, including meta settings, use the component's header menu.

To access a component's header menu, click the component in your **Workspace**.

![Agent component](/img/agent-component.png)

A few options are available directly on the header menu.
For example:

- **Code**: Modify component settings by directly editing the component's Python code.
- **Controls**: Adjust all component parameters, including optional settings that are hidden by default.
- **Tool Mode**: Enable this option when combining a component with an **Agent** component.

For all other options, including **Delete** and **Duplicate** controls, click <Icon name="Ellipsis" aria-hidden="true" /> **Show More**.

### Rename a component

To modify a component's name or description, click the component in the **Workspace**, and then click <Icon name="PencilLine" aria-hidden="true"/> **Edit**.
Component descriptions accept Markdown syntax.

### Run a component

To run a single component, click <Icon name="Play" aria-label="Play button" /> **Run component**.
A **Last Run** value indicates that the component ran successfully.

Running a single component is different from running an entire flow. In a single component run, the `build_vertex` function is called, which builds and runs only the single component with direct inputs provided through the UI (the `inputs_dict` parameter). The `VertexBuildResult` data is passed to the `build_and_run` method that calls the component's `build` method and runs it. Unlike running an entire flow, running a single component doesn't automatically execute its upstream dependencies.

### Inspect component output and logs

To view the output and logs for a single component, click <Icon name="TextSearch" aria-hidden="true" /> **Inspect**.

### Freeze a component

:::important
Freezing a component also freezes all components upstream of the selected component.
:::

Use the freeze option if you expect consistent output from a component _and all upstream components_, and you only need to run those components once.

Freezing a component prevents that component and all upstream components from re-running, and it preserves the last output state for those components.
Any future flow runs use the preserved output.

To freeze a component, click the component in the **Workspace** to expose the component's header menu, click <Icon name="Ellipsis" aria-hidden="true" /> **Show More**, and then select **Freeze**.

## Component ports

Circular port icons (<Icon name="Circle" size="16" aria-label="Circular component port icon" style={{ color: '#4f46e5', fill: '#4f46e5' }}/>) on the border of a component indicate the types of inputs and outputs that can be connected to the component at that port.

![Prompt component with multiple inputs](/img/prompt-component.png)

<!--### Dynamic ports

Some components have ports that are dynamically added or removed.
For example, the **Prompt** component accepts inputs within curly braces, and new ports are opened when a value within curly braces is detected in the **Template** field.

![Prompt component with multiple inputs](/img/prompt-component-with-multiple-inputs.png)-->

### Port colors

Component port colors indicate the data type ingested or emitted by the port.
For example, a text port either accepts or emits text data.

:::tip
Hover over a port to see connection details for that port.
:::

The following table lists the component port colors and their corresponding input types:

| Data type | Port color | Port icon example |
|-----------|--------------|----------|
| Data | Red | <Icon name="Circle" size="16" aria-label="Circular component port icon" style={{ color: '#dc2626', fill: '#dc2626' }} /> |
| DataFrame | Pink | <Icon name="Circle" size="16" aria-label="Circular component port icon" style={{ color: '#ec4899', fill:'#ec4899' }} /> |
| Embeddings | Emerald | <Icon name="Circle" size="16" aria-label="Circular component port icon" style={{ color: '#10b981', fill: '#10b981' }} /> |
| LanguageModel | Fuchsia | <Icon name="Circle" size="16" aria-label="Circular component port icon" style={{ color: '#c026d3', fill: '#c026d3' }} /> |
| Memory | Orange | <Icon name="Circle" size="16" aria-label="Circular component port icon" style={{ color: '#f97316', fill: '#f97316' }} /> |
| Message | Indigo | <Icon name="Circle" size="16" aria-label="Circular component port icon" style={{ color: '#4f46e5', fill: '#4f46e5' }} /> |
| Text | Indigo | <Icon name="Circle" size="16" aria-label="Circular component port icon" style={{ color: '#4f46e5', fill: '#4f46e5' }} /> |
| Tool | Cyan | <Icon name="Circle" size="16" aria-label="Circular component port icon" style={{ color: '#06b6d4', fill: '#06b6d4' }} /> |
| Unknown | Gray | <Icon name="Circle" size="16" aria-label="Circular component port icon" style={{ color: '#9CA3AF', fill: '#9CA3AF' }} /> |

## Component code

All components have underlying code that determines how you configure them and what actions they can perform.
In the context of creating and running flows, component code does the following:

* Determines what configuration options to show in the Langflow UI.
* Validates inputs based on the component's defined input types.
* Processes data using the configured parameters, methods, and functions.
* Passes results to the next component in the flow.

All components inherit from a base `Component` class that defines the component's interface and behavior.
For example, the [Recursive character text splitter](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/components/langchain_utilities/recursive_character.py) is a child of the [LCTextSplitterComponent](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/base/textsplitters/model.py) class.

Each component's code includes definitions for inputs and outputs, which are represented in the **Workspace** as [component ports](/concepts-components#component-ports).
For example, the `RecursiveCharacterTextSplitter` has four inputs. Each input definition specifies the input type, such as `IntInput`, as well as the encoded name, display name, description, and other parameters for that specific input.
These values determine the component settings, such as display names and tooltips in the Langflow UI.

```python
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
```

Additionally, components have methods or functions that handle their functionality.
For example, the `RecursiveCharacterTextSplitter` has two methods:

```python
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

The `get_data_input` method retrieves the text data to be split from the component's input, which makes the data available to the class.
The `build_text_splitter` method creates a `RecursiveCharacterTextSplitter` object by calling its parent class's `build` method. Then, the text is split with the created splitter and passed to the next component.

## Component versions

Component versions and states are stored in an internal Langflow database. When you add a component to a flow, you create a detached copy of the component based on the information in the Langflow database.
These copies are detached from the primary Langflow database, and they don't synchronize with any updates that can occur when you upgrade your Langflow version.

In other words, an individual instance of a component retains the version number and state from the moment you add it to a specific flow. For example, if a component is at version 1.0 when you add it to a flow, it remains at version 1.0 _in that flow_ unless you update it.

### Update component versions

When editing a flow in the **Workspace**, Langflow notifies you if a component's workspace version is behind the database version so you can update the component's workspace version:

* **Update ready**: This notification means the component update contains no breaking changes.
* **Update available**: This notification means the component update might contain breaking changes.

    Breaking changes modify component inputs and outputs, causing the components to be disconnected and break the flow. After updating the component, you might need to edit the component settings or reconnect component ports.

There are two ways to update components:

* Click **Update** to update a single component. This is recommended for updates without breaking changes.
* Click **Review** to view all available updates and create a snapshot before updating. This is recommended for updates with breaking changes.

    To save a snapshot of your flow before updating the components, enable **Create backup flow before updating**. Backup flows are stored in the same project folder as the original flow with the suffix `(backup)`.

    To update specific components, select the components you want to update, and then click **Update Components**.

Components are updated to the latest available version, based on the version of Langflow you are running.

## Group components

Multiple components can be grouped into a single component for reuse. This is useful for organizing large flows by combining related components together, such as a RAG **Agent** component and an associated vector database component.

1. Hold <kbd>Shift</kbd>, and then click and drag to highlight all components you want to merge. Components must be completely within the selection area to be merged.
2. Release the mouse and keyboard, and then click **Group** to merge the components into a single, group component.

Grouped components are configured and managed as a single component, including the component name, code, and settings.

To ungroup the components, click the component in the **Workspace** to expose the component's header menu, click <Icon name="Ellipsis" aria-hidden="true" /> **Show More**, and then select **Ungroup**.

If you want to reuse this grouping in other flows, click the component in the **Workspace** to expose the component's header menu, click <Icon name="Ellipsis" aria-hidden="true" /> **Show More**, and then select **Save** to save the component to the **Components** menu.