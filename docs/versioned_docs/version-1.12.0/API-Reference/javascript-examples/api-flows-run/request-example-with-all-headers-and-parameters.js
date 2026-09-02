const url = `${process.env.LANGFLOW_SERVER_URL ?? ""}/api/v1/run/${process.env.FLOW_ID ?? ""}?stream=true`;

const options = {
  method: 'POST',
  headers: {
    "Content-Type": `application/json`,
    "accept": `application/json`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: JSON.stringify({
  "input_value": "Tell me a story",
  "input_type": "chat",
  "output_type": "chat",
  "output_component": "chat_output",
  "session_id": "chat-123",
  "tweaks": {
    "component_id": {
      "parameter_name": "value"
    }
  }
}),
};

fetch(url, options)
  .then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const text = await response.text();
    console.log(text);
  })
  .catch((error) => console.error(error));
