---
title: Voice mode
slug: /concepts-voice-mode
---

import Icon from "@site/src/components/icon";

The Langflow **Playground** supports **voice mode** for interacting with your applications through a microphone.

An [OpenAI API key](https://platform.openai.com/) is required to use **voice mode**. An [ElevenLabs](https://elevenlabs.io) API key enables more voices in the chat, but is optional.

Your flow must have a [Chat input](/components-io#chat-input) component to interact with the **Playground**.

## Prerequisite

- [An OpenAI API key](https://platform.openai.com/)

## Use voice mode in the Langflow Playground

Chat with an agent in the **Playground**, and get more recent results by asking the agent to use tools.

1. Create a [Simple agent starter project](/simple-agent).
2. Add your **OpenAI API key** credentials to the **Agent** component.
3. To start a chat session, click **Playground**.
4. To enable voice mode, click the <Icon name="Mic" aria-label="Microphone"/> icon.
The **Voice mode** pane opens.
5. In the **OpenAI API Key** field, add your **OpenAI API key** credentials.
This key is saved as a [global variable](/configuration-global-variables) in Langflow and is accessible from any component or flow.
6. Your browser may prompt you for microphone access.
Browser access is **required** to use voice mode.
To continue, allow microphone access in your browser.
7. In the **Audio Input** menu, select the input device to use with voice mode.
:::tip
A higher quality microphone improves OpenAI's voice chat comprehension.
:::
8. Optionally, add your **ElevenLabs API key** in the **ElevenLabs API Key** field.
This makes more voices available for your AI responses.
This key is saved as a [global variable](/configuration-global-variables) in Langflow and is accessible from any component or flow.
9. In the **Preferred Language** menu, select your language for conversing with Langflow.
This option changes both the spoken conversation and the chat responses in the **Playground**.
10. Talk into your microphone.
The waveform in the voice mode pane should register your input, and the agent should respond in voice and in the **Playground**.
11. Ask the agent to use the tools available to find recent news about a subject.

The agent describes its search process, including accessing the **URL** tool to fetch recent news.
The agent summarizes the recent news in speech and in the **Playground**.

Be aware of the following considerations when using voice mode:

* Name and describe your tools accurately, so the **Agent** chooses tools correctly.
* Voice mode does not use the instructions in the Agent component's **Agent Instructions** field, because your spoken instructions override this value.
* Voice mode only maintains context within the conversation session you are currently in.
If you exit a conversation and close the **Playground**, your conversational context is not available in the next chat session.

## Langflow voice mode endpoints

Langflow exposes OpenAI Realtime API-compatible websocket endpoints for your flows. You can build voice applications against these endpoints the same way you would build against [OpenAI Realtime API websockets](https://platform.openai.com/docs/guides/realtime#connect-with-websockets).

The WebSockets endpoints require an [OpenAI API key](https://platform.openai.com/docs/overview) for authentication, and they support an optional [ElevenLabs](https://elevenlabs.io) integration.

Langflow exposes two WebSockets endpoints:

* `/ws/flow_as_tool/{flow_id}` or `/ws/flow_as_tool/{flow_id}/{session_id}`: Establishes a connection to OpenAI Realtime voice, and then invokes flows as tools by the [OpenAI Realtime model](https://platform.openai.com/docs/guides/realtime-conversations#handling-audio-with-websockets).
This approach is ideal for low latency applications, but it is less deterministic since the OpenAI voice-to-voice model determines when to call your flow.

* `/ws/flow_tts/{flow_id}` or `/ws/flow_tts/{flow_id}/{session_id}`: Converts audio to text using [OpenAI Realtime voice transcription](https://platform.openai.com/docs/guides/realtime-transcription), and then each flow is invoked directly for each transcript.
This approach is more deterministic but has higher latency.
This is the mode used in the Langflow playground.

Path parameters:
* `flow_id`: Required path parameter. The ID of the flow to be used as a tool.
* `session_id`: Optional path parameter. A unique identifier for the conversation session. If not provided, one is automatically generated.