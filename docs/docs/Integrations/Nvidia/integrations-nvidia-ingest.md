---
title:  Integrate NVIDIA Retriever Extraction with Langflow
slug: /integrations-nvidia-ingest
---

:::note
NVIDIA Retriever Extraction is also known as NV-Ingest and NeMo Retriever Extraction.
:::

The **NVIDIA Retriever Extraction** component integrates with the [NVIDIA nv-ingest](https://github.com/NVIDIA/nv-ingest) microservice for data ingestion, processing, and extraction of text files.

The `nv-ingest` service supports multiple extraction methods for PDF, DOCX, and PPTX file types, and includes pre-  and post-processing services like splitting, chunking, and embedding generation.

The **NVIDIA Retriever Extraction** component imports the NVIDIA `Ingestor` client, ingests files with requests to the NVIDIA ingest endpoint, and outputs the processed content as a list of [Data](/docs/concepts-objects#data-object) objects. `Ingestor` accepts additional configuration options for data extraction from other text formats. To configure these options, see the [component parameters](/docs/integrations-nvidia-ingest#parameters).

## Prerequisites

* An NVIDIA Ingest endpoint. For more information on setting up an NVIDIA Ingest endpoint, see the [NVIDIA Ingest quickstart](https://github.com/NVIDIA/nv-ingest?tab=readme-ov-file#quickstart).

* The **NVIDIA Retriever Extraction** component requires the installation of additional dependencies to your Langflow environment. To install the dependencies in a virtual environment, run the following commands.

  * If you have the Langflow repository cloned and installed from source:
  ```bash
  source **YOUR_LANGFLOW_VENV**/bin/activate
  uv sync --extra nv-ingest
  uv run langflow run
  ```

  * If you are installing Langflow from the Python Package Index:
  ```bash
  source **YOUR_LANGFLOW_VENV**/bin/activate
  uv pip install --prerelease=allow 'langflow[nv-ingest]'
  uv run langflow run
  ```

## Use the NVIDIA Retriever Extraction component in a flow

The **NVIDIA Retriever Extraction** component accepts **Message** inputs and outputs **Data**. The component calls an NVIDIA Ingest microservice's endpoint to ingest a local file and extract the text.

To use the NVIDIA Retriever Extraction component in your flow, follow these steps:
1. In the component library, click the **NVIDIA Retriever Extraction** component, and then drag it onto the canvas.
2. In the **Base URL** field, enter the URL of the NVIDIA Ingest endpoint.
Optionally, add the endpoint URL as a **Global variable**:
    1. Click **Settings**, and then click **Global Variables**.
    2. Click **Add New**.
    3. Name your variable. Paste your endpoint in the **Value** field.
    4. In the **Apply To Fields** field, select the field you want to globally apply this variable to. In this case, select **NVIDIA Base URL**.
    5. Click **Save Variable**.
3. Click the **Select files** button to select which file you want to ingest.
4. Select which text type to extract from the file.
The component supports text, charts, and tables.
5. Select whether to split the text into chunks.
Modify the splitting parameters in the component's **Configuration** tab.
7. Click **Run** to ingest the file.
8. To confirm the component is ingesting the file, open the **Logs** pane to view the output of the flow.
9. To store the processed data in a vector database, add an **AstraDB Vector** component to your flow, and connect the **NVIDIA Retriever Extraction** component to the **AstraDB Vector** component with a **Data** output.

![NVIDIA Retriever Extraction component flow](nvidia-component-ingest-astra.png)

10. Run the flow.
Inspect your Astra DB vector database to view the processed data.

## NVIDIA Retriever Extraction component parameters {#parameters}

The **NVIDIA Retriever Extraction** component has the following parameters.

For more information, see the [NV-Ingest documentation](https://nvidia.github.io/nv-ingest/user-guide/).

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
| base_url | NVIDIA Ingestion URL | The URL of the NVIDIA Ingestion API. |
| path | Path | File path to process. |
| extract_text | Extract Text | Extract text from documents. Default: `True`. |
| extract_charts | Extract Charts | Extract text from charts. Default: `False`. |
| extract_tables | Extract Tables | Extract text from tables. Default: `True`. |
| text_depth | Text Depth | The level at which text is extracted. Options: 'document', 'page', 'block', 'line', 'span'. Default: `document`. |
| split_text | Split Text | Split text into smaller chunks. Default: `True`. |
| split_by | Split By | How to split into chunks. Options: 'page', 'sentence', 'word', 'size'. Default: `word`. |
| split_length | Split Length | The size of each chunk based on the 'split_by' method. Default: `200`. |
| split_overlap | Split Overlap | The number of segments to overlap from the previous chunk. Default: `20`. |
| max_character_length | Max Character Length | The maximum number of characters in each chunk. Default: `1000`. |
| sentence_window_size | Sentence Window Size | The number of sentences to include from previous and following chunks when `split_by=sentence`. Default: `0`. |

### Outputs

The **NVIDIA Retriever Extraction** component outputs a list of [Data](/docs/concepts-objects#data-object) objects where each object contains:
- `text`: The extracted content.
  - For text documents: The extracted text content.
  - For tables and charts: The extracted table/chart content.
- `file_path`: The source file name and path.
- `document_type`: The type of the document ("text" or "structured").
- `description`: Additional description of the content.

The output varies based on the `document_type`:

- Documents with `document_type: "text"` contain:
  - Raw text content extracted from documents, for example, paragraphs from PDFs or DOCX files.
  - Content stored directly in the `text` field.
  - Content extracted using the `extract_text` parameter.

- Documents with `document_type: "structured"` contain:
  - Text extracted from tables and charts and processed to preserve structural information.
  - Content extracted using the `extract_tables` and `extract_charts` parameters.
  - Content stored in the `text` field after being processed from the `table_content` metadata.

:::note
Images are currently not supported and will be skipped during processing.
:::