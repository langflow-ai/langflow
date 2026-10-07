const url = `${process.env.LANGFLOW_SERVER_URL ?? ""}/health_check`;

const options = {
  method: 'GET',
  headers: {
    "accept": `application/json`,
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
