const url = `${process.env.LANGFLOW_URL ?? ""}/logs-stream`;

const options = {
  method: 'GET',
  headers: {
    "accept": `text/event-stream`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
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
