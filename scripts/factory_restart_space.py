import os

from huggingface_hub import HfApi, list_models
from rich import print

# Use root method
models = list_models()

# Or configure a HfApi client
hf_api = HfApi(
    endpoint="https://huggingface.co",  # Can be a Private Hub endpoint.
    token=os.getenv("HUGGINFACE_API_TOKEN") or "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",
)

space_runtime = hf_api.restart_space("Langflow/Langflow-Preview", factory_reboot=True)
print(space_runtime)
