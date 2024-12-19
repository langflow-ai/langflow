# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "huggingface-hub",  # Library for interacting with the Hugging Face Hub API.
#     "rich",             # Library for colourful and formatted console output.
# ]
# ///

import argparse
import sys

from huggingface_hub import HfApi, list_models  # Import required functions and classes from huggingface-hub.
from rich import print  # noqa: A004

# Fetch and list all models available on the Hugging Face Hub.
# This part is unrelated to restarting a space but demonstrates the usage of list_models.
models = list_models()

# Initialize an argument parser to handle command-line inputs.
args = argparse.ArgumentParser(description="Restart a space in the Hugging Face Hub.")
args.add_argument("--space", type=str, help="The space to restart.")  # Argument for specifying the space name.
args.add_argument("--token", type=str, help="The Hugging Face API token.")  # Argument for providing the API token.

# Parse the command-line arguments.
parsed_args = args.parse_args()

# Extract the space name from the parsed arguments.
space = parsed_args.space

# Check if the space name is provided; exit with an error message if not.
if not space:
    print("Please provide a space to restart.")
    sys.exit()

# Check if the API token is provided; exit with an error message if not.
if not parsed_args.token:
    print("Please provide an API token.")
    sys.exit()

# Create an instance of the HfApi class to interact with the Hugging Face Hub.
hf_api = HfApi(
    endpoint="https://huggingface.co",  # Base endpoint URL for Hugging Face Hub.
    token=parsed_args.token,  # API token used for authentication.
)

# Restart the specified space with a factory reboot.
# The `factory_reboot=True` option resets the space to its original state.
space_runtime = hf_api.restart_space(space, factory_reboot=True)

# Print the runtime status of the restarted space.
print(space_runtime)
