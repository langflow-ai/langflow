import Admonition from "@theme/Admonition";

# Setting up a Streamlit App

To use Streamlit components in Langflow, you first need to ensure that Streamlit application is running and how to access the web server. This guide will walk you through the process of setting up a Streamlit application and granting it access to self hosted streamlit web page.

## Prerequisites

- Docker installed, follow this [guide](https://docs.docker.com/engine/install/).
- Langflow repository cloned locally.

## Step 1: Run a Streamlit application

1. Go to the Langflow cloned repository.
2. Configure the .env file following the ./README.md file.
3. Run the command "docker compose -f docker/".
4. Install if not present and use one of the [supported browsers](https://docs.streamlit.io/knowledge-base/using-streamlit/supported-browsers), open the [self hosted streamlit application](https://localhost:5001/).

## Using Streamlit Components in Langflow

Once you have set up your Streamlit application and accessed the [web page](https://localhost:5001/), you can start using the Streamlit components in Langflow.

Langflow provides the following Streamlit components:

- **Chat Template**: Alters the layout of the Streamlit application, enabling the use of chat components.
- **Send Chat Message**: Send messages to a Streamlit chat component programmatically, enhancing real-time communication.
- **Listen to Chat Message**: Listen for incoming messages in a Streamlit chat component, enabling dynamic responses.
- **Get Session Messages**: Retrieve all messages from a specific Streamlit session, useful for logging and analysis.
- **Get Last Session**: Retrieve the last active session of a Streamlit application, aiding in session management and continuity.

Refer to the individual component documentation for more details on how to use each component in your Langflow flows.

## Components Compatibility
- ChatTemplate:
  - StreamlitListenChatMessage
  - StreamlitSendChatMessage
  - StreamlitGetLastSession
  - StreamlitGetSessionMessages


## Additional Resources

- [Streamlit API Documentation](https://docs.streamlit.io/get-started)
- [Streamlit API Reference](https://docs.streamlit.io/develop/api-reference)


If you encounter any issues or have questions, please reach out to our support team or consult the Langflow community forums.

