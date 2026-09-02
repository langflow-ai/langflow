const url = `${process.env.LANGFLOW_SERVER_URL ?? ""}/api/v1/run/${process.env.FLOW_ID ?? ""}?stream=true`;

const options = {
  method: 'POST',
  headers: {
    "accept": `application/json`,
    "Content-Type": `application/json`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: JSON.stringify({
  "message": "Tell me something interesting!",
  "session_id": "chat-123"
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
