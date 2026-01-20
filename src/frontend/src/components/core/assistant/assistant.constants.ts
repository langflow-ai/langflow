export const TERMINAL_MIN_HEIGHT = 200;
export const TERMINAL_MAX_HEIGHT = 600;
export const TERMINAL_DEFAULT_HEIGHT = 300;
export const TERMINAL_CONFIG_HEIGHT = 280;
export const RESIZE_HANDLE_HEIGHT = 8;
export const HISTORY_STORAGE_KEY = "assistant-terminal-history";
export const MAX_HISTORY_SIZE = 50;
export const TEXTAREA_MAX_HEIGHT = 150;
export const SCROLL_BOTTOM_THRESHOLD = 10;

export const MIN_RETRIES = 0;
export const MAX_RETRIES_LIMIT = 5;

export const RATE_LIMIT_PATTERNS = [
  "rate limit",
  "rate_limit",
  "429",
  "too many requests",
];

export const PROVIDER_ERROR_PATTERNS = [
  "api key",
  "api_key",
  "authentication",
  "unauthorized",
  "model provider",
  "not configured",
];

export const QUOTA_ERROR_PATTERNS = ["quota", "billing", "insufficient"];

export const HELP_TEXT = `**Available commands:**

**MAX_RETRIES=<0-5>** - Set component validation retry attempts (only applies when generating components)

**HELP** or **?** - Show this help message

**CLEAR** - Clear terminal history

Ask questions about Langflow or describe a component to generate.`;

export const LOADING_VARIANTS = [
  "Thinking...",
  "Processing...",
  "Generating response...",
  "Working on it...",
  "Analyzing...",
  "Preparing response...",
  "On it...",
  "Let me think...",
  "Working...",
  "Crafting response...",
  "Computing...",
  "Calculating...",
  "Pondering...",
  "Figuring out...",
  "Running...",
  "Crunching...",
];

export const VALIDATING_VARIANTS = [
  "Validating component...",
  "Checking component...",
  "Analyzing code...",
  "Verifying code...",
  "Testing component...",
  "Reviewing code...",
];

export const STOPPED_VARIANTS = [
  "Generation stopped.",
  "Stopped by user.",
  "Cancelled.",
  "Interrupted.",
  "Aborted.",
  "Stopped.",
];
