from enum import Enum

from langflow.custom import Component
from langflow.io import DictInput, DropdownInput, Output, StrInput
from langflow.schema import Data


class DAppMethodName(Enum):
    GET_ACCOUNT_INFO = "get_account_info"
    GET_BLOCK_HEIGHT = "get_block_height"
    GET_EPOCH_INFO = "get_epoch_info"


class SolanaDAppInteractor(Component):
    display_name: str = "Solana dApp Interactor"
    description: str = "Interact with Solana dApp"
    name = "Solana DApp Interactor"
    icon: str = "Solana"

    output_types: list[str] = ["Document"]
    documentation: str = "https://solana.com/developers"

    inputs = [
        StrInput(
            name="network_url",
            display_name="Network URL",
            required=True,
            info="The Solana network URL (e.g., https://api.devnet.solana.com).",
            value="https://api.devnet.solana.com",
        ),
        StrInput(
            name="program_id",
            display_name="Program ID",
            required=True,
            info="The public key (e.g., Token Program: TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA).",
            value="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        ),
        DropdownInput(
            name="method_name",
            display_name="Method Name",
            info="The method to execute within the dApp. (e.g., Solana Token Program fn , get_account_info ).",
            options=list(DAppMethodName),
            value="get_account_info",
        ),
        DictInput(
            name="method_params",
            display_name="Method Parameters",
            required=False,
            info="Parameters in JSON format.(e.g, transfer_tokens with keys recipient and amount ).",
        ),
    ]

    outputs = [
        Output(display_name="Execution Result", name="execution_result", method="execute_method"),
    ]

    def execute_method(self) -> Data:
        try:
            from solathon import Client, PublicKey

            # Set default network URL if not provided
            network_url = self.network_url or "https://api.devnet.solana.com"
            client = Client(network_url)

            # Validate and prepare inputs
            program_id = PublicKey(self.program_id)
            method_name = self.method_name
            # method_params = self.method_params or {}

            # Example: Fetching account info
            if method_name == "get_account_info":
                account_info = client.get_account_info(program_id)
                if account_info:
                    # Convert the AccountInfo object to a dictionary
                    account_data = {
                        "owner": str(account_info.owner),
                        "executable": account_info.executable,
                        "lamports": account_info.lamports,
                        "data": account_info.data,
                        "rent_epoch": account_info.rent_epoch,
                    }
                    return Data(data={"result": account_data})
                return Data(data={"error": "No data found for the specified account."})

            if method_name == "get_block_height":
                block_height = client.get_block_height()
                return Data(data={"block_height": block_height})

            if method_name == "get_epoch_info":
                epoch_info = client.get_epoch_info()
                if epoch_info:
                    # Serialize the Epoch object into a dictionary
                    epoch_data = {
                        "epoch": epoch_info.epoch,
                        "absolute_slot": epoch_info.absolute_slot,
                        "block_height": epoch_info.block_height,
                        "slot_index": epoch_info.slot_index,
                        "slots_in_epoch": epoch_info.slots_in_epoch,
                    }
                    return Data(data={"result": epoch_data})
                return Data(data={"error": "Unable to fetch epoch info."})

            # Placeholder for additional method implementations
            # elif method_name == "another_method":
            #     # Implement the method logic here
            #     pass

            return Data(data={"error": f"Method '{method_name}' is not implemented."})

        except ImportError as e:
            msg = "Could not import required Solathon package. Please ensure it is installed."
            raise ImportError(msg) from e

        except ValueError as e:
            return Data(data={"error": f"A value error occurred: {e}"})

        except KeyError as e:
            return Data(data={"error": f"A key error occurred: {e}"})

        except AttributeError as e:
            return Data(data={"error": f"An attribute error occurred: {e}"})
