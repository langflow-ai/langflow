---
title: Logic
slug: /components-logic
---

# Logic components in Langflow

Logic components provide functionalities for routing, conditional processing, and flow management.

## Conditional router

This component routes an input message to a corresponding output based on text comparison.

The ConditionalRouterComponent routes messages based on text comparison. It evaluates a condition by comparing two text inputs using a specified operator and routes the message accordingly.

### Inputs

| Name           | Type     | Description                                                       |
|----------------|----------|-------------------------------------------------------------------|
| input_text     | String   | The primary text input for the operation.                         |
| match_text     | String   | The text input to compare against.                                |
| operator       | Dropdown | The operator to apply for comparing the texts.                    |
| case_sensitive | Boolean  | If true, the comparison will be case sensitive.                   |
| message        | Message  | The message to pass through either route.                         |
| max_iterations | Integer  | The maximum number of iterations for the conditional router.      |
| default_route  | Dropdown | The default route to take when max iterations are reached.        |

### Outputs

| Name         | Type    | Description                                |
|--------------|---------|--------------------------------------------|
| true_result  | Message | The output when the condition is true.     |
| false_result | Message | The output when the condition is false.    |

## Data conditional router

This component routes `Data` objects based on a condition applied to a specified key, including boolean validation.

This component is particularly useful in workflows that require conditional routing of complex data structures, enabling dynamic decision-making based on data content.

### Inputs

| Name          | Type     | Description                                                                       |
|---------------|----------|-----------------------------------------------------------------------------------|
| data_input    | Data     | The data object or list of data objects to process.                               |
| key_name      | String   | The name of the key in the data object to check.                               |
| operator      | Dropdown | The operator to apply for comparing the values.                                   |
| compare_value | String   | The value to compare against (not used for boolean validator).                    |

### Outputs

| Name         | Type        | Description                                          |
|--------------|-------------|------------------------------------------------------|
| true_output  | Data/List   | Output when the condition is met.                    |
| false_output | Data/List   | Output when the condition is not met.                |


## Flow as Tool {#flow-as-tool}

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

## Run flow

This component allows you to run a specified flow with given inputs and tweaks.

The RunFlowComponent executes a specified flow within a larger workflow. It provides the ability to run a flow with custom inputs and apply tweaks to modify its behavior.

### Inputs

| Name        | Type         | Description                                           |
|-------------|--------------|-------------------------------------------------------|
| input_value | String       | The input value for the flow to process.          |
| flow_name   | Dropdown     | The name of the flow to run.                          |
| tweaks      | Nested Dict  | Tweaks to apply to the flow.                          |

### Outputs

| Name        | Type        | Description                                    |
|-------------|-------------|------------------------------------------------|
| run_outputs | List[Data]  | The results generated from running the flow.   |

## Sub Flow

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





