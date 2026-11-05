import { createServer } from "node:http";
import { expect, test as fixtureTest } from "../../fixtures";

// Exercise the shared request monitor without bootstrapping the application.
// API responses stay open until the browser discards their document.
const test = fixtureTest.extend<{}, { serverUrl: string }>({
  serverUrl: [
    // biome-ignore lint/correctness/noEmptyPattern: Playwright requires fixture dependencies to use object destructuring.
    async ({}, use) => {
      const server = createServer((request, response) => {
        if (request.url === "/api/delayed-error") {
          setTimeout(() => {
            response.writeHead(503, { "content-type": "application/json" });
            response.end('{"detail":"Expected test error"}');
          }, 200);
          return;
        }
        if (request.url?.startsWith("/api/")) return;
        response.setHeader("content-type", "text/html");
        response.end(
          `<p>Document ready</p>${request.url === "/new-fetch" ? "<script>fetch('/api/delayed-error')</script>" : ""}`,
        );
      });
      await new Promise<void>((resolve) =>
        server.listen(0, "127.0.0.1", resolve),
      );
      const address = server.address();
      if (!address || typeof address === "string") {
        throw new Error("The request-monitor test server did not start.");
      }
      try {
        await use(`http://127.0.0.1:${address.port}`);
      } finally {
        server.closeAllConnections();
        await new Promise<void>((resolve, reject) => {
          server.close((error) => (error ? reject(error) : resolve()));
        });
      }
    },
    { scope: "worker" },
  ],
});

for (const navigation of ["reload", "navigation"] as const) {
  test(
    `retires API requests discarded by a document ${navigation}`,
    { tag: ["@release", "@workspace"] },
    async ({ page, serverUrl }) => {
      await page.goto(serverUrl);
      await Promise.all([
        page.waitForRequest("**/api/pending"),
        page.evaluate(() => {
          void fetch("/api/pending");
        }),
      ]);

      if (navigation === "reload") {
        await page.reload();
      } else {
        await page.goto(`${serverUrl}/next`);
      }
      await expect(page.getByText("Document ready")).toBeVisible();
      // The fixture's teardown must accept the canceled request without an
      // expectPendingRequest allowance or a missing requestfailed event.
    },
  );
}

test(
  "retires API requests when their iframe is detached",
  { tag: ["@release", "@workspace"] },
  async ({ page, serverUrl }) => {
    await page.goto(serverUrl);
    await page.evaluate(() => {
      const iframe = document.createElement("iframe");
      iframe.src = "/child";
      document.body.append(iframe);
    });
    await expect(
      page.frameLocator("iframe").getByText("Document ready"),
    ).toBeVisible();
    const frame = page.frame({ url: `${serverUrl}/child` });
    expect(frame).not.toBeNull();
    await Promise.all([
      page.waitForRequest("**/api/pending"),
      frame!.evaluate(() => {
        void fetch("/api/pending");
      }),
    ]);
    await page.locator("iframe").evaluate((iframe) => iframe.remove());
  },
);

test(
  "keeps checking requests started immediately by the new document",
  { tag: ["@release", "@workspace"] },
  async ({ page, serverUrl }) => {
    await page.goto(serverUrl);
    page.expectServerError({
      method: "GET",
      path: "/api/delayed-error",
      status: 503,
      count: 1,
    });
    await page.goto(`${serverUrl}/new-fetch`);
    // Teardown must wait for and inspect the new document's delayed response.
  },
);

test(
  "keeps checking requests across same-document navigation",
  { tag: ["@release", "@workspace"] },
  async ({ page, serverUrl }) => {
    await page.goto(serverUrl);
    page.expectServerError({
      method: "GET",
      path: "/api/delayed-error",
      status: 503,
      count: 1,
    });
    await Promise.all([
      page.waitForRequest("**/api/delayed-error"),
      page.evaluate(() => {
        void fetch("/api/delayed-error");
      }),
    ]);
    await page.evaluate(() => {
      history.pushState({}, "", "/same-document#fragment");
    });
  },
);
