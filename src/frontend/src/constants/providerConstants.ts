/**
 * Interface for provider variable configuration.
 * Used by providers that may require multiple environment variables.
 */
export interface ProviderVariable {
  /** Display name shown to user (e.g., "API Key", "Project ID") */
  variable_name: string;
  /** Environment variable key (e.g., "OPENAI_API_KEY", "WATSONX_PROJECT_ID") */
  variable_key: string;
  /** Help text describing the variable */
  description: string;
  /** Whether this variable is required */
  required: boolean;
  /** Whether to treat as credential (masked input) */
  is_secret: boolean;
  /** Whether it accepts multiple values */
  is_list: boolean;
  /** Predefined options for dropdown selection */
  options: string[];
}

/**
 * @deprecated Use the API endpoint /api/v1/models/provider-variable-mapping instead.
 * This static mapping only contains the primary variable for each provider.
 * For providers with multiple variables (like IBM WatsonX), use the API.
 */
export const PROVIDER_VARIABLE_MAPPING: Record<string, string> = {
  OpenAI: "OPENAI_API_KEY",
  Anthropic: "ANTHROPIC_API_KEY",
  "Google Generative AI": "GOOGLE_API_KEY",
  Google: "GOOGLE_API_KEY",
  Ollama: "OLLAMA_BASE_URL",
  "IBM WatsonX": "WATSONX_APIKEY",
  Cohere: "COHERE_API_KEY",
  HuggingFace: "HUGGINGFACEHUB_API_TOKEN",
  Groq: "GROQ_API_KEY",
  Mistral: "MISTRAL_API_KEY",
  Together: "TOGETHER_API_KEY",
  Perplexity: "PERPLEXITYAI_API_KEY",
  Bedrock: "AWS_ACCESS_KEY_ID",
  AzureOpenAI: "AZURE_OPENAI_API_KEY",
  VertexAI: "VERTEXAI_API_KEY",
};

/**
 * Providers that don't require any configuration to activate.
 * These providers will show an "Activate" button instead of configuration inputs.
 */
export const NO_API_KEY_PROVIDERS: string[] = [];

export const VARIABLE_CATEGORY = {
  GLOBAL: "Global",
  CREDENTIAL: "Credential",
  LLM: "LLM",
  SETTINGS: "Settings",
} as const;
