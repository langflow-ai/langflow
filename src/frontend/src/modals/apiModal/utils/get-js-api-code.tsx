const payload = {
  "input_value": "Hello",
  "output_type": "chat",
  "input_type": "chat",
  // Optional: Use session tracking if needed
  "session_id": "user_1"
};

const options = {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(payload)
};

fetch('http://localhost:3000/api/v1/run/d861e679-8048-4b65-bf81-f69fbede82d3', options)
  .then(response => response.json())
  .then(data => {
    console.log('Full response structure:');
    console.log(JSON.stringify(data, null, 2));
  })
  .catch(err => console.error(err));
