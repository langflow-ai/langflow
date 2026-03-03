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
export const DEFAULT_SEPARATOR = "\\n";

export const KB_INGEST_FORMATS: Record<string, string[]> = {
  documents: [
    "txt",
    "md",
    "mdx",
    "html",
    "htm",
    "xhtml",
    "xml",
    "adoc",
    "asciidoc",
    "asc",
  ],
  spreadsheets: ["csv"],
  code: ["py", "js", "ts", "tsx", "sh", "sql"],
  data: ["json", "yaml", "yml"],
};

export const KB_INGEST_EXTENSIONS: string[] =
  Object.values(KB_INGEST_FORMATS).flat();

export const ACCEPTED_FILE_TYPES = KB_INGEST_EXTENSIONS.map(
  (ext) => `.${ext}`,
).join(",");

export const KB_NAME_REGEX = /^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]$/;

export const MAX_TOTAL_FILE_SIZE = 1024 * 1024 * 1024; // 1 GB
