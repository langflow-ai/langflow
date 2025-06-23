---
title: Logic
slug: /components-logic
---

# Logic components in Langflow

Logic components provide functionalities for routing, conditional processing, and flow management.

## Use a logic component in a flow

This flow creates a summarizing "for each" loop with the [Loop](/components-logic#loop) component.

The component iterates over a list of [Data](/concepts-objects#data-object) objects until it's completed, and then the **Done** loop aggregates the results.

The **File** component loads text files from your local machine, and then the **Parser** component parses them into a list of structured `Data` objects.
The **Loop** component passes each `Data` object to a **Prompt** to be summarized.

When the **Loop** component runs out of `Data`, the **Done** loop activates, which counts the number of pages and summarizes their tone with another **Prompt**.
This is represented in Langflow by connecting the Parser component's **Data List** output to the Loop component's `Data` loop input.

![Sample Flow looping summarizer](/img/loop-text-summarizer.png)

The output is similar to this:
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

This component routes messages by comparing two strings.
It evaluates a condition by comparing two text inputs using the specified operator and routes the message to `true_result` or `false_result`.

The operator looks for single strings based on your defined [operator behavior](#operator-behavior), but it can also search for multiple words by regex matching.

To use the **Conditional router** component to check incoming messages with regex matching, do the following:

1. Connect the **If-Else** component's **Text Input** port to a **Chat Input** component.
2. In the If-Else component, enter the following values.
* In the **Match Text** field, enter `.*(urgent|warning|caution).*`. The component looks for these values. The regex match is case sensitive, so to look for all permutations of `warning`, enter `warning|Warning|WARNING`.
* In the **Operator** field, enter `regex`. The component looks for the strings `urgent`, `warning`, and `caution`. For more operators, see [Operator behavior](#operator-behavior).
* In the **Message** field, enter `New Message Detected`. This field is optional. The message is sent to both the **True** and **False** ports.
The component is now set up to send a `New Message Detected` message out of its **True** port if it matches any of the strings.
If no strings are detected, it sends a message out of the **False** port.
3. Create two identical flows to process the messages. Connect an **Open AI** component, a **Prompt**, and a **Chat Output** component together.
4. Connect one chain to the **If-Else** component's **True** port, and one chain to the **False** port.

The flow looks like this:

![A conditional router connected to two OpenAI components](/img/component-conditional-router.png)

5. Add your **OpenAI API key** to both **OpenAI** components.
6. In both **Prompt** components, enter the behavior you want each route to take.
When a match is found:
```text
Send a message that a new message has been received and added to the Urgent queue.
```
When a match is not found:
```text
Send a message that a new message has been received and added to the backlog.
```
7. Open the **Playground**.
8. Send the flow some messages. Your messages route differently based on the if-else component's evaluation.
```
User
A new user was created.

AI
A new message has been received and added to the backlog.

User
Sign-in warning: new user locked out.

AI
A new message has been received and added to the Urgent queue. Please review it at your earliest convenience.
```

<details>
<summary>Parameters</summary>

**Inputs**

| Name           | Type     | Description                                                       |
|----------------|----------|-------------------------------------------------------------------|
| input_text     | String   | The primary text input for the operation. |
| match_text     | String   | The text to compare against. |
| operator       | Dropdown | The operator used to compare texts. Options include equals, not equals, contains, starts with, ends with, and regex. The default is equals. |
| case_sensitive | Boolean  | When set to true, the comparison is case sensitive. This setting does not apply to regex comparison. The default is false. |
| message        | Message  | The message to pass through either route. |
| max_iterations | Integer  | The maximum number of iterations allowed for the conditional router. The default is 10. |
| default_route  | Dropdown | The route to take when max iterations are reached. Options include true_result or false_result. The default is false_result. |

**Outputs**

| Name         | Type    | Description                                |
|--------------|---------|--------------------------------------------|
| true_result  | Message | The output produced when the condition is true. |
| false_result | Message | The output produced when the condition is false. |

</details>

### Operator Behavior

The **If-else** component includes a comparison operator to compare the values in `input_text` and `match_text`.

All options respect the `case_sensitive` setting except **regex**.

- **equals**: Exact match comparison.
- **not equals**: Inverse of exact match.
- **contains**: Checks if match_text is found within input_text.
- **starts with**: Checks if input_text begins with match_text.
- **ends with**: Checks if input_text ends with match_text.
- **regex**: Performs regular expression matching. It is always case sensitive and ignores the case_sensitive setting.

## Listen

This component listens for a notification and retrieves its associated state.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type   | Description                                    |
|------|--------|------------------------------------------------|
| name | String | The name of the notification to listen for. |

**Outputs**

| Name   | Type | Description                                |
|--------|------|--------------------------------------------|
| output | Data | The state associated with the notification. |

</details>

## Loop

:::tip
For another **Loop** component example, see the **Research Translation Loop** template.
:::

This component iterates over a list of [Data](/concepts-objects#data-object) objects, outputting one item at a time and aggregating results from loop inputs.

In this example, the **Loop** component iterates over a CSV file through the **Item** port until there are no rows left to process. Then, the **Loop** component performs the actions connected to the **Done** port, which in this case is loading the structured data into **Chroma DB**.

Think of it this way: the **Item** port forms the "main" loop that repeats until a "complete" condition is reached.

1. The **Loop** component accepts **Data** from the **Load CSV** component, and outputs the data from the **Item** port.
2. Each CSV row is converted to a **Message** and processed into structured data with the **Structured Output** component.
The dotted line connected from the **Structured Output** component's **Looping** port tells you where the loop begins again.
3. The **Loop** component repeatedly extracts rows by **Text Key** until there are no more rows to extract.

Once all items are processed, the action connected to the **Done** port is performed.
In this example, the data is loaded into **Chroma DB**.

![Loop CSV parser](/img/component-loop-csv.png)

Follow along with this step-by-step video guide for creating this flow and adding agentic RAG: [Mastering the Loop Component & Agentic RAG in Langflow](https://www.youtube.com/watch?v=9Wx7WODSKTo).

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Type      | Description                                          |
|------|-----------|------------------------------------------------------|
| data | Data/List | The initial list of Data objects to process. |

**Outputs**

| Name | Type    | Description                                           |
|------|---------|-------------------------------------------------------|
| item | Data    | The current item being processed from the data list. |
| done | Data    | The aggregated results after all items are processed. |

</details>

## Notify

This component generates a notification for the Listen component to use.

<details>
<summary>Parameters</summary>

**Inputs**

| Name   | Type    | Description                                                       |
|--------|---------|-------------------------------------------------------------------|
| name   | String  | The name of the notification. |
| data   | Data    | The data to store in the notification. |
| append | Boolean | When set to true, the record is added to the existing notification. |

**Outputs**

| Name   | Type | Description                             |
|--------|------|-----------------------------------------|
| output | Data | The data stored in the notification. |

</details>

## Run flow

This component allows you to run any flow stored in your Langflow database without opening the flow editor.

The Run Flow component can also be used as a tool when connected to an [Agent](/components-agents). The `name` and `description` metadata that the Agent uses to register the tool are created automatically.

When you select a flow, the component fetches the flow's graph structure and uses it to generate the inputs and outputs for the Run Flow component.

To use the Run Flow component as a tool, do the following:
1. Add the **Run Flow** component to the [Simple Agent](/simple-agent) flow.
2. In the **Flow Name** menu, select the sub-flow you want to run.
The appearance of the **Run Flow** component changes to reflect the inputs and outputs of the selected flow.
3. On the **Run Flow** component, enable **Tool Mode**.
4. Connect the **Run Flow** component to the **Toolset** input of the Agent.
Your flow should now look like this:
![Run Flow component](/img/component-run-flow.png)
5. Run the flow. The Agent uses the Run Flow component as a tool to run the selected sub-flow.

<details>
<summary>Parameters</summary>

**Inputs**

| Name              | Type     | Description                                                    |
|-------------------|----------|----------------------------------------------------------------|
| flow_name_selected| Dropdown | The name of the flow to run.                                    |
| flow_tweak_data   | Dict     | Dictionary of tweaks to customize the flow's behavior.         |
| dynamic inputs  | Various  | Additional inputs that are generated based on the selected flow.     |

**Outputs**

| Name         | Type        | Description                                                   |
|--------------|-------------|---------------------------------------------------------------|
| run_outputs  | A `List` of types `Data`, `Message,` or `DataFrame`  | All outputs are generated from running the flow.                   |

</details>

## Legacy components

**Legacy** components are available for use but are no longer supported.

### Data Conditional Router

:::important
This component is in **Legacy**, which means it is no longer in active development as of Langflow version 1.3.
:::

This component routes `Data` objects based on a condition applied to a specified key, including boolean validation. It can process either a single Data object or a list of Data objects.

This component is particularly useful in workflows that require conditional routing of complex data structures, enabling dynamic decision-making based on data content.

#### Inputs

| Name          | Type     | Description                                                                       |
|---------------|----------|-----------------------------------------------------------------------------------|
| data_input    | Data     | The Data object or list of Data objects to process. This input can handle both single items and lists. |
| key_name      | String   | The name of the key in the Data object to check.                                  |
| operator      | Dropdown | The operator to apply. Options: "equals", "not equals", "contains", "starts with", "ends with", "boolean validator". Default: "equals". |
| compare_value | String   | The value to compare against. Not shown/used when operator is "boolean validator". |

#### Outputs

| Name         | Type        | Description                                          |
|--------------|-------------|------------------------------------------------------|
| true_output  | Data/List   | Output when the condition is met.                    |
| false_output | Data/List   | Output when the condition is not met.                |

#### Operator behavior

- **equals**: Exact match comparison between the key's value and compare_value.
- **not equals**: Inverse of exact match.
- **contains**: Checks if compare_value is found within the key's value.
- **starts with**: Checks if the key's value begins with compare_value.
- **ends with**: Checks if the key's value ends with compare_value.
- **boolean validator**: Treats the key's value as a boolean. The following values are considered true:
  - Boolean `true`.
  - Strings: "true", "1", "yes", "y", "on" (case-insensitive).
  - Any other value is converted using Python's `bool()` function.

#### List processing

The following actions occur when processing a list of Data objects:
- Each object in the list is evaluated individually
- Objects meeting the condition go to true_output
- Objects not meeting the condition go to false_output
- If all objects go to one output, the other output is empty

### Pass

:::important
This component is in **Legacy**, which means it is available for use but no longer in active development.
:::

This component forwards the input message, unchanged.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
| input_message | Input Message | The message to forward. |
| ignored_message | Ignored Message | A second message that is ignored. Used as a workaround for continuity. |

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
| output_message | Output Message | The forwarded message from the input. |

</details>

## Deprecated components

Deprecated components have been replaced by newer alternatives and should not be used in new projects.

### Flow as tool {#flow-as-tool}

:::important
This component is deprecated as of Langflow version 1.1.2.
Instead, use the [Run flow component](/components-logic#run-flow)
:::

This component constructs a tool from a function that runs a loaded flow.

#### Inputs

| Name             | Type     | Description                                                |
|------------------|----------|------------------------------------------------------------|
| flow_name        | Dropdown | The name of the flow to run.                               |
| tool_name        | String   | The name of the tool.                                      |
| tool_description | String   | The description of the tool.                               |
| return_direct    | Boolean  | If true, returns the result directly from the tool.        |

#### Outputs

| Name           | Type | Description                            |
|----------------|------|----------------------------------------|
| api_build_tool | Tool | The constructed tool from the flow.    |

### Sub flow

:::important
This component is deprecated as of Langflow version 1.1.2.
Instead, use the [Run flow component](/components-logic#run-flow)
:::

This `SubFlowComponent` generates a component from a flow with all of its inputs and outputs.

This component can integrate entire flows as components within a larger workflow. It dynamically generates inputs based on the selected flow and executes the flow with provided parameters.

#### Inputs

| Name      | Type     | Description                        |
|-----------|----------|------------------------------------|
| flow_name | Dropdown | The name of the flow to run.       |

#### Outputs

| Name         | Type        | Description                           |
|--------------|-------------|---------------------------------------|
| flow_outputs | List[Data]  | The outputs generated from the flow.  |