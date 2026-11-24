const url = `http://${process.env.LANGFLOW_SERVER_URL ?? ""}/api/v1/responses`;

const options = {
  method: 'POST',
  headers: {
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
    "Content-Type": `application/json`,
  },
  body: JSON.stringify({
  "model": "ced2ec91-f325-4bf0-8754-f3198c2b1563",
  "input": "What's my name?",
  "previous_response_id": "c45f4ac8-772b-4675-8551-c560b1afd590"
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
