import asyncio
import httpx
import os

LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY", "sk-private")

# Put multiple flow URLs here
FLOW_URLS = [
    "http://localhost:7860/api/v1/run/cc255b04-b8b2-4077-85f6-dca5b43d41c9",
    "http://localhost:7860/api/v1/run/2dc917a4-9592-4872-898c-49123c18e7e4",
    "http://localhost:7860/api/v1/run/ccf397fa-15f4-44b9-926d-c6e1ae26d748",
    "http://localhost:7860/api/v1/run/caf3179f-2f2c-4f52-8a4f-ab9b2e874549",
    "http://localhost:7860/api/v1/run/213420e9-da09-4750-a273-4f2737e02f3b",
]

# Each flow gets its own message
FLOW_MESSAGES = [
    "Hello",
    "what is my name",
    "Hello, how are you?",
    "The growing demand for personalized, AI-driven mental health support tools that can provide real-time interventions and track long-term emotional well-being.",
    "Create a Langflow post",
]


async def run_flow(flow_url: str, message: str):
    """
    Call a single LangFlow flow via async httpx.
    Uses the same payload structure LangFlow expects.
    """
    payload = {
        "input_type": "chat",
        "output_type": "chat",
        "input_value": message
    }
    headers = {"x-api-key": LANGFLOW_API_KEY}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(flow_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


async def main():
    tasks = [
        run_flow(flow_url, flow_message)
        for flow_url, flow_message in zip(FLOW_URLS, FLOW_MESSAGES)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, result in enumerate(results, 1):
        print(f"\n--- Flow {i} Result ---")
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
