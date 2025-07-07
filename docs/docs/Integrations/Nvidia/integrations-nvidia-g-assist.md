---
title: Integrate NVIDIA G-Assist with Langflow
slug: /integrations-nvidia-g-assist
---

:::important
This component is available only for Langflow users with NVIDIA GPUs on Windows systems.
:::

The **NVIDIA G-Assist** component enables interaction with NVIDIA GPU drivers through natural language prompts.

For example, prompt G-Assist with `"What is my current GPU temperature?"` or `"Show me the available GPU memory"` to get information, and then tell G-Assist to modify your GPU settings.

For more information, see the [NVIDIA G-assist project repository](https://github.com/NVIDIA/g-assist).

## Prerequisites

* Windows operating system
* NVIDIA GPU
* `gassist.rise` package installed. This package is already installed with Langflow.

## Use the G-Assist component in a flow
1. Create a flow with a **Chat input** component, a **G-Assist** component, and a **Chat output** component.
2. Connect the **Chat input** component to the **G-Assist** component's **Prompt** input, and then connect the **G-Assist** component's output to the **Chat output** component.
3. Open the **Playground**, and then ask a question about your GPU. For example, "What is my current GPU temperature?".
The **G-Assist** component queries your GPU, and the response appears in the **Playground**.

### Inputs

The **NVIDIA G-Assist** component accepts a single input:
- `prompt`: A human-readable prompt processed by NVIDIA G-Assist.

### Outputs

The **NVIDIA G-Assist** component outputs a [Message](/docs/concepts-objects#message-object) object that contains:
- `text`: The response from NVIDIA G-Assist containing the completed operation result.
- The NVIDIA G-Assist message response is wrapped in a Langflow [Message](/docs/concepts-objects#message-object) object.