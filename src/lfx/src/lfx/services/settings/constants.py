from pydantic import SecretStr

DEFAULT_SUPERUSER = "langflow"
DEFAULT_SUPERUSER_PASSWORD = SecretStr("")
# Only used to detect and rotate credentials created by older releases.
LEGACY_DEFAULT_SUPERUSER_PASSWORD = SecretStr("langflow")

MINIMUM_SECRET_KEY_LENGTH = 32
SHORT_SECRET_KEY_WARNING = (
    "LANGFLOW_SECRET_KEY is shorter than 32 characters. Short secrets are not recommended for production. "  # noqa: S105
    "Keep this key unchanged during an upgrade so Langflow can read credentials encrypted before 1.10.1, "
    "then use a planned credential rotation to replace it with a randomly generated key of at least 32 characters."
)

VARIABLES_TO_GET_FROM_ENVIRONMENT = [
    "APIMART_API_KEY",
    "COMPOSIO_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "AZURE_AI_FOUNDRY_API_KEY",
    "AZURE_AI_FOUNDRY_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_API_INSTANCE_NAME",
    "AZURE_OPENAI_API_DEPLOYMENT_NAME",
    "AZURE_OPENAI_API_EMBEDDINGS_DEPLOYMENT_NAME",
    "ASTRA_DB_APPLICATION_TOKEN",
    "ASTRA_DB_API_ENDPOINT",
    "COHERE_API_KEY",
    "GROQ_API_KEY",
    "HUGGINGFACEHUB_API_TOKEN",
    "PINECONE_API_KEY",
    "SAMBANOVA_API_KEY",
    "SEARCHAPI_API_KEY",
    "SERPAPI_API_KEY",
    "UPSTASH_VECTOR_REST_URL",
    "UPSTASH_VECTOR_REST_TOKEN",
    "VECTARA_CUSTOMER_ID",
    "VECTARA_CORPUS_ID",
    "VECTARA_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "NOVITA_API_KEY",
    "TAVILY_API_KEY",
    "COMETAPI_KEY",
    "EMPIRIOLABS_API_KEY",
    # IBM WatsonX variables
    "WATSONX_APIKEY",
    "WATSONX_PROJECT_ID",
    "WATSONX_URL",
    # OpenRouter variables
    "OPENROUTER_API_KEY",
    "OPENROUTER_SITE_URL",
    "OPENROUTER_APP_NAME",
]

# Agentic experience specific variables
AGENTIC_VARIABLES = [
    "FLOW_ID",
    "COMPONENT_ID",
    "FIELD_NAME",
    "ASTRA_TOKEN",
]

DEFAULT_AGENTIC_VARIABLE_VALUE = ""
