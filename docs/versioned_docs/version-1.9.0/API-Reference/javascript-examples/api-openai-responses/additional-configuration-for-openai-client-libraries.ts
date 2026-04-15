import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "LANGFLOW_SERVER_URL/api/v1/",
  defaultHeaders: {
    "x-api-key": "LANGFLOW_API_KEY"
  },
  apiKey: "dummy-api-key" // Required by OpenAI SDK but not used by Langflow
});

const response = await client.responses.create({
  model: "FLOW_ID",
  input: "There is an event that happens on the second wednesday of every month. What are the event dates in 2026?"
});

console.log(response.output_text);
