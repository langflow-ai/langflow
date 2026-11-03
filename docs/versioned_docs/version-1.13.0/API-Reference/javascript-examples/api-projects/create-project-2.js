const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/projects/`;

const options = {
  method: 'POST',
  headers: {
    "accept": `application/json`,
    "Content-Type": `application/json`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: JSON.stringify({
  "name": "new_project_name",
  "description": "string",
  "components_list": [
    "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  ],
  "flows_list": [
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
