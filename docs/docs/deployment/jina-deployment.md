# Deploy on Jina AI Cloud

Langflow integrates with langchain-serve to provide a one-command deployment to [Jina AI Cloud](https://github.com/jina-ai/langchain-serve).

Start by installing `langchain-serve` with 

```bash
pip install -U langchain-serve
``` 

Then, run:

```bash
langflow --jcloud
```

```text
🎉 Langflow server successfully deployed on Jina AI Cloud 🎉
🔗 Click on the link to open the server (please allow ~1-2 minutes for the server to startup): https://<your-app>.wolf.jina.ai/
📖 Read more about managing the server: https://github.com/jina-ai/langchain-serve
```

**Complete (example) output:**

```text
  🚀 Deploying Langflow server on Jina AI Cloud
  ╭───────────────────────── 🎉 Flow is available! ──────────────────────────╮
  │                                                                          │
  │   ID                    langflow-e3dd8820ec                              │
  │   Gateway (Websocket)   wss://langflow-e3dd8820ec.wolf.jina.ai           │
  │   Dashboard             https://dashboard.wolf.jina.ai/flow/e3dd8820ec   │
  │                                                                          │
  ╰──────────────────────────────────────────────────────────────────────────╯
  ╭──────────────┬──────────────────────────────────────────────────────────────────────────────╮
  │ App ID       │                     langflow-e3dd8820ec                                      │
  ├──────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Phase        │                            Serving                                           │
  ├──────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Endpoint     │          wss://langflow-e3dd8820ec.wolf.jina.ai                              │
  ├──────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ App logs     │                  dashboards.wolf.jina.ai                                     │
  ├──────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ Swagger UI   │          https://langflow-e3dd8820ec.wolf.jina.ai/docs                       │
  ├──────────────┼──────────────────────────────────────────────────────────────────────────────┤
  │ OpenAPI JSON │        https://langflow-e3dd8820ec.wolf.jina.ai/openapi.json                 │
  ╰──────────────┴──────────────────────────────────────────────────────────────────────────────╯

  🎉 Langflow server successfully deployed on Jina AI Cloud 🎉
  🔗 Click on the link to open the server (please allow ~1-2 minutes for the server to startup): https://langflow-e3dd8820ec.wolf.jina.ai/
  📖 Read more about managing the server: https://github.com/jina-ai/langchain-serve
  ```
## API Usage (with python)

You can use Langflow directly on your browser or the API endpoints on Jina AI Cloud to interact with the server.

```python
import requests

BASE_API_URL = "https://langflow-e3dd8820ec.wolf.jina.ai/api/v1/predict"
FLOW_ID = "864c4f98-2e59-468b-8e13-79cd8da07468"
# You can tweak the flow by adding a tweaks dictionary
# e.g {"OpenAI-XXXXX": {"model_name": "gpt-4"}}
TWEAKS = {
"ChatOpenAI-g4jEr": {},
"ConversationChain-UidfJ": {}
}

def run_flow(message: str, flow_id: str, tweaks: dict = None) -> dict:
  """
  Run a flow with a given message and optional tweaks.

  :param message: The message to send to the flow
  :param flow_id: The ID of the flow to run
  :param tweaks: Optional tweaks to customize the flow
  :return: The JSON response from the flow
  """
  api_url = f"{BASE_API_URL}/{flow_id}"

  payload = {"message": message}

  if tweaks:
      payload["tweaks"] = tweaks

  response = requests.post(api_url, json=payload)
  return response.json()

# Setup any tweaks you want to apply to the flow
print(run_flow("Your message", flow_id=FLOW_ID, tweaks=TWEAKS))
  ```

  ```json
{
  "result": "Great choice! Bangalore in the 1920s was a vibrant city with a rich cultural and political scene. Here are some suggestions for things to see and do:\n\n1. Visit the Bangalore Palace - built in 1887, this stunning palace is a perfect example of Tudor-style architecture. It was home to the Maharaja of Mysore and is now open to the public.\n\n2. Attend a performance at the Ravindra Kalakshetra - this cultural center was built in the 1920s and is still a popular venue for music and dance performances.\n\n3. Explore the neighborhoods of Basavanagudi and Malleswaram - both of these areas have retained much of their old-world charm and are great places to walk around and soak up the atmosphere.\n\n4. Check out the Bangalore Club - founded in 1868, this exclusive social club was a favorite haunt of the British expat community in the 1920s.\n\n5. Attend a meeting of the Indian National Congress - founded in 1885, the INC was a major force in the Indian independence movement and held many meetings and rallies in Bangalore in the 1920s.\n\nHope you enjoy your trip to 1920s Bangalore!"
}
  ```

:::info

Read more about resource customization, cost, and management of Langflow apps on Jina AI Cloud in the **[langchain-serve](https://github.com/jina-ai/langchain-serve)** repository.

:::