const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/projects/b408ddb9-6266-4431-9be8-e04a62758331`;

const options = {
  method: 'PATCH',
  headers: {
    "accept": `application/json`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: JSON.stringify({
  "name": "string",
  "description": "string",
  "parent_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "components": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ],
  "flows": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ]
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
