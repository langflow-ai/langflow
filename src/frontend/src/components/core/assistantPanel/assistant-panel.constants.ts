import i18n from "@/i18n";
import type { AssistantSuggestion } from "./assistant-panel.types";

export const ASSISTANT_TITLE = "Langflow Assistant";

export const ASSISTANT_SESSION_STORAGE_KEY_PREFIX =
  "langflow-assistant-session-";

const ASSISTANT_PLACEHOLDER_KEYS = [
  "assistant.placeholder.0",
  "assistant.placeholder.1",
  "assistant.placeholder.2",
  "assistant.placeholder.3",
  "assistant.placeholder.4",
];

export const ASSISTANT_PLACEHOLDERS: string[] = ASSISTANT_PLACEHOLDER_KEYS.map(
  (key) => i18n.t(key),
);

export function getAssistantPlaceholder(): string {
  return ASSISTANT_PLACEHOLDERS[
    Math.floor(Math.random() * ASSISTANT_PLACEHOLDERS.length)
  ];
}

export const ASSISTANT_SESSIONS_STORAGE_KEY = "langflow-assistant-sessions";
export const ASSISTANT_MAX_SESSIONS = 10;
export const ASSISTANT_SESSION_PREVIEW_LENGTH = 80;

export const ASSISTANT_WELCOME_TEXT = "Here's how I can help";

export const ASSISTANT_SUGGESTIONS: AssistantSuggestion[] = [
  {
    id: "build-agents",
    icon: "Sparkles",
    text: "Build agents and other components",
  },
  {
    id: "answer-questions",
    icon: "Sparkles",
    text: "Answer questions about Langflow",
  },
];
