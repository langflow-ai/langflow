---
title: Voice mode
slug: /concepts-voice-mode
---

import Icon from "@site/src/components/icon";

The Langflow **Playground** supports **voice mode** for interacting with your applications through a microphone.

An [OpenAI API key](https://platform.openai.com/) is required to use **voice mode**. An [ElevenLabs](https://elevenlabs.io) API key enables more voices in the chat, but is optional.

Your flow must have a [Chat input](/components-io#chat-input) component to interact with the **Playground**.

## Prerequisite

- [OpenAI API key created](https://platform.openai.com/)

## Use voice mode in the Langflow Playground

Chat with an agent in the **Playground**, and get more recent results by asking the agent to use tools.

1. Create a [Simple agent starter project](/starter-projects-simple-agent).
2. Add your **OpenAI API key** credentials to the **Agent** component.
3. To start a chat session, click **Playground**.
4. To enable voice mode, click the <Icon name="Mic" aria-label="Microphone"/> icon.
The **Voice mode** pane opens.
5. In the **OpenAI API Key** field, add your **OpenAI API key** credentials.
6. Your browser may prompt you for microphone access.
This is **required** to use voice mode.
To continue, allow microphone access in your browser.
7. In the **Audio Input** menu, select the input device to use with voice mode.
8. Optionally, add your **ElevenLabs API key** in the **ElevenLabs API Key** field.
This makes more voices available for your AI responses.
9. Talk into your microphone.
The waveform in the voice mode pane should register your input, and the agent should respond in voice and print.
10. Ask the agent to use the tools available to find recent news about a subject.

A new chat window opens. The agent describes its search process, including accessing the **URL** tool to fetch recent news.
The agent summarizes the recent news in voice and print.