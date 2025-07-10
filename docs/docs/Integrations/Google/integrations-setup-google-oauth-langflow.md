---
title: Integrate Google OAuth with Langflow
slug: /integrations-setup-google-oauth-langflow
---

import TOCInline from '@theme/TOCInline';
import Icon from "@site/src/components/icon";

Langflow integrates with [Google OAuth](https://developers.google.com/identity/protocols/oauth2) for authenticating the [Gmail loader](/components-data#gmail-loader), [Google Drive loader](components-data#google-drive-loader), and [Google Drive Search](/components-data#google-drive-search) components.

Learn how to create an OAuth app in Google Cloud, obtain the necessary credentials and access tokens, and add them to Langflow’s Google components.

## Create an OAuth Application in Google Cloud {#5b8981b15d86192d17b0e5725c1f95e7}

1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).

2. Click **Select a project**, and then click **New Project** to create a new project.

![OAuth Client ID and Secret](/img/google/create-a-google-cloud-project.gif)

3. To enable APIs for the project, select **APIs & Services**, and then click **Library**. Enable the APIs you need for your project. For example, if your flow uses the Google Drive component, enable the Google Drive API.
4. To navigate to the OAuth consent screen, click **APIs & Services**, and then click **OAuth consent screen**.
5. Populate your OAuth consent screen with the application name, audience, and user support email.
For audience, select **External**.
This creates a testing application environment that you can add users to.
6. To add users to your OAuth audience, click **Audience**.
Under **Test users**, click **Add users**.
Enter any email addresses you intend to use to authenticate Langflow with OAuth.
These email addresses have access to the application while it's in a **Testing** publishing state.
For more information, see the [Google documentation](https://support.google.com/cloud/answer/13461325?hl=en).
7. To create an **OAuth Client ID**, navigate to **Clients**, and then click **Create Client**.
8. Choose **Desktop app** as the application type, and then name your client ID.
9. Click **Create**.
A Client ID and Client Secret are created.
Download the credentials as a JSON file to your local machine and save it securely.

![OAuth Client ID and Secret](/img/google/create-oauth-client-id.gif)

## Retrieve Access and Refresh Tokens

With your OAuth application configured and your credentials JSON file created, follow these steps to authenticate the Langflow application.

1. Create a new project in Langflow.
2. Add a **Google OAuth Token** component to your flow.
3. In the **Credentials File** field of the Google OAuth Token component, enter the path to your **Credentials File**, the JSON file containing the Client ID credentials you downloaded from Google in the previous steps.
4. In the **Scopes** field of the Google Oauth Token component, enter the scope required to access your resources.
For example, to allow your Langflow application to access a user's Google Drive, the scope is `https://www.googleapis.com/auth/drive`.
For more information, see the [Google documentation](https://developers.google.com/identity/protocols/oauth2/scopes).
5. To authenticate your application, in the **Google OAuth Token** component, click <Icon name="Play" aria-hidden="True" /> **Run component**.
A new tab opens in the browser to authenticate your application using your Google Cloud account. You must authenticate the application with the same Google account that created the OAuth credentials.

:::info
If a new tab does not open automatically, check the Langflow **Logs** for the Google authentication URL. Open this URL in your browser to complete the authentication.
:::

6. After successful authentication, your Langflow application can request and refresh tokens.
These tokens enable Langflow to interact with Google services on your behalf and execute your specified requests.

## Create a flow with Google Drive loader

For a pre-built JSON file of a flow that uses the Google Drive loader component, download the <a href="./files/Google_Drive_Docs_Translations_Example.json" download>Google Drive Document Translation Example Flow JSON</a> to your local machine.

In this example, the **Google Drive loader** component loads a text file hosted on Google Drive, translates the text to Spanish, and returns it to a chat output.

1. Download the <a href="./files/Google_Drive_Docs_Translations_Example.json" download>Google Drive Document Translation Example Flow JSON</a> to your local machine.
2. To import the downloaded JSON to Langflow, click **Options**, and then select **Import**.
3. In the **Credentials File** field of the Google OAuth Token component, enter the path to your **Credentials File**, the JSON file containing the Client ID credentials you downloaded from Google in the previous steps.
4. In the **Scopes** field of the Google Oauth Token component, enter the scope required to access your resources.
For example, to allow your Langflow application to access a user's Google Drive, the scope is `https://www.googleapis.com/auth/drive`.
For more information, see the [Google documentation](https://developers.google.com/identity/protocols/oauth2/scopes).
The example flow includes a **Parse data** component to convert the `data` output of the Google OAuth Token component to the `text` input of the JSON Cleaner component.
5. To allow the Langflow component to access the document in Google Drive, copy the Google Drive `documentID` from the document's URL.
:::info
The `documentID` is located between `/d/` and `/edit` in a Google Drive document's URL.
For example, in the URL `https://drive.google.com/file/d/1a2b3c4D5E6F7gHI8J9klmnopQ/edit`, the `documentID` is `1a2b3c4D5E6F7gHI8J9klmnopQ`.
:::
6. In the Google Drive loader component, in the **Document ID** field, paste the document URL.
7. To view the translated document, open the **Playground**.
