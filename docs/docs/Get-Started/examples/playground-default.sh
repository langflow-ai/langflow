curl --request POST \
     --url 'http://localhost:7860/api/v1/run/29deb764-af3f-4d7d-94a0-47491ed241d6?stream=false' \
     --header 'Content-Type: application/json' \
     --data '{
		           "output_type": "chat",
		           "input_type": "chat",
		           "input_value": "hello world!"
		         }'