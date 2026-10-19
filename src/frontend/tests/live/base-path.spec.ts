import { expect, test } from "../fixtures";
import { skipIfMissing } from "../utils/env/skip-if-missing";

test(
  "serves assets, API docs, and health under the prefix",
  { tag: ["@release", "@api"] },
  async ({ request, baseURL }) => {
    skipIfMissing.basePathTestUrl();
    const root = `${baseURL!.replace(/\/+$/, "")}/`;
    const prefix = new URL(root).pathname;
    const response = await request.get(root);
    expect(response.ok()).toBe(true);
    const html = await response.text();
    expect(html).toContain(`<base href="${prefix}"`);
    const assets = [
      ...html.matchAll(/(?:src|href)="([^"\s]+\.(?:js|css|ico|json))"/g),
    ].map((match) => match[1]);
    expect(assets.length).toBeGreaterThan(0);
    for (const asset of assets) {
      const assetUrl = new URL(asset, root);
      expect(assetUrl.pathname.startsWith(prefix)).toBe(true);
      const assetResponse = await request.get(assetUrl.href);
      expect(assetResponse.ok()).toBe(true);
      expect(assetResponse.headers()["content-type"]).not.toContain(
        "text/html",
      );
    }
    expect((await request.get(`${root}health_check`)).ok()).toBe(true);
    const docs = await request.get(`${root}docs`);
    expect(docs.ok()).toBe(true);
    expect(await docs.text()).toContain(`${prefix}openapi.json`);
  },
);

test(
  "preserves a protected deep link through login and reload",
  { tag: ["@release", "@workspace"] },
  async ({ page, baseURL }) => {
    skipIfMissing.basePathTestUrl();
    const username = process.env.LANGFLOW_BASE_PATH_TEST_USERNAME;
    const password = process.env.LANGFLOW_BASE_PATH_TEST_PASSWORD;
    expect(username, "Set LANGFLOW_BASE_PATH_TEST_USERNAME").toBeTruthy();
    expect(password, "Set LANGFLOW_BASE_PATH_TEST_PASSWORD").toBeTruthy();
    const root = `${baseURL!.replace(/\/+$/, "")}/`;
    const { origin, pathname: prefix } = new URL(root);
    const escapedRequests: string[] = [];
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.origin === origin && !url.pathname.startsWith(prefix))
        escapedRequests.push(url.pathname);
    });
    const target = `${root}settings/api-keys`;
    await page.route("https://fonts.googleapis.com/**", (route) =>
      route.abort(),
    );
    await page.goto(target, { waitUntil: "domcontentloaded" });
    await expect(
      page.getByPlaceholder("Username", { exact: true }),
    ).toBeVisible();
    await expect(page).toHaveURL(`${root}login`);
    await page.getByPlaceholder("Username", { exact: true }).fill(username!);
    await page.getByPlaceholder("Password", { exact: true }).fill(password!);
    await page.getByRole("button", { name: /^sign in$/i }).click();
    await expect(page).toHaveURL(target, { timeout: 30_000 });
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("api-key-button-store")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page).toHaveURL(target);
    expect(escapedRequests).toEqual([]);
  },
);
