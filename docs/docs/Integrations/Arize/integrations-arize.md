---
title: Integrate Arize with Langflow
slug: /integrations-arize
---

Arize is a tool built on [OpenTelemetry](https://opentelemetry.io/) and [OpenInference](https://docs.arize.com/phoenix/reference/open-inference) for monitoring and optimizing LLM applications.

To add tracing to your Langflow application, add the `ARIZE_SPACE_ID` and `ARIZE_API_KEY` environment variables to your Langflow application.

## Prerequisites

* If you are using the [standard Arize platform](https://docs.arize.com/arize), you need an **Arize Space ID** and **API API Key**.
* If you are using the open-source [Arize Phoenix platform](https://docs.arize.com/phoenix), you need an **Arize Phoenix API key**.

## Connect Arize to Langflow

1. To retrieve your **Arize Space ID** and **API API Key**, navigate to the [Arize dashboard](https://app.arize.com/).
2. Click **Settings**, and then click **Space Settings and Keys**.
3. Copy the **SpaceID** and **API Key (Ingestion Service Account Key)** values.
4. Create a `.env` file in the root of your Langflow application.
5. Add the `ARIZE_SPACE_ID` and `ARIZE_API_KEY` environment variables to your Langflow application.
You do not need to specify the **Arize Project** name if you're using the standard Arize platform.
Replace the following:

* YOUR_ARIZE_SPACE_ID: the **SpaceID** value copied from Arize
* YOUR_ARIZE_API_KEY: the **API Key** value copied from Arize

```bash
ARIZE_SPACE_ID=YOUR_ARIZE_SPACE_ID
ARIZE_API_KEY=YOUR_ARIZE_API_KEY
```

6. Optional: if you are using the [Arize Phoenix platform](https://docs.arize.com/phoenix), add the `PHOENIX_API_KEY` environment variable to your application instead of `ARIZE_SPACE_ID` and `ARIZE_API_KEY`.
Replace `YOUR_PHOENIX_API_KEY` with the Arize Phoenix API key copied from the Arize Phoenix platform.

```bash
PHOENIX_API_KEY=YOUR_PHOENIX_API_KEY
```
7. Save the `.env` file.
8. Start your Langflow application with the values from the `.env` file.

```bash
uv run langflow run --env-file .env
```

For more information, see the [Arize documentation](https://docs.arize.com/phoenix/tracing/integrations-tracing/langflow#go-to-arize-phoenix).
## Run a flow and view metrics in Arize

1. In Langflow, select the [Simple agent](/starter-projects-simple-agent) starter project.
2. In the **Agent** component's **OpenAI API Key** field, paste your **OpenAI API key**.
3. Click **Playground**.
Ask your Agent some questions to generate traffic.
4. Navigate to the [Arize dashboard](https://app.arize.com/), and then open your project.
You may have to wait a few minutes for Arize to process the data.
5. The **LLM Tracing** tab shows metrics for your flow.
Each Langflow execution generates two traces in Arize.
The `AgentExecutor` trace is the Arize trace of Langchain's `AgentExecutor`. The UUID trace is the trace of the Langflow components.
6. To view traces, click the **Traces** tab.
A **trace** is the complete journey of a request, made of multiple **spans**.
7. To view **Spans**, select the **Spans** tab.
A **span** is a single operation within a trace. For example, a **span** could be a single API call to OpenAI or a single function call to a custom tool.
For more on traces, spans, and other metrics in Arize, see the [Arize documentation](https://docs.arize.com/arize/llm-tracing/tracing).
8. All metrics in the **LLM Tracing** tab can be added to **Datasets**.
To add a span to a **Dataset**, click the **Add to Dataset** button.
9. To view a **Dataset**, click the **Datasets** tab, and then select your **Dataset**.
For more on **Datasets**, see the [Arize documentation](https://docs.arize.com/arize/llm-datasets-and-experiments/datasets-and-experiments).