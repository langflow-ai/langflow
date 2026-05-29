import type { Page } from "@playwright/test";

/**
 * Stub the /api/v1/auto_login endpoint so the app falls back to manual
 * sign-in, then perform the username/password login flow.
 *
 * Replaces the 3 inline copies of this route+init-script+login block.
 *
 * The caller is responsible for the subsequent assertions (e.g. waiting
 * for the mainpage_title).
 */
export async function mockAutoLoginDisabled(page: Page): Promise<void> {
  await page.route("**/api/v1/auto_login", (route) => {
    route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ detail: { auto_login: false } }),
    });
  });

  await page.addInitScript(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    (window as any).process = (window as any).process || {};
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    const proc = (window as any).process as { env?: Record<string, string> };
    const newEnv = {
      ...(proc.env ?? {}),
      LANGFLOW_AUTO_LOGIN: "false",
    };
    Object.defineProperty(proc, "env", {
      value: newEnv,
      writable: true,
      configurable: true,
    });
    sessionStorage.setItem("testMockAutoLogin", "true");
  });
}
