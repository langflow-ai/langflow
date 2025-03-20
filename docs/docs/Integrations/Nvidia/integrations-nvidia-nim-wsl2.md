---
title:  Integrate Nvidia NIMs with Langflow
slug: /integrations-nvidia-ingest-wsl2
---

Connect **Langflow** with **NVIDIA NIM** on an RTX Windows system with Windows Subsystem for Linux 2 (WSL2) installed.

[NVIDIA NIM](https://developer.nvidia.com/nim) provides containers to self-host GPU-accelerated inferencing microservices.
This example deploys the `mistral-nemo-12b-instruct` NIM on an **RTX Windows system** with WSL2 and uses it as a model component in **Langflow**.

For more on NVIDIA NIM, see the [NVIDIA documentation](https://developer.nvidia.com/nim).

Nvidia

## Prerequisites

* [NVIDIA NIM WSL2 installed](https://docs.nvidia.com/nim/wsl2/latest/getting-started.html)
* A NIM container deployed. The prerequisites vary between models.
For example, to deploy the `mistral-nemo-12b-instruct` NIM, follow the instructions for **Windows on RTX AI PCs (Beta)** on your [model's deployment overview](https://build.nvidia.com/nv-mistralai/mistral-nemo-12b-instruct/deploy?environment=wsl2.md)
* Windows 11 build 23H2 (and later)
* At least 12 GB of RAM

## Use the NVIDIA NIM in a flow

To connect the NIM you've deployed with Langflow, add the **NVIDIA on WSL2** model component to a flow.

1. Create a [basic prompting flow](/get-started-quickstart).
2. Replace the **OpenAI** model component with the **NVIDIA on WSL** component.
3. In the **NVIDIA on WSL** component's **Model Name** field, select the deployed NIM model.
4. Open the **Playground** and chat with your **NIM** model.


