---
title: Setting up a Streamlit App
sidebar_position: 1
slug: /setup
---



Streamlit is a powerful tool for creating interactive web applications. To integrate Streamlit components into Langflow, first ensure your Streamlit application is running. Follow the guide to set up your Streamlit application and grant access to your self-hosted Streamlit web page. Once done, you can seamlessly use Streamlit components within Langflow!


## Step-by-step Configuration {#b912579a43984f9a92921232b67c885f}


---


1. Add the following keys to Langflow .env file:

`LANGFLOW_STREAMLIT_ENABLED=true LANGFLOW_STREAMLIT_PORT=5001`


or export the environment variables in your terminal:


`export LANGFLOW_STREAMLIT_ENABLED=true export LANGFLOW_STREAMLIT_PORT=5001`

1. Restart Langflow using `langflow run --env-file .env`
2. Run any project and check the LangSmith dashboard for monitoring and observability.




## Using Streamlit Components in Langflow

Once you have set up your Streamlit application and accessed the [web page](https://localhost:5001/), you can start using the Streamlit components in Langflow.

Langflow provides the following Streamlit components:

- **Chat Template**: Alters the layout of the Streamlit application, enabling the use of chat components.
- **Send Chat Message**: Send messages to a Streamlit chat component programmatically, enhancing real-time communication.
- **Listen to Chat Message**: Listen for incoming messages in a Streamlit chat component, enabling dynamic responses.
- **Get Session Messages**: Retrieve all messages from a specific Streamlit session, useful for logging and analysis.
- **Get Last Session**: Retrieve the last active session of a Streamlit application, aiding in session management and continuity.

Refer to the individual component documentation for more details on how to use each component in your Langflow flows.

## Additional Resources

- [Streamlit API Documentation](https://docs.streamlit.io/get-started)
- [Streamlit API Reference](https://docs.streamlit.io/develop/api-reference)


If you encounter any issues or have questions, please reach out to our support team or consult the Langflow community forums.

