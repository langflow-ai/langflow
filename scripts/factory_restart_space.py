import argparse

from huggingface_hub import HfApi, list_models
from rich import print

# Use root method
models = list_models()

args = argparse.ArgumentParser(description="Restart a space in the Hugging Face Hub.")
args.add_argument("--space", type=str, help="The space to restart.")
args.add_argument("--token", type=str, help="The Hugging Face API token.")

parsed_args = args.parse_args()

space = parsed_args.space

if not space:
    print("Please provide a space to restart.")
    exit()

if not parsed_args.token:
    print("Please provide an API token.")
    exit()

# Or configure a HfApi client
hf_api = HfApi(
    endpoint="https://huggingface.co",  # Can be a Private Hub endpoint.
    token=parsed_args.token,
)

space_runtime = hf_api.restart_space(space, factory_reboot=True)
print(space_runtime)
