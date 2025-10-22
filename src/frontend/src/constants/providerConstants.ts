export const PROVIDER_VARIABLE_MAPPING: Record<string, string> = {
  OpenAI: "OPENAI_API_KEY",
  Anthropic: "ANTHROPIC_API_KEY",
  "Google Generative AI": "GOOGLE_API_KEY",
};

export const VARIABLE_CATEGORY = {
  GLOBAL: "Global",
  CREDENTIAL: "Credential",
  LLM: "LLM",
  SETTINGS: "Settings",
} as const;
