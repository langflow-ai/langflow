---
title: 'Setup Google Cloud Vertex AI for Langflow Integration'
slug: /integrations-setup-google-cloud-vertex-ai-langflow
sidebar_position: 2
description: "A comprehensive guide on creating a Google OAuth app, obtaining tokens, and integrating them with Langflow's Google components."
---

# Setting up Google Cloud Vertex AI for Langflow

This guide walks you through creating a Google Cloud Vertex AI API Key and configuring it in Langflow's Vertex AI component.

## Step 1: Create a New Project {#689304485d979f767f1a2ee4c8986cf6}

Go to the [https://console.cloud.google.com/projectcreate](https://console.cloud.google.com/projectcreate), enter a name for the project, and click **Create**.

![Create a new project](/img/google/create-a-new-project.png)

## Step 2: Create a Service Account

Go to [https://console.cloud.google.com/iam-admin/serviceaccounts](https://console.cloud.google.com/iam-admin/serviceaccounts), Select the project you created in the [Step 1: Create a New Project](#689304485d979f767f1a2ee4c8986cf6), and click **Create Service Account**. Provide a name, description, and then click on **Create and Continue**.

Create a new **Service Account**:

![Create a new Service Account](/img/google/create-a-new-service-account.png)

Enter **Service Account Details**:

![Enter Service Account Details](/img/google/enter-service-account-details.png)

### Step 2.1: Assign the Vertex AI Service Agent Role

Assign the **Vertex AI Service Agent** role to your new account and complete the setup.

![Assign Vertex AI Service Agent Role](/img/google/assing-vertex-ai-service-agent-role.gif)

## Step 3: Generate a New Key

Go to the **Keys** tab under your Service Account, click **Add Key > Create new key**, select **JSON**, and click **Create**. A JSON key file will be downloaded.

![Create a new private key](/img/google/create-a-new-private-key.gif)

The saved file looks like the example below:

```json
{
  "type": "service_account",
  "project_id": "mimetic-client-847522-v1",
  "private_key_id": "206a9b53bba3cea76d5a42e4eddf9410da0222d2",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDJd4y2kAfjMjIL\nuqN3fecSmrAPgxGb9q1cSf/DYnppDQv7Co7hLxD/nWHLrP5Q++Yte0IJbdIjWJOb\nfhjlkjasd152as65T7asd8z4w9vwHS03cyCcIPijujzainWEL8HgQrj8/0FSAKBd\nfhjlkjasd152as65T7asd8WlUfkrjIGUAL6psr7IOfhLuyvRS9WiYrUFvV2Hdivr\nasd846f6545NZzXOJtuZd9Wk5TSo5exO8EKNHLNUU2F7HC9KAAIXb\n3546asd656873xZt75sVubOnlPj68R4UsIl2OLFMXM12cIGwRYj2vg/\n6579ads654dasd32168L4RT9GwJGCmgE+6ZU05wvwCJtpqnfD4p9cDiK0hrL\nfhjlkjasd152as65T7asd5JjO0E8whBQKBgQD9GRXUNG8OO3BZvEOZCYE3PDP9Yc\nasd315465132a1sd6544IcVSOqfiB0/ELPjPt8V4hjEcpkdQsiSYZLbM87mQcB\n-----END PRIVATE KEY-----\n",
  "client_email": "example@mimetic-client-847522-v1.iam.gserviceaccount.com",
  "client_id": "2956348811335699541865",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/example%40mimetic-client-847522-v1.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}
```

## Step 4: Enable the Vertex AI API

Go to the [Vertex AI API page](https://console.cloud.google.com/marketplace/product/google/aiplatform.googleapis.com), select your project, and click **Enable**.

![Enable Vertex AI API](/img/google/enable-vertex-ai-api.png)

## Step 5: Configure Credentials in Langflow Components

1. Open Langflow
2. Create a new project or open an existing one
3. From the components sidebar, drag and drop either the **Vertex AI** or **Vertex AI Embeddings** component to your workspace
4. In the component settings:
   - Locate the **credentials** field
   - Click on the field
   - Browse and select the JSON credentials file containing your API key downloaded in [Step 3: Generate a New Key](#step-3-generate-a-new-key)
5. After the credentials file is loaded, the component is ready to use

![Configure Vertex AI Credentials in Langflow](/img/google/configure-vertex-ai-credentials-in-langflow.gif)

Remember to add the credentials file in the credentials field for each Vertex AI component you add to your workspace.

---
