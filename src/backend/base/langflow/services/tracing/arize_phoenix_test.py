import asyncio
import httpx
import os

LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY", "sk-private")

# Put multiple flow URLs here
FLOW_URLS = [
    "http://localhost:7860/api/v1/run/cc255b04-b8b2-4077-85f6-dca5b43d41c9",
    "http://localhost:7860/api/v1/run/2dc917a4-9592-4872-898c-49123c18e7e4",
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
    # Each flow gets its own message
    messages = [
        "Hello from Flow 1",
        "Hello from Flow 2",
    ]

    tasks = [
        run_flow(flow_url, msg)
        for flow_url, msg in zip(FLOW_URLS, messages)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results, 1):
        print(f"\n--- Flow {i} Result ---")
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
