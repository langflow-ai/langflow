import Admonition from "@theme/Admonition";
import ThemedImage from "@theme/ThemedImage";
import useBaseUrl from "@docusaurus/useBaseUrl";
import ZoomableImage from "/src/theme/ZoomableImage.js";

# Introduction to Streamlit in Langflow

The Streamlit integration in Langflow enables seamless connectivity with Streamlit applications, facilitating automation and enhancing user interactions.

<ZoomableImage
  alt="Streamlit Components in Langflow"
  sources={{
    light: "img/streamlit/streamlit_bundle.png",
    dark: "img/streamlit/streamlit_bundle.png",
  }}
  style={{ width: "100%", margin: "20px 0" }}
/>

#### <a target="\_blank" href="json_files/Streamlit_Components_bundle.json" download>Download Streamlit Components Bundle</a>

### Key Features of Streamlit Integration in Langflow

- **Send Chat Message**: Send messages to a Streamlit chat component programmatically, enhancing real-time communication.
- **Listen to Chat Message**: Listen for incoming messages in a Streamlit chat component, enabling dynamic responses.
- **Get Session Messages**: Retrieve all messages from a specific Streamlit session, useful for logging and analysis.
- **Get Last Session**: Retrieve the last active session of a Streamlit application, aiding in session management and continuity.

### Potential Use Cases for Streamlit Integration in Langflow

- **Real-Time Data Interaction**: Enable dynamic data interaction in Streamlit applications using Langflow's components.
- **Automated Responses**: Create automated responses to user interactions in Streamlit, improving user experience.
- **Session Management**: Efficiently manage and analyze user sessions in Streamlit applications.
- **Enhanced Communication**: Facilitate real-time communication within Streamlit applications, ideal for collaborative environments.

### Getting Started with Streamlit Integration in Langflow

1. **Setting up a Streamlit App**: Follow the guide [Setting up a Streamlit App](./setup) to set up a Streamlit application in your workspace.
2. **Connect Components**: Integrate Streamlit components with other Langflow components to build your workflow.
3. **Test and Refine**: Ensure your Langflow flow operates as intended by testing and refining it.
4. **Deploy and Run**: Deploy your Langflow flow to automate Streamlit-related tasks and processes.

The Streamlit integration in Langflow enhances your workflow by providing tools for session data retrieval and message management. With components like StreamlitGetSessionMessages, you can efficiently extract and utilize session messages from your Streamlit applications, making it easier to monitor and analyze interactions within your projects.