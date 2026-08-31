import type { Page } from "@playwright/test";

export function getDefaultProjectIdForTest(page: Page): Promise<string>;
