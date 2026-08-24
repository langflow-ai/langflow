import type { Page } from "@playwright/test";
import type { ICheckerResult } from "accessibility-checker";

export type A11yScanOptions = {
  colorScheme?: "light" | "dark";
};

export type ExpectedServerError = {
  method: string;
  path: string;
  status: number;
  count: number;
};

/**
 * Page augmented with the `allowFlowErrors()` helper attached by
 * `fixtures.ts`. Call this to opt out of the per-test flow-error
 * detector when a spec intentionally drives the backend into an
 * error response (e.g. validation-error tests).
 */
export type LangflowPage = Page & {
  allowFlowErrors: () => void;
  expectServerError: (expectation: ExpectedServerError) => void;
  /**
   * Declare a request the spec deliberately leaves in flight — e.g. a route
   * mocked with a delay longer than the test body so a loading state stays
   * rendered. Without this the teardown drain reports it as unsettled.
   */
  expectPendingRequest: (expectation: {
    method?: string;
    path: string;
  }) => void;
  runA11yScan: (
    label: string,
    options?: A11yScanOptions,
  ) => Promise<ICheckerResult | null>;
};
