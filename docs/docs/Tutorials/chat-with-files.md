---
title: Create a chatbot that can ingest files
slug: /chat-with-files
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

This tutorial shows you how to build a chatbot that can read and answer questions about files you upload, such as meeting notes or job applications.

For example, you could upload a contract and ask, “What are the termination clauses in this agreement?” Or upload a resume and ask, “Does this candidate have experience with marketing analytics?”

The main focus of this tutorial is to show you how to provide files as input to a Langflow flow, so your chatbot can use the content of those files in its responses.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [A Langflow API key](/configuration-api-keys)
- [An OpenAI API key](https://platform.openai.com/api-keys)

    This tutorial uses an OpenAI LLM. If you want to use a different provider, you need a valid credential for that provider.

## Create a flow that accepts file input

To ingest files, your flow must have a **File** component attached to a component that receives input, such as a **Prompt** or **Agent** component.

The following steps modify the [**Basic prompting**](/basic-prompting) template to accept file input:

1. In Langflow, click **New Flow**, and then select the **Basic prompting** template.
2. In the **Language Model** component, enter your OpenAI API key.

    If you want to use a different provider or model, edit the **Model Provider**, **Model Name**, and **API Key** fields accordingly.
3. To verify that your API key is valid, click <Icon name="Play" aria-hidden="true" /> **Playground**, and then ask the LLM a question.
The LLM should respond according to the specifications in the **Prompt** component's **Template** field.
4. Exit the **Playground**, and then modify the **Prompt** component to accept file input in addition to chat input.
To do this, edit the **Template** field, and then replace the default prompt with the following text:
    ```text
    ChatInput:
    {chat-input}
    File:
    {file}
    ```
    The **Prompt** component gets a new input port for each value in curly braces. At this point, your **Prompt** component should have **chat-input** and **file** input ports.

    :::tip
    Within the curly braces, you can use any port name you like. For this tutorial, the ports are named after the components that connect to them.
    :::

5. Add a [File component](/components-data#file) to the flow, and then connect the **Raw Content** output port to the Prompt component's **file** input port.
To connect ports, click and drag from one port to the other.

    You can add files directly to the file component to pre-load input before running the flow, or you can load files at runtime. The next section of this tutorial covers runtime file uploads.

    At this point your flow has five components. The Chat Input and File components are connected to the Prompt component's input ports. Then, the Prompt component's output port is connected to the Language Model component's input port. Finally, the Language Model component's output port is connected to the Chat Output component, which returns the final response to the user.

    ![File loader chat flow](/img/tutorial-chat-file-loader.png)


## Send requests to your flow from a Python application

This section of the tutorial demonstrates how you can send file input to a flow from an application.

To do this, your application must send a `POST /run` request to your Langflow server with the file you want to upload and a text prompt.
The result includes the outcome of the flow run and the LLM's response.

This example uses a local Langflow instance, and it asks the LLM to evaluate a sample resume.
If you don't have a resume on hand, you can download [fake-resume.txt](/files/fake-resume.txt).

:::tip
For help with constructing file upload requests in Python, JavaScript, and curl, see the [Langflow File Upload Utility](https://langflow-file-upload-examples.onrender.com).
:::

1. To construct the request, gather the following information:

    * `LANGFLOW_SERVER_ADDRESS`: Your Langflow server's domain. The default value is `127.0.0.1:7860`. You can get this value from the code snippets on your flow's [**API access** pane](/concepts-publish#api-access).
    * `FLOW_ID`: Your flow's UUID or custom endpoint name. You can get this value from the code snippets on your flow's [**API access** pane](/concepts-publish#api-access).
    * `FILE_COMPONENT_ID`: The UUID of the File component in your flow, such as `File-KZP68`. To find the component ID, open your flow in Langflow, click the File component, and then click **Controls**.
    * `CHAT_INPUT`: The message you want to send to the Chat Input of your flow, such as `Evaluate this resume for a job opening in my Marketing department.`
    * `FILE_NAME` and `FILE_PATH`: The name and path to the local file that you want to send to your flow.
    * `LANGFLOW_API_KEY`: A valid Langflow API key. To create an API key, see [API keys](/configuration-api-keys).

2. Copy the following script into a Python file, and then replace the placeholders with the information you gathered in the previous step:

    ```python
    # Python example using requests
    import requests
    import json

    # 1. Set the upload URL
    url = "http://LANGFLOW_SERVER_ADDRESS/api/v2/files/"

    # 2. Prepare the file and payload
    payload = {}
    files = [
      ('file', ('FILE_PATH', open('FILE_NAME', 'rb'), 'application/octet-stream'))
    ]
    headers = {
      'Accept': 'application/json',
      'x-api-key': 'LANGFLOW_API_KEY'
    }

    # 3. Upload the file to Langflow
    response = requests.request("POST", url, headers=headers, data=payload, files=files)
    print(response.text)

    # 4. Get the uploaded file path from the response
    uploaded_data = response.json()
    uploaded_path = uploaded_data.get('path')

    # 5. Call the Langflow run endpoint with the uploaded file path
    run_url = "http://LANGFLOW_SERVER_ADDRESS/api/v1/run/FLOW_ID"
    run_payload = {
        "input_value": "CHAT_INPUT",
        "output_type": "chat",
        "input_type": "chat",
        "tweaks": {
            "FILE_COMPONENT_ID": {
                "path": uploaded_path
            }
        }
    }
    run_headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'x-api-key': 'LANGFLOW_API_KEY'
    }
    run_response = requests.post(run_url, headers=run_headers, data=json.dumps(run_payload))
    langflow_data = run_response.json()
    # Output only the message
    message = None
    try:
        message = langflow_data['outputs'][0]['outputs'][0]['results']['message']['data']['text']
    except (KeyError, IndexError, TypeError):
        pass
    print(message)

    ```

    This script contains two requests.

    The first request uploads a file, such as `fake-resume.txt`, to your Langflow server at the `/v2/files` endpoint. This request returns a file path that can be referenced in subsequent Langflow requests, such as `02791d46-812f-4988-ab1c-7c430214f8d5/fake-resume.txt`

    The second request sends a chat message to the Langflow flow at the `/v1/run/` endpoint.
    The `tweaks` parameter includes the path to the uploaded file as the variable `uploaded_path`, and sends this file directly to the File component.

3. Save and run the script to send the requests and test the flow.

    <details>
    <summary>Response</summary>

    The following is an example of a response returned from this tutorial's flow. Due to the nature of LLMs and variations in your inputs, your response might be different.

    ```
    {"id":"793ba3d8-5e7a-4499-8b89-d9a7b6325fee","name":"fake-resume (1)","path":"02791d46-812f-4988-ab1c-7c430214f8d5/fake-resume.txt","size":1779,"provider":null}
    The resume for Emily J. Wilson presents a strong candidate for a position in your Marketing department. Here are some key points to consider:

    ### Strengths:
    1. **Experience**: With over 8 years in marketing, Emily has held progressively responsible positions, culminating in her current role as Marketing Director. This indicates a solid foundation in the field.

    2. **Quantifiable Achievements**: The resume highlights specific accomplishments, such as a 25% increase in brand recognition and a 30% sales increase after launching new product lines. These metrics demonstrate her ability to drive results.

    3. **Diverse Skill Set**: Emily's skills encompass various aspects of marketing, including strategy development, team management, social media marketing, event planning, and data analysis. This versatility can be beneficial in a dynamic marketing environment.

    4. **Educational Background**: Her MBA and a Bachelor's degree in Marketing provide a strong academic foundation, which is often valued in marketing roles.

    5. **Certifications**: The Certified Marketing Professional (CMP) and Google Analytics Certification indicate a commitment to professional development and staying current with industry standards.

    ### Areas for Improvement:
    1. **Specificity in Skills**: While the skills listed are relevant, providing examples of how she has applied these skills in her previous roles could strengthen her resume further.

    2. **References**: While stating that references are available upon request is standard, including a couple of testimonials or notable endorsements could enhance credibility.

    3. **Formatting**: Ensure that the resume is visually appealing and easy to read. Clear headings and bullet points help in quickly identifying key information.

    ### Conclusion:
    Overall, Emily J. Wilson's resume reflects a well-rounded marketing professional with a proven track record of success. If her experience aligns with the specific needs of your Marketing department, she could be a valuable addition to your team. Consider inviting her for an interview to further assess her fit for the role.
    ```

    </details>

    The initial output contains the JSON response object from the file upload endpoint, including the internal path where Langflow stores the file.

    The LLM then retrieves this file and evaluates its content, in this case the suitability of the resume for a job position.

## Next steps

To process multiple files in a single flow run, add a separate File component for each file you want to ingest. Then, modify your script to upload each file, retrieve each returned file path, and then pass a unique file path to each File component ID.

For example, you can modify `tweaks` to accept multiple file components.
The following code is just an example; it is not working code:

```python
## set multiple file paths
file_paths = {
    FILE_COMPONENT_1: uploaded_path_1,
    FILE_COMPONENT_2: uploaded_path_2
}

def chat_with_flow(input_message, file_paths):
    """Compare the contents of these two files."""
    run_url = f"{LANGFLOW_SERVER_ADDRESS}/api/v1/run/{FLOW_ID}"
    # Prepare tweaks with both file paths
    tweaks = {}
    for component_id, file_path in file_paths.items():
        tweaks[component_id] = {"path": file_path}
```

To upload files from another machine that is not your local environment, your Langflow server must first be accessible over the internet. Then, authenticated users can upload files your public Langflow server's `/v2/files/` endpoint, as shown in the tutorial. For more information, see [Langflow deployment overview](/deployment-overview).