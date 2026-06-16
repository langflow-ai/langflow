import type { Page } from "@playwright/test";
import type { ICheckerResult } from "accessibility-checker";

/**
 * Page augmented with the `allowFlowErrors()` helper attached by
 * `fixtures.ts`. Call this to opt out of the per-test flow-error
 * detector when a spec intentionally drives the backend into an
 * error response (e.g. validation-error tests).
 */
export type LangflowPage = Page & {
  allowFlowErrors: () => void;
  runA11yScan: (label: string) => Promise<ICheckerResult | null>;
};
