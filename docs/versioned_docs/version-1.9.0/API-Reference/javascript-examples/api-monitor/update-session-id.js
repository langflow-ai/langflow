const url = `${process.env.LANGFLOW_URL ?? ""}/api/v1/monitor/messages/session/01ce083d-748b-4b8d-97b6-33adbb6a528a?new_session_id=different_session_id`;

const options = {
  method: 'PATCH',
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
