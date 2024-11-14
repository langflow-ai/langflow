---
title: Integrate Google OAuth with Langflow
slug: /integrations-setup-google-oauth-langflow
sidebar_position: 3
description: "A comprehensive guide on creating a Google OAuth app, obtaining tokens, and integrating them with Langflow's Google components."
---

import TOCInline from '@theme/TOCInline';

Langflow integrates with [Google OAuth](https://developers.google.com/identity/protocols/oauth2) for authenticating the [Gmail Loader](/components-data#gmail-loader), [Google Drive Loader](components-data#google-drive-loader), and [Google Drive Search](/components-data#google-drive-search) components.

Learn how to create an OAuth app in Google Cloud, obtain the necessary credentials and access tokens, and add them to Langflow’s Google components.

## Create an OAuth Application in Google Cloud {#5b8981b15d86192d17b0e5725c1f95e7}

1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).

2. Click **Select a project**, and then click **New Project** to create a new project.

![OAuth Client ID and Secret](/img/google/create-a-google-cloud-project.gif)

3. To enable APIs for the project, select **APIs & Services** and click **Library**. Enable the APIs you need for your project. For example, if your flow uses the Google Drive component, enable the Google Drive API.
4. To navigate to the OAuth consent screen, click **APIs & Services**, and then click **OAuth consent screen**.
5. Populate your OAuth consent screen with the application name, user support email, required [scopes](https://developers.google.com/identity/protocols/oauth2/scopes), and authorized domains.
6. To create an **OAuth Client ID**, navigate to **Clients**, and then select **Create Client**.
7. Choose **Desktop app** as the application type, and then name your client ID.
8. Click **Create**. A Client ID and Client Secret are created. Download the credentials as a JSON file to your local machine and save it securely.

![OAuth Client ID and Secret](/img/google/create-oauth-client-id.gif)

---

## Retrieve Access and Refresh Tokens

With your OAuth application configured and your credentials JSON file created, follow these steps to authenticate the Langflow application.

1. Create a new project in Langflow.
2. Add a **Google OAuth Token** component to your flow.
3. Input in the field **Credentials File** on the Google OAuth Token component, the JSON file containing the Client ID credentials you downloaded from Google in the [previous steps](#5b8981b15d86192d17b0e5725c1f95e7).
4. Click the **Play** button in the **Google OAuth Token** component to authenticate your application.
   When the component code is executed, a new tab should open in the browser to authenticate your application using your Google Cloud account. You must authenticate with the account where you created the OAuth credentials for your application.
   If a new tab does not open automatically, check the Langflow **Logs** for the Google authentication URL. Open this URL in your browser to complete the authentication. Only after authenticating will the JSON token be generated.

5. After successful authentication, your Langflow application can now request and refresh tokens for your application. These tokens enable Langflow to interact with Google services on your behalf and execute the requests you’ve specified.
   By default, token validity is managed by Google’s servers. In Langflow, tokens refresh automatically after initial authentication. However, if your application is inactive for an extended period, the tokens may expire, requiring you to re-authenticate to resume use in Langflow.

## Configure Google Components in Langflow

In this example, use the **Google Drive Loader** component to load a text file hosted on Google Drive, translate the text to Spanish, and return it to a chat output.

For a pre-built example of this flow, download the <a href="./files/Google_Drive_Docs_Translations_Example.json" download>Google Drive Document Translation Example Flow JSON</a> to your local machine.

To import the downloaded JSON to Langflow, click **Options**, and then select **Import**.

1. Open Langflow and add a **Google Drive Loader** component to your flow.

2. Add the **OAuth Credentials** to the component. In the `JSON String of the Service Account Token` or `Token String` field of the Google Drive Loader component, enter your JSON string containing the token returned in the output of the Google OAuth Token component.

Remember to convert the data output from the Google OAuth Token component to text using the `Parse Data` component.

3. To allow the Langflow component to access the file in Google Drive, copy the Google Drive File ID from the document's URL.
   The file ID is located between `/d/` and `/edit` in a Google Drive document's URL.
   For example, in the URL `https://drive.google.com/file/d/1a2b3c4D5E6F7gHI8J9klmnopQ/edit`, the File ID is `1a2b3c4D5E6F7gHI8J9klmnopQ`.

4. Paste the copied Google Drive File ID into the **Document ID** field in the **Google Drive Loader** component.

5. Test the component’s functionality within your flow to ensure a successful connection.

By following these steps, your Langflow environment will be fully integrated with Google services, providing a powerful tool for automating workflows that involve Google Gmail, Drive, and more.

---

## Troubleshooting

- **Token Expiration**: Ensure to refresh your tokens periodically if you encounter authentication errors.
- **Permission Errors**: Double-check your OAuth consent settings and scopes in your Google Cloud account as well as in your Langflow component settings to ensure you’ve granted the necessary permissions.
- **A new window for authentication did not open?**: Check the Langflow Logs and look for text similar to **Please visit this URL to authorize this application: https://accounts.google.com/...**
  Visit this message's URL for authentication.

---
