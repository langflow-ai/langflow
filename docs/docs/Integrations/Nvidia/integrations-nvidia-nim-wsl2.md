---
title:  Integrate NVIDIA NIMs with Langflow
slug: /integrations-nvidia-ingest-wsl2
---

Connect **Langflow** with **NVIDIA NIM** on an RTX Windows system with [Windows Subsystem for Linux 2 (WSL2)](https://learn.microsoft.com/en-us/windows/wsl/install) installed.

[NVIDIA NIM (NVIDIA Inference Microservices)](https://docs.nvidia.com/nim/index.html) provides containers to self-host GPU-accelerated inferencing microservices.
In this example, you connect a model component in **Langflow** to a deployed `mistral-nemo-12b-instruct` NIM on an **RTX Windows system** with **WSL2**.

For more information on NVIDIA NIM, see the [NVIDIA documentation](https://docs.nvidia.com/nim/index.html).

## Prerequisites

* [NVIDIA NIM WSL2 installed](https://docs.nvidia.com/nim/wsl2/latest/getting-started.html)
* A NIM container deployed according to the model's instructions. Prerequisites vary between models.
For example, to deploy the `mistral-nemo-12b-instruct` NIM, follow the instructions for **Windows on RTX AI PCs (Beta)** on your [model's deployment overview](https://build.nvidia.com/nv-mistralai/mistral-nemo-12b-instruct/deploy?environment=wsl2.md)
* Windows 11 build 23H2 or later
* At least 12 GB of RAM

## Use the NVIDIA NIM in a flow

To connect the NIM you've deployed with Langflow, add the **NVIDIA** model component to a flow.

1. Create a [basic prompting flow](/docs/get-started-quickstart).
2. Replace the **OpenAI** model component with the **NVIDIA** component.
3. In the **NVIDIA** component's **Base URL** field, add the URL where your NIM is accessible. If you followed your model's [deployment instructions](https://build.nvidia.com/nv-mistralai/mistral-nemo-12b-instruct/deploy?environment=wsl2.md), the value is `http://localhost:8000/v1`.
4. In the **NVIDIA** component's **NVIDIA API Key** field, add your NVIDIA API Key.
5. Select your model from the **Model Name** dropdown.
6. Open the **Playground** and chat with your **NIM** model.