import type { AssistantSuggestion } from "./assistant-panel.types";

export const ASSISTANT_TITLE = "Langflow Assistant";

export const ASSISTANT_PLACEHOLDER = "Create an agent component...";

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
