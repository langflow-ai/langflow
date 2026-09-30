const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/flows/download/`;

const options = {
  method: 'POST',
  headers: {
    "accept": `application/json`,
    "Content-Type": `application/json`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: JSON.stringify([
  "e1e40c77-0541-41a9-88ab-ddb3419398b5",
  "92f9a4c5-cfc8-4656-ae63-1f0881163c28"
]),
};

fetch(url, options)
  .then(async (response) => {
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.arrayBuffer();
    console.log("Received binary response for langflow-flows.zip", data.byteLength);
  })
  .catch((error) => console.error(error));
