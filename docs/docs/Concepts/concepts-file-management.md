---
title: Manage files
slug: /concepts-file-management
---

import Icon from "@site/src/components/icon";

Upload, store, and manage files in Langflow's **File management** system.

Uploading files to the **File management** system keeps your files in a central location, and allows you to re-use files across flows without repeated manual uploads.

## Upload a file

The **File management** system is available at the `/files` URL. For example, if you're running Langflow at the default `http://localhost:7860` address, the **File management** system is located at `http://localhost:7860/files`.

To upload a file from your local machine:

1. From the **My Files** window at `http://localhost:7860/files`, click **Upload**.
2. Select the file to upload.
   The file is uploaded to Langflow.

You can upload multiple files in a single action.
Files are available to flows stored in different projects.

Files stored in **My Files** can be renamed, downloaded, duplicated, or deleted.

To delete a file from your project, hover over a file's icon to click and select it, and then click <Icon name="Trash2" aria-hidden="true"/> **Delete**.
You can delete multiple files in a single action.

To download a file from your project, hover over a file's icon to click and select it, and then click <Icon name="Download" aria-hidden="true"/> **Download**.
You can download multiple files in a single action, but they will be saved together in a .ZIP file.

## Use uploaded files in a flow

To use your uploaded files in flows:

1. Include the [File](/components-data#file) component in a flow.
2. To select a document to load, in the **File** component, click the **Select files** button.
3. Select a file to upload, and then click **Select file**. The loaded file name appears in the component.

For an example of using the **File** component in a flow, see the [Document QA tutorial project](/document-qa).

:::note
If you prefer a one-time upload, the [File](/components-data#file) component still allows one-time uploads directly from your local machine.
:::

## Supported file types

The maximum supported file size is 100 MB.

Text files:

- `.txt` - Text files
- `.md`, `.mdx` - Markdown files
- `.csv` - CSV files
- `.json` - JSON files
- `.yaml`, `.yml` - YAML files
- `.xml` - XML files
- `.html`, `.htm` - HTML files
- `.pdf` - PDF files
- `.docx` - Word documents
- `.py` - Python files
- `.sh` - Shell scripts
- `.sql` - SQL files
- `.js` - JavaScript files
- `.ts`, `.tsx` - TypeScript files

Archive formats (for bundling multiple files):

- `.zip` - ZIP archives
- `.tar` - TAR archives
- `.tgz` - Gzipped TAR archives
- `.bz2` - Bzip2 compressed files
- `.gz` - Gzip compressed files
