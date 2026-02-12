import type { AssistantSuggestion } from "./assistant-panel.types";

export const ASSISTANT_TITLE = "Langflow Assistant";

const ASSISTANT_PLACEHOLDERS = [
  "Create an agent component...",
  "Build a RAG pipeline...",
  "Make a chatbot with memory...",
  "Create a web scraper component...",
  "Build a document parser...",
  "Ask me anything about Langflow...",
];

export const ASSISTANT_PLACEHOLDER =
  ASSISTANT_PLACEHOLDERS[Math.floor(Math.random() * ASSISTANT_PLACEHOLDERS.length)];

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
