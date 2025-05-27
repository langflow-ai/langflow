---
title: Integrate NVIDIA System-Assist with Langflow
slug: /integrations-nvidia-system-assist
---

:::important
This component is only available for Langflow users with NVIDIA GPUs on Windows systems.
:::

The **NVIDIA System-Assist** component enables interaction with NVIDIA GPU drivers through natural language prompts.

For example, prompt System-Assist with `"What is my current GPU temperature?"` or `"Show me the available GPU memory"` to get information, and then tell System-Assist to modify your GPU settings.

For more information, see the [NVIDIA G-assist project repository](https://github.com/NVIDIA/g-assist).

## Prerequisites

* Windows operating system
* NVIDIA GPU
* `gassist.rise` package installed. This package is already installed with Langflow.

## Use the System-Assist component in a flow
1. Create a flow with a **Chat input** component, a **System-Assist** component, and a **Chat output** component.
2. Connect the **Chat input** component to the **System-Assist** component's **Prompt** input, and then connect the **System-Assist** component's output to the **Chat output** component.
3. Open the **Playground**, and then ask "What is my current GPU temperature?".
The **System-Assist** component queries your GPU, and the response appears in the **Playground**.

### Inputs

The **NVIDIA System-Assist** component accepts a single input:
- `prompt`: A human-readable prompt processed by NVIDIA System-Assist.

### Outputs

The **NVIDIA System-Assist** component outputs a [Message](/concepts-objects#message-object) object that contains:
- `text`: The response from NVIDIA System-Assist containing the completed operation result.
- The NVIDIA System-Assist message response is wrapped in a Langflow [Message](/concepts-objects#message-object) object.