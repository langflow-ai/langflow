---
title:  Integrate NVIDIA System Assist with Langflow
slug: /integrations-nvidia-system-assist
---

The NVIDIA System-Assist component is a custom Langflow component that enables interaction with NVIDIA GPU drivers through natural language prompts. This component leverages NVIDIA's Rise client to communicate with the GPU system and perform various operations.

The component allows users to check their GPU state and interact with the NVIDIA GPU Driver using natural language. For example, prompt system assist with "What is my current GPU temperature?" or "Show me the available GPU memory" to get information, then tell system assist to modify your GPU settings.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| prompt | System-Assist Prompt | A human-readable prompt that will be processed by NVIDIA System-Assist. The prompt should describe the desired GPU operation or query in natural language. |

### Outputs

The NVIDIA System-Assist component outputs a [Message](/concepts-objects#message-object) object that contains:
- `text`: The response from NVIDIA System-Assist containing the completed operation result.
- The NVIDIA System-Assist message is response is wrapped in a Langflow [Message](/concepts-objects#message-object) object for consistent handling in the flow.

## Usage

The component automatically initializes the Rise client on first use. Users can interact with it by providing natural language prompts that describe the desired GPU operation or query.

