const url = `${process.env.LANGFLOW_SERVER_URL ?? ""}/api/v1/responses`;

const options = {
  method: 'POST',
  headers: {
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
    "Content-Type": `application/json`,
    "X-LANGFLOW-GLOBAL-VAR-OPENAI_API_KEY": `sk-...`,
    "X-LANGFLOW-GLOBAL-VAR-USER_ID": `user123`,
    "X-LANGFLOW-GLOBAL-VAR-ENVIRONMENT": `production`,
  },
  body: JSON.stringify({
  "model": "your-flow-id",
  "input": "Hello"
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
