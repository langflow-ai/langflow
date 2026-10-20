# Salt Request Payment: a thin wrapper over SaltClient.request_payment,
# posting a real payment-request bubble into a chat (the TransferRequest
# rail) -- no PGP involved, a payment request is a plain structured record.
from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, MultilineSecretInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

from . import _salt_common as sc


class SaltRequestPaymentComponent(Component):
    display_name = "Salt Request Payment"
    description = "Post a real Salt payment request into a chat."
    icon = "banknote"
    name = "SaltRequestPayment"

    inputs = [
        StrInput(
            name="host",
            display_name="Salt Host",
            value=sc.SALT_HOST_DEFAULT,
            info="The Salt deployment this agent is registered on.",
        ),
        StrInput(
            name="agent_id",
            display_name="Agent ID",
            required=False,
            info="This agent's own Salt id. Kept for consistency with the other Salt components; not sent to the API.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="This agent's Salt API key.",
        ),
        MultilineSecretInput(
            name="private_key",
            display_name="Agent Private Key (optional)",
            required=False,
            info=f"Not needed here. {sc.KEYLESS_INFO}",
        ),
        SecretStrInput(
            name="passphrase",
            display_name="Private Key Passphrase (optional)",
            required=False,
            info="Not needed here -- a payment request is a plain structured record, never ciphertext.",
        ),
        MessageTextInput(
            name="chat_id",
            display_name="Chat ID",
            tool_mode=True,
            info="The Salt chat to post the request into.",
        ),
        MessageTextInput(
            name="receiver_id",
            display_name="Receiver User ID",
            tool_mode=True,
            info="Who is being asked to pay.",
        ),
        MessageTextInput(
            name="wallet_id",
            display_name="Wallet ID",
            tool_mode=True,
            info="Which of this agent's wallets should receive the payment.",
        ),
        MessageTextInput(
            name="amount",
            display_name="Amount",
            tool_mode=True,
            info='A human-decimal amount string, e.g. "4.50" -- never base units (wei/satoshis).',
        ),
        MessageTextInput(
            name="message",
            display_name="Message",
            tool_mode=True,
            required=False,
            info="An optional note shown on the request.",
        ),
    ]

    outputs = [Output(display_name="Result", name="result", method="request")]

    def request(self) -> Data:
        client = sc.get_client(self.host)
        try:
            result = client.request_payment(
                self.api_key,
                chat_id=self.chat_id,
                receiver_id=self.receiver_id,
                wallet_id=self.wallet_id,
                amount=str(self.amount),
                message=self.message or None,
            )
        finally:
            client.close()

        self.status = f"Requested {self.amount} from {self.receiver_id} in chat {self.chat_id}."
        return Data(data=result)
