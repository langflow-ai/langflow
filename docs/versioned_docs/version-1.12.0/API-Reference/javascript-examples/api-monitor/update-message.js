const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/monitor/messages/3ab66cc6-c048-48f8-ab07-570f5af7b160`;

const options = {
  method: 'PUT',
  headers: {
    "accept": `application/json`,
    "Content-Type": `application/json`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: JSON.stringify({
  "text": "testing 1234"
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
