import i18n from "@/i18n";
import type { WizardStep } from "./types";

export const getStepTitles = (): Record<WizardStep, string> => ({
  1: i18n.t("knowledge.createTitle"),
  2: i18n.t("knowledge.reviewTitle"),
});

export const getStepDescriptions = (): Record<WizardStep, string> => ({
  1: i18n.t("knowledge.createDescription"),
  2: i18n.t("knowledge.reviewDescription"),
});

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
    "pdf",
    "docx",
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

// Modal height constants
export const MODAL_HEIGHT_WITH_ADVANCED = 760;
// Step 1 stacks Name + Embedding Model + DB Provider (with helper
// text). 455 forced an inner scrollbar on standard viewports — bumped so
// the three required fields fit comfortably without scrolling.
export const MODAL_HEIGHT_DEFAULT = 580;
export const VALIDATION_ERROR_LINE_HEIGHT = 16;
