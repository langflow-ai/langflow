---
title: 'Integrate Google Cloud Vertex AI with Langflow'
slug: /integrations-setup-google-cloud-vertex-ai-langflow
sidebar_position: 2
description: "A comprehensive guide on creating a Google OAuth app, obtaining tokens, and integrating them with Langflow's Google components."
---

Langflow integrates with the [Google Vertex AI API](https://console.cloud.google.com/marketplace/product/google/aiplatform.googleapis.com) for authenticating the [Vertex AI embeddings model](/components-embedding-models#vertexai-embeddings) and [Vertex AI](/components-models#vertexai) components.

Learn how to create a service account JSON in Google Cloud to authenticate Langflow’s Vertex AI components.

## Create a project and enable the Vertex AI API

1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click **Select a project**, and then click **New Project** to create a new project.
3. To enable the Vertex AI API, navigate to the [Vertex AI API](https://console.cloud.google.com/marketplace/product/google/aiplatform.googleapis.com).
4. Select your project, and then click **Enable**.

## Create a service account

1. Navigate to **IAM & Admin**, and then click **Service Accounts**.
2. To create a new service account, click **Create Service Account**.
3. Provide a name and a description, and then click on **Create and Continue**.
4. Assign the **Vertex AI Service Agent** role to your new account.
This role allows Langflow to access Vertex AI resources.
For more information, see [Vertex AI access control with IAM](https://cloud.google.com/vertex-ai/docs/general/access-control).
5. To generate a new JSON key for the service account, navigate to your service account.
6. Click **Add Key**, and then click **Create new key**.
7. Under **Key type**, select **JSON**, and then click **Create**.
A JSON private key file is downloaded.

## Configure credentials in Langflow components

With your service account configured and your credentials JSON file created, follow these steps to authenticate the Langflow application.

1. Create a new project in Langflow.
2. From the components sidebar, drag and drop either the **Vertex AI** or **Vertex AI Embeddings** component to your workspace.
3. In the Vertex AI component's **Credentials** field, add the service account JSON file.
4. Confirm the component can access the Vertex AI resources.
Connect a **Chat input** and **Chat output** component to the Vertex AI component.
A successful chat confirms the component has access to the Vertex AI resources.

![Configure Vertex AI Credentials in Langflow](/img/google/configure-vertex-ai-credentials-in-langflow.gif)

