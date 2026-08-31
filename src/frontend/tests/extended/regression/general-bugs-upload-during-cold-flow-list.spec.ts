import { readFileSync } from "fs";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { openFlowsList } from "../../utils/flow/open-flows-list";

const PROJECT_PAGE_PATTERN = /\/api\/v1\/projects\/[^/?]+\?/;
const FIRST_PAGE_DELAY_MS = 6000;

test(
  "uploaded flow must appear when the project list is still loading its first page",
  { tag: ["@release"] },
  async ({ page }) => {
    /* Reproduces the Windows-CI failure of outdated-actions.spec.ts.
     *
     * `useGetFolder` paginates the project page. Upload a flow while that
     * query is still loading its FIRST page and its `data` is undefined, so
     * TanStack's cancelRefetch fast path does not apply: the refetch fired by
     * the create mutation resolves with the request that was already in
     * flight — the one issued before the upload. The new card never renders,
     * and nothing refetches afterwards.
     *
     * Holding back that first response reproduces on any OS what a slow
     * Windows runner produces by accident. */

    // Without a seeded project the page renders the welcome screen and never
    // issues the paginated request this test has to catch mid-flight.
    await awaitBootstrapTest(page, { skipModal: true });

    // The response must be fetched BEFORE the upload and delivered after it.
    // Delaying the request instead would let the server answer with a snapshot
    // that already contains the new flow, and the race would never show.
    let firstPageHeld = false;
    await page.route(
      (url) => PROJECT_PAGE_PATTERN.test(url.toString()),
      async (route) => {
        if (firstPageHeld) {
          await route.continue();
          return;
        }
        firstPageHeld = true;
        const response = await route.fetch();
        const body = await response.body();
        await new Promise((resolve) =>
          setTimeout(resolve, FIRST_PAGE_DELAY_MS),
        );
        await route.fulfill({ response, body });
      },
    );

    const firstPageRequest = page.waitForRequest(
      (request) => PROJECT_PAGE_PATTERN.test(request.url()),
      { timeout: TIMEOUTS.standard },
    );

    const dropTarget = await openFlowsList(page);

    // The drop only reproduces the bug while that first page is unanswered.
    await firstPageRequest;

    const flowName = `Cold List Upload ${Date.now()}`;
    const jsonContent = JSON.stringify({
      ...JSON.parse(readFileSync("tests/assets/outdated_flow.json", "utf-8")),
      name: flowName,
    });

    const dataTransfer = await page.evaluateHandle((data) => {
      const dt = new DataTransfer();
      dt.items.add(
        new File([data], "outdated_flow.json", { type: "application/json" }),
      );
      return dt;
    }, jsonContent);

    const flowCreated = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().endsWith("/api/v1/flows/") &&
        response.status() === 201,
      { timeout: TIMEOUTS.standard },
    );

    await dropTarget.dispatchEvent("drop", { dataTransfer });
    await flowCreated;

    await expect(
      page.getByTestId("list-card").filter({ hasText: flowName }),
    ).toBeVisible({ timeout: TIMEOUTS.standard });
  },
);
