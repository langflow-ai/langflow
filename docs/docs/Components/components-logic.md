---
title: Logic
slug: /components-logic
---

# Logic components in Langflow

Logic components provide functionalities for routing, conditional processing, and flow management.

## Use a logic component in a flow

This flow creates a summarizing "for each" loop with the [Loop](/components-logic#loop) component.

The component iterates over a list of [Data](/concepts-objects#data-object) objects until it's completed, and then the **Done** loop aggregates the results.

The **File** component loads text files from your local machine, and then the **Parse Data** component parses them into a list of structured `Data` objects.
The **Loop** component passes each `Data` object to a **Prompt** to be summarized.

When the **Loop** component runs out of `Data`, the **Done** loop activates, which counts the number of pages and summarizes their tone with another **Prompt**.
This is represented in Langflow by connecting the Parse Data component's **Data List** output to the Loop component's `Data` loop input.

![Sample Flow looping summarizer](/img/loop-text-summarizer.png)

The output will look similar to this:
```text
Document Summary
Total Pages Processed
Total Pages: 2
Overall Tone of Document
Tone: Informative and Instructional
The documentation outlines microservices architecture patterns and best practices.
It emphasizes service isolation and inter-service communication protocols.
The use of asynchronous messaging patterns is recommended for system scalability.
It includes code examples of REST and gRPC implementations to demonstrate integration approaches.
```

## Conditional router (If-Else component)

This component routes messages by comparing two strings. It evaluates a condition by comparing two text inputs using the specified operator and routes the message to `true_result` or `false_result`.

### Inputs

| Name           | Type     | Description                                                       |
|----------------|----------|-------------------------------------------------------------------|
| input_text     | String   | The primary text input for the operation.                         |
| match_text     | String   | The text input to compare against.                                |
| operator       | Dropdown | The operator to compare texts. Options: "equals", "not equals", "contains", "starts with", "ends with", "regex". Default: "equals". |
| case_sensitive | Boolean  | If true, the comparison is case sensitive. This setting is ignored for regex comparison. Default: false. |
| message        | Message  | The message to pass through either route.                         |
| max_iterations | Integer  | (Advanced) The maximum number of iterations for the conditional router. Default: 10. |
| default_route  | Dropdown | (Advanced) The default route to take when max iterations are reached. Options: "true_result" or "false_result". Default: "false_result". |

### Outputs

| Name         | Type    | Description                                |
|--------------|---------|--------------------------------------------|
| true_result  | Message | The output when the condition is true.     |
| false_result | Message | The output when the condition is false.    |

### Operator Behavior

The **If-else** component includes a comparison operator to compare the values in `input_text` and `match_text`.

All options respect the `case_sensitive` setting except **regex**.

- **equals**: Exact match comparison
- **not equals**: Inverse of exact match
- **contains**: Checks if match_text is found within input_text
- **starts with**: Checks if input_text begins with match_text
- **ends with**: Checks if input_text ends with match_text
- **regex**: Performs regular expression matching. It is always case sensitive and ignores the case_sensitive setting.

## Data Conditional Router

:::important
This component is in **Legacy**, which means it is no longer in active development as of Langflow version 1.3.
:::

This component routes `Data` objects based on a condition applied to a specified key, including boolean validation. It can process either a single Data object or a list of Data objects.

This component is particularly useful in workflows that require conditional routing of complex data structures, enabling dynamic decision-making based on data content.

### Inputs

| Name          | Type     | Description                                                                       |
|---------------|----------|-----------------------------------------------------------------------------------|
| data_input    | Data     | The Data object or list of Data objects to process. Can handle both single items and lists. |
| key_name      | String   | The name of the key in the Data object to check.                                  |
| operator      | Dropdown | The operator to apply. Options: "equals", "not equals", "contains", "starts with", "ends with", "boolean validator". Default: "equals". |
| compare_value | String   | The value to compare against. Not shown/used when operator is "boolean validator". |

### Outputs

| Name         | Type        | Description                                          |
|--------------|-------------|------------------------------------------------------|
| true_output  | Data/List   | Output when the condition is met.                    |
| false_output | Data/List   | Output when the condition is not met.                |

### Operator Behavior

- **equals**: Exact match comparison between the key's value and compare_value
- **not equals**: Inverse of exact match
- **contains**: Checks if compare_value is found within the key's value
- **starts with**: Checks if the key's value begins with compare_value
- **ends with**: Checks if the key's value ends with compare_value
- **boolean validator**: Treats the key's value as a boolean. The following values are considered true:
  - Boolean `true`
  - Strings: "true", "1", "yes", "y", "on" (case-insensitive)
  - Any other value is converted using Python's `bool()` function

### List Processing

The following actions occur when processing a list of Data objects:
- Each object in the list is evaluated individually
- Objects meeting the condition go to true_output
- Objects not meeting the condition go to false_output
- If all objects go to one output, the other output is empty

## Flow as tool {#flow-as-tool}

:::important
This component is deprecated as of Langflow version 1.1.2.
Instead, use the [Run flow component](/components-logic#run-flow)
:::

This component constructs a tool from a function that runs a loaded flow.

### Inputs

| Name             | Type     | Description                                                |
|------------------|----------|------------------------------------------------------------|
| flow_name        | Dropdown | The name of the flow to run.                               |
| tool_name        | String   | The name of the tool.                                      |
| tool_description | String   | The description of the tool.                               |
| return_direct    | Boolean  | If true, returns the result directly from the tool.        |

### Outputs

| Name           | Type | Description                            |
|----------------|------|----------------------------------------|
| api_build_tool | Tool | The constructed tool from the flow.    |

## Listen

This component listens for a notification and retrieves its associated state.

### Inputs

| Name | Type   | Description                                    |
|------|--------|------------------------------------------------|
| name | String | The name of the notification to listen for.    |

### Outputs

| Name   | Type | Description                                |
|--------|------|--------------------------------------------|
| output | Data | The state associated with the notification. |


## Loop

This component iterates over a list of [Data](/concepts-objects#data-object) objects, outputting one item at a time and aggregating results from loop inputs.

### Inputs

| Name | Type      | Description                                          |
|------|-----------|------------------------------------------------------|
| data | Data/List | The initial list of Data objects to iterate over.    |

### Outputs

| Name | Type    | Description                                           |
|------|---------|-------------------------------------------------------|
| item | Data    | Outputs one item at a time from the data list.        |
| done | Data    | Triggered when iteration complete, returns aggregated results. |

## Notify

This component generates a notification for the Listen component to use.

### Inputs

| Name   | Type    | Description                                                       |
|--------|---------|-------------------------------------------------------------------|
| name   | String  | The name of the notification.                                     |
| data   | Data    | The data to store in the notification.                            |
| append | Boolean | If true, the record will be appended to the existing notification.|

### Outputs

| Name   | Type | Description                             |
|--------|------|-----------------------------------------|
| output | Data | The data stored in the notification.    |

## Pass message

This component forwards the input message, unchanged.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| input_message | Input Message | The message to be passed forward. |
| ignored_message | Ignored Message | A second message to be ignored. Used as a workaround for continuity. |

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
| output_message | Output Message | The forwarded input message. |

## Run flow

This component allows you to run any flow stored in your Langflow database without opening the flow editor.

The Run Flow component can also be used as a tool when connected to an [Agent](/components-agents). The `name` and `description` metadata that the Agent uses to register the tool are created automatically.

When you select a flow, the component fetches the flow's graph structure and uses it to generate the inputs and outputs for the Run Flow component.

To use the Run Flow component as a tool, do the following:
1. Add the **Run Flow** component to the [Simple Agent](/starter-projects-simple-agent) flow.
2. In the **Flow Name** menu, select the sub-flow you want to run.
The appearance of the **Run Flow** component changes to reflect the inputs and outputs of the selected flow.
3. On the **Run Flow** component, enable **Tool Mode**.
4. Connect the **Run Flow** component to the **Toolset** input of the Agent.
Your flow should now look like this:
![Run Flow component](/img/component-run-flow.png)
5. Run the flow. The Agent uses the Run Flow component as a tool to run the selected sub-flow.

### Inputs

| Name              | Type     | Description                                                    |
|-------------------|----------|----------------------------------------------------------------|
| flow_name_selected| Dropdown | The name of the flow to run.                                    |
| flow_tweak_data   | Dict     | Dictionary of tweaks to customize the flow's behavior.         |
| dynamic inputs  | Various  | Additional inputs that are generated based on the selected flow.     |

### Outputs

| Name         | Type        | Description                                                   |
|--------------|-------------|---------------------------------------------------------------|
| run_outputs  | A `List` of types `Data`, `Message,` or `DataFrame`  | All outputs are generated from running the flow.                   |

## Sub flow

:::important
This component is deprecated as of Langflow version 1.1.2.
Instead, use the [Run flow component](/components-logic#run-flow)
:::

This `SubFlowComponent` generates a component from a flow with all of its inputs and outputs.

This component can integrate entire flows as components within a larger workflow. It dynamically generates inputs based on the selected flow and executes the flow with provided parameters.

### Inputs

| Name      | Type     | Description                        |
|-----------|----------|------------------------------------|
| flow_name | Dropdown | The name of the flow to run.       |

### Outputs

| Name         | Type        | Description                           |
|--------------|-------------|---------------------------------------|
| flow_outputs | List[Data]  | The outputs generated from the flow.  |





