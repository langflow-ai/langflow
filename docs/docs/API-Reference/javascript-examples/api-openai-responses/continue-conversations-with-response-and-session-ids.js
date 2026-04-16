const url = `http://${process.env.LANGFLOW_SERVER_URL ?? ""}/api/v1/responses`;

const options = {
  method: 'POST',
  headers: {
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
    "Content-Type": `application/json`,
  },
  body: JSON.stringify({
  "model": "$FLOW_ID",
  "input": "Hello, my name is Alice"
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
