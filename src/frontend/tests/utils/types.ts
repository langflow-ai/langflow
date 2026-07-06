import type { Page } from "@playwright/test";
import type { ICheckerResult } from "accessibility-checker";

export type A11yScanOptions = {
  colorScheme?: "light" | "dark";
  /**
   * Rule IDs to exclude from violation counts and failure messages.
   * Useful for suppressing known issues in shared chrome (header, nav)
   * that are not owned by the feature under test.
   * Example: ["aria_content_in_landmark", "label_name_visible"]
   */
  ignoreRules?: string[];
};

/**
 * Page augmented with the `allowFlowErrors()` helper attached by
 * `fixtures.ts`. Call this to opt out of the per-test flow-error
 * detector when a spec intentionally drives the backend into an
 * error response (e.g. validation-error tests).
 */
export type LangflowPage = Page & {
  allowFlowErrors: () => void;
  runA11yScan: (
    label: string,
    options?: A11yScanOptions,
  ) => Promise<ICheckerResult | null>;
};
