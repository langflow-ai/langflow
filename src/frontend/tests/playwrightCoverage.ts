// tests/playwrightCoverage.ts

import { test } from "@playwright/test";
import fs from "fs";
import path from "path";

test.afterEach(async ({ page }, testInfo) => {
  const coverage = await page.evaluate(() => {
    return (window as unknown as { __coverage__?: Record<string, unknown> })
      .__coverage__;
  });

  if (!coverage) return;

  const dir = "coverage/playwright/individual-test";
  fs.mkdirSync(dir, { recursive: true });

  const safeTitle = testInfo.title.replace(/[^a-zA-Z0-9-_]/g, "_");
  const fileName = `coverage-${safeTitle}-${testInfo.testId}.json`;
  fs.writeFileSync(path.join(dir, fileName), JSON.stringify(coverage));
});
