const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/flows/${process.env.FLOW_ID ?? ""}`;

const options = {
  method: 'PATCH',
  headers: {
    "accept": `application/json`,
    "Content-Type": `application/json`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: JSON.stringify({
  "name": "string",
  "description": "string",
  "data": {},
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "endpoint_name": "my_new_endpoint_name",
  "locked": true
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
