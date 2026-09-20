const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/files/download/${process.env.FLOW_ID ?? ""}/2024-12-30_15-19-43_your_file.txt`;

const options = {
  method: 'GET',
  headers: {
    "accept": `application/json`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
};

fetch(url, options)
  .then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.arrayBuffer();
    console.log("Received binary response for downloaded_file.txt", data.byteLength);
  })
  .catch((error) => console.error(error));
