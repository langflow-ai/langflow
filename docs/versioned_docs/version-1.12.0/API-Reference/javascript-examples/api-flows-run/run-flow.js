const url = `${process.env.LANGFLOW_SERVER_URL ?? ""}/api/v1/run/${process.env.FLOW_ID ?? ""}`;

const options = {
  method: 'POST',
  headers: {
    "Content-Type": `application/json`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: JSON.stringify({
  "input_value": "Tell me about something interesting!",
  "session_id": "chat-123",
  "input_type": "chat",
  "output_type": "chat",
  "output_component": ""
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
