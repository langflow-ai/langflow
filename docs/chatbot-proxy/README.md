## Docs Chatbot Proxy

Very small FastAPI service that:
- **Ingests docs into Postgres (pgvector)** for RAG (optional).
- **Uses a Langflow vector RAG flow** over those docs.
- **Proxies chat requests to Langflow**, streaming tokens and logging queries.

1. Optional: ingest docs to Postgres.
If you have a different vector database, skip this step and point the Langflow flow to that database instead.

```bash
cd docs/chatbot-proxy
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-ingest.txt

cp .env.example .env  # if needed
# Edit .env: set DATABASE_URL, OPENAI_API_KEY
# Optional: DOCS_PATH, COLLECTION_NAME, PRE_DELETE_COLLECTION

python ingest_docs.py
```

This creates/updates the `COLLECTION_NAME` table (default `langflow_docs`) using the same schema as Langflow's `PGVector` component.

2. Create the Langflow vector RAG flow.

   1. Start Langflow (`make run_cli`, or your usual dev setup).
   2. Create or open a **vector store RAG** flow that:
     - Uses a `PGVector` component pointed at the same `DATABASE_URL` and `COLLECTION_NAME` as above.
     - Uses an embedding model compatible with `ingest_docs.py` (default: `text-embedding-3-small`).
     - Accepts a **chat input** and returns a **chat output**.
   3. Get the flow's **Flow ID/endpoint name** and its **API key** for use by the proxy.

3. Run the chatbot proxy.

```bash
cd docs/chatbot-proxy
source .venv/bin/activate  # or create a venv
pip install -r requirements.txt

# In .env, set:
# LANGFLOW_BASE_URL, LANGFLOW_API_KEY, FLOW_ID, DATABASE_URL

uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

The proxy exposes:
- `GET /health`
- `POST /chat/stream` – JSON body: `{ "message": "...", "session_id": "optional" }`

For production, you can use CORS to control access origins by setting the origin to the URL of your docs domain in `main.py`.
For example: `allowed_origins = ["https://docs.my-domain.com"]`.


4. Start the docs site with the proxy enabled

Run the docs site from the repo roo and pass the proxy URL environment variable so the floating button opens the chatbot instead of Algolia search.

```bash
cd docs
npm install        # first time only
DOCS_CHATBOT_PROXY_URL=http://localhost:8001 npm run start
```

Open the docs in your browser and use the popup chatbot to ask questions about the docs.

