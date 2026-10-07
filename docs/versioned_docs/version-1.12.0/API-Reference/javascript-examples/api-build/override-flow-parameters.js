const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/build/${process.env.FLOW_ID ?? ""}/flow`;

const options = {
  method: 'POST',
  headers: {
    "accept": `application/json`,
    "Content-Type": `application/json`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: JSON.stringify({
  "data": {
    "nodes": [],
    "edges": []
  },
  "inputs": {
    "input_value": "Your custom input here",
    "session": "session_id"
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
