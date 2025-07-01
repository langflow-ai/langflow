---
title: Import and export flows
slug: /concepts-flows-import
---

import Icon from "@site/src/components/icon";

You can import and export flows to transfer flows between Langflow instances or save backups of your flows.

## Export a flow

There are three ways to export a flow:

* From the **Projects** page, find the flow you want to export, click <Icon name="Ellipsis" aria-hidden="true" /> **More**, and then select **Export**.
* When editing a flow, click **Share**, and then click **Export**.
* Use the Langflow API [`/flows/download`](/api-flows#export-flows) endpoint.

Exported flows are downloaded to your local machine as a JSON files named `FLOW_NAME.json`.
For more information, see [Langflow JSON file contents](#langflow-json-file-contents).

### Save with my API keys

When exporting from the Langflow UI, you can select **Save with my API keys** to export the flow _and_ any defined API key variables.
Non-API key variables are included in the export regardless of the **Save with my API keys** setting.

:::warning
If you directly entered the key value into a component's API key field, then **Save with my API keys** exports the literal key value.

If your key is stored in a Langflow global variable, **Save with my API keys** exports only the variable name.
:::

When you or another user import the flow to another Langflow instance, that instance must have Langflow global variables with the same names and a valid values in order to run the flow successfully.
If any variables are missing or invalid, those variables must be created or edited after importing the flow.

### Export all flows

If you want to export all flows within a project, do either of the following:

* Go to the **Projects** page, find the project you want to export, click <Icon name="Ellipsis" aria-hidden="true" /> **Options**, and then select **Download**.
* Use the Langflow API [`/projects/download`](/api-projects#export-a-project) endpoint.

The project's flows are downloaded as JSON files in a zip archive.

## Import a flow

You can import Langflow JSON files from your local machine in the following ways:

* From the **Projects** page, click <Icon name="Upload" aria-hidden="true"/> **Upload a flow**.
* Drag and drop Langflow JSON files from your file explorer into your Langflow window to import a flow from any Langflow page.
* Use the Langflow API [`/flows/upload/`](/api-flows#import-flows) endpoint to upload one JSON file.
* Use the Langflow API [`/projects/upload`](/api-projects#import-a-project) endpoint to upload a Langflow project zip file.

### Run an imported flow

Once imported, your flow is ready to use.
If the flow contains any global variables, make sure your Langflow instance has global variables with the same names and valid values.
For more information, see [Save with my API keys](/concepts-flows-import#save-with-my-api-keys).

## Langflow JSON file contents

Exported flows are downloaded to your local machine as a JSON files named `FLOW_NAME.json`.

Langflow JSON files contain [nodes](#nodes) and [edges](#edges) that describe components and connections, and [additional metadata](#additional-metadata-and-project-information) that describe the flow.

For an example Langflow JSON file, examine the [Basic Prompting.json](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/initial_setup/starter_projects/Basic%20Prompting.json) file in the Langflow repository.

### Nodes

Nodes represent the components that make up the flow.
For example, this object represents a **Chat Input** component:

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

Each node has a unique identifier in the format of `NODE_NAME-UUID`, such as `ChatInput-jFwUm`.

Entrypoint nodes, such as the `ChatInput` node, are the first node executed when running a flow.

### Edges

Edges represent the connections between nodes.

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

* Notes are comments that help you understand the flow within the workspace.
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

## See also

* [Create flows](/concepts-flows)
* [Publish flows](/concepts-publish)