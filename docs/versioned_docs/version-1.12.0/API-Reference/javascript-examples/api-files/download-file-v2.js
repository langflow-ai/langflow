const url = `${process.env.LANGFLOW_URL ?? ""}/api/v2/files/c7b22c4c-d5e0-4ec9-af97-5d85b7657a34`;

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
