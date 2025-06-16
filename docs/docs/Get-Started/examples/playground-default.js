const payload = {
    "output_type": "chat",
    "input_type": "chat",
    "input_value": "hello world!",
    "session_id": "user_1"
};

const options = {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
};

fetch('http://localhost:7860/api/v1/run/29deb764-af3f-4d7d-94a0-47491ed241d6', options)
    .then(response => response.json())
    .then(response => console.log(response))
    .catch(err => console.error(err));