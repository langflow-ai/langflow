---
title: Flows
slug: /concepts-flows
---

import Icon from "@site/src/components/icon";

Flows in Langflow are fully serializable and can be saved and loaded from the file system. In this guide, we'll explore how to import and export flows.

## Import flow

If you already have a Langflow JSON file on your local machine, from the **Projects** page, click <Icon name="Upload" aria-hidden="true"/> **Upload a flow**.

Once imported, your flow is ready to use.

:::tip
You can drag and drop Langflow JSON files directly from your file system into the Langflow window to import a flow, even into the initial Langflow splash screen.
:::

## Export flow

To **Export** your flow, in the **Playground**, click **Share**, and then click **Export**.

Select **Save with my API keys** to save the flow with any **Global variables** included.

:::important
If your key is saved as a **Global variable**, only the global variable you created to contain the value is saved.
If your key value is manually entered into a component field, the actual key value is saved in the JSON file.
:::

When you share your flow file with another user who has the same global variables populated, the flow runs without requiring keys to be added again.

The `FLOW_NAME.json` file is downloaded to your local machine.

## Langflow JSON file contents

Langflow JSON files contain [nodes](#nodes) and [edges](#edges) that describe components and connections, and [additional metadata](#additional-metadata-and-project-information) that describe the flow.

For an example Langflow JSON file, examine the [Basic Prompting.json](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/initial_setup/starter_projects/Basic%20Prompting.json) file in the Langflow repository.

### Nodes

**Nodes** represent the components that make up the flow.

The `ChatInput` node is the entry point of the flow. It's the first node that will be executed.

`ChatInput-jFwUm` is a unique identifier for the node.

```json
{
  "data": {
    "description": "Get chat inputs from the Playground.",
    "display_name": "Chat Input",
    "id": "ChatInput-jFwUm",
    "node": {
      "base_classes": ["Message"],
      "description": "Get chat inputs from the Playground.",
      "display_name": "Chat Input",
      "icon": "MessagesSquare",
      "template": {
        "input_value": {
          "display_name": "Text",
          "info": "Message to be passed as input.",
          "value": "Hello"
        },
        "sender": {
          "value": "User",
          "options": ["Machine", "User"]
        },
        "sender_name": {
          "value": "User"
        },
        "should_store_message": {
          "value": true
        }
      }
    },
    "type": "ChatInput"
  },
  "position": {
    "x": 689.5720422421635,
    "y": 765.155834131403
  }
}
```

### Edges

**Edges** represent the connections between nodes.

The connection between the `ChatInput` node and the `OpenAIModel` node is represented as an edge:

```json
{
  "className": "",
  "data": {
    "sourceHandle": {
      "dataType": "ChatInput",
      "id": "ChatInput-jFwUm",
      "name": "message",
      "output_types": ["Message"]
    },
    "targetHandle": {
      "fieldName": "input_value",
      "id": "OpenAIModel-OcXkl",
      "inputTypes": ["Message"],
      "type": "str"
    }
  },
  "id": "reactflow__edge-ChatInput-jFwUm{œdataTypeœ:œChatInputœ,œidœ:œChatInput-jFwUmœ,œnameœ:œmessageœ,œoutput_typesœ:[œMessageœ]}-OpenAIModel-OcXkl{œfieldNameœ:œinput_valueœ,œidœ:œOpenAIModel-OcXklœ,œinputTypesœ:[œMessageœ],œtypeœ:œstrœ}",
  "source": "ChatInput-jFwUm",
  "sourceHandle": "{œdataTypeœ: œChatInputœ, œidœ: œChatInput-jFwUmœ, œnameœ: œmessageœ, œoutput_typesœ: [œMessageœ]}",
  "target": "OpenAIModel-OcXkl",
  "targetHandle": "{œfieldNameœ: œinput_valueœ, œidœ: œOpenAIModel-OcXklœ, œinputTypesœ: [œMessageœ], œtypeœ: œstrœ}"
}
```

This edge shows that the `ChatInput` component outputs a `Message` type to the `target` node, which is the `OpenAIModel` node.
The `OpenAIModel` component accepts the `Message` type at the `input_value` field.

### Additional metadata and project information

Additional information about the flow is stored in the root `data` object.

* Metadata and project information including the name, description, and `last_tested_version` of the flow.
```json
{
  "name": "Basic Prompting",
  "description": "Perform basic prompting with an OpenAI model.",
  "tags": ["chatbots"],
  "id": "1511c230-d446-43a7-bfc3-539e69ce05b8",
  "last_tested_version": "1.0.19.post2",
  "gradient": "2",
  "icon": "Braces"
}
```

* Visual information about the flow defining the initial position of the flow in the workspace.
```json
"viewport": {
  "x": -37.61270157375441,
  "y": -155.91266341888854,
  "zoom": 0.7575251406952855
}
```

**Notes** are like comments to help you understand the flow within the workspace.
They may contain links, code snippets, and other information.
Notes are written in Markdown and stored as `node` objects.
```json
{
  "id": "undefined-kVLkG",
  "node": {
    "description": "## 📖 README\nPerform basic prompting with an OpenAI model.\n\n#### Quick Start\n- Add your **OpenAI API key** to the **OpenAI Model**\n- Open the **Playground** to chat with your bot.\n..."
  }
}
```

