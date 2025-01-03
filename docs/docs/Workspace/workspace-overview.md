---
title: Workspace concepts
slug: /workspace-overview
---

The **workspace** is where you create AI applications by connecting and running components in flows.

The workspace controls allow you to adjust your view and lock your flows in place.

## Components

A **component** is a single building block within a flow and consists of inputs, outputs, and parameters that define its functionality.

To add a component to your flow, drag it from the sidebar onto the workspace.

To connect components, drag a line from the output handle (⚪) of one component to the input handle of another.

For more information, see [How to build flows with components](/components-overview).

<img src="/img/prompt-component.png" alt="Prompt component" style={{display: 'block', margin: 'auto', width: 300}} />

## Playground

The **Playground** executes the current flow in the workspace.

Chat with your flow, view inputs and outputs, and modify your AI's memories to tune your responses in real time.

Either the **Chat Input** or **Chat Output** component can be opened in the **Playground** and tested in real time.

For more information, see the [Playground documentation](/workspace-playground).

![](/img/playground.png)

## API

The **API** pane provides code templates to integrate your flows into external applications.

For more information, see the [API documentation](/workspace-api).

![](/img/api-pane.png)

## Projects and folders

The **My Projects** page displays all the flows and components you've created in the Langflow workspace.

![](/img/my-projects.png)

**My Projects** is the default folder where all new projects and components are initially stored.

Projects, folders, and flows are exchanged as JSON objects.

* To create a new folder, click 📁 **New Folder**.

* To rename a folder, double-click the folder name.

* To download a folder, click 📥 **Download**.

* To upload a folder, click 📤 **Upload**. The default maximum file upload size is 100 MB.

* To move a flow or component, drag and drop it into the desired folder.

## Options menu

The dropdown menu labeled with the project name offers several management and customization options for the current flow in the Langflow workspace.

* **New**: Create a new flow from scratch.
* **Settings**: Adjust settings specific to the current flow, such as its name, description, and endpoint name.
* **Logs**: View logs for the current project, including execution history, errors, and other runtime events.
* **Import**: Import a flow or component from a JSON file into the workspace.
* **Export**: Export the current flow as a JSON file.
* **Undo (⌘Z)**: Revert the last action taken in the project.
* **Redo (⌘Y)**: Reapply a previously undone action.
* **Refresh All**: Refresh all components and delete cache.

## Settings

Click ⚙️ **Settings** to access **Global variables**, **Langflow API**, **Shortcuts**, and **Messages**.



