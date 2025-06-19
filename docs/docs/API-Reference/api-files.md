---
title: Files endpoints
slug: /api-files
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Use the `/files` endpoint to add or delete files between your local machine and Langflow.

There are `/v1` and `/v2` versions of the `/files` endpoints.
The `v2/files` version offers several improvements over `/v1`:

- In `v1`, files are organized by `flow_id`. In `v2`, files are organized by `user_id`.
  This means files are accessed based on user ownership, and not tied to specific flows.
  You can upload a file to Langflow one time, and use it with multiple flows.
- In `v2`, files are tracked in the Langflow database, and can be added or deleted in bulk, instead of one by one.
- Responses from the `/v2` endpoint contain more descriptive metadata.
- The `v2` endpoints require authentication by an API key or JWT.
- The `/v2/files` endpoint does not support sending **image** files to flows through the API. To send **image** files to your flows through the API, follow the procedure in [Upload image files (v1)](#upload-image-files-v1).

## Files/V1 endpoints

Use the `/files` endpoint to add or delete files between your local machine and Langflow.

- In `v1`, files are organized by `flow_id`.
- In `v2`, files are organized by `user_id` and tracked in the Langflow database, and can be added or deleted in bulk, instead of one by one.

### Upload file (v1)

Upload a file to the `v1/files/upload/<YOUR-FLOW-ID>` endpoint of your flow.
Replace **FILE_NAME** with the uploaded file name.

<Tabs>

  <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/files/upload/$FLOW_ID" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@FILE_NAME.txt"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "flowId": "92f9a4c5-cfc8-4656-ae63-1f0881163c28",
  "file_path": "92f9a4c5-cfc8-4656-ae63-1f0881163c28/2024-12-30_15-19-43_your_file.txt"
}
```

  </TabItem>
</Tabs>

### Upload image files (v1)

Send image files to the Langflow API for AI analysis.

The default file limit is 100 MB. To configure this value, change the `LANGFLOW_MAX_FILE_SIZE_UPLOAD` environment variable.
For more information, see [Supported environment variables](/environment-variables#supported-variables).

1. To send an image to your flow with the API, POST the image file to the `v1/files/upload/<YOUR-FLOW-ID>` endpoint of your flow.
   Replace **FILE_NAME** with the uploaded file name.

```bash
curl -X POST "$LANGFLOW_URL/api/v1/files/upload/a430cc57-06bb-4c11-be39-d3d4de68d2c4" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@FILE_NAME.png"
```

The API returns the image file path in the format `"file_path":"<YOUR-FLOW-ID>/<TIMESTAMP>_<FILE-NAME>"}`.

```json
{
  "flowId": "a430cc57-06bb-4c11-be39-d3d4de68d2c4",
  "file_path": "a430cc57-06bb-4c11-be39-d3d4de68d2c4/2024-11-27_14-47-50_image-file.png"
}
```

<!-- TODO: What link goes here? -->
2. Post the image file to the **Chat Input** component of a **Basic prompting** flow.
   Pass the file path value as an input in the **Tweaks** section of the curl call to Langflow.
   To find your Chat input component's ID, use the [](#)

```bash
curl -X POST \
    "$LANGFLOW_URL/api/v1/run/a430cc57-06bb-4c11-be39-d3d4de68d2c4?stream=false" \
    -H 'Content-Type: application/json'\
    -d '{
    "output_type": "chat",
    "input_type": "chat",
    "tweaks": {
  "ChatInput-b67sL": {
    "files": "a430cc57-06bb-4c11-be39-d3d4de68d2c4/2024-11-27_14-47-50_image-file.png",
    "input_value": "what do you see?"
  }
}}'
```

Your chatbot describes the image file you sent.

```text
"text": "This flowchart appears to represent a complex system for processing financial inquiries using various AI agents and tools. Here's a breakdown of its components and how they might work together..."
```

### List files (v1)

List all files associated with a specific flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/files/list/$FLOW_ID" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "files": ["2024-12-30_15-19-43_your_file.txt"]
}
```

  </TabItem>
</Tabs>

### Download file (v1)

Download a specific file from a flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/files/download/$FLOW_ID/2024-12-30_15-19-43_your_file.txt" \
  -H "accept: application/json" \
  --output downloaded_file.txt
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
File contents downloaded to downloaded_file.txt
```

  </TabItem>
</Tabs>

### Delete file (v1)

Delete a specific file from a flow.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X DELETE \
  "$LANGFLOW_URL/api/v1/files/delete/$FLOW_ID/2024-12-30_15-19-43_your_file.txt" \
  -H "accept: application/json"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "message": "File 2024-12-30_15-19-43_your_file.txt deleted successfully"
}
```

  </TabItem>
</Tabs>

## Files/V2 endpoints

In `v2`, files are organized by `user_id` and tracked in the Langflow database, and can be added or deleted in bulk, instead of one by one.
The `v2` endpoints require authentication by an API key or JWT.
To create a Langflow API key and export it as an environment variable, see [Get started with the Langflow API](/api-reference-api-examples).

### Upload file (v2)

Upload a file to your user account. The file can be used across multiple flows.

The file is uploaded in the format `USER_ID/FILE_ID.FILE_EXTENSION`, such as `07e5b864-e367-4f52-b647-a48035ae7e5e/d44dc2e1-9ae9-4cf6-9114-8d34a6126c94.pdf`.

To retrieve your current `user_id`, call the `/whoami` endpoint.
```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/users/whoami" \
  -H "accept: application/json"
```

Result:
```
{"id":"07e5b864-e367-4f52-b647-a48035ae7e5e","username":"langflow","profile_image":null,"store_api_key":null,"is_active":true,"is_superuser":true,"create_at":"2025-05-08T17:59:07.855965","updated_at":"2025-05-28T19:00:42.556460","last_login_at":"2025-05-28T19:00:42.554338","optins":{"github_starred":false,"dialog_dismissed":true,"discord_clicked":false,"mcp_dialog_dismissed":true}}
```

In the POST request to `v2/files`, replace **@FILE_NAME.EXTENSION** with the uploaded file name and its extension.
You must include the ampersand (`@`) in the request to instruct curl to upload the contents of the file, not the string `FILE_NAME.EXTENSION`.

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v2/files" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -F "file=@FILE_NAME.EXTENSION"
```

The file is uploaded in the format `USER_ID/FILE_ID.FILE_EXTENSION`, and the API returns metadata about the uploaded file:

```json
{
  "id":"d44dc2e1-9ae9-4cf6-9114-8d34a6126c94",
  "name":"engine_manual",
  "path":"07e5b864-e367-4f52-b647-a48035ae7e5e/d44dc2e1-9ae9-4cf6-9114-8d34a6126c94.pdf",
  "size":851160,
  "provider":null
}
```

### Send files to your flows (v2)

:::important
The `/v2/files` endpoint does not support sending **image** files to flows.
To send **image** files to your flows through the API, follow the procedure in [Upload image files (v1)](#upload-image-files-v1).
:::

Send a file to your flow for analysis using the [File](/components-data#file) component and the API.
Your flow must contain a [File](/components-data#file) component to receive the file.

The default file limit is 100 MB. To configure this value, change the `LANGFLOW_MAX_FILE_SIZE_UPLOAD` environment variable.
For more information, see [Supported environment variables](/environment-variables#supported-variables).

1. To send a file to your flow with the API, POST the file to the `/api/v2/files` endpoint.
   Replace **FILE_NAME** with the uploaded file name.
   This is the same step described in [Upload file (v2)](#upload-file-v2), but since you need the filename to upload to your flow, it is included here.

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v2/files" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -F "file=@FILE_NAME.EXTENSION"
```

The file is uploaded in the format `USER_ID/FILE_ID.FILE_EXTENSION`, and the API returns metadata about the uploaded file:

```json
{
  "id":"d44dc2e1-9ae9-4cf6-9114-8d34a6126c94",
  "name":"engine_manual",
  "path":"07e5b864-e367-4f52-b647-a48035ae7e5e/d44dc2e1-9ae9-4cf6-9114-8d34a6126c94.pdf",
  "size":851160,
  "provider": null
}
```

2. To use this file in your flow, add a [File](/components-data#file) component to load a file into the flow.
3. To load the file into your flow, send it to the **File** component.
To retrieve the **File** component's full name with the UUID attached, call the [Read flow](/api-flows#read-flow) endpoint, and then include your **File** component and the file path as a tweak with the `/v1/run` POST request.
In this example, the file uploaded to `/v2/files` is included with the `/v1/run` POST request.

```text
curl --request POST \
  --url "$LANGFLOW_URL/api/v1/run/$FLOW_ID" \
  --header "Content-Type: application/json" \
  --data '{
  "input_value": "what do you see?",
  "output_type": "chat",
  "input_type": "text",
  "tweaks": {
    "File-1olS3": {
      "path": [
        "07e5b864-e367-4f52-b647-a48035ae7e5e/3a290013-fe1e-4d3d-a454-cacae81288f3.pdf"
      ]
    }
  }
}'
```

Result:
```text
"text":"This document provides important safety information and instructions for selecting, installing, and operating Briggs & Stratton engines. It includes warnings and guidelines to prevent injury, fire, or damage, such as choosing the correct engine model, proper installation procedures, safe fuel handling, and correct engine operation. The document emphasizes following all safety precautions and using authorized parts to ensure safe and effective engine use."
```

### List files (v2)

List all files associated with your user account.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v2/files" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
[
  {
    "id": "c7b22c4c-d5e0-4ec9-af97-5d85b7657a34",
    "name": "your_file",
    "path": "6f17a73e-97d7-4519-a8d9-8e4c0be411bb/c7b22c4c-d5e0-4ec9-af97-5d85b7657a34.txt",
    "size": 1234,
    "provider": null
  }
]
```

  </TabItem>
</Tabs>

### Download file (v2)

Download a specific file by its ID and file extension.

:::tip
You must specify the file type you expect in the `--output` value.
:::

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v2/files/c7b22c4c-d5e0-4ec9-af97-5d85b7657a34" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  --output downloaded_file.txt
```

  </TabItem>
  <TabItem value="result" label="Result">

```text
File contents downloaded to downloaded_file.txt
```

  </TabItem>
</Tabs>

### Edit file name (v2)

Change a file name.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X PUT \
  "$LANGFLOW_URL/api/v2/files/$FILE_ID?name=new_file_name" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "id": "76543e40-f388-4cb3-b0ee-a1e870aca3d3",
  "name": "new_file_name",
  "path": "6f17a73e-97d7-4519-a8d9-8e4c0be411bb/76543e40-f388-4cb3-b0ee-a1e870aca3d3.png",
  "size": 2728251,
  "provider": null
}
```

  </TabItem>
</Tabs>
### Delete file (v2)

Delete a specific file by its ID.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X DELETE \
  "$LANGFLOW_URL/api/v2/files/$FILE_ID" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "message": "File deleted successfully"
}
```

  </TabItem>
</Tabs>

### Delete all files (v2)

Delete all files associated with your user account.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X DELETE \
  "$LANGFLOW_URL/api/v2/files" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "message": "All files deleted successfully"
}
```

  </TabItem>
</Tabs>

## Create upload file (Deprecated)

This endpoint is deprecated. Use the `/files` endpoints instead.