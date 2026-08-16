import type { Locator } from "@playwright/test";
import { test } from "../fixtures";

// Some provider components ship in optional bundle distributions. While a
// bundle is absent its component never appears in the palette, so a test built
// around it cannot run. Skip cleanly instead of failing; tests for generic UI
// behavior should prefer a base component instead of using this guard.
export const skipIfComponentUnavailable = async (
  locator: Locator,
  componentName: string,
  timeout = 3000,
) => {
  const available = await locator
    .first()
    .waitFor({ state: "visible", timeout })
    .then(() => true)
    .catch(() => false);

  test.skip(
    !available,
    `${componentName} component unavailable (optional bundle is not installed)`,
  );
};
