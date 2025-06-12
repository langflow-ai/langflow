import requests
import json

url = "http://127.0.0.1:7861/api/v1/run/0373ff1f-0173-4314-b6b6-959e5f39987b"

def ask_agent(question):
    # Payload structure for Langflow API:
    # - output_type: Specifies the type of output expected ("chat" for text responses)
    # - input_type: Specifies the type of input being sent ("chat" for text questions)
    # - input_value: The actual question or message to send to the agent
    payload = {
        "output_type": "chat",  # Must be "chat" for text responses
        "input_type": "chat",   # Must be "chat" for text input
        "input_value": question # Your question or message
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        # Get the response message
        data = response.json()
        message = data["outputs"][0]["outputs"][0]["outputs"]["message"]["message"]
        return message
        
    except Exception as e:
        return f"Error: {str(e)}"

# Store the previous answer
previous_answer = None

while True:
    # Get user input
    print("\nAsk the agent anything (e.g., 'What is 15 * 7?' or 'What is the square root of 144?')")
    print("Type 'quit' to exit or 'compare' to see the previous answer")
    user_question = input("Your question: ")
    
    if user_question.lower() == 'quit':
        break
    elif user_question.lower() == 'compare':
        if previous_answer:
            print(f"\nPrevious answer was: {previous_answer}")
        else:
            print("\nNo previous answer to compare with!")
        continue
    
    # Get and display the answer
    result = ask_agent(user_question)
    print(f"\nAgent's answer: {result}")
    
    # Store the answer for comparison
    previous_answer = result