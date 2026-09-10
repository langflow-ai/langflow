from langchain_cloudflare import CloudflareWorkersAIEmbeddings
from langchain_core.runnables.config import run_in_executor
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import Embeddings
from lfx.io import BoolInput, DictInput, IntInput, MessageTextInput, Output, SecretStrInput


class CloudflareWorkersAIEmbeddingsComponent(LCModelComponent):
    display_name: str = "Cloudflare Workers AI Embeddings"
    description: str = "Generate embeddings using Cloudflare Workers AI models."
    documentation: str = "https://python.langchain.com/docs/integrations/text_embedding/cloudflare_workersai/"
    icon = "Cloudflare"
    name = "CloudflareWorkersAIEmbeddings"

    inputs = [
        MessageTextInput(
            name="account_id",
            display_name="Cloudflare account ID",
            info="Find your account ID https://developers.cloudflare.com/fundamentals/setup/find-account-and-zone-ids/#find-account-id-workers-and-pages",
            required=True,
        ),
        SecretStrInput(
            name="api_token",
            display_name="Cloudflare API token",
            info="Create an API token https://developers.cloudflare.com/fundamentals/api/get-started/create-token/",
            required=True,
        ),
        MessageTextInput(
            name="model_name",
            display_name="Model Name",
            info="List of supported models https://developers.cloudflare.com/workers-ai/models/#text-embeddings",
            required=True,
            value="@cf/baai/bge-base-en-v1.5",
        ),
        BoolInput(
            name="strip_new_lines",
            display_name="Strip New Lines",
            advanced=True,
            value=True,
        ),
        IntInput(
            name="batch_size",
            display_name="Batch Size",
            advanced=True,
            value=50,
        ),
        MessageTextInput(
            name="api_base_url",
            display_name="Cloudflare API base URL",
            advanced=True,
            value="https://api.cloudflare.com/client/v4/accounts",
        ),
        DictInput(
            name="headers",
            display_name="Headers",
            info="Additional request headers",
            is_list=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        class CompatibleCloudflareEmbeddings(CloudflareWorkersAIEmbeddings):
            # The new provider's async client adds a hard-coded five-second timeout.
            # Keep the existing executor-backed behavior used by knowledge-base calls.
            async def aembed_query(self, text: str) -> list[float]:
                return await run_in_executor(None, self.embed_query, text)

            async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
                return await run_in_executor(None, self.embed_documents, texts)

        try:
            embeddings = CompatibleCloudflareEmbeddings(
                account_id=self.account_id,
                api_base_url=self.api_base_url,
                api_token=self.api_token,
                batch_size=self.batch_size,
                headers=self.headers,
                model_name=self.model_name,
                strip_new_lines=self.strip_new_lines,
                # Existing flows do not opt into the new package's AI_GATEWAY environment default.
                ai_gateway=None,
            )
        except Exception as e:
            msg = f"Could not connect to CloudflareWorkersAIEmbeddings API: {e!s}"
            raise ValueError(msg) from e

        return embeddings
