const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/monitor/messages?flow_id=${process.env.FLOW_ID ?? ""}&session_id=01ce083d-748b-4b8d-97b6-33adbb6a528a&sender=Machine&sender_name=AI&order_by=timestamp`;

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
