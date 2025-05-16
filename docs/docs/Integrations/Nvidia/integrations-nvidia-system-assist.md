---
title: Integrate NVIDIA System Assist with Langflow
slug: /integrations-nvidia-system-assist
---

:::important
This component is only available for Langflow users with NVIDIA GPUs on Windows systems.
:::

The NVIDIA System-Assist component is a custom Langflow component that enables interaction with NVIDIA GPU drivers through natural language prompts. This component leverages NVIDIA's Rise client to communicate with the GPU system and perform various operations.

The component allows users to check their GPU state and interact with the NVIDIA GPU Driver using natural language. For example, prompt system assist with "What is my current GPU temperature?" or "Show me the available GPU memory" to get information, then tell system assist to modify your GPU settings.

The component automatically initializes the NVIDIA Rise client on first use. You can interact with the component by providing natural language prompts that describe the desired GPU operation or query.

For more information, see the [NVIDIA G-assist project repository](https://github.com/NVIDIA/g-assist).

## Prerequisites

* Windows operating system
* NVIDIA GPU
* `gassist.rise` package installed (included with Langflow)

### Inputs

The NVIDIA System-Assist component accepts a single input:
- `prompt`: A human-readable prompt that will be processed by NVIDIA System-Assist. The prompt should describe the desired GPU operation or query in natural language.

### Outputs

The NVIDIA System-Assist component outputs a [Message](/concepts-objects#message-object) object that contains:
- `text`: The response from NVIDIA System-Assist containing the completed operation result.
- The NVIDIA System-Assist message response is wrapped in a Langflow [Message](/concepts-objects#message-object) object.