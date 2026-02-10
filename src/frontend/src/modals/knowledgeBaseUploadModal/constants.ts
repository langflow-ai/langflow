import type { WizardStep } from "./types";

export const STEP_TITLES: Record<WizardStep, string> = {
  1: "Create Knowledge Base",
  2: "Review & Build",
};

export const STEP_DESCRIPTIONS: Record<WizardStep, string> = {
  1: "Name your knowledge base, upload sources, and select an embedding model",
  2: "Preview how your files will be chunked and confirm your settings",
};

export const DEFAULT_CHUNK_SIZE = 100;
export const DEFAULT_CHUNK_OVERLAP = 0;
export const DEFAULT_SEPARATOR = "";

export const ACCEPTED_FILE_TYPES =
  ".pdf,.txt,.md,.docx,.doc,.csv,.json,.html,.xml";
