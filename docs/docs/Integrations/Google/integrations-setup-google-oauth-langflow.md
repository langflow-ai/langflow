---
title: "Setup Google OAuth for Langflow Integration"
slug: /integrations-setup-google-oauth-langflow
sidebar_position: 3
description: "A comprehensive guide on creating a Google OAuth app, obtaining tokens, and integrating them with Langflow's Google components."
---

import TOCInline from '@theme/TOCInline';

# Setting Up Google OAuth for Langflow

Quickly set up Google OAuth to integrate Google Gmail and Drive with Langflow. To do this, create an OAuth app in Google Cloud, obtain the necessary credentials and access tokens, and add them to Langflow’s Google components.

# Overview

Langflow supports OAuth for seamless integration with Google services. Just follow the setup steps to configure OAuth credentials, retrieve tokens, and connect your Google services to Langflow.

---

## Step 1: Creating an OAuth Application in Google Cloud {#5b8981b15d86192d17b0e5725c1f95e7}

1. **Access Google Cloud Console**

   - Go to the [Google Cloud Console](https://console.cloud.google.com/).

2. **Create or Select a Project**

   - Click **Select a project** at the top of the page and choose an existing project or create a new one.

![OAuth Client ID and Secret](/img/google/create-a-google-cloud-project.gif)

3. **Enable APIs for the Project**

   - Go to **APIs & Services > Library** and enable the APIs you need (e.g., Google Drive API, Google Gmail API).

4. **Navigate to OAuth consent screen**
   - Go to **APIs & Services >** and click on **OAuth consent screen**.
5. **Set Up OAuth Consent Screen**

   - On the OAuth consent screen, set up essential app details like the application name, user support email, required [scopes](https://developers.google.com/identity/protocols/oauth2/scopes) (permissions your app needs), and authorized domains.
   - Ensure you **publish** the app if it’s not restricted to internal use.

![OAuth Consent Screen](/img/google/setup-oauth-consent-screen.png)

:::info

- Configuring the OAuth consent screen is crucial for obtaining user permissions.

::::

6. **Create OAuth Client ID**

   - Go back to **Credentials**, select **Create Credentials > OAuth Client ID**.
   - Choose **Desktop app** as the application type.

7. **Save OAuth Client ID and Client Secret**

   - After creating, you'll receive a Client ID and Client Secret. You can either view them directly or download them as a JSON file. Please download and save this information securely, as it's essential for using Langflow.

![OAuth Client ID and Secret](/img/google/create-oauth-client-id.png)

---

## Step 2: Retrieving Access and Refresh Tokens

With your OAuth application configured and with your Client ID created, follow these steps to obtain the tokens:

1. **Authenticate the Application**

   - Create a new project in Langflow.
   - Add a Google OAuth Token component.
   - Input in the field **Credentials File** on the Google OAuth Token component, the JSON file containing the Client ID credentials you downloaded from Google in the [previous steps](#5b8981b15d86192d17b0e5725c1f95e7).
   - Run the Google OAuth Token component to authenticate your application.

:::info

- Note that when the component is executed, a new tab maybe open in the browser so that you can authenticate using your Google Cloud account where you created the project containing the OAuth Application, the credentials and activated the API that you need to use.
- If a new tab does not open automatically, check the Langflow **Logs** for the Google authentication URL. Open this URL in your browser to complete the authentication. Only after authenticating will the JSON token be generated.

  :::

2. **Refresh Tokens**

   - After successful authentication, your Langflow application can request and refresh tokens for your app. These tokens will enable Langflow to interact with Google services on your behalf and execute the requests you’ve specified.
   - By default, token validity is managed by Google’s servers. In Langflow, tokens refresh automatically after initial authentication. However, if your application is inactive for an extended period, the tokens may expire, requiring you to re-authenticate to resume use in Langflow.

---

## Step 3: Configuring Google Components in Langflow

In this example, we will use the Google Drive Loader component to load a text file hosted on Google Drive, translate the text in it to Spanish, and return it to a chat output.

1. **Open Langflow and Add Google Drive Loader Component**

   - In Langflow, go to your flow editor and add a **Google Drive Loader** component.

2. **Enter OAuth Credentials**

   - In the `JSON String of the Service Account Token` or `Token String` field of the Google Drive Loader component, enter your JSON string containing the token returned in the output of the Google OAuth Token component. Remember to convert the data output from the Google OAuth Token component to text using the `Parse Data` component.

3. **Getting File ID from Google Drive**

   Steps to Obtain the Google Drive File ID from a URL:

   1. **Copy the Google Drive URL:**

      - Open the document in Google Drive and copy the link from the address bar.

   2. **Identify the Document ID:**

      - The file ID is located between `/d/` and `/edit` in the URL. Example:

      ```
      https://drive.google.com/file/d/1a2b3c4D5E6F7gHI8J9klmnopQ/edit
      ```

      Here, the ID is `1a2b3c4D5E6F7gHI8J9klmnopQ`.

   3. **Enter the ID in the Component:**

      - In Langflow, paste the copied ID to field Document ID in Google Drive Loader component to allow the component to access the file.

4. **Test the Connection**

   - After adding credentials and Document ID, test the component’s functionality within your flow to ensure a successful connection.

---

## Step 4: Using Google Components in Your Flow

With OAuth successfully configured, you can now use Google components in Langflow to automate tasks:

- **Gmail Loader**  
   Loads emails from Gmail using the provided credentials.
- **Google Drive Loader**  
   Loads documents from Google Drive using provided credentials.
- **Google Drive Search**  
   Searches Google Drive files using provided credentials and query parameters.

Each component will utilize your OAuth tokens to perform these actions seamlessly.

## Flow Example

You can use the Flow below as a starting example for your tests.

- Flow Google Drive Docs Translations Example -
  (<a href="./files/Google_Drive_Docs_Translations_Example.json" download>Download link</a>)

---

## Troubleshooting Common Issues

- **Token Expiration**: Ensure to refresh your tokens periodically if you encounter authentication errors.
- **Permission Errors**: Double-check your OAuth consent settings and scopes in your Google Cloud account as well as in your Langflow component settings to ensure you’ve granted the necessary permissions.
- **A new window for authentication did not open?**: Don't worry, you can check the Langflow Logs and look for the following text below.

  Example:

  ```
  Please visit this URL to authorize this application: https://accounts.google.com/o/oauth2/auth?response_type=code&client_id=156549873216-fa86b6a74ff8ee9a69d2b98e0bc478e8.apps.googleusercontent.com&redirect_uri=http%3A%2F%2Flocalhost%3A54899%2F&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive.readonly&state=75gxTJWwpUZjSWeyWDL81BmJAzGt1Q&access_type=offline
  ```

---

By following these steps, your Langflow environment will be fully integrated with Google services, providing a powerful tool for automating workflows that involve Google Gmail, Drive, and more.
