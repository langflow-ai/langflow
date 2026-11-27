# FastAPI Guard middleware

On Python 3.11 through 3.14, install `langflow[guard]` and set
`LANGFLOW_GUARD_ENABLED=true` to enable Guard. Use `langflow-base[guard]` if
your deployment installs the base package directly. Langflow stops at startup
if you enable Guard without installing the extra.

The `/health`, `/healthz`, and `/health_check` probes remain available when a
shared client IP reaches its rate limit or is automatically banned. Configured
IP allow and block lists still apply. Guard responses follow Langflow's CORS
settings. With `LANGFLOW_GUARD_SECURITY_HEADERS=true`, the app can embed
cross-origin images and use its same-origin microphone.
