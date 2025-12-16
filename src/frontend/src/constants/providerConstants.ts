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
