const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/flows/?remove_example_flows=false&components_only=false&get_all=true&header_flows=false&page=1&size=50`;

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
    const text = await response.text();
    console.log(text);
  })
  .catch((error) => console.error(error));
