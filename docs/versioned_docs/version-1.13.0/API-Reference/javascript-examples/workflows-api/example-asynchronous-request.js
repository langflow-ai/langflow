const url = `${process.env.LANGFLOW_SERVER_URL ?? ""}/api/v2/workflows`;

const options = {
  method: 'POST',
  headers: {
    "Content-Type": `application/json`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: JSON.stringify({
  "flow_id": "67ccd2be-17f0-8190-81ff-3bb2cf6508e6",
  "input_value": "Process this in the background",
  "session_id": "session-456",
  "mode": "background"
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
