const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/run/a430cc57-06bb-4c11-be39-d3d4de68d2c4?stream=false`;

const options = {
  method: 'POST',
  headers: {
    "Content-Type": `application/json`,
    "x-api-key": `${process.env.LANGFLOW_API_KEY ?? ""}`,
  },
  body: JSON.stringify({
  "output_type": "chat",
  "input_type": "chat",
  "tweaks": {
    "ChatInput-b67sL": {
      "files": "a430cc57-06bb-4c11-be39-d3d4de68d2c4/2024-11-27_14-47-50_image-file.png",
      "input_value": "describe this image"
    }
  }
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
