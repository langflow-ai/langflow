import { createServer } from "node:http";
import type { Page, Request } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { installDocumentRequestCleanup } from "../../utils/document-request-cleanup";
import {
  createPendingRequestTracker,
  createServerErrorContract,
  getServerErrorContractFailures,
  observeServerError,
  type PendingRequestTracker,
  type ServerErrorContract,
} from "../../utils/server-error-contract.mjs";

type LifecycleFixture = {
  page: Page;
  url: string;
  trackers: PendingRequestTracker<Request>[];
  errors: ServerErrorContract;
  startXhr(path: string): Promise<Request>;
};

const lifecycleTest = test.extend<{ lifecycle: LifecycleFixture }>({
  lifecycle: async ({ browser }, use) => {
    const server = createServer((request, response) => {
      const url = new URL(request.url ?? "/", "http://localhost");
      if (url.pathname.startsWith("/api/hang/")) return;
      if (url.pathname.startsWith("/api/error/")) {
        response.writeHead(500, { "content-type": "application/json" });
        response.end('{"detail":"intentional lifecycle regression error"}');
        return;
      }
      const xhr = url.searchParams.get("xhr");
      response.writeHead(200, { "content-type": "text/html" });
      response.end(
        `<title>Request lifecycle</title>${xhr ? `<script>const xhr = new XMLHttpRequest(); xhr.open("GET", ${JSON.stringify(xhr)}); xhr.send();</script>` : ""}`,
      );
    });
    await new Promise<void>((resolve) =>
      server.listen(0, "127.0.0.1", resolve),
    );
    const address = server.address();
    if (!address || typeof address === "string")
      throw new Error("The local lifecycle server did not bind a TCP port");
    const url = `http://127.0.0.1:${address.port}`;
    const context = await browser.newContext();
    const page = await context.newPage();
    const trackers = [
      createPendingRequestTracker<Request>(),
      createPendingRequestTracker<Request>(),
    ];
    const errors = createServerErrorContract();
    page.on("request", (request) => {
      if (new URL(request.url()).pathname.startsWith("/api/")) {
        for (const tracker of trackers) tracker.start(request);
      }
    });
    const finish = (request: Request) => {
      for (const tracker of trackers) tracker.finish(request);
    };
    page.on("requestfinished", finish);
    page.on("requestfailed", finish);
    page.on("response", (response) => {
      trackers[0].finish(response.request());
      if (response.status() >= 500)
        observeServerError(errors, {
          method: response.request().method(),
          path: new URL(response.url()).pathname,
          status: response.status(),
        });
    });
    const stop = await installDocumentRequestCleanup(page, trackers);
    await page.goto(url);
    try {
      await use({
        page,
        url,
        trackers,
        errors,
        async startXhr(path) {
          const requested = page.waitForEvent(
            "request",
            (request) => new URL(request.url()).pathname === path,
          );
          await page.evaluate((pathname) => {
            const xhr = new XMLHttpRequest();
            xhr.open("GET", pathname);
            xhr.send();
          }, path);
          return requested;
        },
      });
    } finally {
      stop();
      await context.close();
      server.closeAllConnections();
      await new Promise<void>((resolve) => server.close(() => resolve()));
    }
  },
});

lifecycleTest.describe("document request cleanup", () => {
  lifecycleTest(
    "retires an old-document XHR after reload",
    { tag: ["@release", "@workspace"] },
    async ({ lifecycle: { page, trackers, startXhr } }) => {
      await startXhr("/api/hang/old");
      await page.reload();
      for (const tracker of trackers)
        await expect.poll(() => tracker.snapshot().length).toBe(0);
    },
  );

  lifecycleTest(
    "keeps an XHR started immediately by the new document",
    { tag: ["@release", "@workspace"] },
    async ({ lifecycle: { page, url, trackers, startXhr } }) => {
      const oldRequest = await startXhr("/api/hang/old");
      const newRequestPromise = page.waitForEvent(
        "request",
        (request) => new URL(request.url()).pathname === "/api/hang/new",
      );
      await page.goto(`${url}/?xhr=/api/hang/new`);
      const newRequest = await newRequestPromise;
      for (const tracker of trackers) {
        await expect
          .poll(() => tracker.snapshot().includes(oldRequest))
          .toBe(false);
        expect(await tracker.drain(30)).toEqual([newRequest]);
      }
    },
  );

  lifecycleTest(
    "keeps pending XHRs across history and hash navigation",
    { tag: ["@release", "@workspace"] },
    async ({ lifecycle: { page, trackers, startXhr } }) => {
      const request = await startXhr("/api/hang/same-document");
      await page.evaluate(() => {
        history.pushState({}, "", "/changed-route");
        location.hash = "changed-hash";
      });
      for (const tracker of trackers)
        expect(await tracker.drain(30)).toEqual([request]);
    },
  );

  lifecycleTest(
    "keeps pending XHRs when navigation is aborted",
    { tag: ["@release", "@workspace"] },
    async ({ lifecycle: { page, url, trackers, startXhr } }) => {
      const request = await startXhr("/api/hang/retained-document");
      await page.route("**/aborted-document", (route) =>
        route.abort("aborted"),
      );
      await expect(page.goto(`${url}/aborted-document`)).rejects.toThrow();
      await expect(page).toHaveTitle("Request lifecycle");
      for (const tracker of trackers)
        expect(await tracker.drain(30)).toEqual([request]);
    },
  );

  lifecycleTest(
    "retains observed server errors and detects errors in the new document",
    { tag: ["@release", "@workspace"] },
    async ({ lifecycle: { page, url, errors, startXhr } }) => {
      await startXhr("/api/error/old");
      await expect
        .poll(() => getServerErrorContractFailures(errors).unexpected.length)
        .toBe(1);
      await startXhr("/api/hang/canceled");
      await page.goto(`${url}/?xhr=/api/error/new`);
      await expect
        .poll(() => getServerErrorContractFailures(errors).unexpected)
        .toEqual([
          { method: "GET", path: "/api/error/old", status: 500 },
          { method: "GET", path: "/api/error/new", status: 500 },
        ]);
    },
  );
});
