const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/monitor/messages`;

const options = {
  method: 'DELETE',
  headers: {
    "accept": `*/*`,
    "Content-Type": `application/json`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: JSON.stringify([
  "MESSAGE_ID_1",
  "MESSAGE_ID_2"
]),
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
