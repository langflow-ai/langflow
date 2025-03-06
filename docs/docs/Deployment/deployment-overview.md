---
title: Langflow deployment overview
slug: /deployment-overview
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

You have a flow, and want to share it with the world in a production environment.

This page outlines the journey from locally-run flow to a cloud-hosted production server.

## Langflow deployment architecture

Langflow can be deployed as an **IDE** or a **runtime**.

The **IDE** includes the frontend, for visual development of your flow.

The **runtime** is equivalent to headless or backend-only mode. The server exposes your flow as an endpoint, and serves only the backend.

Your flow is served within a container, with Postgres as the backing database. 

## Prerequisites

This guide assumes you have a running flow that you have [exported as a JSON file](/concepts-flows).

This file will be packaged with the Docker image.



## Docker compose


The Langflow repository hosts a docker-compose.yml file.

The Dockerfile includes the command `COPY ./*json /app/flows.`
Your flow exists as a .JSON file.

To include it with the

### Package flow

## Push to container registry

## Deploy to Kubernetes

