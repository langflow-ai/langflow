---
title: Playground
sidebar_position: 1
slug: /workspace-playground
---

import ReactPlayer from "react-player";

The **Playground** is a dynamic interface designed for real-time interaction with AIs, allowing users to chat, access memories and monitor inputs and outputs. Here, users can directly prototype and their models, making adjustments and observing different outcomes.


As long as you have an [Input or Output](/components-io) component working, you can open it up by clicking the **Playground** button.


![](./1109547993.png)


:::tip

Notice how the **Playground's** window arrangement changes depending on what components are being used. Langflow can be used for applications that go beyond chat-based interfaces.

:::




You can also open a flow's **Playground** without entering its workspace. From **My Collections** or **Langflow Store**, click the **Playground** in one of the projects card.


<ReactPlayer controls url="https://prod-files-secure.s3.us-west-2.amazonaws.com/09f11537-5a5b-4f56-9e8d-de8ebcfae549/80ac6543-5548-4751-94fd-ddca60c23e62/langflow_playground.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=AKIAT73L2G45HZZMZUHI%2F20240717%2Fus-west-2%2Fs3%2Faws4_request&X-Amz-Date=20240717T012916Z&X-Amz-Expires=3600&X-Amz-Signature=cb34d17f448ff4e4d41960a509139004e4c67a2325e43eb84b2d0bbbd8cb9dbc&X-Amz-SignedHeaders=host&x-id=GetObject" />


## Memory Management {#821a5ee2a8a44d35b49943cba630511c}


---


Whenever you send a message from the **Playground** interface, under the **Memories** **Tab** you'll see a table of previous interactions for that session.


Langflow allows every chat message to be stored, and a single flow can have multiple memory sessions. To learn more about how to use memories in Langflow, see [Chat Memory](/guides-chat-memory).

