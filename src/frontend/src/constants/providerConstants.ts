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
 * Providers that don't require an API key to activate.
 * These providers will show an "Activate" button instead of an API key input.
 */
export const NO_API_KEY_PROVIDERS: string[] = ["Ollama"];

export const VARIABLE_CATEGORY = {
  GLOBAL: "Global",
  CREDENTIAL: "Credential",
  LLM: "LLM",
  SETTINGS: "Settings",
} as const;
