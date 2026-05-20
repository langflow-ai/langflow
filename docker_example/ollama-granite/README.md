# Langflow + Ollama (granite4:350m) preset

Turnkey stack: Langflow, Postgres, and an Ollama server with `granite4:350m` pre-pulled. The Langflow service sees `OLLAMA_BASE_URL=http://ollama:11434`, so the Ollama provider is auto-enabled in **Model Providers** on first login.

## Run

```bash
docker compose up
```

Or, with Podman:

```bash
podman compose up        # podman-compose / podman compose plugin
```

Open http://localhost:7860. The first start downloads the model (a few hundred MB for `granite4:350m`).

## Services

- **langflow** — `localhost:7860`, with `OLLAMA_BASE_URL` already set
- **postgres** — `localhost:5432` (`langflow/langflow`)
- **ollama** — `localhost:11434`
- **ollama-init** — one-shot, pulls `granite4:350m` then exits

## GPU

Uncomment the `deploy.resources` block on the `ollama` service in `docker-compose.yml`. Requires the NVIDIA Container Toolkit on the host.

## Tear down

```bash
docker compose down            # keep volumes (model + DB persist)
docker compose down -v         # also wipe volumes
```
