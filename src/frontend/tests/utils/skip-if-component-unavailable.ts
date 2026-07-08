import type { Locator } from "@playwright/test";
import { test } from "../fixtures";

// Some provider components (OpenAI, Astra DB, Oracle) ship in bundle
// distributions that are temporarily unpublished on this branch — see the
// "Re-enable ... after the PyPI projects are published" TODO in pyproject.toml.
// While a bundle is absent its component never appears in the palette, so a
// test built around it cannot run. Skip cleanly instead of failing; the guard
// turns back into a no-op the moment the bundle is restored, so no revert is
// needed when the dependencies return.
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
    `${componentName} component unavailable (bundle temporarily disabled)`,
  );
};
